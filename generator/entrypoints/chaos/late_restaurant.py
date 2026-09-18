"""Breaks ONLY dbt source freshness on raw_catalog.restaurants (never `dbt test` — that
command never checks freshness).

Pushes synced_at of every currently-fresh restaurant (< 24h old — by construction, the
dormant restaurant reserved by generator_history is the only one) back beyond the 72h
error_after threshold. Updates synced_at rather than deleting the row: deleting would
orphan its menu_items and trip the relationships test instead of freshness.
"""

from __future__ import annotations

import argparse

from generator.utils.warehouse import DATABASE, RAW_SCHEMA, connect

RESTAURANTS = f"{DATABASE}.{RAW_SCHEMA}.restaurants"

default_config = {"freeze_hours": 96, "fresh_threshold_hours": 24}


class NoRecentRestaurantError(Exception):
    """Raised when no restaurant is currently fresh — freshness may already be broken."""


def entrypoint(**kwargs) -> str:
    config = {**default_config, **kwargs}
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""update {RESTAURANTS}
                set synced_at = dateadd(hour, -{int(config['freeze_hours'])}, current_timestamp())
                where synced_at > dateadd(hour, -{int(config['fresh_threshold_hours'])}, current_timestamp())"""
        )
        updated = cur.rowcount
    if not updated:
        raise NoRecentRestaurantError("no restaurant was fresh enough to freeze")
    message = f"{updated} restaurant(s) frozen: synced_at pushed beyond error_after"
    print(message)
    return message


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze_hours", type=int, default=default_config["freeze_hours"])
    parser.add_argument("--fresh_threshold_hours", type=int, default=default_config["fresh_threshold_hours"])
    return parser.parse_args()


def main() -> None:
    entrypoint(**vars(parse_args()))


if __name__ == "__main__":
    main()
