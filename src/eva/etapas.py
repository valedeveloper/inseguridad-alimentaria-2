"""
Etapas de la rama EVA y de la integracion, una funcion por tarea del DAG.

Cada funcion recibe la ruta del lote y la devuelve: los datos viajan por
disco (Parquet dentro del lote), nunca por XCom.

    extraer_eva           descarga la API y congela la respuesta en el lote
    transformar_eva       agrega a departamento x cultivo x anio y aplica la canasta
    modelar_eva           dim_departamento, dim_cultivo y los dos hechos agricolas
    integrar_indicadores  une ECV y EVA en fact_indicadores_departamento
                          (requiere que la rama ECV ya haya modelado)
"""
import pandas as pd

from src.comun.artefactos import guardar_parquet, leer_parquet
from src.comun.config import NOMBRE_DIVIPOLA, dir_referencia
from src.ecv.extract import FUENTE as FUENTE_ECV
from src.eva import extract
from src.eva.dimensional_model import construir_fact_indicadores, modelar
from src.eva.extract import FUENTE as FUENTE_EVA
from src.eva.transform import cargar_canasta, transformar

FUENTE_INTEGRADO = 'integrado'
TABLA_AGREGADA = 'produccion_agregada'


def extraer_eva(lote):
    return extract.extraer_eva(lote)


def transformar_eva(lote):
    agregado = transformar(extract.leer_eva(lote), cargar_canasta())
    guardar_parquet(agregado, lote, FUENTE_EVA, TABLA_AGREGADA)
    return lote


def modelar_eva(lote):
    divipola = pd.read_csv(dir_referencia() / NOMBRE_DIVIPOLA, dtype=str)
    modelo = modelar(leer_parquet(lote, FUENTE_EVA, TABLA_AGREGADA), divipola)
    for nombre, tabla in modelo.items():
        guardar_parquet(tabla, lote, FUENTE_EVA, nombre)
    return lote


def integrar_indicadores(lote):
    tabla = construir_fact_indicadores(
        leer_parquet(lote, FUENTE_ECV, 'fact_seguridad_alimentaria_hogar'),
        leer_parquet(lote, FUENTE_ECV, 'dim_geografia'),
        leer_parquet(lote, FUENTE_EVA, 'dim_departamento'),
        leer_parquet(lote, FUENTE_EVA, 'fact_produccion_agricola'),
        leer_parquet(lote, FUENTE_EVA, 'fact_variacion_produccion'),
        leer_parquet(lote, FUENTE_EVA, 'dim_cultivo'),
    )
    guardar_parquet(tabla, lote, FUENTE_INTEGRADO, 'fact_indicadores_departamento')
    return lote
