"""Breaks ONLY relationships(order_lines.item_id -> menu_items.item_id).

Appends one order_line to yesterday's most recent order, referencing a sentinel
item_id ('I-999999') that never exists (real ids run I-000001..I-000600 for 50
restaurants x 12 items). order_id is a real one and quantity/unit_price_eur stay
positive, so nothing else reacts — not unique_combination_of_columns(order_id, line_id),
since line_id is picked past the order's existing max.
"""

from __future__ import annotations

import argparse

from generator.domain import ORDER_LINE_COLUMNS
from generator.utils.warehouse import DATABASE, RAW_SCHEMA, connect, execute, insert_rows

ORDERS = f"{DATABASE}.{RAW_SCHEMA}.orders"
ORDER_LINES = f"{DATABASE}.{RAW_SCHEMA}.order_lines"
SENTINEL_ITEM_ID = "I-999999"

default_config: dict = {}


class NoOrderError(Exception):
    """Raised when no order from yesterday exists — run generator_history first."""


def entrypoint(**kwargs) -> str:
    with connect() as conn:
        rows = execute(
            conn,
            f"""select order_id from {ORDERS}
                where ordered_at >= dateadd(day, -1, sysdate()::date)
                  and ordered_at < sysdate()::date
                order by ordered_at desc limit 1""",
        )
        if not rows:
            raise NoOrderError("no order from yesterday found")
        order_id = rows[0][0]
        next_line_id = execute(
            conn,
            f"select coalesce(max(line_id), 0) + 1 from {ORDER_LINES} where order_id = %s",
            [order_id],
        )[0][0]
        insert_rows(
            conn, "order_lines", ORDER_LINE_COLUMNS,
            [[order_id, next_line_id, SENTINEL_ITEM_ID, 2, 9.90]],
        )
    message = f"order_lines line {next_line_id} of {order_id} references missing item {SENTINEL_ITEM_ID}"
    print(message)
    return message


def parse_args() -> argparse.Namespace:
    return argparse.ArgumentParser(description=__doc__).parse_args()


def main() -> None:
    entrypoint(**vars(parse_args()))


if __name__ == "__main__":
    main()
