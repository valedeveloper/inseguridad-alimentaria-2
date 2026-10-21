"""
Ejecucion de Great Expectations (Core 1.23.1) para las compuertas de calidad.

Sigue el esquema del taller de GX: Data Context efimero -> Data Source pandas
-> Data Asset de DataFrame -> Batch Definition del DataFrame completo ->
Expectation Suite -> Validation Definition -> Checkpoint (result_format
SUMMARY).

Cada expectativa lleva en `meta` el ID de la regla de docs/reglas_calidad.md
(C1..C16, A1..A3) y su severidad (critical o warning). La severidad no cambia
si la expectativa pasa o falla: solo indica que hace el pipeline cuando falla.
"""
import json
import os

os.environ.setdefault('GX_ANALYTICS_ENABLED', 'False')

import great_expectations as gx  # noqa: E402
from great_expectations.data_context.types.base import ProgressBarsConfig  # noqa: E402

CRITICA = 'critical'
ADVERTENCIA = 'warning'


def regla(id_regla, severidad, descripcion, clase, **parametros):
    """Crea una expectativa de GX etiquetada con su regla y su severidad."""
    return clase(**parametros, severity=severidad,
                 meta={'regla': id_regla, 'descripcion': descripcion})


def _serializable(valor):
    return json.loads(json.dumps(valor, default=str))


def validar(nombre, dataframe, expectativas):
    """Valida un DataFrame con una lista de expectativas. Devuelve un resultado por regla."""
    contexto = gx.get_context(mode='ephemeral')
    contexto.variables.progress_bars = ProgressBarsConfig(globally=False, metric_calculations=False)
    fuente = contexto.data_sources.add_pandas(f'fuente_{nombre}')
    activo = fuente.add_dataframe_asset(f'activo_{nombre}')
    definicion_lote = activo.add_batch_definition_whole_dataframe(f'lote_{nombre}')
    suite = contexto.suites.add(gx.ExpectationSuite(name=f'suite_{nombre}'))
    for expectativa in expectativas:
        suite.add_expectation(expectativa)
    validacion = contexto.validation_definitions.add(
        gx.ValidationDefinition(name=f'validacion_{nombre}', data=definicion_lote, suite=suite))
    checkpoint = contexto.checkpoints.add(
        gx.Checkpoint(name=f'checkpoint_{nombre}', validation_definitions=[validacion], result_format='SUMMARY'))
    corrida = checkpoint.run(batch_parameters={'dataframe': dataframe})

    resultados = []
    for resultado in next(iter(corrida.run_results.values())).results:
        config = resultado.expectation_config
        detalle = resultado.result or {}
        resultados.append(_serializable({
            'regla': config.meta.get('regla'),
            'descripcion': config.meta.get('descripcion'),
            'severidad': getattr(config.severity, 'value', str(config.severity)),
            'tabla': nombre,
            'expectativa': config.type,
            'parametros': {k: v for k, v in config.kwargs.items() if k not in ('batch_id', 'value_set')},
            'exito': bool(resultado.success),
            'observado': detalle.get('observed_value'),
            'inesperados': detalle.get('unexpected_count'),
            'ejemplos': (detalle.get('partial_unexpected_list') or [])[:5],
            'excepcion': (resultado.exception_info or {}).get('exception_message')
                         if isinstance(resultado.exception_info, dict) else None,
        }))
    return resultados
