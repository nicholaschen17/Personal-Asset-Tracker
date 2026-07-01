# db_deploy

Schema and migration tooling for the two Postgres databases in this project.

**Related docs:** [docs/design/db1.md](../../docs/design/db1.md), [docs/design/db2.md](../../docs/design/db2.md)

---

## Role in the architecture

The stack uses two Postgres instances (C-9):

| Database | Compose service | Port (host) | Purpose |
|----------|-----------------|-------------|---------|
| **DB1** | `postgres_db_1` | `5432` | Source of truth — watchlist, poller writes |
| **DB2** | `postgres_db_2` | `5433` | Serving copy — CDC from DB1, read by detector/alerts |

```
poller / watchlist tools  →  DB1  →  (logical replication)  →  DB2  →  drop detector
```

- **DB1** is written by the REST poller and watchlist management (FR-4, FR-8).
- **DB2** is not written by application code directly; it converges via CDC (FR-10–FR-13).
- This package owns **DDL and schema changes** for both databases, not runtime queries (those live in `src/poller/`, `manage_watchlist.py`, etc.).

---

## Directory layout

```
src/db_deploy/
├── README.md           # this file
├── init_db_1/          # first-time setup for DB1 (watchlist, price_observations, …)
├── init_db_2/          # first-time setup for DB2 (mirrored tables + replication consumer prep)
├── sql/                # shared or versioned SQL files (CREATE TABLE, indexes, grants)
└── patch/              # incremental migrations applied after init (001_, 002_, …)
```

| Folder | When to use |
|--------|-------------|
| `init_db_1/` | Empty DB1 — base schema from scratch |
| `init_db_2/` | Empty DB2 — schema expected on the serving side |
| `sql/` | Reusable SQL fragments referenced by init/patch scripts |
| `patch/` | Ordered, idempotent changes to existing databases |

Naming convention for patches: `patch/NNN_short_description.sql` (e.g. `001_add_watchlist.sql`).

---

## Expected tables (v1)

Detailed column lists belong in `docs/design/db1.md` / `db2.md`. Minimum set implied by requirements and the poller:

### DB1 — source

**`watchlist`** (FR-1–FR-4)

| Column | Notes |
|--------|--------|
| `id` | Primary key |
| `ticker` | e.g. `AAPL` |
| `asset_class` | e.g. `equity` |
| `delete_flg` | Soft delete |
| `added_at`, `updated_at` | Timestamps |

**`price_observations`** (FR-8, poller DTO `AlpacaMarketData`)

Append-only time series written each poll cycle. Suggested shape:

| Column | Notes |
|--------|--------|
| `id` | `bigserial` PK |
| `ticker` | |
| `last_price` | From last trade |
| `bid`, `ask` | Nullable quote sides |
| `trade_at` | Alpaca trade timestamp |
| `quote_at` | Alpaca quote timestamp (nullable) |
| `ingested_at` | Poller write time, default `now()` |

Constraints:

- `UNIQUE (ticker, trade_at)` — idempotent inserts (`ON CONFLICT DO NOTHING`, NFR-8)
- Index on `(ticker, trade_at DESC)` when query patterns need it

### DB2 — serving

Same table definitions as DB1 for replicated relations (FR-11). Replication config (publication, subscription, roles) is applied separately from table DDL; document it in `init_db_2/` when implemented.

---

## Connection strings

From project root `.env` (see `docker-compose.yml`):

| Variable | Used by |
|----------|---------|
| `POSTGRES_DB_1_USER`, `POSTGRES_DB_1_PASSWORD`, `POSTGRES_DB_1_DB` | DB1 |
| `POSTGRES_DB_2_USER`, `POSTGRES_DB_2_PASSWORD`, `POSTGRES_DB_2_DB` | DB2 |

**From host:**

```bash
psql "postgresql://${POSTGRES_DB_1_USER}:${POSTGRES_DB_1_PASSWORD}@localhost:5432/${POSTGRES_DB_1_DB}"
psql "postgresql://${POSTGRES_DB_2_USER}:${POSTGRES_DB_2_PASSWORD}@localhost:5433/${POSTGRES_DB_2_DB}"
```

**From another container:**

```text
postgresql://USER:PASSWORD@postgres_db_1:5432/DBNAME
postgresql://USER:PASSWORD@postgres_db_2:5432/DBNAME
```

The poller uses `POSTGRES_DB_1_URL` (compose sets this automatically).

---

## Running schema changes

Automation (Python CLI or compose service) is not wired yet. Until then, apply SQL manually:

```bash
# Example — once files exist under sql/ or init_db_1/
psql "$POSTGRES_DB_1_URL" -f src/db_deploy/init_db_1/001_schema.sql
psql "$POSTGRES_DB_2_URL" -f src/db_deploy/init_db_2/001_schema.sql
```

Intended workflow:

1. **New environment** — run all scripts in `init_db_1/`, then `init_db_2/`, then configure CDC.
2. **Existing environment** — apply the next numbered script in `patch/` only; never edit applied migrations in place.
3. **Record changes** — structural DB decisions go in `docs/adr/` (see `skills/manage-architecture.md`).

---

## What this package does not own

| Concern | Owner |
|---------|--------|
| Alpaca polling / inserts | `src/poller/` |
| CDC replication runtime | Postgres logical replication (configured outside or in `init_db_2/`) |
| Drop detection reads | Future detector service (reads DB2) |
| Secrets | `.env` / compose `environment:` (C-12) — never commit credentials |

---

## Checklist

- [ ] Add `init_db_1/` SQL for `watchlist` and `price_observations`
- [ ] Add `init_db_2/` SQL mirroring replicated tables
- [ ] Document publication/subscription in `docs/design/db2.md`
- [ ] Add patch runner or `make db-migrate` target
- [ ] Align poller `insert_market_data` with final column names
