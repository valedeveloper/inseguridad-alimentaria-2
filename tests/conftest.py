"""Configuracion compartida de las pruebas.

Las pruebas unitarias usan datos pequenos inventados y una carpeta temporal.
Las de integracion (marca `integracion`) usan los CSV reales de la ECV en
data/raw/ecv y la copia del perfilamiento de EVA en data/profiling, sin llamar
a la API. Si esos archivos no estan, se saltan.
"""
import copy
import json
import os
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
DIR_ECV = RAIZ / 'data' / 'raw' / 'ecv'
COPIA_EVA = RAIZ / 'data' / 'profiling' / 'eva_2024_2025.json'
DIR_REFERENCIA = RAIZ / 'data' / 'reference'


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    """Lotes en una carpeta temporal; referencias y ECV del repositorio."""
    monkeypatch.setenv('ETL_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('ETL_REFERENCE_DIR', str(DIR_REFERENCIA))
    monkeypatch.setenv('ECV_RAW_DIR', str(DIR_ECV))
    return tmp_path


def _hay_datos_reales():
    return COPIA_EVA.exists() and all((DIR_ECV / n).exists() for n in (
        'Datos de la vivienda.csv', 'Servicios del hogar.csv',
        'Condiciones de vida del hogar y tenencia de bienes.csv'))


def contenido_eva_desde_copia(duplicar=False):
    """Contenido de la API a partir de la copia del perfilamiento (sin red).

    La copia no trae los conteos de la API; se toman de los propios registros,
    asi que la conciliacion C3 pasa por construccion en estas pruebas.
    """
    contenido = copy.deepcopy(json.loads(COPIA_EVA.read_text(encoding='utf-8')))
    registros = contenido['registros']
    if duplicar:
        registros.append(dict(registros[0]))
    conteos = {}
    for r in registros:
        conteos[r['a_o']] = conteos.get(r['a_o'], 0) + 1
    contenido['conteo_api'] = dict(conteos)
    contenido['registros_extraidos'] = dict(conteos)
    return contenido


def congelar_eva(lote, contenido):
    from src.comun import lotes
    from src.eva.extract import FUENTE, NOMBRE_CRUDO
    ruta = Path(lote) / FUENTE / 'raw' / NOMBRE_CRUDO
    lotes.escribir_json(ruta, contenido)
    lotes.registrar_archivo(lote, FUENTE, ruta)


@pytest.fixture(scope='session')
def lote_preparado(tmp_path_factory):
    """Pipeline completo con datos reales hasta la compuerta 3 (una vez por sesion)."""
    if not _hay_datos_reales():
        pytest.skip('Faltan los CSV de la ECV en data/raw/ecv o la copia de EVA en data/profiling')
    anteriores = {k: os.environ.get(k) for k in ('ETL_DATA_DIR', 'ETL_REFERENCE_DIR', 'ECV_RAW_DIR')}
    os.environ.update(ETL_DATA_DIR=str(tmp_path_factory.mktemp('datos')),
                      ETL_REFERENCE_DIR=str(DIR_REFERENCIA), ECV_RAW_DIR=str(DIR_ECV))
    from src.calidad import compuertas
    from src.comun import lotes
    from src.ecv import etapas as ecv
    from src.eva import etapas as eva

    lote = lotes.crear_lote('pytest__completo')
    ecv.extraer_ecv(lote)
    compuertas.validar_ecv_cruda(lote)
    ecv.transformar_ecv(lote)
    ecv.modelar_ecv(lote)
    congelar_eva(lote, contenido_eva_desde_copia())
    compuertas.validar_eva_cruda(lote)
    eva.transformar_eva(lote)
    eva.modelar_eva(lote)
    eva.integrar_indicadores(lote)
    compuertas.validar_preparados(lote)
    yield lote
    for clave, valor in anteriores.items():
        if valor is None:
            os.environ.pop(clave, None)
        else:
            os.environ[clave] = valor
