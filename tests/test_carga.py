"""Carga al warehouse y re-ejecucion segura (test C). Requiere el warehouse arriba."""
import os

import pytest

pytestmark = [pytest.mark.integracion, pytest.mark.warehouse]


@pytest.fixture(scope='module')
def conexion():
    psycopg2 = pytest.importorskip('psycopg2')
    url = os.getenv('ETL_DATABASE_URL')
    if not url:
        pytest.skip('Define ETL_DATABASE_URL para probar la carga')
    try:
        con = psycopg2.connect(url, connect_timeout=5)
    except psycopg2.OperationalError:
        pytest.skip('El warehouse no esta disponible')
    yield con
    con.close()


def _huellas(con):
    from src.carga import TABLAS
    with con.cursor() as cur:
        resultado = {}
        for _, tabla in TABLAS:
            cur.execute(f"SELECT count(*), md5(coalesce(string_agg(x::text, '|' ORDER BY x::text), '')) FROM {tabla} x")
            resultado[tabla] = cur.fetchone()
    con.commit()
    return resultado


def test_c_recargar_el_mismo_lote_no_duplica_ni_altera(lote_preparado, conexion):
    from src.carga import cargar
    cargar(lote_preparado)
    antes = _huellas(conexion)
    cargar(lote_preparado)
    despues = _huellas(conexion)
    assert antes == despues
    assert antes['fact_seguridad_alimentaria_hogar'][0] == 87060


def test_vistas_analiticas_disponibles(lote_preparado, conexion):
    from src.carga import cargar
    cargar(lote_preparado)
    with conexion.cursor() as cur:
        cur.execute('SELECT count(*) FROM vw_r1_distribucion_territorial')
        assert cur.fetchone()[0] == 34
        cur.execute("SELECT diversidad_cultivos_2025 FROM vw_r6_diversidad_departamental WHERE codigo_departamento = '11'")
        assert cur.fetchone()[0] is None                                   # Bogota sin dato agricola
    conexion.commit()
