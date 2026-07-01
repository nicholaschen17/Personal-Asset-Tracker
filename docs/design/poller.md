# Poller Design

Long-running Python service that ingests latest stock quotes from the Alpaca Market
Data REST API into DB1. See [ADR-001](../adr/ADR-001-rest-poller-ingestion.md).

**Related docs:** [db1.md](db1.md) (source schema), [observability.md](observability.md)
(logs/metrics/health).

---

## Purpose

The poller is the **live ingest path** (C-10, FR-5). It:

1. Reads the active watchlist from DB1 (FR-4).
2. Calls Alpaca with **one batched request per poll cycle** for all active tickers.
3. Writes quote observations to DB1 (FR-8).
4. Respects the **200 req/min** Alpaca limit (C-1, NFR-1).
5. Retries transient failures without corrupting data (FR-9, NFR-8).

Downstream stages (CDC → DB2 → drop detector) are out of scope here; the poller only
owns Alpaca → DB1.

---

## Requirements traceability

| ID | How the poller satisfies it |
|----|-----------------------------|
| FR-4 | Poll only tickers where `watchlist.delete_flg = false` |
| FR-5 | Long-running process; batched `/v2/stocks/quotes/latest` |
| FR-6 | Runs continuously; backfill is a separate on-demand path |
| FR-7 | Every write includes `observed_at` (Alpaca quote timestamp) |
| FR-8 | Inserts ticker, bid/ask/mid, quote fields, `observed_at` |
| FR-9 | Log + backoff on 429/5xx; no crash on single failure |
| NFR-1 | ~333 ms between calls; batch all symbols per request |
| NFR-8 | One DB transaction per poll cycle; commit all or none |
| C-1 | Token-bucket / fixed interval capped at 200 req/min |
| C-12 | Alpaca keys and DB URL from environment only |

---

## Data flow

```
┌─────────────┐     read active tickers      ┌──────────────┐
│    DB1      │ ───────────────────────────► │    Poller    │
│  watchlist  │                              │  (Python)    │
└─────────────┘                              └──────┬───────┘
       ▲                                            │
       │ write quotes (1 txn / cycle)               │ batched GET
       │                                            ▼
       │                                     ┌──────────────┐
       └─────────────────────────────────────│ Alpaca REST  │
                                             │ latest quotes│
                                             └──────────────┘
```

**Per cycle (target ~333 ms wall time, excluding backoff):**

1. Load active tickers from `watchlist`.
2. If empty → sleep full interval, log `poll_skipped_empty_watchlist`, continue.
3. Wait for rate-limiter permit.
4. `GET /v2/stocks/quotes/latest?symbols=AAPL,MSFT,...&feed=iex`
5. Parse response; map each symbol to a row.
6. `BEGIN` → bulk `INSERT` into `price_observations` → `COMMIT`.
7. Emit structured log + metrics for the cycle.
8. Sleep until next slot (fixed interval or token bucket).

---

## Alpaca integration

### Endpoint

```
GET https://data.alpaca.markets/v2/stocks/quotes/latest
```

| Param | Value |
|-------|-------|
| `symbols` | Comma-separated active watchlist tickers (uppercase) |
| `feed` | `iex` on free tier (C-2); configurable via env |

### Auth

Alpaca Market Data v2 uses header-based auth (C-12):

```
APCA-API-KEY-ID:     ${ALPACA_API_KEY_ID}
APCA-API-SECRET-KEY: ${ALPACA_API_SECRET_KEY}
```

### Response handling

Alpaca returns a map keyed by symbol, e.g.:

```json
{
  "quotes": {
    "AAPL": {
      "ap": 189.50,
      "as": 1,
      "bp": 189.48,
      "bs": 2,
      "t": "2026-06-29T14:32:01.123456789Z"
    }
  }
}
```

| Alpaca field | DB column (see db1.md) | Notes |
|--------------|------------------------|-------|
| `t` | `observed_at` | Quote timestamp from Alpaca (FR-7) |
| `ap` / `bp` | `ask_price` / `bid_price` | Nullable if missing |
| derived | `mid_price` | `(ap + bp) / 2` when both present |
| `as` / `bs` | `ask_size` / `bid_size` | Optional |
| symbol key | `ticker` | FK logical link to watchlist |

**Missing symbols:** If Alpaca omits a requested ticker (halted, invalid), log
`quote_missing` for that ticker; do not fail the whole cycle.

**Chunking:** If the watchlist grows large enough to hit URL/message limits, split
symbols into chunks and consume multiple rate-limiter tokens per cycle. For a
personal watchlist (<100 tickers), a single request is expected.

