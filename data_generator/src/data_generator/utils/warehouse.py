"""Snowflake connection and low-level SQL helpers, no dbt dependency.

Reuses the same env vars as dbt's profiles.yml (DBT_SNOWFLAKE_ACCOUNT / DBT_SNOWFLAKE_PAT)
so the generator and dbt always point at the same warehouse without a second secret.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager

import snowflake.connector
from snowflake.connector import SnowflakeConnection

DATABASE = "jnadal_db"
RAW_SCHEMA = "raw"
INSERT_CHUNK_SIZE = 2000


def _connection_params() -> dict[str, str]:
    account = os.environ.get("DBT_SNOWFLAKE_ACCOUNT")
    password = os.environ.get("DBT_SNOWFLAKE_PAT")
    if not account or not password:
        raise SystemExit("DBT_SNOWFLAKE_ACCOUNT and DBT_SNOWFLAKE_PAT must be set (see .env)")
    return {
        "account": account,
        "password": password,
        "user": os.environ.get("SNOWFLAKE_USER", "jnadal"),
        "role": os.environ.get("SNOWFLAKE_ROLE", "r_jnadal"),
        "warehouse": os.environ.get("SNOWFLAKE_WAREHOUSE", "common_wh_xs"),
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
