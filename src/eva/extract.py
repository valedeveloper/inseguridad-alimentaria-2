"""
Modulo de extraccion de la API EVA (UPRA) en datos.gov.co (Socrata SODA).

1. Consulta el conteo oficial de registros por anio (count(*)).
2. Descarga los registros de 2024 y 2025 paginando con $order=:id, $limit y
   $offset (5.000 por pagina, verificado en el perfilamiento: sin perdidas
   ni duplicados).
3. Guarda la respuesta cruda en el lote, con la fecha de extraccion y los
   conteos, y registra su sha256. La UPRA advierte que las cifras de los dos
   ultimos anios pueden revisarse, por eso la fecha queda trazada.
4. Si la tarea se reintenta, reutiliza la extraccion ya guardada en el lote
   y no vuelve a llamar a la API (copia inmutable de la corrida).

Manejo de errores:
- Red, timeout, HTTP 429 o 5xx: se reintenta la peticion hasta 3 veces con
  espera creciente (2, 4 y 8 s). Si persiste -> ErrorTransitorio.
- Cualquier otro HTTP 4xx o una respuesta con forma inesperada ->
  ErrorDeterminista (reintentar no lo arregla).

La conciliacion extraidos vs. count(*) (regla C3) y el resto de reglas de la
fuente se evaluan en la compuerta de calidad, no aqui.
"""
import json
import time
from pathlib import Path

import requests

from src.comun import lotes
from src.comun.errores import ErrorDeterminista, ErrorTransitorio

FUENTE = 'eva'
URL_API = 'https://www.datos.gov.co/resource/uejq-wxrr.json'
ANIOS = (2024, 2025)
TAM_PAGINA = 5000
TIMEOUT_S = 60
ESPERAS_REINTENTO_S = (2, 4, 8)
CODIGOS_TRANSITORIOS = {429, 500, 502, 503, 504}
NOMBRE_CRUDO = 'eva_2024_2025.json'


def _consultar(params, dormir=time.sleep):
    """GET a la API con reintentos solo ante fallas transitorias."""
    ultimo_error = None
    for intento, espera in enumerate((0,) + ESPERAS_REINTENTO_S):
        if espera:
            dormir(espera)
        try:
            respuesta = requests.get(URL_API, params=params, timeout=TIMEOUT_S)
        except (requests.ConnectionError, requests.Timeout) as error:
            ultimo_error = f'{type(error).__name__}: {error}'
            continue
        if respuesta.status_code in CODIGOS_TRANSITORIOS:
            ultimo_error = f'HTTP {respuesta.status_code}'
            continue
        if respuesta.status_code != 200:
            raise ErrorDeterminista(
                f'La API respondio HTTP {respuesta.status_code} a {params}: {respuesta.text[:200]}'
            )
        try:
            datos = respuesta.json()
        except ValueError:
            ultimo_error = 'respuesta no es JSON valido'
            continue
        if not isinstance(datos, list):
            raise ErrorDeterminista(f'La API devolvio una forma inesperada ({type(datos).__name__}) a {params}.')
        return datos
    raise ErrorTransitorio(
        f'La API no respondio tras {len(ESPERAS_REINTENTO_S) + 1} intentos ({ultimo_error}). Parametros: {params}'
    )


def contar_registros(anio, dormir=time.sleep):
    """Conteo oficial de registros de un anio segun la API."""
    datos = _consultar({'$select': 'count(*)', '$where': f'a_o={anio}'}, dormir)
    try:
        return int(datos[0]['count'])
    except (IndexError, KeyError, TypeError, ValueError) as error:
        raise ErrorDeterminista(f'Respuesta de conteo inesperada para {anio}: {datos!r:.200}') from error


def descargar_anio(anio, dormir=time.sleep):
    """Todos los registros de un anio, paginando hasta una pagina incompleta."""
    registros, paginas, offset = [], 0, 0
    while True:
        pagina = _consultar(
            {'$where': f'a_o={anio}', '$order': ':id', '$limit': TAM_PAGINA, '$offset': offset},
            dormir,
        )
        registros.extend(pagina)
        paginas += 1
        if len(pagina) < TAM_PAGINA:
            return registros, paginas
        offset += TAM_PAGINA


def extraer_eva(lote, dormir=time.sleep):
    """Extrae EVA 2024-2025 y la congela en el lote. Devuelve la ruta del lote."""
    if lotes.archivo_congelado(lote, FUENTE, NOMBRE_CRUDO) is not None:
        return lote
    fecha = lotes.ahora_utc()
    conteos_api, extraidos, paginas, registros = {}, {}, {}, []
    for anio in ANIOS:
        conteos_api[str(anio)] = contar_registros(anio, dormir)
        datos, n_paginas = descargar_anio(anio, dormir)
        extraidos[str(anio)] = len(datos)
        paginas[str(anio)] = n_paginas
        registros.extend(datos)
    contenido = {
        'fuente': 'EVA - UPRA (datos.gov.co, uejq-wxrr)',
        'url': URL_API,
        'fecha_extraccion_utc': fecha,
        'tam_pagina': TAM_PAGINA,
        'conteo_api': conteos_api,
        'registros_extraidos': extraidos,
        'paginas': paginas,
        'registros': registros,
    }
    ruta = Path(lote) / FUENTE / 'raw' / NOMBRE_CRUDO
    lotes.escribir_json(ruta, contenido)
    lotes.registrar_archivo(
        lote, FUENTE, ruta,
        fecha_extraccion_utc=fecha, conteo_api=conteos_api, registros_extraidos=extraidos,
    )
    return lote


def leer_eva(lote):
    """Lee la extraccion congelada del lote, verificando antes su sha256."""
    ruta = lotes.verificar_archivo(lote, FUENTE, f'raw/{NOMBRE_CRUDO}')
    return json.loads(ruta.read_text(encoding='utf-8'))
