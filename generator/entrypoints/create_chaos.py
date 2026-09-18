"""Runs all 5 chaos scenarios in sequence, each breaking exactly one dbt/Elementary test
with no side effect on the others.

Order matters for exactly one pair: drop_column must run LAST because
duplicate_menu_item's INSERT explicitly lists the `label` column, which no longer
exists once drop_column has run. The other 4 scenarios touch disjoint tables/rows and
have no ordering constraint between them.
"""

from __future__ import annotations

import argparse

from generator.entrypoints.chaos import (
    drop_column,
    duplicate_menu_item,
    late_restaurant,
    new_restaurant_volume,
    orphan_menu_item,
)

SEQUENCE = (
    duplicate_menu_item,
    orphan_menu_item,
    new_restaurant_volume,
    late_restaurant,
    drop_column,  # last: see module docstring
)

default_config: dict = {}


def entrypoint(**kwargs) -> list[str]:
    messages = []
    for module in SEQUENCE:
        name = module.__name__.rsplit(".", 1)[-1]
        message = module.entrypoint()
        messages.append(f"[{name}] {message}")
    return messages


def parse_args() -> argparse.Namespace:
    return argparse.ArgumentParser(description=__doc__).parse_args()


def main() -> None:
    for line in entrypoint():
        print(line)


if __name__ == "__main__":
    main()
