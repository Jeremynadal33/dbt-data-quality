"""Appends exactly one new, complete day of orders — the day right after the latest one
already in `orders` — and refreshes the dormant restaurant's synced_at so freshness keeps
passing. Meant to run once a day (a scheduled GitHub Actions job) between the initial
`generator_history` and the presentation itself, so clean history keeps accumulating on
its own. See generator.domain.append_day for the full reasoning.

Raises (and exits non-zero) if orders is empty (run generator_history first) or if
orders already has data through today (this scenario/day was already generated —
running the scheduled job twice on the same day is a no-op error, not silently accepted,
so a mis-scheduled re-run doesn't insert two batches for the same day).
"""

from __future__ import annotations

import argparse

from generator import domain
from generator.utils.warehouse import connect

default_config = {"seed": 20260101}


def entrypoint(**kwargs) -> dict:
    config = {**default_config, **kwargs}
    with connect() as conn:
        result = domain.append_day(conn, seed=int(config["seed"]))
    print(
        f"day appended: {result['day']}\n"
        f"  orders             {result['orders']:>7}\n"
        f"  order_lines        {result['order_lines']:>7}\n"
        f"  dormant restaurant {result['dormant_restaurant_id']:>7} (synced_at refreshed)"
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=default_config["seed"])
    return parser.parse_args()


def main() -> None:
    entrypoint(**vars(parse_args()))


if __name__ == "__main__":
    main()
