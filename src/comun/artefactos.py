"""
Datos intermedios del pipeline guardados dentro del lote, en Parquet.

Entre tareas del DAG nunca viaja un DataFrame (ni por XCom ni de otra forma):
cada etapa escribe su resultado aqui y devuelve solo la ruta del lote. La
etapa siguiente lo lee desde el lote. Parquet conserva los tipos (booleanos,
decimales, nulos), que un CSV perderia.

Cada archivo queda registrado en el manifiesto de su fuente con su sha256 y su
numero de filas, y se verifica al leerlo.
"""
import os
from pathlib import Path

import pandas as pd

from src.comun import lotes


def _relativa(nombre):
    return f'procesado/{nombre}.parquet'


def guardar_parquet(df, lote, fuente, nombre):
    """Guarda un DataFrame en el lote de forma atomica y lo registra."""
    ruta = Path(lote) / fuente / _relativa(nombre)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(f'.{ruta.name}.{os.getpid()}.tmp')
    df.to_parquet(temporal, index=False)
    temporal.replace(ruta)
    lotes.registrar_archivo(lote, fuente, ruta, filas=int(len(df)), columnas=int(df.shape[1]))
    return str(ruta)


def leer_parquet(lote, fuente, nombre):
    """Lee un DataFrame del lote, verificando antes que no cambio."""
    ruta = lotes.verificar_archivo(lote, fuente, _relativa(nombre))
    return pd.read_parquet(ruta)
