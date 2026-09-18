"""Drops the raw schema entirely. `generator_history` recreates it from scratch (`create
or replace table` is idempotent), so there is no separate "init" step.
"""

from __future__ import annotations

import argparse

from generator import domain
from generator.utils.warehouse import connect

default_config: dict = {}


def entrypoint(**kwargs) -> None:
    with connect() as conn:
        domain.drop_schema(conn)
    print("Cleaned schemas")


def parse_args() -> argparse.Namespace:
    return argparse.ArgumentParser(description=__doc__).parse_args()


def main() -> None:
    entrypoint(**vars(parse_args()))


if __name__ == "__main__":
    main()
