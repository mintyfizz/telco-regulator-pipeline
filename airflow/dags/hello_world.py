from datetime import datetime

from airflow.decorators import dag, task


@dag(
    dag_id="hello_world",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["example"],
)
def hello_world_dag() -> None:
    """Trivial DAG that proves Airflow can run Python tasks."""

    @task
    def say_hello() -> str:
        return "Hello from Airflow"

    @task
    def show_message(msg: str) -> None:
        print(f"Message received: {msg}")

    show_message(say_hello())


hello_world_dag()
