"""CSV pipeline. Artifacts live on the volume shared by all Airflow workers."""
import csv
import hashlib
import json
import math
import os
import re
import shutil
import unicodedata
from pathlib import Path


def settings():
    return json.loads(Path(os.getenv('ETL_CONFIG_PATH', '/opt/airflow/config/pipeline.json')).read_text())


def data_dir():
    return Path(os.getenv('ETL_DATA_DIR', '/opt/airflow/data'))


def normalize(value):
    value = unicodedata.normalize('NFKD', value.strip()).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '_', value).strip('_')


def write_json(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def read_csv(path, config, transformed=False):
    with Path(path).open(encoding='utf-8' if transformed else config['encoding'], newline='') as stream:
        reader = csv.DictReader(stream, delimiter=',' if transformed else config['delimiter'])
        fields = reader.fieldnames
        if not fields or any(not f or not f.strip() for f in fields) or len(set(fields)) != len(fields):
            raise ValueError(f'Cabeceras vacías o duplicadas: {path}')
        rows = list(reader)
        if not rows or any(None in row or any(v is None for v in row.values()) for row in rows):
            raise ValueError(f'CSV vacío o filas con número incorrecto de columnas: {path}')
        return fields, rows


def extract(run_id):
    config = settings()
    batch = data_dir() / 'batches' / hashlib.sha256(run_id.encode()).hexdigest()[:24]
    batch.mkdir(parents=True, exist_ok=True)
    # Reuse the immutable snapshot on retry, even if incoming files have changed.
    manifest = batch / 'manifest.json'
    if manifest.exists():
        return str(batch)
    sources = sorted((data_dir() / 'incoming').glob(config['file_glob']))
    sources = [p for p in sources if p.is_file()]
    if not sources:
        raise ValueError('No hay CSV en data/incoming. Agregue las fuentes antes de ejecutar.')
    raw = batch / 'raw'
    raw.mkdir(exist_ok=True)
    files = []
    for index, source in enumerate(sources):
        target = raw / f'{index:04d}_{source.name}'
        shutil.copyfile(source, target)
        files.append({'name': target.name, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    write_json(manifest, {'run_id': run_id, 'config': config, 'files': files})
    return str(batch)


def manifest_for(batch):
    return json.loads((Path(batch) / 'manifest.json').read_text(encoding='utf-8'))


def validate(batch):
    manifest = manifest_for(batch)
    config = manifest['config']
    total = 0
    schema = None
    for item in manifest['files']:
        path = Path(batch) / 'raw' / item['name']
        if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError(f'El archivo extraído cambió: {path}')
        fields, rows = read_csv(path, config)
        mapped = [config['column_mapping'].get(f, normalize(f)) for f in fields]
        if any(not f for f in mapped) or len(set(mapped)) != len(mapped):
            raise ValueError('Colisiones o nombres vacíos al normalizar columnas')
        if schema is not None and set(mapped) != schema:
            raise ValueError('Las fuentes tienen esquemas incompatibles')
        schema = set(mapped)
        if not set(config['required_columns']).issubset(schema):
            raise ValueError('Faltan columnas obligatorias')
        total += len(rows)
    write_json(Path(batch) / 'validation.json', {'status': 'passed', 'rows': total})
    return batch


def transform(batch):
    config = manifest_for(batch)['config']
    output = []
    seen = set()
    columns = None
    for item in manifest_for(batch)['files']:
        fields, rows = read_csv(Path(batch) / 'raw' / item['name'], config)
        mapping = {f: config['column_mapping'].get(f, normalize(f)) for f in fields}
        if columns is None:
            columns = list(mapping.values())
        for row in rows:
            record = {mapping[k]: v.strip() for k, v in row.items()}
            for col in config['numeric_ranges']:
                value = record.get(col, '')
                if value:
                    record[col] = str(float(value.replace(',', '.')))
            identity = tuple(record[c] for c in columns)
            if config['drop_duplicates'] and identity in seen:
                continue
            seen.add(identity)
            output.append(record)
    target = Path(batch) / 'transformed.csv'
    temp = target.with_suffix('.tmp')
    with temp.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(output)
    temp.replace(target)
    return batch


def post_validate(batch):
    config = manifest_for(batch)['config']
    fields, rows = read_csv(Path(batch) / 'transformed.csv', config, transformed=True)
    required = set(config['required_columns']) | set(config['not_null_columns']) | set(config['primary_key']) | set(config['numeric_ranges'])
    if not required.issubset(fields):
        raise ValueError(f'Faltan columnas para validar: {required - set(fields)}')
    keys = set()
    for number, row in enumerate(rows, 2):
        for col in set(config['not_null_columns']) | set(config['primary_key']):
            if not row[col]:
                raise ValueError(f'Valor nulo: fila {number}, columna {col}')
        for col, bounds in config['numeric_ranges'].items():
            if not row[col] and col not in config['not_null_columns']:
                continue
            value = float(row[col])
            low, high = bounds
            if not math.isfinite(value) or (low is not None and value < low) or (high is not None and value > high):
                raise ValueError(f'Valor fuera de rango: fila {number}, columna {col}')
        if config['primary_key']:
            key = tuple(row[c] for c in config['primary_key'])
            if key in keys:
                raise ValueError(f'Clave duplicada: {key}')
            keys.add(key)
    raw_count = json.loads((Path(batch) / 'validation.json').read_text())['rows']
    if len(rows) > raw_count or (not config['drop_duplicates'] and len(rows) != raw_count):
        raise ValueError('Conteo inconsistente después de transformar')
    write_json(Path(batch) / 'post_validation.json', {
        'status': 'passed', 'input_rows': raw_count, 'output_rows': len(rows),
        'duplicates_removed': raw_count - len(rows),
        'sha256': hashlib.sha256((Path(batch) / 'transformed.csv').read_bytes()).hexdigest(),
    })
    return batch


def load(batch):
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extras import Json, execute_values

    manifest = manifest_for(batch)
    report = json.loads((Path(batch) / 'post_validation.json').read_text())
    path = Path(batch) / 'transformed.csv'
    if report['status'] != 'passed' or hashlib.sha256(path.read_bytes()).hexdigest() != report['sha256']:
        raise ValueError('La salida cambió después de validarse')
    _, rows = read_csv(path, manifest['config'], transformed=True)
    table = manifest['config']['target_table']
    # Full canonical row hash gives retry-safe loads; configured keys allow updates.
    key_cols = manifest['config']['primary_key']
    records = []
    for row in rows:
        identity = [row[c] for c in key_cols] if key_cols else row
        key = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        records.append((key, Json(row), manifest['run_id']))
    with psycopg2.connect(os.environ['ETL_DATABASE_URL']) as conn:
        with conn.cursor() as cur:
            cur.execute(sql.SQL('CREATE TABLE IF NOT EXISTS {} (record_key TEXT PRIMARY KEY, payload JSONB NOT NULL, source_run_id TEXT NOT NULL, loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW())').format(sql.Identifier(table)))
            execute_values(cur, sql.SQL('INSERT INTO {} (record_key, payload, source_run_id) VALUES %s ON CONFLICT (record_key) DO UPDATE SET payload=EXCLUDED.payload, source_run_id=EXCLUDED.source_run_id, loaded_at=NOW()').format(sql.Identifier(table)).as_string(conn), records)
    write_json(Path(batch) / 'load.json', {'status': 'passed', 'table': table, 'rows': len(records)})
    return {'table': table, 'rows': len(records)}
