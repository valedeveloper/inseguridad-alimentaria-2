"""
Configuracion central: rutas y conexion leidas de variables de entorno.

Cada valor tiene un valor por defecto relativo a la raiz del repositorio, de
modo que el mismo codigo funciona en local (.venv) y dentro del contenedor de
Airflow (donde la raiz es /opt/airflow). Se usan funciones y no constantes para
que un cambio de variable de entorno (por ejemplo en pruebas) se refleje sin
reimportar el modulo.

Variables:
- ETL_DATA_DIR       carpeta de datos (por defecto <raiz>/data)
- ECV_RAW_DIR        CSV crudos de la ECV (por defecto <ETL_DATA_DIR>/raw/ecv)
- ETL_REFERENCE_DIR  diccionario DANE y DIVIPOLA (por defecto <ETL_DATA_DIR>/reference)
- ETL_CONFIG_DIR     configuracion versionada (por defecto <raiz>/config)
- ETL_SQL_DIR        scripts SQL (por defecto <raiz>/sql)
- ETL_DATABASE_URL   conexion al warehouse (obligatoria para cargar)
"""
import os
from pathlib import Path

from src.comun.errores import ErrorDeterminista

RAIZ = Path(__file__).resolve().parents[2]

# Tablas de referencia versionadas en data/reference/.
NOMBRE_DICCIONARIO = 'Plantilla_Diccionario_Datos.csv'
NOMBRE_DIVIPOLA = 'divipola_departamentos.csv'


def _ruta(variable, por_defecto):
    valor = os.getenv(variable)
    return Path(valor) if valor else Path(por_defecto)


def dir_datos():
    return _ruta('ETL_DATA_DIR', RAIZ / 'data')


def dir_ecv_crudo():
    return _ruta('ECV_RAW_DIR', dir_datos() / 'raw' / 'ecv')


def dir_referencia():
    return _ruta('ETL_REFERENCE_DIR', dir_datos() / 'reference')


def dir_lotes():
    return dir_datos() / 'batches'


def dir_config():
    return _ruta('ETL_CONFIG_DIR', RAIZ / 'config')


def dir_sql():
    return _ruta('ETL_SQL_DIR', RAIZ / 'sql')


def url_warehouse():
    url = os.getenv('ETL_DATABASE_URL')
    if not url:
        raise ErrorDeterminista('Falta la variable ETL_DATABASE_URL con la conexion al warehouse.')
    return url
