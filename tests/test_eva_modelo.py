"""Transformacion y modelo agricola con datos pequenos inventados."""
import pandas as pd
import pytest

from src.comun.errores import ErrorDeterminista
from src.eva.dimensional_model import construir_fact_indicadores, modelar
from src.eva.transform import transformar

CANASTA = pd.DataFrame({
    'nombre_cultivo': ['Papa', 'Frijol', 'Yuca', 'Mango', 'Arroz', 'Tabaco'],
    'en_canasta': [True, True, True, True, True, False],
    'motivo_canasta': ['x'] * 6,
})
DIVIPOLA = pd.DataFrame({'Código Departamento': ['05', '08', '11'],
                         'Nombre Departamento': ['ANTIOQUIA', 'ATLÁNTICO', 'BOGOTÁ, D.C.']})


def registro(depto, municipio, cultivo, anio, produccion, periodo=None):
    return {
        'c_digo_dane_departamento': depto, 'departamento': depto, 'c_digo_dane_municipio': municipio,
        'cultivo': cultivo, 'grupo_cultivo': 'G', 'subgrupo': 'S', 'ciclo_del_cultivo': 'Transitorio',
        'estado_f_sico_del_cultivo': 'En fresco', 'a_o': str(anio), 'periodo': periodo or str(anio),
        'rea_sembrada': '10.00', 'rea_cosechada': '10.00', 'producci_n': f'{produccion:.2f}',
    }


def contenido(registros):
    return {'fecha_extraccion_utc': '2026-10-21T00:00:00+00:00', 'registros': registros}


@pytest.fixture
def modelo():
    registros = [
        registro('05', '05001', 'Papa', 2024, 100), registro('05', '05002', 'Papa', 2024, 50),  # 2 municipios
        registro('05', '05001', 'Papa', 2025, 120),                                              # comparable, sube
        registro('05', '05001', 'Frijol', 2024, 0), registro('05', '05001', 'Frijol', 2025, 30), # base cero
        registro('05', '05001', 'Yuca', 2024, 40),                                               # solo 2024
        registro('05', '05001', 'Mango', 2025, 25),                                              # solo 2025
        registro('05', '05001', 'Arroz', 2024, 80), registro('05', '05001', 'Arroz', 2025, 0),   # cae 100 %
        registro('05', '05001', 'Tabaco', 2024, 5), registro('05', '05001', 'Tabaco', 2025, 1),  # fuera de canasta
        registro('08', '08001', 'Papa', 2024, 10, '2024A'), registro('08', '08001', 'Papa', 2025, 5, '2025A'),
    ]
    agregado = transformar(contenido(registros), CANASTA)
    return agregado, modelar(agregado, DIVIPOLA)


def test_agregacion_conserva_produccion_y_cuenta_municipios(modelo):
    agregado, _ = modelo
    papa_2024 = agregado[(agregado.codigo_departamento == '05') & (agregado.nombre_cultivo == 'Papa') & (agregado.anio == 2024)]
    assert papa_2024.produccion_t.item() == 150 and papa_2024.numero_municipios.item() == 2
    assert agregado.produccion_t.sum() == 100 + 50 + 120 + 30 + 40 + 25 + 80 + 5 + 1 + 10 + 5


def test_estados_de_comparabilidad(modelo):
    _, m = modelo
    v = m['fact_variacion_produccion'].merge(m['dim_cultivo'], on='id_cultivo').merge(m['dim_departamento'], on='id_departamento')
    v = v[v.codigo_departamento == '05'].set_index('nombre_cultivo')
    assert v.loc['Papa', 'estado_comparabilidad'] == 'comparable' and v.loc['Papa', 'variacion_pct'] == -20.0
    assert bool(v.loc['Papa', 'en_descenso']) is True
    assert v.loc['Frijol', 'estado_comparabilidad'] == 'base_cero' and pd.isna(v.loc['Frijol', 'variacion_pct'])
    assert v.loc['Yuca', 'estado_comparabilidad'] == 'solo_2024'
    assert v.loc['Mango', 'estado_comparabilidad'] == 'solo_2025'
    assert v.loc['Arroz', 'variacion_pct'] == -100.0                     # caida del 100 % con base positiva
    assert 'Tabaco' not in v.index                                         # fuera de la canasta


def _ecv_sintetica():
    dim_geografia = pd.DataFrame({'id_geografia': [1, 2, 3], 'codigo_departamento': ['05', '08', '11']})
    hecho = pd.DataFrame({
        'id_hogar': [1, 2, 3, 4, 5],
        'id_geografia': [1, 1, 2, 3, 3],
        'factor_expansion': [1.0, 3.0, 2.0, 1.0, 1.0],
        'prob_ia_moderada_grave': [100.0, 0.0, 50.0, 20.0, None],
        'prob_ia_grave': [0.0, 0.0, 10.0, 0.0, None],
    })
    return hecho, dim_geografia


def test_indicadores_por_departamento(modelo):
    _, m = modelo
    hecho, dim_geografia = _ecv_sintetica()
    i = construir_fact_indicadores(hecho, dim_geografia, m['dim_departamento'], m['fact_produccion_agricola'],
                                   m['fact_variacion_produccion'], m['dim_cultivo'])
    i = i.merge(m['dim_departamento'], on='id_departamento').set_index('codigo_departamento')
    assert i.loc['05', 'prevalencia_ia_moderada_grave'] == 25.0           # (1x100 + 3x0) / 4, ponderada
    assert i.loc['05', 'diversidad_cultivos_2025'] == 3                    # Papa, Frijol, Mango (>0 en 2025, canasta)
    assert i.loc['05', 'cultivos_comparables'] == 2                        # Papa y Arroz
    assert i.loc['05', 'cultivos_en_descenso'] == 2                        # Papa 150->120 y Arroz 80->0
    assert i.loc['05', 'pct_cultivos_en_descenso'] == 100.0
    assert bool(i.loc['05', 'baja_cobertura']) is True                    # menos de 15 comparables
    bogota = i.loc['11']
    assert bogota[['diversidad_cultivos_2025', 'cultivos_comparables', 'pct_cultivos_en_descenso']].isna().all()
    assert bogota['hogares_muestra'] == 2 and bogota['hogares_con_fies'] == 1   # el sin FIES no entra al denominador


def test_cultivo_fuera_de_la_canasta_detiene(modelo):
    with pytest.raises(ErrorDeterminista, match='Cultivo'):
        transformar(contenido([registro('05', '05001', 'Cultivo nuevo', 2025, 1)]), CANASTA)
