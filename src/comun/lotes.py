"""
Lotes de ejecucion: copias congeladas de las fuentes con su huella sha256.

Adaptado del patron de lotes de src/pipeline.py del equipo (manifiesto, sha256,
copia inmutable reutilizada en reintentos y escritura atomica de JSON).

Estructura de un lote:

    data/batches/<id>/
        lote.json                 run_id y fecha de creacion
        ecv/manifiesto.json       archivos congelados de la ECV y su sha256
        ecv/raw/...
        eva/manifiesto.json       respuesta de la API y su sha256
        eva/raw/...

Cada fuente tiene su propio manifiesto: las ramas ECV y EVA del DAG pueden
correr en paralelo sin escribir el mismo archivo.

El id del lote se deriva del run_id de Airflow, asi que un reintento de la
misma corrida reutiliza el mismo lote y las mismas copias congeladas, aunque
la fuente original haya cambiado entre intentos.
"""
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from src.comun.config import dir_lotes
from src.comun.errores import ErrorDeterminista

MANIFIESTO = 'manifiesto.json'


def ahora_utc():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def escribir_json(ruta, valor):
    """Escribe JSON de forma atomica: archivo temporal y luego reemplazo."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(f'.{ruta.name}.{os.getpid()}.tmp')
    temporal.write_text(json.dumps(valor, ensure_ascii=False, indent=2), encoding='utf-8')
    temporal.replace(ruta)


def leer_json(ruta):
    return json.loads(Path(ruta).read_text(encoding='utf-8'))


def sha256_archivo(ruta):
    huella = hashlib.sha256()
    with Path(ruta).open('rb') as archivo:
        for bloque in iter(lambda: archivo.read(1024 * 1024), b''):
            huella.update(bloque)
    return huella.hexdigest()


def id_lote(run_id):
    return hashlib.sha256(run_id.encode('utf-8')).hexdigest()[:24]


def crear_lote(run_id):
    """Crea (o reutiliza) la carpeta del lote de una corrida y devuelve su ruta."""
    lote = dir_lotes() / id_lote(run_id)
    lote.mkdir(parents=True, exist_ok=True)
    if not (lote / 'lote.json').exists():
        escribir_json(lote / 'lote.json', {'run_id': run_id, 'creado_utc': ahora_utc()})
    return str(lote)


def _ruta_manifiesto(lote, fuente):
    return Path(lote) / fuente / MANIFIESTO


def leer_manifiesto(lote, fuente):
    ruta = _ruta_manifiesto(lote, fuente)
    if not ruta.exists():
        return {'fuente': fuente, 'archivos': {}}
    return leer_json(ruta)


def registrar_archivo(lote, fuente, ruta, **metadatos):
    """Registra en el manifiesto un archivo que ya esta dentro del lote."""
    ruta = Path(ruta)
    relativa = ruta.relative_to(Path(lote) / fuente).as_posix()
    manifiesto = leer_manifiesto(lote, fuente)
    manifiesto['archivos'][relativa] = {
        'sha256': sha256_archivo(ruta),
        'bytes': ruta.stat().st_size,
        'registrado_utc': ahora_utc(),
        **metadatos,
    }
    escribir_json(_ruta_manifiesto(lote, fuente), manifiesto)
    return str(ruta)


def archivo_congelado(lote, fuente, nombre):
    """Ruta del archivo si ya fue congelado en este lote; None si no."""
    manifiesto = leer_manifiesto(lote, fuente)
    relativa = f'raw/{nombre}'
    ruta = Path(lote) / fuente / relativa
    if relativa in manifiesto['archivos'] and ruta.exists():
        return ruta
    return None


def congelar_archivo(lote, fuente, origen, nombre=None):
    """Copia un archivo de origen al lote y registra su sha256.

    Si el archivo ya estaba congelado en este lote (reintento), devuelve la
    copia existente sin volver a leer el origen.
    """
    origen = Path(origen)
    nombre = nombre or origen.name
    existente = archivo_congelado(lote, fuente, nombre)
    if existente is not None:
        return str(existente)
    if not origen.is_file():
        raise ErrorDeterminista(f'No existe el archivo de origen: {origen}')
    destino = Path(lote) / fuente / 'raw' / nombre
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_name(f'.{destino.name}.{os.getpid()}.tmp')
    shutil.copyfile(origen, temporal)
    temporal.replace(destino)
    return registrar_archivo(lote, fuente, destino, origen=str(origen))


def verificar_archivo(lote, fuente, relativa):
    """Comprueba un solo archivo del lote contra su sha256 registrado.

    Devuelve su ruta. Lanza ErrorDeterminista si no esta registrado, si falta
    o si su contenido cambio despues de registrarse.
    """
    info = leer_manifiesto(lote, fuente)['archivos'].get(relativa)
    if info is None:
        raise ErrorDeterminista(f'El archivo {fuente}/{relativa} no esta registrado en el lote.')
    ruta = Path(lote) / fuente / relativa
    if not ruta.exists():
        raise ErrorDeterminista(f'Falta el archivo congelado {fuente}/{relativa}.')
    if sha256_archivo(ruta) != info['sha256']:
        raise ErrorDeterminista(f'El archivo congelado {fuente}/{relativa} cambio despues de extraerse.')
    return ruta


def verificar_integridad(lote, fuente):
    """Comprueba que todos los archivos de una fuente no cambiaron.

    Lanza ErrorDeterminista si alguno falta o su sha256 no coincide.
    Devuelve la lista de rutas relativas verificadas.
    """
    manifiesto = leer_manifiesto(lote, fuente)
    if not manifiesto['archivos']:
        raise ErrorDeterminista(f'El lote no tiene archivos congelados de {fuente}.')
    for relativa in manifiesto['archivos']:
        verificar_archivo(lote, fuente, relativa)
    return sorted(manifiesto['archivos'])
