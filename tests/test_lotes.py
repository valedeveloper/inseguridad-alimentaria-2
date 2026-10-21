"""Lotes: identidad por run_id, copias inmutables y deteccion de alteraciones."""
from pathlib import Path

import pytest

from src.comun import lotes
from src.comun.errores import ErrorDeterminista


def test_mismo_run_id_reutiliza_el_lote(entorno):
    assert lotes.crear_lote('run_1') == lotes.crear_lote('run_1')
    assert lotes.crear_lote('run_1') != lotes.crear_lote('run_2')


def test_reintento_conserva_la_copia_original(entorno):
    origen = entorno / 'fuente.csv'
    origen.write_text('a;b\n1;2\n', encoding='utf-8')
    lote = lotes.crear_lote('run_1')
    copia = lotes.congelar_archivo(lote, 'ecv', origen)
    origen.write_text('a;b\n9;9\n', encoding='utf-8')          # la fuente cambia entre intentos
    assert lotes.congelar_archivo(lote, 'ecv', origen) == copia
    assert Path(copia).read_text(encoding='utf-8') == 'a;b\n1;2\n'


def test_archivo_alterado_se_detecta(entorno):
    origen = entorno / 'fuente.csv'
    origen.write_text('x', encoding='utf-8')
    lote = lotes.crear_lote('run_1')
    copia = lotes.congelar_archivo(lote, 'ecv', origen)
    assert lotes.verificar_integridad(lote, 'ecv') == ['raw/fuente.csv']
    Path(copia).write_text('alterado', encoding='utf-8')
    with pytest.raises(ErrorDeterminista, match='cambio'):
        lotes.verificar_integridad(lote, 'ecv')


def test_origen_inexistente_es_determinista(entorno):
    with pytest.raises(ErrorDeterminista):
        lotes.congelar_archivo(lotes.crear_lote('run_1'), 'ecv', entorno / 'no_existe.csv')


def test_un_manifiesto_por_fuente(entorno):
    origen = entorno / 'f.csv'
    origen.write_text('x', encoding='utf-8')
    lote = lotes.crear_lote('run_1')
    lotes.congelar_archivo(lote, 'ecv', origen)
    lotes.congelar_archivo(lote, 'eva', origen)
    assert (Path(lote) / 'ecv' / 'manifiesto.json').exists()
    assert (Path(lote) / 'eva' / 'manifiesto.json').exists()
