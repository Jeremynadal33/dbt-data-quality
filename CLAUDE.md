# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A demo of dbt + Elementary as a data-quality engine — **not** a transformation project.
`dbt/src/` contains only `sources:` (`raw_catalog.restaurants`/`menu_items`,
`raw_orders.orders`/`order_lines`) with data tests attached; there are zero dbt models.
The fictional domain is a restaurant marketplace with two owning teams: Catalog
(referential: restaurants/menu_items) and Orders (transactional: orders/order_lines).
`data_generator/` is a separate Python project that seeds clean history into Snowflake and
injects 5 targeted "chaos" scenarios, each designed to break exactly one specific test.

The demo's narrative (a "trust pyramid": valid → present → plausible → actionable) and the
exact expected output of every scenario are documented in `DEMO.md` — read it before touching
anything under `dbt/src/models/sources/` or `data_generator/src/data_generator/entrypoints/chaos/`,
since the two must stay in sync with what `DEMO.md` claims.

## Repo layout

Two independent `uv` projects, each with its own `pyproject.toml`/`.venv`, orchestrated from the
repo root by `mise.toml` — commands always run via `uv run --project <dbt|data_generator> ...`
from the root, never via `cd`, so that dbt's output paths (`docs/dbt_docs`,
`docs/elementary_report`) stay relative to the repo root (required for the gh-pages deploy).

- `dbt/` — the dbt project (`dbt-snowflake` + `elementary-data`). Sources live in
  `dbt/src/models/sources/_catalog__sources.yml` and `_orders__sources.yml`.
- `data_generator/` — the Python generator. Code is under
  `data_generator/src/data_generator/`:
  - `domain.py` — schema DDL + Faker-based generation logic.
  - `entrypoints/` — one module per CLI command (see `entrypoints/history.py` for the
    pattern). Each entrypoint is callable directly as `entrypoint(**kwargs)` or via its
    installed script (`generator_<name>`).
  - `entrypoints/chaos/` — the 5 chaos scenario scripts.
  - `utils/warehouse.py` — Snowflake connection/SQL helpers, no dbt dependency; reuses the
    same `DBT_SNOWFLAKE_ACCOUNT`/`DBT_SNOWFLAKE_PAT` env vars as dbt's `profiles.yml`.
- `docs/` — build output (dbt docs + Elementary report + landing page), published to
  gh-pages. Generated, do not hand-edit.

## Commands

Prerequisites: [`mise`](https://mise.jdx.dev/) (task runner) and [`uv`](https://docs.astral.sh/uv/)
(installed automatically by mise). Requires a `.env` at the repo root with
`DBT_SNOWFLAKE_ACCOUNT`, `DBT_SNOWFLAKE_PAT`, `SLACK_BOT_TOKEN` (mise loads it automatically).

```bash
mise tasks                # list all available tasks
mise run setup             # uv sync both projects + dbt deps
mise run dbt:debug         # check the Snowflake connection
mise run dbt:deps          # install dbt packages (elementary, dbt_utils, dbt_expectations)
mise run dbt:run           # run the elementary models
mise run dbt:test          # run dbt_data_quality tests + dbt source freshness
mise run demo:verify       # dbt:run + dbt:test (shared by history/new-day/chaos tasks)
mise run demo:history      # load 30 clean days ending yesterday, then demo:verify
mise run demo:new-day      # append one more clean day (meant for a daily cron)
mise run demo:chaos        # run all 5 chaos scenarios in the safe order, then verify + alert
mise run demo:alert        # send pending Elementary alerts to Slack
mise run demo:status       # orders/day + restaurant freshness snapshot
mise run demo:reset        # drop the raw schema
mise run webapp:build      # build dbt docs + Elementary report into docs/ (cached, incremental)
mise run webapp:build:force  # same, bypassing the up-to-date cache
mise run webapp:serve      # build then serve docs/ locally on :8000
mise run charts:serve      # serve the dbt Charts dashboards (dbt/charts/) live, filters enabled
mise run charts:build      # render them to static HTML into docs/charts/ (filters frozen at default)
mise run ci:run            # reproduce CI's "Run dbt project" step (debug, deps, run, test)
mise run ci:docs           # reproduce CI's "Generate docs" step (debug, deps, docs+report)
```

Single chaos scenarios have one task each (injection only — chain `mise run demo:verify`
yourself). The presentation in `docs/presentation/` only shows `mise` commands, so keep it
in sync with these task names:

```bash
mise run dbt:compile                       # compile the project (tests' SQL in dbt/target/compiled)
mise run demo:chaos:<name>                 # duplicate-menu-item, orphan-menu-item,
                                           # new-restaurant-volume, late-restaurant, drop-column
mise run demo:failures <test_name>         # show the store_failures rows of a failing test
```

**Ordering constraint**: `drop_column` must run *after* `duplicate_menu_item` if both are used —
`duplicate_menu_item` does an `INSERT` that explicitly lists the `label` column, which
`drop_column` removes. The other 4 scenarios have no ordering constraint between them
(disjoint tables/rows). Always reset (`mise run demo:reset && mise run demo:history`) before
replaying an individual scenario in isolation — they're only designed against fresh history.

`DBT_TARGET` defaults to `prod` (see `mise.toml`); `local` and `prod` point at the same
Snowflake account — Elementary models are only enabled on `prod` (see `dbt_project.yml`).

## Architecture notes

- **The dormant restaurant**: `load_history` always reserves the last-generated restaurant
  with zero orders (`domain.py: _dormant_restaurant_id`/`find_dormant_restaurant`). It exists
  in `restaurants`/`menu_items` (so FKs stay valid) with a fresh `synced_at`, but never
  receives orders during normal history loading. It's the pivot for two chaos scenarios:
  `new_restaurant_volume` (its first burst of orders — triggers `elementary.volume_anomalies`)
  and `late_restaurant` (freezing its `synced_at` — breaks `dbt source freshness` without
  touching `dbt test`). Chaos scripts always rediscover its id dynamically, never hardcode it.
- **`store_failures`**: enabled globally for `dbt_data_quality` tests (`dbt_project.yml`),
  materializing failing rows into the `dq_failures` schema for direct SQL inspection instead
  of just a pass/fail count.
- **`schema_changes_from_baseline` vs `schema_changes`**: the `menu_items` source uses the
  former deliberately — it flags a mismatch against the declared `columns:` baseline on the
  very first run, unlike `schema_changes`, which needs two runs straddling the change. The
  `label` column has no data test of its own; it exists solely so the baseline knows it existed
  before `drop_column` removes it.
- Daily order volume is generated with ±15% noise on purpose — a perfectly flat count gives
  `stddev = 0`, and Elementary forces `anomaly_score = 0` when stddev is 0, which would make
  `volume_anomalies` untestable even under chaos.
- `.github/workflows/generate-daily-data.yml` runs `generator_new_day` on a daily cron — but
  GitHub only evaluates `schedule` triggers on the repo's default branch, so until the working
  branch is merged/made default, trigger it manually via `workflow_dispatch`.
