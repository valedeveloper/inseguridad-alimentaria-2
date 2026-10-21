"""
Tipos de error del pipeline.

Separan las fallas que vale la pena reintentar de las que no. El enunciado
prohibe reintentos genericos: cada tarea del DAG debe reintentar solo ante
fallas transitorias.

- ErrorTransitorio: falla externa y pasajera (red, timeout, HTTP 429 o 5xx).
  Reintentar puede resolverla.
- ErrorDeterminista: falla que se repite igual en cada intento (regla de
  calidad critica, esquema inesperado, conteo que no concilia, archivo
  alterado). Reintentar no sirve; hay que corregir la causa.

Estas clases no dependen de Airflow. En el DAG, un ErrorDeterminista puede
convertirse en AirflowFailException para que la tarea falle sin reintentar.
"""


class ErrorPipeline(Exception):
    """Base de los errores propios del pipeline."""


class ErrorTransitorio(ErrorPipeline):
    """Falla externa y pasajera; se puede reintentar."""


class ErrorDeterminista(ErrorPipeline):
    """Falla que se repetiria igual en cada intento; no se reintenta."""


class ErrorCalidadCritica(ErrorDeterminista):
    """Una compuerta de calidad encontro una regla critica incumplida.

    Guarda la ruta del reporte de validacion para consultarlo desde el DAG.
    """

    def __init__(self, mensaje, ruta_reporte=None):
        super().__init__(mensaje)
        self.ruta_reporte = ruta_reporte