### Rate-limit headers

Read on every response (FR-9):

- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`

On **429**: log `rate_limited`, sleep until `Reset` (or exponential backoff with
jitter), do **not** write partial DB rows for that cycle.

---

## Rate limiting

### Target cadence

```
200 requests / 60 seconds = 1 request every 0.3 s (⅓ second)
```

### Strategy: token bucket

A token bucket is preferred over a naive `sleep(0.333)` because it handles:

- Temporary pauses (DB slow, 429 backoff) without bursting when resuming
- Optional on-demand backfill sharing the same budget later

| Setting | Default | Env var |
|---------|---------|---------|
| Max tokens (burst) | 5 | `POLLER_RATE_BURST` |
| Refill rate | 200/min (~3.33/sec) | `POLLER_RATE_PER_MIN` |
| Min interval | 0.3 s | `POLLER_MIN_INTERVAL_SEC` |

**Rule:** One Alpaca call consumes **one token**. A poll cycle with chunked symbols
consumes one token per chunk.

Reserve headroom: default refill to **180/min** if backfill or manual tools will
share the same Alpaca account (C-1).

---

## Watchlist integration

The poller reads DB1; it does **not** maintain its own symbol list.

```sql
SELECT ticker
FROM watchlist
WHERE delete_flg = false
ORDER BY ticker;
```

| Event | Poller behavior |
|-------|-----------------|
| New ticker added | Picked up on next cycle (no restart) |
| Ticker soft-deleted | Stops polling on next cycle |
| Empty watchlist | Idle loop; no Alpaca calls |

Reload the watchlist **every cycle** (simple, correct). Cache only if profiling
shows DB load is a problem — unlikely at ~3 queries/sec.

---

## DB writes

Full schema lives in [db1.md](db1.md). The poller writes to **`price_observations`**
(append-only time series).

### Write model

- **Append-only inserts** each cycle (preserves history for drop detection windows).
- **One transaction per poll cycle** (NFR-8): all inserts commit or none do.
- **Idempotency:** natural key `(ticker, observed_at)` unique constraint; on conflict
  `DO NOTHING` so retries do not duplicate rows.

Example insert shape:

```sql
INSERT INTO price_observations (
    ticker, bid_price, ask_price, mid_price,
    bid_size, ask_size, observed_at, ingested_at
) VALUES (...)
ON CONFLICT (ticker, observed_at) DO NOTHING;
```

`ingested_at` = poller wall-clock time when the row was written (distinct from
Alpaca's `observed_at`).

### Connection

- Pool size: 2–5 connections (single poller process).
- Use `asyncpg` or `psycopg` with explicit transaction boundaries.
- Credentials from `POSTGRES_DB_1_URL` (C-12).

---

## Error handling

| Condition | Behavior |
|-----------|----------|
| Network timeout / connection error | Log `alpaca_request_failed`, retry next cycle (no partial write) |
| 401 / 403 | Log `alpaca_auth_failed`, exponential backoff; alert via ops channel when observability is wired |
| 429 | Honor `X-RateLimit-Reset`; skip write for this cycle |
| 5xx | Retry with backoff (max 3 attempts within cycle); then skip write |
| DB connection failure | Log `db_write_failed`, retry next cycle; poller stays alive |
| Partial Alpaca response | Insert rows for symbols returned; log missing tickers |
| Unparseable JSON | Log `alpaca_parse_failed`, skip write |

The process **must not exit** on a single bad cycle (FR-9, C-15). Only fatal
misconfiguration (missing env vars) should fail fast at startup.

---

## Configuration

All runtime behavior via environment (FR-27, C-12):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ALPACA_API_KEY_ID` | yes | — | Alpaca API key |
| `ALPACA_API_SECRET_KEY` | yes | — | Alpaca API secret |
| `POSTGRES_DB_1_URL` | yes | — | DB1 connection string |
| `ALPACA_DATA_BASE_URL` | no | `https://data.alpaca.markets` | API base |
| `ALPACA_FEED` | no | `iex` | Market data feed (C-2) |
| `POLLER_RATE_PER_MIN` | no | `180` | Max Alpaca calls per minute |
| `POLLER_MIN_INTERVAL_SEC` | no | `0.333` | Floor between calls |
| `POLLER_HTTP_TIMEOUT_SEC` | no | `10` | Request timeout |
| `POLLER_WATCHLIST_REFRESH` | no | `every_cycle` | `every_cycle` (only option for v1) |

---

