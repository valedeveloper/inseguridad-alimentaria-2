"""
Etapas de la rama ECV, una funcion por tarea del DAG.

Cada funcion recibe la ruta del lote y devuelve la ruta del lote: los datos
viajan por disco (Parquet dentro del lote), nunca por XCom.

    extraer_ecv     congela las tres tablas crudas en el lote
    transformar_ecv limpia, integra y transforma a una tabla a nivel hogar
    modelar_ecv     construye las 5 dimensiones y el hecho de hogares
"""
from src.comun.artefactos import guardar_parquet, leer_parquet
from src.ecv.clean import limpiar_condiciones_vida, limpiar_servicios_hogar, limpiar_vivienda
from src.ecv.dimensional_model import modelar
from src.ecv.extract import (
    FUENTE,
    congelar_ecv,
    extraer_condiciones_vida,
    extraer_servicios_hogar,
    extraer_vivienda,
)
from src.ecv.transform import transformar

TABLA_TRANSFORMADA = 'hogares_transformados'


def extraer_ecv(lote):
    return congelar_ecv(lote)


def transformar_ecv(lote):
    df = transformar(
        limpiar_vivienda(extraer_vivienda(lote)),
        limpiar_servicios_hogar(extraer_servicios_hogar(lote)),
        limpiar_condiciones_vida(extraer_condiciones_vida(lote)),
    )
    guardar_parquet(df, lote, FUENTE, TABLA_TRANSFORMADA)
    return lote


def modelar_ecv(lote):
    modelo = modelar(leer_parquet(lote, FUENTE, TABLA_TRANSFORMADA))
    for nombre, tabla in modelo.items():
        guardar_parquet(tabla, lote, FUENTE, nombre)
    return lote
