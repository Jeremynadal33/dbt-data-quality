"""Breaks ONLY elementary.schema_changes_from_baseline on raw_catalog.menu_items.

`label` carries no other dbt test, so dropping it changes nothing else: no test
references a column that no longer exists.

Must run LAST in generator_create_chaos's sequence: duplicate_menu_item's INSERT
explicitly lists the `label` column, which would fail to compile once this column is
gone. Run on its own, this scenario has no ordering constraint of its own.
"""

from __future__ import annotations

import argparse

from data_generator.utils.warehouse import DATABASE, RAW_SCHEMA, connect, execute, execute_many_statements

MENU_ITEMS = f"{DATABASE}.{RAW_SCHEMA}.menu_items"

default_config: dict = {}


class ColumnAlreadyDroppedError(Exception):
    """Raised when `label` is already gone — this scenario was run twice in a row."""


def entrypoint(**kwargs) -> str:
    with connect() as conn:
        columns = {row[0].upper() for row in execute(conn, f"describe table {MENU_ITEMS}")}
        if "LABEL" not in columns:
            raise ColumnAlreadyDroppedError(f"{MENU_ITEMS} has no `label` column left to drop")
        execute_many_statements(conn, (f"alter table {MENU_ITEMS} drop column label",))
    message = f"{MENU_ITEMS}.label dropped"
    print(message)
    return message


def parse_args() -> argparse.Namespace:
    return argparse.ArgumentParser(description=__doc__).parse_args()


def main() -> None:
    entrypoint(**vars(parse_args()))


if __name__ == "__main__":
    main()
