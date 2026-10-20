"""ETL principal: cinco etapas secuenciales con barreras de calidad."""
from datetime import datetime, timedelta, timezone

from airflow.sdk import dag, task, get_current_context


@dag(
    dag_id='inseguridad_alimentaria_etl',
    description='Extracción, validación, transformación, postvalidación y carga',
    start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    default_args={'owner': 'etl', 'retries': 2, 'retry_delay': timedelta(minutes=1), 'execution_timeout': timedelta(minutes=30)},
    tags=['inseguridad-alimentaria', 'etl'],
)
def etl():
    from src import pipeline

    @task(task_id='extraccion')
    def extract():
        return pipeline.extract(get_current_context()['run_id'])

    @task(task_id='validate')
    def validate(batch: str):
        return pipeline.validate(batch)

    @task(task_id='transformacion')
    def transform(batch: str):
        return pipeline.transform(batch)

    @task(task_id='post_validate_transformacion')
    def post_validate(batch: str):
        return pipeline.post_validate(batch)

    @task(task_id='carga')
    def load(batch: str):
        return pipeline.load(batch)

    load(post_validate(transform(validate(extract()))))


etl()
