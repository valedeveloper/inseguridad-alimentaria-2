"""Integration smoke test against the configured warehouse; uses isolated fixtures."""
import json
import os
import tempfile
import uuid
from pathlib import Path

import psycopg2
from psycopg2 import sql
from src import pipeline


def main():
    table = 'etl_smoke_' + uuid.uuid4().hex[:12]
    config = pipeline.settings()
    config['target_table'] = table
    config['primary_key'] = ['municipio']
    config['required_columns'] = ['municipio', 'porcentaje']
    config['not_null_columns'] = ['municipio']
    config['numeric_ranges'] = {'porcentaje': [0, 100]}
    try:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'incoming').mkdir()
            (root / 'incoming/demo.csv').write_text('Municipio,Porcentaje\n Cali ,28.5\n Cali ,28.5\nPalmira,22\n')
            (root / 'config.json').write_text(json.dumps(config))
            os.environ['ETL_DATA_DIR'] = folder
            os.environ['ETL_CONFIG_PATH'] = str(root / 'config.json')
            batch = pipeline.post_validate(pipeline.transform(pipeline.validate(pipeline.extract('smoke'))))
            assert pipeline.load(batch)['rows'] == 2
            pipeline.load(batch)
            with psycopg2.connect(os.environ['ETL_DATABASE_URL']) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql.SQL('SELECT COUNT(*) FROM {}').format(sql.Identifier(table)))
                    assert cur.fetchone()[0] == 2, 'Reintento duplicó los registros'
            print('PASS: cinco etapas, PostgreSQL real, carga repetida sin duplicados')
    finally:
        with psycopg2.connect(os.environ['ETL_DATABASE_URL']) as conn:
            with conn.cursor() as cur:
                cur.execute(sql.SQL('DROP TABLE IF EXISTS {}').format(sql.Identifier(table)))


if __name__ == '__main__':
    main()
