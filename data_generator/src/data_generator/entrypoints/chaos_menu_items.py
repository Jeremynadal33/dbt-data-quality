"""Demo part 1: runs the 3 menu_items-related chaos scenarios in sequence.

Breaks unique(menu_items.item_id), relationships(order_lines.item_id -> menu_items.item_id)
and schema_changes_from_baseline on menu_items — nothing else.

drop_column runs last: duplicate_menu_item's INSERT explicitly lists the `label` column.
"""

from __future__ import annotations

import argparse

from data_generator.entrypoints.chaos import drop_column, duplicate_menu_item, orphan_menu_item
from data_generator.entrypoints.create_chaos import run_sequence

SEQUENCE = (
    duplicate_menu_item,
    orphan_menu_item,
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
