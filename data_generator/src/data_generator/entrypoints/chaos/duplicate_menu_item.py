"""Breaks ONLY unique(item_id) on raw_catalog.menu_items.

Clones the first menu_items row (by item_id, deterministic so the demo always talks
about the same item) verbatim into a new row: same item_id, and every other column
copied from a value that was already valid. Nothing else changes, so no other test
reacts — not the regex on sku, not accepted_values on category, not is_positive on
price_eur.
"""

from __future__ import annotations

import argparse

from data_generator.domain import MENU_ITEM_COLUMNS
from data_generator.utils.warehouse import DATABASE, RAW_SCHEMA, connect, execute, insert_rows

MENU_ITEMS = f"{DATABASE}.{RAW_SCHEMA}.menu_items"

default_config: dict = {}


class NoMenuItemError(Exception):
    """Raised when menu_items is empty — run generator_history first."""


def entrypoint(**kwargs) -> str:
    with connect() as conn:
        rows = execute(
            conn,
            f"select item_id, restaurant_id, sku, label, price_eur, category "
            f"from {MENU_ITEMS} order by item_id limit 1",
        )
        if not rows:
            raise NoMenuItemError(f"{MENU_ITEMS} is empty")
        insert_rows(conn, "menu_items", MENU_ITEM_COLUMNS, [list(rows[0])])
    message = f"menu_items.item_id {rows[0][0]} is now duplicated"
    print(message)
    return message


def parse_args() -> argparse.Namespace:
    return argparse.ArgumentParser(description=__doc__).parse_args()


def main() -> None:
    entrypoint(**vars(parse_args()))


if __name__ == "__main__":
    main()
