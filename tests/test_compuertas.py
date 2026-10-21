"""Compuertas de Great Expectations con los datos reales (incluye el test B)."""
import json
from pathlib import Path

import pytest

from conftest import congelar_eva, contenido_eva_desde_copia

pytestmark = pytest.mark.integracion


def _reporte(lote, numero):
    return json.loads((Path(lote) / 'calidad' / f'compuerta_{numero}.json').read_text(encoding='utf-8'))


def test_las_tres_compuertas_aprueban_los_datos_reales(lote_preparado):
    assert _reporte(lote_preparado, 1)['estado'] == 'aprobada'
    assert _reporte(lote_preparado, 2)['estado'] == 'aprobada'
    tercera = _reporte(lote_preparado, 3)
    assert tercera['estado'] == 'aprobada_con_advertencias'
    assert tercera['advertencias'] == ['A3'] and tercera['criticas_fallidas'] == []
    assert abs(tercera['metricas']['prevalencia_nacional_hecho'] - 21.1) <= 0.1
    assert tercera['metricas']['diferencia_produccion_t'] < 1


def test_b_registro_duplicado_detiene_en_la_compuerta_2(lote_preparado):
    from src.calidad import compuertas
    from src.comun import lotes
    from src.comun.errores import ErrorCalidadCritica

    lote = lotes.crear_lote('pytest__test_b')
    congelar_eva(lote, contenido_eva_desde_copia(duplicar=True))
    with pytest.raises(ErrorCalidadCritica) as error:
        compuertas.validar_eva_cruda(lote)
    reporte = json.loads(Path(error.value.ruta_reporte).read_text(encoding='utf-8'))
    assert reporte['estado'] == 'rechazada' and reporte['criticas_fallidas'] == ['C7']
