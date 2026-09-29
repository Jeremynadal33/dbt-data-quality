"""Demo part 1: runs the 4 Catalog-related chaos scenarios in sequence.

Breaks unique(menu_items.item_id), relationships(order_lines.item_id -> menu_items.item_id),
schema_changes_from_baseline on menu_items and source freshness on restaurants — nothing else.

drop_column runs last: duplicate_menu_item's INSERT explicitly lists the `label` column.
"""

from __future__ import annotations

import argparse

from data_generator.entrypoints.chaos import (
    drop_column,
    duplicate_menu_item,
    late_restaurant,
    orphan_menu_item,
)
from data_generator.entrypoints.create_chaos import run_sequence

SEQUENCE = (
    duplicate_menu_item,
    orphan_menu_item,
    late_restaurant,
    drop_column,  # last: see module docstring
)

default_config: dict = {}


def entrypoint(**kwargs) -> list[str]:
    return run_sequence(SEQUENCE)


def parse_args() -> argparse.Namespace:
    return argparse.ArgumentParser(description=__doc__).parse_args()


def main() -> None:
    for line in entrypoint():
        print(line)


if __name__ == "__main__":
    main()
