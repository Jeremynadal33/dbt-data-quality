"""Loads a clean synthetic history: `days` complete days of orders ending yesterday,
across the 4 raw tables (restaurants, menu_items, orders, order_lines). Nothing is
generated for today — see generator.domain.load_history for why, and
generator.entrypoints.new_day for how today's (and each following day's) data lands.

Every source-level dbt test declared in src/models/sources/ must pass against this
state, including the restaurants freshness check (see generator.domain module docstring
for why a "dormant" restaurant is reserved to make that possible).
"""

from __future__ import annotations

import argparse

from generator import domain
from generator.utils.warehouse import connect

default_config = {"days": 30, "seed": 20260101}


def entrypoint(**kwargs) -> dict:
    config = {**default_config, **kwargs}
    with connect() as conn:
        counts = domain.load_history(conn, days=int(config["days"]), seed=int(config["seed"]))
    print(
        f"history loaded: {counts['days']} complete day(s) ending yesterday\n"
        f"  restaurants        {counts['restaurants']:>7}\n"
        f"  menu_items         {counts['menu_items']:>7}\n"
        f"  orders             {counts['orders']:>7}\n"
        f"  order_lines        {counts['order_lines']:>7}\n"
        f"  dormant restaurant {counts['dormant_restaurant_id']:>7}"
    )
    return counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=default_config["days"])
    parser.add_argument("--seed", type=int, default=default_config["seed"])
    return parser.parse_args()


def main() -> None:
    entrypoint(**vars(parse_args()))


if __name__ == "__main__":
    main()
