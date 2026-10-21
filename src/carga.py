"""
Carga del modelo dimensional al Data Warehouse (PostgreSQL).

1. Exige que la compuerta 3 (datos preparados) haya pasado: sin compuerta
   aprobada no se carga nada.
2. Lee las 11 tablas desde el lote (Parquet), verificando su sha256.
3. En una sola transaccion: crea las tablas si no existen (sql/create_tables.sql),
   vacia las 11 con un unico TRUNCATE e inserta en orden (dimensiones antes que
   hechos). Si algo falla, PostgreSQL revierte todo y el warehouse queda como
   estaba.
4. Concilia: el conteo de cada tabla en la base debe ser igual al del lote.
5. Guarda el resultado en data/batches/<id>/carga/carga.json.

Re-ejecucion segura (test C): las fuentes son fotos completas, asi que cada
carga reemplaza el contenido por el del lote. Cargar dos veces el mismo lote
deja exactamente los mismos datos, sin duplicados.

Errores: no poder conectarse a la base es transitorio (se puede reintentar);
cualquier otro error de base de datos o de conciliacion es determinista.
"""
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values

from src.comun import lotes
from src.comun.artefactos import leer_parquet
from src.comun.config import dir_sql, url_warehouse
from src.comun.errores import ErrorDeterminista, ErrorTransitorio

NOMBRE_DDL = 'create_tables.sql'
ESTADOS_QUE_PERMITEN_CARGAR = ('aprobada', 'aprobada_con_advertencias')

# (fuente en el lote, tabla). Orden de insercion: dimensiones antes que hechos.
TABLAS = [
    ('ecv', 'dim_geografia'),
    ('ecv', 'dim_nivel_ingreso'),
    ('ecv', 'dim_nivel_severidad_ia'),
    ('ecv', 'dim_choque_economico'),
    ('ecv', 'dim_estrategia_afrontamiento'),
    ('eva', 'dim_departamento'),
    ('eva', 'dim_cultivo'),
    ('ecv', 'fact_seguridad_alimentaria_hogar'),
    ('eva', 'fact_produccion_agricola'),
    ('eva', 'fact_variacion_produccion'),
    ('integrado', 'fact_indicadores_departamento'),
]


def _verificar_compuerta_3(lote):
    ruta = lotes.verificar_archivo(lote, 'calidad', 'compuerta_3.json')
    estado = lotes.leer_json(ruta)['estado']
    if estado not in ESTADOS_QUE_PERMITEN_CARGAR:
        raise ErrorDeterminista(f'La compuerta 3 no aprobo los datos (estado: {estado}); no se carga.')
    return estado


def _filas(df):
    """Filas como tuplas de tipos nativos de Python, con None en lugar de nulos."""
    return list(df.astype(object).where(pd.notna(df), None).itertuples(index=False, name=None))


def cargar(lote):
    estado_compuerta = _verificar_compuerta_3(lote)
    tablas = {tabla: leer_parquet(lote, fuente, tabla) for fuente, tabla in TABLAS}
    ddl = (dir_sql() / NOMBRE_DDL).read_text(encoding='utf-8')

    try:
        conexion = psycopg2.connect(url_warehouse(), connect_timeout=15)
    except psycopg2.OperationalError as error:
        raise ErrorTransitorio(f'No fue posible conectarse al warehouse: {error}') from error

    conteos = {}
    try:
        with conexion:  # una transaccion: commit al final o rollback ante cualquier error
            with conexion.cursor() as cursor:
                cursor.execute(ddl)
                cursor.execute(sql.SQL('TRUNCATE TABLE {}').format(
                    sql.SQL(', ').join(sql.Identifier(t) for _, t in TABLAS)))
                for _, tabla in TABLAS:
                    df = tablas[tabla]
                    consulta = sql.SQL('INSERT INTO {} ({}) VALUES %s').format(
                        sql.Identifier(tabla), sql.SQL(', ').join(sql.Identifier(c) for c in df.columns))
                    execute_values(cursor, consulta.as_string(cursor), _filas(df), page_size=5000)
                for _, tabla in TABLAS:
                    cursor.execute(sql.SQL('SELECT COUNT(*) FROM {}').format(sql.Identifier(tabla)))
                    en_base = cursor.fetchone()[0]
                    if en_base != len(tablas[tabla]):
                        raise ErrorDeterminista(
                            f'Conciliacion fallida en {tabla}: {en_base} filas en la base, '
                            f'{len(tablas[tabla])} en el lote.')
                    conteos[tabla] = en_base
    except psycopg2.Error as error:
        raise ErrorDeterminista(f'Error de base de datos durante la carga (revertida): {error}') from error
    finally:
        conexion.close()

    ruta = Path(lote) / 'carga' / 'carga.json'
    lotes.escribir_json(ruta, {
        'fecha_utc': lotes.ahora_utc(),
        'estado_compuerta_3': estado_compuerta,
        'estrategia': 'TRUNCATE + INSERT en una transaccion',
        'filas_por_tabla': conteos,
        'total_filas': sum(conteos.values()),
    })
    lotes.registrar_archivo(lote, 'carga', ruta)
    return lote
