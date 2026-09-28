"""Snowflake connection and low-level SQL helpers, no dbt dependency.

Reuses the same DBT_SNOWFLAKE_* env vars as dbt's profiles.yml so the
generator and dbt always point at the same warehouse without a second secret.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager

import snowflake.connector
from snowflake.connector import SnowflakeConnection


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"{name} must be set (see .env)")
    return value


DATABASE = _require_env("DBT_SNOWFLAKE_DATABASE")
RAW_SCHEMA = "raw"
INSERT_CHUNK_SIZE = 2000


def _connection_params() -> dict[str, str]:
    return {
        "account": _require_env("DBT_SNOWFLAKE_ACCOUNT"),
        "password": _require_env("DBT_SNOWFLAKE_PAT"),
        "user": _require_env("DBT_SNOWFLAKE_USER"),
        "role": _require_env("DBT_SNOWFLAKE_ROLE"),
        "warehouse": _require_env("DBT_SNOWFLAKE_WAREHOUSE"),
        "database": DATABASE,
        # No default `schema`: every statement below already fully qualifies
        # {DATABASE}.{RAW_SCHEMA}.<table>, and setting one here makes connect() fail
        # right after a reset, before create_schema() gets a chance to recreate it.
    }


@contextmanager
def connect() -> Iterator[SnowflakeConnection]:
    conn = snowflake.connector.connect(**_connection_params())
    try:
        yield conn
    finally:
        conn.close()


def execute(conn: SnowflakeConnection, statement: str, params: Sequence | None = None) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(statement, params)
        return cur.fetchall()


def execute_many_statements(conn: SnowflakeConnection, statements: Iterable[str]) -> None:
    with conn.cursor() as cur:
        for statement in statements:
            cur.execute(statement)


def insert_rows(conn: SnowflakeConnection, table: str, columns: Sequence[str], rows: Sequence[Sequence]) -> int:
    if not rows:
        return 0
    placeholders = ", ".join(["%s"] * len(columns))
    statement = (
        f"insert into {DATABASE}.{RAW_SCHEMA}.{table} ({', '.join(columns)}) values ({placeholders})"
    )
    with conn.cursor() as cur:
        for start in range(0, len(rows), INSERT_CHUNK_SIZE):
            chunk = rows[start : start + INSERT_CHUNK_SIZE]
            cur.executemany(statement, chunk)
    return len(rows)
