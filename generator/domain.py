"""Schema DDL and synthetic-data generation for the restaurant marketplace demo.

Every dbt test declared on raw_catalog/raw_orders (see src/models/sources/) must pass
against the state produced by `load_history`. Daily order volume carries +/-15% noise on
purpose: a perfectly flat count gives stddev = 0, and Elementary forces
anomaly_score = 0 whenever stddev is 0 — a flat baseline would never trigger any anomaly
test, chaos or not.

One restaurant is always reserved "dormant": present in restaurants/menu_items (so every
FK stays valid), onboarded less than a day ago (synced_at), but with zero rows in
orders/order_lines. It is the pivot for two chaos scenarios: `new_restaurant_volume`
(its first burst of orders) and `late_restaurant` (freezing the only fresh synced_at row
to break freshness). Chaos scripts never hardcode its id — they rediscover it by its
shape in the data (`find_dormant_restaurant`), so this stays correct even if
RESTAURANT_COUNT changes.

Two ways to build up order history: `load_history` (a one-off backfill of `days` complete
days) and `append_day` (one more complete day past the latest one, meant to run daily —
e.g. via a scheduled GitHub Actions job — between the initial `load_history` and the
presentation, so the clean history keeps growing on its own). `append_day` also refreshes
the dormant restaurant's synced_at each time it runs, so freshness stays green day after
day until the `late_restaurant` chaos scenario deliberately breaks it.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta

from faker import Faker

from generator.utils.warehouse import DATABASE, RAW_SCHEMA, execute, execute_many_statements, insert_rows

RESTAURANT_COLUMNS = (
    "restaurant_id", "name", "city", "cuisine_type",
    "siret", "contact_email", "opened_at", "synced_at",
)
MENU_ITEM_COLUMNS = ("item_id", "restaurant_id", "sku", "label", "price_eur", "category")
ORDER_COLUMNS = ("order_id", "restaurant_id", "customer_id", "ordered_at", "status", "total_amount_eur")
ORDER_LINE_COLUMNS = ("order_id", "line_id", "item_id", "quantity", "unit_price_eur")

CUISINE_TYPES = ("italian", "japanese", "french", "indian", "lebanese", "mexican")
MENU_CATEGORIES = ("starter", "main", "dessert", "drink", "side")
ORDER_STATUSES = ("placed", "preparing", "delivered", "cancelled")
STATUS_WEIGHTS = (5, 8, 80, 7)

_CUISINE_SKU_PREFIX = {
    "italian": "ITA", "japanese": "JPN", "french": "FRE",
    "indian": "IND", "lebanese": "LEB", "mexican": "MEX",
}

RESTAURANT_COUNT = 50
ITEMS_PER_RESTAURANT = 12
ORDERS_PER_DAY = 500
ORDERS_PER_DAY_NOISE = 0.15
LINES_PER_ORDER = (1, 4)
QUANTITY_RANGE = (1, 3)
ITEM_PRICE_RANGE = (3.0, 15.0)

# The dormant restaurant's synced_at: young enough (< 24h) that freshness
# (warn_after=24h) is green on a freshly loaded history.
DORMANT_SYNCED_AT_MAX_AGE_HOURS = 20
# Every other restaurant: old enough that only the dormant one can ever be
# max(synced_at) — the freshness check always reads *that* row, deterministically.
STALE_SYNCED_AT_MIN_AGE_DAYS = 30
STALE_SYNCED_AT_MAX_AGE_DAYS = 400

_INIT_DDL = (
    f"create schema if not exists {DATABASE}.{RAW_SCHEMA}",
    f"""create or replace table {DATABASE}.{RAW_SCHEMA}.restaurants (
        restaurant_id varchar, name varchar, city varchar, cuisine_type varchar,
        siret varchar, contact_email varchar, opened_at date, synced_at timestamp_ntz
    )""",
    f"""create or replace table {DATABASE}.{RAW_SCHEMA}.menu_items (
        item_id varchar, restaurant_id varchar, sku varchar, label varchar,
        price_eur number(10, 2), category varchar
    )""",
    f"""create or replace table {DATABASE}.{RAW_SCHEMA}.orders (
        order_id varchar, restaurant_id varchar, customer_id varchar,
        ordered_at timestamp_ntz, status varchar, total_amount_eur number(10, 2)
    )""",
    f"""create or replace table {DATABASE}.{RAW_SCHEMA}.order_lines (
        order_id varchar, line_id number(5, 0), item_id varchar,
        quantity number(5, 0), unit_price_eur number(10, 2)
    )""",
)

_SCHEMAS_TO_RESET = (f"{DATABASE}.{RAW_SCHEMA}",f"{DATABASE}.DQ_FAILURES", f"{DATABASE}.ELEMENTARY",)

class NoDormantRestaurantError(Exception):
    """Raised when no restaurant with zero orders exists — run generator_history first."""


class NoHistoryError(Exception):
    """Raised by append_day when orders is empty — run generator_history first."""


class AlreadyUpToDateError(Exception):
    """Raised by append_day when orders already has data through today."""


def utc_now() -> datetime:
    return datetime.utcnow()


def create_schema(conn) -> None:
    execute_many_statements(conn, _INIT_DDL)


def drop_schema(conn) -> None:
    execute_many_statements(conn, tuple(f"drop schema if exists {schema} cascade" for schema in _SCHEMAS_TO_RESET))


def _generate_catalog(faker: Faker, rng: random.Random) -> tuple[list[list], list[list]]:
    restaurants: list[list] = []
    menu_items: list[list] = []
    for index in range(1, RESTAURANT_COUNT + 1):
        restaurant_id = f"R-{index:04d}"
        cuisine = rng.choice(CUISINE_TYPES)
        opened_at = faker.date_between(start_date="-8y", end_date="-6m")
        restaurants.append(
            [
                restaurant_id,
                faker.company(),
                faker.city(),
                cuisine,
                str(rng.randint(10**13, 10**14 - 1)),  # 14-digit SIRET
                faker.company_email(),
                opened_at,
            ]
        )
        prefix = _CUISINE_SKU_PREFIX[cuisine]
        for item_seq in range(1, ITEMS_PER_RESTAURANT + 1):
            item_id = f"I-{(index - 1) * ITEMS_PER_RESTAURANT + item_seq:06d}"
            menu_items.append(
                [
                    item_id,
                    restaurant_id,
                    f"{prefix}-{item_seq:05d}",
                    faker.word().capitalize(),
                    round(rng.uniform(*ITEM_PRICE_RANGE), 2),
                    rng.choice(MENU_CATEGORIES),
                ]
            )
    return restaurants, menu_items


def _dormant_restaurant_id(restaurants: list[list]) -> str:
    """The last restaurant generated never receives orders during history load."""
    return restaurants[-1][0]


def _fresh_synced_at(now: datetime, rng: random.Random) -> datetime:
    """A synced_at young enough (< 24h) that freshness (warn_after=24h) stays green."""
    return now - timedelta(hours=rng.uniform(1, DORMANT_SYNCED_AT_MAX_AGE_HOURS))


def _synced_at_values(restaurant_count: int, now: datetime, rng: random.Random) -> list[datetime]:
    values = []
    for index in range(1, restaurant_count + 1):
        if index == restaurant_count:  # the dormant restaurant
            values.append(_fresh_synced_at(now, rng))
        else:
            age = timedelta(days=rng.uniform(STALE_SYNCED_AT_MIN_AGE_DAYS, STALE_SYNCED_AT_MAX_AGE_DAYS))
            values.append(now - age)
    return values


def _items_by_restaurant(menu_items: list[list]) -> dict[str, list[tuple[str, float]]]:
    by_restaurant: dict[str, list[tuple[str, float]]] = {}
    for item_id, restaurant_id, _sku, _label, price_eur, _category in menu_items:
        by_restaurant.setdefault(restaurant_id, []).append((item_id, float(price_eur)))
    return by_restaurant


def build_orders_for_day(
    day: date,
    order_count: int,
    items_by_restaurant: dict[str, list[tuple[str, float]]],
    rng: random.Random,
    faker: Faker,
    id_prefix: str = "",
    max_hour: float = 24.0,
    restaurant_ids: list[str] | None = None,
) -> tuple[list[list], list[list]]:
    """order_count orders (+ their lines) for `day`, restricted to `restaurant_ids`.

    `restaurant_ids` defaults to every key of `items_by_restaurant` (the usual history
    load); the `new_restaurant_volume` chaos scenario instead passes a single restaurant
    so 100% of the injected burst lands on the dormant one.
    """
    pool = list(restaurant_ids) if restaurant_ids is not None else list(items_by_restaurant)
    orders: list[list] = []
    lines: list[list] = []
    for seq in range(1, order_count + 1):
        restaurant_id = rng.choice(pool)
        catalog = items_by_restaurant[restaurant_id]
        hour = rng.uniform(0, max_hour)
        ordered_at = datetime.combine(day, datetime.min.time()) + timedelta(hours=hour)
        order_id = f"O-{day:%Y%m%d}-{id_prefix}{seq:05d}"
        status = rng.choices(ORDER_STATUSES, weights=STATUS_WEIGHTS, k=1)[0]

        line_count = rng.randint(*LINES_PER_ORDER)
        total = 0.0
        for line_id in range(1, line_count + 1):
            item_id, price_eur = rng.choice(catalog)
            quantity = rng.randint(*QUANTITY_RANGE)
            lines.append([order_id, line_id, item_id, quantity, price_eur])
            total += price_eur * quantity

        orders.append([order_id, restaurant_id, f"C-{rng.randint(1, 5000):05d}", ordered_at, status, round(total, 2)])
    return orders, lines


def load_history(conn, days: int, seed: int) -> dict:
    """`days` complete days of orders ending yesterday — nothing for today. Today's data
    is meant to land via a separate, incremental `append_day` call (one per day, e.g. a
    daily GitHub Actions run) rather than a partial slice generated here: that way a
    day's count is always the full, final one, never topped up or double-counted by a
    later `append_day` run landing on the same calendar day.
    """
    rng = random.Random(seed)
    faker = Faker("fr_FR")
    Faker.seed(seed)

    create_schema(conn)
    restaurants, menu_items = _generate_catalog(faker, rng)
    dormant_id = _dormant_restaurant_id(restaurants)

    now = utc_now()
    for row, synced_at in zip(restaurants, _synced_at_values(len(restaurants), now, rng)):
        row.append(synced_at)

    insert_rows(conn, "restaurants", RESTAURANT_COLUMNS, restaurants)
    insert_rows(conn, "menu_items", MENU_ITEM_COLUMNS, menu_items)

    items_by_restaurant = _items_by_restaurant(menu_items)
    order_restaurant_ids = [rid for rid in items_by_restaurant if rid != dormant_id]

    today = now.date()
    all_orders: list[list] = []
    all_lines: list[list] = []
    for offset in range(days, 0, -1):
        day = today - timedelta(days=offset)
        noise = rng.uniform(-ORDERS_PER_DAY_NOISE, ORDERS_PER_DAY_NOISE)
        count = int(round(ORDERS_PER_DAY * (1 + noise)))
        orders, lines = build_orders_for_day(
            day, count, items_by_restaurant, rng, faker, restaurant_ids=order_restaurant_ids
        )
        all_orders.extend(orders)
        all_lines.extend(lines)

    insert_rows(conn, "orders", ORDER_COLUMNS, all_orders)
    insert_rows(conn, "order_lines", ORDER_LINE_COLUMNS, all_lines)

    return {
        "restaurants": len(restaurants),
        "menu_items": len(menu_items),
        "orders": len(all_orders),
        "order_lines": len(all_lines),
        "days": days,
        "dormant_restaurant_id": dormant_id,
    }


def last_order_date(conn) -> date | None:
    rows = execute(conn, f"select max(ordered_at)::date from {DATABASE}.{RAW_SCHEMA}.orders")
    return rows[0][0] if rows else None


def append_day(conn, seed: int) -> dict:
    """Generates exactly one new, complete day of orders — the day right after the
    latest one already in `orders` — and refreshes the dormant restaurant's synced_at so
    freshness keeps passing day after day. Meant to run once a day (e.g. via a scheduled
    GitHub Actions job) between an initial `load_history` and the presentation itself, so
    the clean history keeps growing on its own without anyone re-running `load_history`.

    The dormant restaurant (see module docstring) never receives orders here either — it
    stays the reserved pivot for `new_restaurant_volume`/`late_restaurant` until chaos day.
    """
    last_date = last_order_date(conn)
    if last_date is None:
        raise NoHistoryError("orders is empty — run generator_history first")

    now = utc_now()
    today = now.date()
    next_day = last_date + timedelta(days=1)
    if next_day > today:
        raise AlreadyUpToDateError(f"orders already has data through {last_date} (today is {today})")

    rng = random.Random(seed + next_day.toordinal())
    faker = Faker("fr_FR")
    Faker.seed(seed + next_day.toordinal())

    dormant_id = find_dormant_restaurant(conn)
    items_by_restaurant = load_catalog_snapshot(conn)
    order_restaurant_ids = [rid for rid in items_by_restaurant if rid != dormant_id]

    noise = rng.uniform(-ORDERS_PER_DAY_NOISE, ORDERS_PER_DAY_NOISE)
    count = int(round(ORDERS_PER_DAY * (1 + noise)))
    orders, lines = build_orders_for_day(
        next_day, count, items_by_restaurant, rng, faker, restaurant_ids=order_restaurant_ids
    )
    insert_rows(conn, "orders", ORDER_COLUMNS, orders)
    insert_rows(conn, "order_lines", ORDER_LINE_COLUMNS, lines)

    fresh_synced_at = _fresh_synced_at(now, rng)
    execute_many_statements(
        conn,
        (
            f"""update {DATABASE}.{RAW_SCHEMA}.restaurants
                set synced_at = '{fresh_synced_at.isoformat()}'
                where restaurant_id = '{dormant_id}'""",
        ),
    )

    return {
        "day": next_day,
        "orders": len(orders),
        "order_lines": len(lines),
        "dormant_restaurant_id": dormant_id,
    }


def load_catalog_snapshot(conn) -> dict[str, list[tuple[str, float]]]:
    """Re-reads menu_items from Snowflake, grouped by restaurant_id — used by chaos
    scenarios that need real, currently-valid (item_id, price_eur) pairs."""
    rows = execute(conn, f"select item_id, restaurant_id, price_eur from {DATABASE}.{RAW_SCHEMA}.menu_items")
    by_restaurant: dict[str, list[tuple[str, float]]] = {}
    for item_id, restaurant_id, price_eur in rows:
        by_restaurant.setdefault(restaurant_id, []).append((item_id, float(price_eur)))
    return by_restaurant


def find_dormant_restaurant(conn) -> str:
    rows = execute(
        conn,
        f"""select r.restaurant_id
            from {DATABASE}.{RAW_SCHEMA}.restaurants r
            where not exists (
                select 1 from {DATABASE}.{RAW_SCHEMA}.orders o
                where o.restaurant_id = r.restaurant_id
            )
            order by r.synced_at desc
            limit 1""",
    )
    if not rows:
        raise NoDormantRestaurantError("No restaurant with zero orders found — run generator_history first.")
    return rows[0][0]


def daily_status(conn) -> list[tuple]:
    return execute(
        conn,
        f"""select ordered_at::date as day, count(*) as order_count, round(avg(total_amount_eur), 2) as avg_basket
            from {DATABASE}.{RAW_SCHEMA}.orders
            group by 1 order by 1""",
    )


def freshness_status(conn) -> tuple:
    rows = execute(
        conn,
        f"""select max(synced_at), datediff('hour', max(synced_at), sysdate())
            from {DATABASE}.{RAW_SCHEMA}.restaurants""",
    )
    return rows[0]
