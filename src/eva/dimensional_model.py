"""
Modelo dimensional agricola (R6 y R7).

Construye, a partir de la produccion agregada por transform.py:
- dim_departamento: dimension conformada reducida de dim_geografia (mismos
  codigos y nombres DIVIPOLA, 33 departamentos, Bogota incluida).
- dim_cultivo: un cultivo de EVA con sus atributos y su pertenencia a la canasta.
- fact_produccion_agricola: departamento x cultivo x anio (los 160 cultivos).
- fact_variacion_produccion: R7 por cultivo, 2024 -> 2025, solo canasta.
- fact_indicadores_departamento: R6 y R7 por departamento, unidos con la
  prevalencia FIES de la ECV (drill-across por codigo de departamento).

Reglas de R7 (README del equipo y docs/reglas_calidad.md):
- comparable: el cultivo tiene registro en ambos anios y base 2024 > 0.
  variacion = 100 x (produccion 2025 / produccion 2024 - 1). Un 2025 en 0 con
  base positiva es una caida del 100 %.
- base_cero: registro en ambos anios pero base 2024 = 0 (no calculable).
- solo_2024 / solo_2025: el cultivo falta en uno de los anios (no calculable).
Los casos no calculables quedan con variacion y en_descenso nulos; nunca se
registran como caida ni se convierten en 0.
"""
import numpy as np
import pandas as pd

from src.comun.errores import ErrorDeterminista

ANIO_BASE = 2024
ANIO_COMPARACION = 2025
UMBRAL_BAJA_COBERTURA = 15  # regla A3: menos de 15 cultivos comparables


def construir_dim_departamento(divipola):
    dim = (
        divipola.rename(columns={'Código Departamento': 'codigo_departamento',
                                 'Nombre Departamento': 'nombre_departamento'})
        [['codigo_departamento', 'nombre_departamento']]
        .drop_duplicates()
        .sort_values('codigo_departamento')
        .reset_index(drop=True)
    )
    if dim['codigo_departamento'].duplicated().any():
        raise ErrorDeterminista('DIVIPOLA tiene codigos de departamento con mas de un nombre.')
    dim.insert(0, 'id_departamento', range(1, len(dim) + 1))
    return dim


def construir_dim_cultivo(agregado):
    columnas = ['nombre_cultivo', 'grupo_cultivo', 'subgrupo', 'ciclo_cultivo',
                'estado_fisico', 'en_canasta', 'motivo_canasta']
    dim = agregado[columnas].drop_duplicates().sort_values('nombre_cultivo').reset_index(drop=True)
    if dim['nombre_cultivo'].duplicated().any():
        raise ErrorDeterminista('Un cultivo tiene atributos distintos entre registros.')
    dim.insert(0, 'id_cultivo', range(1, len(dim) + 1))
    return dim


def construir_fact_produccion(agregado, dim_departamento, dim_cultivo):
    hecho = (
        agregado
        .merge(dim_departamento[['id_departamento', 'codigo_departamento']],
               on='codigo_departamento', how='left', validate='many_to_one')
        .merge(dim_cultivo[['id_cultivo', 'nombre_cultivo']],
               on='nombre_cultivo', how='left', validate='many_to_one')
    )
    if hecho[['id_departamento', 'id_cultivo']].isna().any().any():
        raise ErrorDeterminista('Hay departamentos o cultivos de EVA sin fila en su dimension.')
    hecho = hecho.sort_values(['id_departamento', 'id_cultivo', 'anio']).reset_index(drop=True)
    hecho.insert(0, 'id_produccion', range(1, len(hecho) + 1))
    return hecho[['id_produccion', 'id_departamento', 'id_cultivo', 'anio',
                  'area_sembrada_ha', 'area_cosechada_ha', 'produccion_t',
                  'numero_municipios', 'fecha_extraccion']]


def clasificar_variacion(fact_produccion):
    """Comparacion 2024 -> 2025 por departamento y cultivo (para los cultivos recibidos)."""
    tabla = (
        fact_produccion
        .pivot(index=['id_departamento', 'id_cultivo'], columns='anio', values='produccion_t')
        .reindex(columns=[ANIO_BASE, ANIO_COMPARACION])
    )
    tabla.columns = ['produccion_2024_t', 'produccion_2025_t']
    tabla = tabla.reset_index()
    base, actual = tabla['produccion_2024_t'], tabla['produccion_2025_t']

    tabla['estado_comparabilidad'] = np.select(
        [base.isna(), actual.isna(), base.eq(0)],
        ['solo_2025', 'solo_2024', 'base_cero'],
        default='comparable',
    )
    comparable = tabla['estado_comparabilidad'].eq('comparable')
    variacion = 100 * (actual / base.where(base > 0) - 1)
    tabla['variacion_pct'] = variacion.where(comparable).round(2)
    tabla['en_descenso'] = (actual < base).astype('boolean').where(comparable, pd.NA)
    return tabla[['id_departamento', 'id_cultivo', 'produccion_2024_t', 'produccion_2025_t',
                  'variacion_pct', 'estado_comparabilidad', 'en_descenso']]


def construir_fact_variacion(fact_produccion, dim_cultivo):
    """R7 por cultivo: solo cultivos de la canasta."""
    en_canasta = dim_cultivo.loc[dim_cultivo['en_canasta'], 'id_cultivo']
    return clasificar_variacion(fact_produccion[fact_produccion['id_cultivo'].isin(en_canasta)])


