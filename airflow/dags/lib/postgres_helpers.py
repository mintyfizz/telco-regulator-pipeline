"""
Postgres interaction helpers for Airflow tasks.

Uses the Airflow connection named telco_warehouse and keeps DAG task code
focused on ingestion logic rather than connection boilerplate.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from airflow.providers.postgres.hooks.postgres import PostgresHook
from psycopg2 import sql as psycopg_sql
from psycopg2.extras import execute_values


@contextmanager
def get_warehouse_connection() -> Iterator[Any]:
    hook = PostgresHook(postgres_conn_id="telco_warehouse")
    conn = hook.get_conn()
    try:
        yield conn
    finally:
        conn.close()


def insert_rows(
    table_name: str,
    columns: list[str],
    rows: list[tuple],
    conn: Any | None = None,
) -> int:
    if not rows:
        return 0
    if conn is None:
        with get_warehouse_connection() as managed_conn:
            try:
                with managed_conn.cursor() as cur:
                    execute_values(
                        cur,
                        _build_insert_sql(cur, table_name, columns),
                        rows,
                        page_size=500,
                    )
                managed_conn.commit()
            except Exception:
                managed_conn.rollback()
                raise
    else:
        with conn.cursor() as cur:
            execute_values(
                cur,
                _build_insert_sql(cur, table_name, columns),
                rows,
                page_size=500,
            )
    return len(rows)


def execute_sql(
    sql: str,
    params: tuple | None = None,
    fetch_one: bool = False,
    fetch_all: bool = False,
) -> Any:
    with get_warehouse_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                result = None
                if fetch_one:
                    result = cur.fetchone()
                elif fetch_all:
                    result = cur.fetchall()
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise


def _build_insert_sql(cur: Any, table_name: str, columns: list[str]) -> str:
    """Build a safe INSERT statement using quoted table and column identifiers."""
    if not columns:
        raise ValueError("insert_rows requires at least one column")

    table_identifier = psycopg_sql.Identifier(*table_name.split("."))
    column_identifiers = psycopg_sql.SQL(", ").join(
        psycopg_sql.Identifier(column)
        for column in columns
    )
    query = psycopg_sql.SQL("INSERT INTO {} ({}) VALUES %s").format(
        table_identifier,
        column_identifiers,
    )
    return query.as_string(cur)
