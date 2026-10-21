"""
Modulo de transformacion de EVA (UPRA).

1. Convierte a tabla los registros crudos de la API. Todos llegan como texto,
   incluso los numericos (verificado en el perfilamiento).
2. Convierte a numero areas y produccion (punto decimal, no coma como la ECV)
   y el anio a entero.
3. Clasifica cada cultivo con la canasta de config/canasta_cultivos.csv. Un
   cultivo que no este en la canasta (ni incluido ni excluido) detiene el
   proceso: la canasta debe ser fija (regla C9).
4. Agrega municipios y periodos a departamento x cultivo x anio: suma areas y
   produccion y cuenta municipios con registro. El rendimiento no se agrega
   (es una razon); se puede recalcular como produccion / area cosechada.

Nota: en 8 casos de "Plantas aromaticas" la fuente trae periodo anual y
semestral a la vez para el mismo municipio y anio, y la suma los cuenta
juntos. Ese cultivo esta fuera de la canasta, asi que no afecta R6 ni R7,
pero su produccion en fact_produccion_agricola puede estar sobrestimada
(hallazgos del perfilamiento, seccion 7).
"""
import pandas as pd

from src.comun.config import dir_config
from src.comun.errores import ErrorDeterminista

NOMBRE_CANASTA = 'canasta_cultivos.csv'

# Campos de la API que usa el pipeline y su nombre de negocio.
COLUMNAS_API = {
    'c_digo_dane_departamento': 'codigo_departamento',
    'departamento': 'nombre_departamento',
    'c_digo_dane_municipio': 'codigo_municipio',
    'cultivo': 'nombre_cultivo',
    'grupo_cultivo': 'grupo_cultivo',
    'subgrupo': 'subgrupo',
    'ciclo_del_cultivo': 'ciclo_cultivo',
    'estado_f_sico_del_cultivo': 'estado_fisico',
    'a_o': 'anio',
    'periodo': 'periodo',
    'rea_sembrada': 'area_sembrada_ha',
    'rea_cosechada': 'area_cosechada_ha',
    'producci_n': 'produccion_t',
}
MEDIDAS = ['area_sembrada_ha', 'area_cosechada_ha', 'produccion_t']
LLAVE_AGREGADO = ['codigo_departamento', 'nombre_cultivo', 'anio']
ATRIBUTOS_CULTIVO = ['grupo_cultivo', 'subgrupo', 'ciclo_cultivo', 'estado_fisico']


def cargar_canasta():
    """Lee la canasta versionada y la deja como cultivo -> en_canasta, motivo."""
    canasta = pd.read_csv(dir_config() / NOMBRE_CANASTA, dtype=str, encoding='utf-8')
    if canasta['cultivo'].duplicated().any():
        raise ErrorDeterminista('La canasta tiene cultivos repetidos.')
    if not canasta['incluido'].isin(['si', 'no']).all():
        raise ErrorDeterminista("La columna 'incluido' de la canasta solo admite 'si' o 'no'.")
    return pd.DataFrame({
        'nombre_cultivo': canasta['cultivo'],
        'en_canasta': canasta['incluido'].eq('si'),
        'motivo_canasta': canasta['motivo'],
    })


def registros_a_tabla(contenido):
    """Registros crudos de la API -> DataFrame con nombres de negocio y tipos."""
    df = pd.DataFrame(contenido['registros'], dtype=str)
    faltantes = sorted(set(COLUMNAS_API) - set(df.columns))
    if faltantes:
        raise ErrorDeterminista(f'A la extraccion de EVA le faltan campos: {faltantes}')
    df = df[list(COLUMNAS_API)].rename(columns=COLUMNAS_API)
    try:
        for columna in MEDIDAS:
            df[columna] = pd.to_numeric(df[columna], errors='raise')
        df['anio'] = df['anio'].astype(int)
    except ValueError as error:
        raise ErrorDeterminista(f'EVA trae valores no numericos: {error}') from error
    return df


def transformar(contenido, canasta):
    """Devuelve la produccion agregada a departamento x cultivo x anio."""
    df = registros_a_tabla(contenido)

    sin_clasificar = sorted(set(df['nombre_cultivo']) - set(canasta['nombre_cultivo']))
    if sin_clasificar:
        raise ErrorDeterminista(f'Cultivos de EVA que no estan en la canasta: {sin_clasificar}')

    agregado = (
        df.groupby(['codigo_departamento', 'nombre_departamento', 'nombre_cultivo', *ATRIBUTOS_CULTIVO, 'anio'],
                   as_index=False)
          .agg(area_sembrada_ha=('area_sembrada_ha', 'sum'),
               area_cosechada_ha=('area_cosechada_ha', 'sum'),
               produccion_t=('produccion_t', 'sum'),
               numero_municipios=('codigo_municipio', 'nunique'))
    )
    agregado[MEDIDAS] = agregado[MEDIDAS].round(2)
    agregado = agregado.merge(canasta, on='nombre_cultivo', how='left', validate='many_to_one')
    agregado['fecha_extraccion'] = pd.Timestamp(contenido['fecha_extraccion_utc'])
    return agregado.sort_values(LLAVE_AGREGADO).reset_index(drop=True)
