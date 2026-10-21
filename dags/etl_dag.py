"""
DAG principal: ECV 2025 (DANE) + API EVA (UPRA) -> modelo dimensional en PostgreSQL.

Dos ramas independientes que convergen cuando ambas compuertas crudas pasan:

    preparar_lote -+- extraer_ecv -> validar_ecv_cruda -+
                   +- extraer_eva -> validar_eva_cruda -+
                                                        +-> transformar_ecv -> modelar_ecv -+
                                                        +-> transformar_eva -> modelar_eva -+-> integrar_indicadores
                                                                  -> validar_preparados -> cargar

- Entre tareas solo viaja la ruta del lote (data/batches/<id>); los datos van
  en archivos del lote, nunca por XCom.
- El lote se deriva del run_id: un reintento reutiliza las mismas copias.
- Reintentos selectivos: solo extraer_eva (API) y cargar (warehouse). Un
  ErrorDeterminista (calidad, esquema, conteo, archivo alterado) se convierte
  en AirflowFailException y nunca se reintenta.
- Parametro falla_controlada: activa el test B (duplica un registro de la API;
  la compuerta 2 detiene el pipeline por la regla C7).

Los modulos de src/ se importan dentro de cada tarea para que el procesador de
DAGs no cargue pandas ni Great Expectations en cada lectura del archivo.
"""
from datetime import datetime, timedelta, timezone

from airflow.exceptions import AirflowFailException
from airflow.sdk import Param, dag, get_current_context, task

# Reintentos justificados (docs/integracion_airflow.md):
# - API: el extractor ya reintenta cada peticion 3 veces (~14 s); esto cubre caidas mas largas.
# - Warehouse: puede estar reiniciando; la carga es una transaccion, repetirla es seguro.
REINTENTOS_API = {'retries': 2, 'retry_delay': timedelta(minutes=5)}
REINTENTOS_WAREHOUSE = {'retries': 2, 'retry_delay': timedelta(minutes=1)}


def _ejecutar(funcion, *args, **kwargs):
    """Ejecuta una etapa; un error determinista falla la tarea sin reintentos."""
    from src.comun.errores import ErrorDeterminista

    try:
        return funcion(*args, **kwargs)
    except ErrorDeterminista as error:
        raise AirflowFailException(f'{type(error).__name__}: {error}') from error


@dag(
    dag_id='inseguridad_alimentaria_etl',
    description='ECV 2025 + API EVA -> compuertas Great Expectations -> modelo dimensional en PostgreSQL',
    start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    default_args={'owner': 'etl', 'retries': 0, 'execution_timeout': timedelta(minutes=30)},
    params={
        'falla_controlada': Param(
            False, type='boolean',
            description='Test B: duplica un registro de la API para que la compuerta 2 detenga el pipeline (regla C7).'),
    },
    tags=['inseguridad-alimentaria', 'etl', 'great-expectations'],
    doc_md=__doc__,
)
def inseguridad_alimentaria_etl():

    @task
    def preparar_lote() -> str:
        from src.comun.lotes import crear_lote
        return _ejecutar(crear_lote, get_current_context()['run_id'])

    # --- Rama fuente primaria (ECV) ---
    @task
    def extraer_ecv(lote: str) -> str:
        from src.ecv import etapas
        return _ejecutar(etapas.extraer_ecv, lote)

    @task
    def validar_ecv_cruda(lote: str) -> str:
        from src.calidad import compuertas
        return _ejecutar(compuertas.validar_ecv_cruda, lote)

    # --- Rama API (EVA) ---
    @task(**REINTENTOS_API)
    def extraer_eva(lote: str) -> str:
        from src.eva import etapas
        falla = bool(get_current_context()['params'].get('falla_controlada', False))
        return _ejecutar(etapas.extraer_eva, lote, falla_controlada=falla)

    @task
    def validar_eva_cruda(lote: str) -> str:
        from src.calidad import compuertas
        return _ejecutar(compuertas.validar_eva_cruda, lote)

    # --- Transformacion e integracion (solo si ambas compuertas crudas pasaron) ---
    @task
    def transformar_ecv(lote: str) -> str:
        from src.ecv import etapas
        return _ejecutar(etapas.transformar_ecv, lote)

    @task
    def modelar_ecv(lote: str) -> str:
        from src.ecv import etapas
        return _ejecutar(etapas.modelar_ecv, lote)

    @task
    def transformar_eva(lote: str) -> str:
        from src.eva import etapas
        return _ejecutar(etapas.transformar_eva, lote)

    @task
    def modelar_eva(lote: str) -> str:
        from src.eva import etapas
        return _ejecutar(etapas.modelar_eva, lote)

    @task
    def integrar_indicadores(lote: str) -> str:
        from src.eva import etapas
        return _ejecutar(etapas.integrar_indicadores, lote)

    # --- Validacion de preparados y carga ---
    @task
    def validar_preparados(lote: str) -> str:
        from src.calidad import compuertas
        return _ejecutar(compuertas.validar_preparados, lote)

    @task(**REINTENTOS_WAREHOUSE)
    def cargar(lote: str) -> str:
        from src.carga import cargar as cargar_modelo
        return _ejecutar(cargar_modelo, lote)

    lote = preparar_lote()
    ecv_validada = validar_ecv_cruda(extraer_ecv(lote))
    eva_validada = validar_eva_cruda(extraer_eva(lote))

    ecv_transformada = transformar_ecv(ecv_validada)
    eva_transformada = transformar_eva(eva_validada)
    eva_validada >> ecv_transformada   # la transformacion espera ambas compuertas crudas
    ecv_validada >> eva_transformada

    ecv_modelada = modelar_ecv(ecv_transformada)
    integrada = integrar_indicadores(modelar_eva(eva_transformada))
    ecv_modelada >> integrada

    cargar(validar_preparados(integrada))


inseguridad_alimentaria_etl()
