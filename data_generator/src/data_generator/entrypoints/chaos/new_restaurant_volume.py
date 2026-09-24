"""Breaks ONLY elementary.volume_anomalies on raw_orders.orders.

Targets the dormant restaurant reserved by generator_history (zero orders so far,
freshest synced_at, but a fully valid catalog — its own restaurants/menu_items rows,
so every FK stays intact). Injects a burst of orders+lines dated yesterday, drawn only
from that restaurant's own valid item_ids, sized so the table-wide daily order count
for yesterday becomes ~`spike_factor` times its current value.

Elementary's default backfill window only scores the last 2 days, so the spike must
land on yesterday to be caught on the very next `dbt test` run.
"""

from __future__ import annotations

import argparse
import random
from datetime import timedelta

from faker import Faker

from data_generator import domain
from data_generator.utils.warehouse import DATABASE, RAW_SCHEMA, connect, execute, insert_rows

ORDERS = f"{DATABASE}.{RAW_SCHEMA}.orders"

default_config = {"spike_factor": 10}


def entrypoint(**kwargs) -> str:
    config = {**default_config, **kwargs}
    spike_factor = int(config["spike_factor"])

    with connect() as conn:
        dormant_id = domain.find_dormant_restaurant(conn)
        yesterday = domain.utc_now().date() - timedelta(days=1)
        current_total = execute(
            conn,
            f"""select count(*) from {ORDERS}
                where ordered_at >= %s and ordered_at < dateadd(day, 1, %s)""",
            [yesterday, yesterday],
        )[0][0]
        extra = current_total * (spike_factor - 1)

        items_by_restaurant = domain.load_catalog_snapshot(conn)
        dormant_only = {dormant_id: items_by_restaurant[dormant_id]}

        rng = random.Random(yesterday.toordinal())
        faker = Faker("fr_FR")
        orders, lines = domain.build_orders_for_day(
            yesterday, extra, dormant_only, rng, faker, id_prefix="V", restaurant_ids=[dormant_id]
        )
        insert_rows(conn, "orders", domain.ORDER_COLUMNS, orders)
        insert_rows(conn, "order_lines", domain.ORDER_LINE_COLUMNS, lines)

    message = (
        f"restaurant {dormant_id}: yesterday's order volume {current_total} -> "
        f"{current_total + extra} (x{spike_factor})"
    )
    print(message)
    return message


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spike_factor", type=int, default=default_config["spike_factor"])
    return parser.parse_args()


def main() -> None:
    entrypoint(**vars(parse_args()))


if __name__ == "__main__":
    main()
