"""Extractor de la API EVA con respuestas simuladas (sin red)."""
from unittest import mock

import pytest
import requests

from src.comun import lotes
from src.comun.errores import ErrorDeterminista, ErrorTransitorio
from src.eva import extract


class Respuesta:
    def __init__(self, codigo, datos=None, texto=''):
        self.status_code, self._datos, self.text = codigo, datos, texto

    def json(self):
        if self._datos is None:
            raise ValueError('no es JSON')
        return self._datos


def test_fallas_transitorias_se_reintentan_con_espera_creciente():
    esperas = []
    respuestas = [requests.ConnectionError('red'), Respuesta(503), Respuesta(200, [{'count': '7'}])]
    with mock.patch.object(extract.requests, 'get', side_effect=respuestas):
        assert extract.contar_registros(2025, esperas.append) == 7
    assert esperas == [2, 4]


def test_falla_persistente_es_transitoria():
    esperas = []
    with mock.patch.object(extract.requests, 'get', side_effect=[Respuesta(503)] * 4):
        with pytest.raises(ErrorTransitorio):
            extract.contar_registros(2025, esperas.append)
    assert esperas == [2, 4, 8]


def test_http_404_es_determinista_y_no_se_reintenta():
    with mock.patch.object(extract.requests, 'get', side_effect=[Respuesta(404, texto='no')]) as get:
        with pytest.raises(ErrorDeterminista):
            extract.contar_registros(2025, lambda s: None)
    assert get.call_count == 1


def test_respuesta_con_forma_inesperada_es_determinista():
    with mock.patch.object(extract.requests, 'get', side_effect=[Respuesta(200, {'error': 'x'})]):
        with pytest.raises(ErrorDeterminista):
            extract.contar_registros(2025, lambda s: None)


def test_paginacion_hasta_pagina_incompleta():
    paginas = [Respuesta(200, [{}] * 5000), Respuesta(200, [{}] * 5000), Respuesta(200, [{}] * 12)]
    with mock.patch.object(extract.requests, 'get', side_effect=paginas) as get:
        registros, n = extract.descargar_anio(2024, lambda s: None)
    assert (len(registros), n) == (10012, 3)
    assert [c.kwargs['params']['$offset'] for c in get.call_args_list] == [0, 5000, 10000]


def _api_simulada(*_, params=None, **__):
    anio = params['$where'].split('=')[1]
    if params.get('$select') == 'count(*)':
        return Respuesta(200, [{'count': '1'}])
    return Respuesta(200, [{'a_o': anio, 'c_digo_dane_municipio': '05001', 'c_digo_del_cultivo': '1', 'periodo': anio}])


def test_falla_controlada_duplica_un_registro_y_queda_anotada(entorno):
    lote = lotes.crear_lote('run_b')
    with mock.patch.object(extract.requests, 'get', side_effect=_api_simulada):
        extract.extraer_eva(lote, falla_controlada=True, dormir=lambda s: None)
    contenido = extract.leer_eva(lote)
    assert len(contenido['registros']) == 3
    assert contenido['falla_controlada'] == 'registro_duplicado'
    assert contenido['conteo_api'] == contenido['registros_extraidos'] == {'2024': 2, '2025': 1}


def test_reintento_no_vuelve_a_llamar_a_la_api(entorno):
    lote = lotes.crear_lote('run_a')
    with mock.patch.object(extract.requests, 'get', side_effect=_api_simulada):
        extract.extraer_eva(lote, dormir=lambda s: None)
    with mock.patch.object(extract.requests, 'get', side_effect=AssertionError('no debe llamar')):
        extract.extraer_eva(lote, dormir=lambda s: None)
