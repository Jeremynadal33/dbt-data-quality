"""Prints daily order counts/basket averages and the restaurants freshness state — the
quick sanity check to run before presenting, to confirm `history` (or a chaos scenario)
left the warehouse in the expected shape.
"""

from __future__ import annotations

import argparse

from generator import domain
from generator.utils.warehouse import connect

default_config: dict = {}


def entrypoint(**kwargs) -> None:
    with connect() as conn:
        rows = domain.daily_status(conn)
        latest_synced_at, age_hours = domain.freshness_status(conn)

    if not rows:
        print("no data: run generator_history first")
        return

    print(f"{'day':<12} {'orders':>8} {'avg basket':>12}")
    for day, order_count, avg_basket in rows:
        print(f"{day!s:<12} {order_count:>8} {avg_basket:>12}")
    print(f"\nmost recently synced restaurant: {latest_synced_at} ({age_hours}h ago)")


def parse_args() -> argparse.Namespace:
    return argparse.ArgumentParser(description=__doc__).parse_args()


def main() -> None:
    entrypoint(**vars(parse_args()))


if __name__ == "__main__":
    main()
