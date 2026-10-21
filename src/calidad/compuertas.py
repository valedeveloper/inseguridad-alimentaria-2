"""
Compuertas de calidad del pipeline (docs/reglas_calidad.md).

    validar_ecv_cruda   compuerta 1: ECV cruda (C1, C2)
    validar_eva_cruda   compuerta 2: EVA cruda de la API (C3-C9, A1, A2)
    validar_preparados  compuerta 3: datos preparados antes de cargar (C10-C16, A3)

Cada funcion recibe la ruta del lote y la devuelve. Guarda su reporte en
data/batches/<id>/calidad/compuerta_<n>.json. Politica:
- alguna regla critica falla -> ErrorCalidadCritica (determinista: no se
  reintenta y el pipeline se detiene antes de cargar);
- solo fallan advertencias -> el pipeline continua y el reporte las registra.

Las reglas que no son de una sola columna se expresan con columnas derivadas
(por ejemplo "sin dato coincide con probabilidad nula") o con una tabla de una
fila con metricas de conciliacion, validadas con expectativas estandar de GX.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import great_expectations as gx

from src.calidad.gx_comun import ADVERTENCIA, CRITICA, regla, validar
from src.comun import lotes
from src.comun.artefactos import leer_parquet
from src.comun.config import NOMBRE_DIVIPOLA, dir_referencia
from src.comun.errores import ErrorCalidadCritica
from src.ecv.extract import FUENTE as FUENTE_ECV
from src.ecv.extract import NOMBRE_CONDICIONES_VIDA, NOMBRE_SERVICIOS_HOGAR, NOMBRE_VIVIENDA
from src.eva.etapas import FUENTE_INTEGRADO
from src.eva.extract import FUENTE as FUENTE_EVA
from src.eva.extract import leer_eva
from src.eva.transform import cargar_canasta

E = gx.expectations
CAMPOS_EVA = [
    'c_digo_dane_departamento', 'departamento', 'c_digo_dane_municipio', 'municipio',
    'grupo_cultivo', 'subgrupo', 'cultivo', 'desagregaci_n_cultivo', 'a_o', 'periodo',
    'rea_sembrada', 'rea_cosechada', 'producci_n', 'rendimiento', 'ciclo_del_cultivo',
    'estado_f_sico_del_cultivo', 'c_digo_del_cultivo', 'nombre_cient_fico_del_cultivo',
]
CAMPOS_NUMERICOS_EVA = ['rea_sembrada', 'rea_cosechada', 'producci_n', 'rendimiento']
ANIOS_EVA = ['2024', '2025']
PREVALENCIA_DANE = 21.1
TOLERANCIA_PREVALENCIA = 0.1
DEPARTAMENTOS_EVA_ESPERADOS = 32
MAX_RAZON_RENDIMIENTO = 20


def _codigos_divipola():
    divipola = pd.read_csv(dir_referencia() / NOMBRE_DIVIPOLA, dtype=str)
    return sorted(divipola['Código Departamento'].dropna().unique())


def _cerrar_compuerta(lote, numero, nombre, resultados, metricas=None):
    criticas = [r for r in resultados if not r['exito'] and r['severidad'] == CRITICA]
    advertencias = [r for r in resultados if not r['exito'] and r['severidad'] == ADVERTENCIA]
    estado = 'rechazada' if criticas else ('aprobada_con_advertencias' if advertencias else 'aprobada')
    reporte = {
        'compuerta': numero,
        'nombre': nombre,
        'fecha_utc': lotes.ahora_utc(),
        'estado': estado,
        'reglas_evaluadas': sorted({r['regla'] for r in resultados}),
        'criticas_fallidas': sorted({r['regla'] for r in criticas}),
        'advertencias': sorted({r['regla'] for r in advertencias}),
        'metricas': metricas or {},
        'resultados': resultados,
    }
    ruta = Path(lote) / 'calidad' / f'compuerta_{numero}.json'
    lotes.escribir_json(ruta, reporte)
    lotes.registrar_archivo(lote, 'calidad', ruta, estado=estado)
    if criticas:
        raise ErrorCalidadCritica(
            f'Compuerta {numero} ({nombre}) rechazada. Reglas criticas incumplidas: '
            f'{reporte["criticas_fallidas"]}. Reporte: {ruta}', ruta_reporte=str(ruta))
    return lote


# ---------------------------------------------------------------------------
# Compuerta 1: ECV cruda
# ---------------------------------------------------------------------------
def _leer_columnas_ecv(lote, nombre, columnas):
    ruta = lotes.verificar_archivo(lote, FUENTE_ECV, f'raw/{nombre}')
    return pd.read_csv(ruta, sep=';', dtype=str, encoding='utf-8-sig', usecols=columnas)


def validar_ecv_cruda(lote):
    resultados = []
    for nombre_archivo, tabla in [(NOMBRE_CONDICIONES_VIDA, 'ecv_condiciones_vida'),
                                  (NOMBRE_SERVICIOS_HOGAR, 'ecv_servicios_hogar')]:
        df = _leer_columnas_ecv(lote, nombre_archivo, ['DIRECTORIO', 'ORDEN'])
        resultados += validar(tabla, df, [
            regla('C1', CRITICA, 'Llave del hogar (DIRECTORIO, ORDEN) unica',
                  E.ExpectCompoundColumnsToBeUnique, column_list=['DIRECTORIO', 'ORDEN']),
            regla('C1', CRITICA, 'DIRECTORIO sin nulos', E.ExpectColumnValuesToNotBeNull, column='DIRECTORIO'),
            regla('C1', CRITICA, 'ORDEN sin nulos', E.ExpectColumnValuesToNotBeNull, column='ORDEN'),
        ])

    vivienda = _leer_columnas_ecv(lote, NOMBRE_VIVIENDA, ['DIRECTORIO', 'P1_DEPARTAMENTO'])
    vivienda['departamento_normalizado'] = vivienda['P1_DEPARTAMENTO'].str.zfill(2)
    resultados += validar('ecv_vivienda', vivienda, [
        regla('C2', CRITICA, 'P1_DEPARTAMENTO sin nulos',
              E.ExpectColumnValuesToNotBeNull, column='P1_DEPARTAMENTO'),
        regla('C2', CRITICA, 'Departamento (zfill 2) dentro de DIVIPOLA',
              E.ExpectColumnValuesToBeInSet, column='departamento_normalizado', value_set=_codigos_divipola()),
    ])
    return _cerrar_compuerta(lote, 1, 'ECV cruda', resultados)


# ---------------------------------------------------------------------------
# Compuerta 2: EVA cruda (API)
# ---------------------------------------------------------------------------
def validar_eva_cruda(lote):
    contenido = leer_eva(lote)
    df = pd.DataFrame(contenido['registros'], dtype=str)
    columnas = set(df.columns)

    # Columnas derivadas (solo si existen sus columnas de origen; si no, C4 ya falla).
    if {'periodo', 'a_o'} <= columnas:
        df['periodo_valido'] = [p in (a, f'{a}A', f'{a}B') for p, a in zip(df['periodo'], df['a_o'])]
    if {'c_digo_dane_municipio', 'c_digo_dane_departamento'} <= columnas:
        df['prefijo_municipio_valido'] = (
            df['c_digo_dane_municipio'].str[:2] == df['c_digo_dane_departamento'])
    if {'rendimiento', 'c_digo_del_cultivo'} <= columnas:
        rendimiento = pd.to_numeric(df['rendimiento'], errors='coerce')
        mediana = rendimiento.groupby(df['c_digo_del_cultivo']).transform('median')
        df['razon_rendimiento_mediana'] = (rendimiento / mediana.where(mediana > 0)).astype(float)

    expectativas = [
        regla('C4', CRITICA, 'Llegan los 18 campos esperados de la API',
              E.ExpectTableColumnsToMatchSet, column_set=CAMPOS_EVA, exact_match=False),
        regla('C5', CRITICA, 'Anio en {2024, 2025}', E.ExpectColumnValuesToBeInSet, column='a_o', value_set=ANIOS_EVA),
        regla('C5', CRITICA, 'Llegan los dos anios', E.ExpectColumnDistinctValuesToEqualSet,
              column='a_o', value_set=ANIOS_EVA),
        regla('C5', CRITICA, 'Periodo = anio, anio+A o anio+B', E.ExpectColumnValuesToBeInSet,
              column='periodo_valido', value_set=[True]),
        regla('C7', CRITICA, 'Llave municipio + codigo de cultivo + periodo unica',
              E.ExpectCompoundColumnsToBeUnique,
              column_list=['c_digo_dane_municipio', 'c_digo_del_cultivo', 'periodo']),
        regla('C8', CRITICA, 'Departamento dentro de DIVIPOLA', E.ExpectColumnValuesToBeInSet,
              column='c_digo_dane_departamento', value_set=_codigos_divipola()),
        regla('C8', CRITICA, 'Municipio de 5 digitos', E.ExpectColumnValuesToMatchRegex,
              column='c_digo_dane_municipio', regex=r'^\d{5}$'),
        regla('C8', CRITICA, 'Municipio con el prefijo de su departamento', E.ExpectColumnValuesToBeInSet,
              column='prefijo_municipio_valido', value_set=[True]),
        regla('C9', CRITICA, 'Todo cultivo esta clasificado en la canasta', E.ExpectColumnValuesToBeInSet,
              column='cultivo', value_set=sorted(cargar_canasta()['nombre_cultivo'])),
        regla('A2', ADVERTENCIA, 'Rendimiento <= 20 veces la mediana de su codigo',
              E.ExpectColumnValuesToBeBetween, column='razon_rendimiento_mediana',
              max_value=MAX_RAZON_RENDIMIENTO),
    ]
    for campo in CAMPOS_NUMERICOS_EVA:
        expectativas += [
            regla('C6', CRITICA, f'{campo} sin nulos', E.ExpectColumnValuesToNotBeNull, column=campo),
            regla('C6', CRITICA, f'{campo} numerico y >= 0 (formato con punto decimal)',
                  E.ExpectColumnValuesToMatchRegex, column=campo, regex=r'^\d+(\.\d+)?$'),
        ]
    resultados = validar('eva_registros', df, expectativas)

    # Metricas de conciliacion por anio (C3) y cobertura (A1).
    conteo_api = contenido.get('conteo_api', {})
    extraidos = contenido.get('registros_extraidos', {})
    metricas = {}
    for anio in ANIOS_EVA:
        metricas[f'diferencia_extraidos_api_{anio}'] = (
            extraidos.get(anio, np.nan) - conteo_api.get(anio, np.nan)
            if anio in conteo_api and anio in extraidos else np.nan)
        metricas[f'departamentos_{anio}'] = (
            df.loc[df['a_o'] == anio, 'c_digo_dane_departamento'].nunique()
            if {'a_o', 'c_digo_dane_departamento'} <= columnas else np.nan)
    metricas = pd.DataFrame([metricas])
    exp_metricas = []
    for anio in ANIOS_EVA:
        exp_metricas += [
            regla('C3', CRITICA, f'Registros extraidos = count(*) de la API ({anio})',
                  E.ExpectColumnValuesToBeBetween, column=f'diferencia_extraidos_api_{anio}', min_value=0, max_value=0),
            regla('C3', CRITICA, f'Conteo de conciliacion disponible ({anio})',
                  E.ExpectColumnValuesToNotBeNull, column=f'diferencia_extraidos_api_{anio}'),
            regla('A1', ADVERTENCIA, f'{DEPARTAMENTOS_EVA_ESPERADOS} departamentos con datos ({anio})',
                  E.ExpectColumnValuesToBeBetween, column=f'departamentos_{anio}',
                  min_value=DEPARTAMENTOS_EVA_ESPERADOS),
        ]
    resultados += validar('eva_conciliacion', metricas, exp_metricas)
    return _cerrar_compuerta(lote, 2, 'EVA cruda (API)', resultados,
                             metricas=metricas.iloc[0].to_dict())


# ---------------------------------------------------------------------------
# Compuerta 3: datos preparados
# ---------------------------------------------------------------------------
def _prevalencia(factor, probabilidad):
    validos = probabilidad.notna()
    return float((factor[validos] * probabilidad[validos]).sum() / factor[validos].sum())


def validar_preparados(lote):
    L = lambda fuente, nombre: leer_parquet(lote, fuente, nombre)  # noqa: E731
    transformados = L(FUENTE_ECV, 'hogares_transformados')
    hecho = L(FUENTE_ECV, 'fact_seguridad_alimentaria_hogar')
    severidad = L(FUENTE_ECV, 'dim_nivel_severidad_ia')
    choques = L(FUENTE_ECV, 'dim_choque_economico')
    estrategias = L(FUENTE_ECV, 'dim_estrategia_afrontamiento')
    produccion = L(FUENTE_EVA, 'fact_produccion_agricola')
    variacion = L(FUENTE_EVA, 'fact_variacion_produccion')
    indicadores = L(FUENTE_INTEGRADO, 'fact_indicadores_departamento')
    crudo = pd.DataFrame(leer_eva(lote)['registros'], columns=['producci_n'], dtype=str)

    resultados = []

    # --- Hecho de hogares: C10, C12, C13 ---
    h = (hecho
         .merge(severidad[['id_nivel_severidad_ia', 'nombre_severidad']], on='id_nivel_severidad_ia', how='left')
         .merge(choques[['id_choque_economico', 'numero_choques']], on='id_choque_economico', how='left')
         .merge(estrategias[['id_estrategia_afrontamiento', 'numero_estrategias']],
                on='id_estrategia_afrontamiento', how='left'))
    h['sin_dato_coincide_con_nulo'] = h['nombre_severidad'].eq('Sin dato') == h['prob_ia_moderada_grave'].isna()
    h['choque_estrategia_coherente'] = h['numero_choques'].eq(0) == h['numero_estrategias'].eq(0)
    resultados += validar('fact_seguridad_alimentaria_hogar', h, [
        regla('C10', CRITICA, 'id_hogar unico', E.ExpectColumnValuesToBeUnique, column='id_hogar'),
        regla('C10', CRITICA, 'Llave natural (directorio, orden) unica',
              E.ExpectCompoundColumnsToBeUnique, column_list=['directorio', 'orden']),
        regla('C12', CRITICA, 'Severidad "Sin dato" si y solo si la probabilidad FIES es nula',
              E.ExpectColumnValuesToBeInSet, column='sin_dato_coincide_con_nulo', value_set=[True]),
        regla('C13', CRITICA, 'Hogar sin choque <=> hogar sin estrategia',
              E.ExpectColumnValuesToBeInSet, column='choque_estrategia_coherente', value_set=[True]),
    ])
    for dim, banderas, conteo, nombre in [
        (choques, [c for c in choques.columns if c.startswith('choque_')], 'numero_choques', 'dim_choque_economico'),
        (estrategias, [c for c in estrategias.columns if c.startswith('estrategia_')], 'numero_estrategias',
         'dim_estrategia_afrontamiento'),
    ]:
        d = dim.assign(conteo_coincide=dim[conteo].eq(dim[banderas].sum(axis=1)))
        resultados += validar(nombre, d, [
            regla('C13', CRITICA, f'{conteo} = suma de sus banderas',
                  E.ExpectColumnValuesToBeInSet, column='conteo_coincide', value_set=[True]),
        ])

    # --- Produccion agricola: C14 ---
    resultados += validar('fact_produccion_agricola', produccion, [
        regla('C14', CRITICA, 'Llave departamento + cultivo + anio unica',
              E.ExpectCompoundColumnsToBeUnique, column_list=['id_departamento', 'id_cultivo', 'anio']),
    ])

    # --- Variacion R7 por cultivo: C16 ---
    v = variacion.copy()
    comparable = v['estado_comparabilidad'].eq('comparable')
    v['nulos_segun_estado'] = (comparable == v['variacion_pct'].notna()) & (comparable == v['en_descenso'].notna())
    v['variacion_finita'] = v['variacion_pct'].isna() | np.isfinite(v['variacion_pct'].astype(float))
    resultados += validar('fact_variacion_produccion', v, [
        regla('C16', CRITICA, 'Estado de comparabilidad valido', E.ExpectColumnValuesToBeInSet,
              column='estado_comparabilidad', value_set=['comparable', 'base_cero', 'solo_2024', 'solo_2025']),
        regla('C16', CRITICA, 'Variacion y descenso existen solo si el par es comparable',
              E.ExpectColumnValuesToBeInSet, column='nulos_segun_estado', value_set=[True]),
        regla('C16', CRITICA, 'Variacion sin infinitos', E.ExpectColumnValuesToBeInSet,
              column='variacion_finita', value_set=[True]),
        regla('C16', CRITICA, 'Variacion >= -100 %', E.ExpectColumnValuesToBeBetween,
              column='variacion_pct', min_value=-100),
    ])

    # --- Indicadores por departamento: C15, C16, A3 ---
    i = indicadores.copy()
    con_eva = i['id_departamento'].isin(set(produccion['id_departamento']))
    agricolas = ['diversidad_cultivos_2025', 'cultivos_comparables', 'cultivos_en_descenso']
    i['agricola_nulo_solo_sin_eva'] = np.where(con_eva, i[agricolas].notna().all(axis=1),
                                               i[agricolas + ['pct_cultivos_en_descenso']].isna().all(axis=1))
    i['descenso_no_supera_comparables'] = (
        i['cultivos_en_descenso'].isna() | (i['cultivos_en_descenso'] <= i['cultivos_comparables'])).astype(bool)
    resultados += validar('fact_indicadores_departamento', i, [
        regla('C15', CRITICA, 'Una fila por departamento (33)', E.ExpectTableRowCountToEqual, value=33),
        regla('C15', CRITICA, 'id_departamento unico', E.ExpectColumnValuesToBeUnique, column='id_departamento'),
        regla('C15', CRITICA, 'Indicadores agricolas nulos solo donde no hay EVA (nunca 0 imputado)',
              E.ExpectColumnValuesToBeInSet, column='agricola_nulo_solo_sin_eva', value_set=[True]),
        regla('C16', CRITICA, '% de cultivos en descenso entre 0 y 100', E.ExpectColumnValuesToBeBetween,
              column='pct_cultivos_en_descenso', min_value=0, max_value=100),
        regla('C16', CRITICA, 'Cultivos en descenso <= cultivos comparables', E.ExpectColumnValuesToBeInSet,
              column='descenso_no_supera_comparables', value_set=[True]),
        regla('A3', ADVERTENCIA, 'Departamento con menos de 15 cultivos comparables (baja cobertura)',
              E.ExpectColumnValuesToBeInSet, column='baja_cobertura', value_set=[False]),
    ])

    # --- Metricas de conciliacion: C10, C11, C14 ---
    produccion_cruda = pd.to_numeric(crudo['producci_n'], errors='coerce').sum()
    recompuesta = float((i['prevalencia_ia_moderada_grave'] * i['hogares_expandidos']).sum()
                        / i['hogares_expandidos'].sum())
    metricas = pd.DataFrame([{
        'diferencia_filas_hecho': len(hecho) - len(transformados),
        'prevalencia_nacional_hecho': _prevalencia(hecho['factor_expansion'], hecho['prob_ia_moderada_grave']),
        'prevalencia_recompuesta_departamentos': recompuesta,
        'diferencia_hogares_departamentos': int(i['hogares_muestra'].sum()) - len(hecho),
        'diferencia_produccion_t': abs(float(produccion['produccion_t'].sum()) - float(produccion_cruda)),
    }])
    bajo, alto = PREVALENCIA_DANE - TOLERANCIA_PREVALENCIA, PREVALENCIA_DANE + TOLERANCIA_PREVALENCIA
    resultados += validar('conciliacion_preparados', metricas, [
        regla('C10', CRITICA, 'Filas del hecho = filas transformadas (sin fan-out)',
              E.ExpectColumnValuesToBeBetween, column='diferencia_filas_hecho', min_value=0, max_value=0),
        regla('C11', CRITICA, 'Prevalencia nacional del hecho = 21,1 % +/- 0,1',
              E.ExpectColumnValuesToBeBetween, column='prevalencia_nacional_hecho', min_value=bajo, max_value=alto),
        regla('C11', CRITICA, 'Prevalencia recompuesta desde la tabla departamental = 21,1 % +/- 0,1',
              E.ExpectColumnValuesToBeBetween, column='prevalencia_recompuesta_departamentos',
              min_value=bajo, max_value=alto),
        regla('C11', CRITICA, 'Hogares por departamento suman el total de la ECV',
              E.ExpectColumnValuesToBeBetween, column='diferencia_hogares_departamentos', min_value=0, max_value=0),
        regla('C14', CRITICA, 'La agregacion conserva la produccion (diferencia < 1 t por redondeo)',
              E.ExpectColumnValuesToBeBetween, column='diferencia_produccion_t',
              min_value=0, max_value=1, strict_max=True),
    ])
    return _cerrar_compuerta(lote, 3, 'Datos preparados', resultados, metricas=metricas.iloc[0].to_dict())
