"""
Modulo de extraccion de datos crudos (ECV 2025, DANE).

1. Congela en el lote las tres tablas de la ECV (copia con sha256), tomadas de
   la carpeta configurada en ECV_RAW_DIR (por defecto data/raw/ecv). Si la
   tarea se reintenta, reutiliza las copias del lote aunque los originales
   hayan cambiado.
2. Lee cada tabla desde el lote con los parametros validados durante el
   perfilamiento: separador punto y coma, todas las columnas como texto y
   codificacion utf-8 con BOM. Verifica antes que el archivo no cambio.
3. No aplica ninguna regla de negocio ni limpieza.

Los nombres de las funciones de lectura son los de la Primera Entrega; ahora
reciben la ruta del lote.
"""
import pandas as pd

from src.comun import lotes
from src.comun.config import dir_ecv_crudo
from src.comun.errores import ErrorDeterminista

FUENTE = 'ecv'

# Los nombres incluyen espacios porque asi se descargan del portal DANE y se
# dejan intactos para mantener trazabilidad directa con la fuente.
NOMBRE_VIVIENDA = 'Datos de la vivienda.csv'
NOMBRE_SERVICIOS_HOGAR = 'Servicios del hogar.csv'
NOMBRE_CONDICIONES_VIDA = 'Condiciones de vida del hogar y tenencia de bienes.csv'
ARCHIVOS_ECV = [NOMBRE_VIVIENDA, NOMBRE_SERVICIOS_HOGAR, NOMBRE_CONDICIONES_VIDA]


def congelar_ecv(lote):
    """Copia las tres tablas de la ECV al lote. Devuelve la ruta del lote."""
    origen = dir_ecv_crudo()
    faltantes = [
        nombre for nombre in ARCHIVOS_ECV
        if lotes.archivo_congelado(lote, FUENTE, nombre) is None and not (origen / nombre).is_file()
    ]
    if faltantes:
        raise ErrorDeterminista(
            f'Faltan archivos de la ECV en {origen}: {faltantes}. '
            'Descargalos siguiendo data/raw/README.md o define ECV_RAW_DIR.'
        )
    for nombre in ARCHIVOS_ECV:
        lotes.congelar_archivo(lote, FUENTE, origen / nombre, nombre=nombre)
    return lote


def leer_csv_crudo(ruta):
    """
    Lee un archivo CSV de la ECV 2025 con los parametros validados durante
    el perfilamiento: separador punto y coma, todas las columnas como texto,
    y codificacion utf-8 con BOM.
    """
    return pd.read_csv(ruta, sep=';', dtype=str, encoding='utf-8-sig')


def _leer_del_lote(lote, nombre):
    return leer_csv_crudo(lotes.verificar_archivo(lote, FUENTE, f'raw/{nombre}'))


def extraer_vivienda(lote):
    """Lee la tabla de datos de la vivienda (nivel: vivienda, llave: DIRECTORIO)."""
    return _leer_del_lote(lote, NOMBRE_VIVIENDA)


def extraer_servicios_hogar(lote):
    """Lee la tabla de servicios del hogar (nivel: hogar, llave: DIRECTORIO + ORDEN)."""
    return _leer_del_lote(lote, NOMBRE_SERVICIOS_HOGAR)


def extraer_condiciones_vida(lote):
    """Lee la tabla de condiciones de vida (nivel: hogar, llave: DIRECTORIO + ORDEN)."""
    return _leer_del_lote(lote, NOMBRE_CONDICIONES_VIDA)