def construir_fact_indicadores(hecho_hogar, dim_geografia, dim_departamento,
                               fact_produccion, fact_variacion, dim_cultivo):
    """
    R6 y R7 por departamento, con la prevalencia FIES de la ECV.

    Prevalencia = suma(factor x probabilidad) / suma(factor) sobre hogares con
    FIES valido; las probabilidades ya estan en escala 0 a 100.
    hogares_expandidos es ese denominador: hogares expandidos con FIES valido.
    Un departamento sin datos en EVA (Bogota) queda con los indicadores
    agricolas nulos, nunca en 0.
    """
    # --- ECV: prevalencia por departamento ---
    hogares = hecho_hogar.merge(dim_geografia[['id_geografia', 'codigo_departamento']],
                                on='id_geografia', how='left', validate='many_to_one')
    valido = hogares['prob_ia_moderada_grave'].notna()
    hogares['fex_valido'] = hogares['factor_expansion'].where(valido, 0.0)
    hogares['pond_mg'] = (hogares['factor_expansion'] * hogares['prob_ia_moderada_grave']).fillna(0.0)
    hogares['pond_g'] = (hogares['factor_expansion'] * hogares['prob_ia_grave']).fillna(0.0)
    ecv = hogares.groupby('codigo_departamento').agg(
        hogares_muestra=('id_hogar', 'size'),
        hogares_con_fies=('prob_ia_moderada_grave', 'count'),
        hogares_expandidos=('fex_valido', 'sum'),
        pond_mg=('pond_mg', 'sum'),
        pond_g=('pond_g', 'sum'),
    ).reset_index()
    ecv['prevalencia_ia_moderada_grave'] = (ecv['pond_mg'] / ecv['hogares_expandidos']).round(2)
    ecv['prevalencia_ia_grave'] = (ecv['pond_g'] / ecv['hogares_expandidos']).round(2)
    ecv['hogares_expandidos'] = ecv['hogares_expandidos'].round(2)

    faltan = set(ecv['codigo_departamento']) - set(dim_departamento['codigo_departamento'])
    if faltan:
        raise ErrorDeterminista(f'Departamentos de la ECV sin fila en dim_departamento: {sorted(faltan)}')

    # --- EVA: diversidad 2025 (R6) y cultivos en descenso (R7) ---
    canasta = dim_cultivo.loc[dim_cultivo['en_canasta'], 'id_cultivo']
    con_eva = set(fact_produccion['id_departamento'])
    prod_2025 = fact_produccion[
        fact_produccion['anio'].eq(ANIO_COMPARACION)
        & fact_produccion['id_cultivo'].isin(canasta)
        & fact_produccion['produccion_t'].gt(0)
    ]
    diversidad = prod_2025.groupby('id_departamento')['id_cultivo'].nunique().rename('diversidad_cultivos_2025')
    r7 = fact_variacion.assign(
        comparable=fact_variacion['estado_comparabilidad'].eq('comparable'),
        descenso=fact_variacion['en_descenso'].fillna(False).astype(bool),
    ).groupby('id_departamento').agg(cultivos_comparables=('comparable', 'sum'),
                                      cultivos_en_descenso=('descenso', 'sum'))

    tabla = (
        dim_departamento[['id_departamento', 'codigo_departamento']]
        .merge(ecv, on='codigo_departamento', how='left', validate='one_to_one')
        .merge(diversidad, on='id_departamento', how='left')
        .merge(r7, on='id_departamento', how='left')
    )
    tiene_eva = tabla['id_departamento'].isin(con_eva)
    for columna in ['diversidad_cultivos_2025', 'cultivos_comparables', 'cultivos_en_descenso']:
        tabla[columna] = tabla[columna].fillna(0).where(tiene_eva).astype('Int64')
    tabla['pct_cultivos_en_descenso'] = (
        100 * tabla['cultivos_en_descenso'] / tabla['cultivos_comparables'].where(tabla['cultivos_comparables'] > 0)
    ).astype('Float64').round(2)
    tabla['baja_cobertura'] = (tabla['cultivos_comparables'] < UMBRAL_BAJA_COBERTURA).astype('boolean').where(tiene_eva, pd.NA)

    tabla = tabla[tabla['hogares_muestra'].notna()].copy()
    tabla['hogares_muestra'] = tabla['hogares_muestra'].astype(int)
    tabla['hogares_con_fies'] = tabla['hogares_con_fies'].astype(int)
    return tabla[['id_departamento', 'hogares_muestra', 'hogares_con_fies', 'hogares_expandidos',
                  'prevalencia_ia_moderada_grave', 'prevalencia_ia_grave',
                  'diversidad_cultivos_2025', 'cultivos_comparables', 'cultivos_en_descenso',
                  'pct_cultivos_en_descenso', 'baja_cobertura']].reset_index(drop=True)


def modelar(agregado, divipola):
    """Dimensiones y hechos agricolas (sin la integracion con la ECV)."""
    dim_departamento = construir_dim_departamento(divipola)
    dim_cultivo = construir_dim_cultivo(agregado)
    fact_produccion = construir_fact_produccion(agregado, dim_departamento, dim_cultivo)
    return {
        'dim_departamento': dim_departamento,
        'dim_cultivo': dim_cultivo,
        'fact_produccion_agricola': fact_produccion,
        'fact_variacion_produccion': construir_fact_variacion(fact_produccion, dim_cultivo),
    }