## Process structure

Proposed layout under `src/poller/`:

```
src/poller/
├── __init__.py
├── __main__.py          # entrypoint: python -m poller
├── config.py            # env parsing + validation
├── rate_limiter.py      # token bucket
├── alpaca_client.py     # HTTP client, auth, parse response
├── watchlist.py         # load active tickers from DB1
├── writer.py            # transactional inserts
└── loop.py              # main poll loop orchestration
```

Reuse `src/app_logging/` for structured JSON logs (FR-23).

### Main loop (pseudocode)

```python
async def run():
    config = load_config()          # fail fast if invalid
    limiter = TokenBucket(...)
    alpaca = AlpacaClient(config)
    db = await connect(config.db_url)

    while True:
        tickers = await watchlist.load_active(db)
        if not tickers:
            await sleep(config.min_interval)
            continue

        await limiter.acquire()
        try:
            quotes = await alpaca.fetch_latest(tickers)
            async with db.transaction():
                await writer.insert_observations(db, quotes)
            log.info("poll_ok", ticker_count=len(quotes), ...)
        except RateLimited as e:
            log.warning("rate_limited", reset_at=e.reset_at)
            await sleep_until(e.reset_at)
        except TransientError as e:
            log.warning("poll_failed", error=str(e))
        await limiter.wait_for_next_slot()
```

Use **asyncio** + **httpx** (or **aiohttp**) for non-blocking HTTP; DB driver
matching the rest of the stack.

---

## Deployment

Docker Compose service (replaces Meltano on the ingest path per ADR-001):

```yaml
poller:
  build: .
  command: python -m poller
  depends_on:
    - postgres_db_1
  environment:
    ALPACA_API_KEY_ID: ${ALPACA_API_KEY_ID}
    ALPACA_API_SECRET_KEY: ${ALPACA_API_SECRET_KEY}
    POSTGRES_DB_1_URL: postgresql://${POSTGRES_DB_1_USER}:...
  restart: unless-stopped
```

- **Single replica** (C-13, C-5): one poller process avoids duplicate Alpaca calls.
- **Health:** HTTP `/health` or Docker healthcheck verifying last successful poll
  within N seconds (see observability.md, FR-24).
- **Graceful shutdown:** SIGTERM finishes current cycle or rolls back open txn, then exits.

---

## Observability

Each poll cycle emits structured logs (FR-23):

| Event | Level | Fields |
|-------|-------|--------|
| `poll_ok` | info | `ticker_count`, `rows_written`, `duration_ms`, `rate_limit_remaining` |
| `poll_skipped_empty_watchlist` | debug | — |
| `rate_limited` | warn | `reset_at`, `remaining` |
| `alpaca_request_failed` | warn | `status_code`, `error` |
| `quote_missing` | warn | `ticker` |
| `db_write_failed` | error | `error` |

Metrics (FR-24, detailed in observability.md):

- `poller_polls_total` (counter)
- `poller_quotes_written_total` (counter)
- `poller_last_success_timestamp` (gauge)
- `poller_cycle_duration_seconds` (histogram)
- `poller_alpaca_rate_limit_remaining` (gauge)

**Stall detection:** if `poller_last_success_timestamp` is older than 60s while
watchlist is non-empty → operational alert (NFR-15).

---

## Out of scope (v1)

| Item | Notes |
|------|-------|
| Historical backfill | Separate CLI/job (FR-6); shares rate limiter budget |
| WebSocket ingest | Ruled out by C-10 |
| Writing to DB2 | CDC handles replication (FR-10) |
| Drop detection / alerts | Separate detector service |
| Meltano / Singer | Off live path (ADR-001) |

---

## Open questions

1. **Exact `price_observations` schema** — finalize in db1.md (retention policy per C-6).
2. **Mid price vs last trade** — quotes only for v1, or also `/v2/stocks/trades/latest`?
3. **Market hours** — poll 24/5, regular session only, or always? Default: always;
   Alpaca returns last available quote off-hours.
4. **Shared rate limit** — if backfill CLI is added, use a file/redis lock or single
   process for all Alpaca callers on this account.

---

## Implementation checklist

- [ ] Finalize `price_observations` + `watchlist` in db1.md
- [ ] `src/poller/` module with config, client, loop, writer
- [ ] Token-bucket rate limiter with 429 handling
- [ ] Docker Compose `poller` service
- [ ] Tests: rate limiter, response parser, writer idempotency, empty watchlist
- [ ] Health / stall metrics in observability.md
- [ ] Remove Meltano from compose once poller is verified
