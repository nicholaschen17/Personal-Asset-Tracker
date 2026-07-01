# ADR 001: REST Poller for Live Ingestion

## Context

The product ingests Alpaca market data for a personal watchlist into Postgres DB1,
then replicates to DB2 via CDC for drop detection and alerting. Constraint C-1 caps
the Alpaca free tier at ~200 REST requests per minute. NFR-1 targets the highest
poll cadence within that limit (~one batched call every ⅓ second).

The original constraints (C-10) specified Meltano / Singer taps for ingestion.
Meltano is designed for scheduled ELT jobs, not a continuous sub-second polling loop.
WebSocket ingestion is not available for this API integration. Flink and Spark are
ruled out by C-5 (single host, no cluster).

## Decision

- **Live ingestion** uses a **long-running Python REST poller** that:
  - Reads the active watchlist from DB1
  - Batches all tickers into Alpaca `/v2/stocks/quotes/latest` (or equivalent) calls
  - Spaces requests to stay within 200 req/min (target interval: ~333 ms)
  - Writes quote rows to DB1 with observation timestamps
  - Backs off on rate-limit (429) and transient errors (FR-9)
- **Replication, detection, and alerting** are unchanged: Postgres CDC DB1 → DB2,
  then a separate app service for drop detection and notifications.
- **Meltano / Singer** is **not** used on the live ingest path. Existing tap code
  may remain for reference or optional backfill until removed deliberately.
- **WebSocket, Flink, and Spark** are **not** used for core data flow.

## Consequences

**Good**
- Matches rate-limit math and NFR-1 batching strategy directly
- Simpler hot path: one service, one loop, easy rate limiting and observability
- Lower RAM footprint vs Meltano orchestration (C-4, NFR-19)
- Fits single-host constraint (C-5)

**Bad**
- Loses Singer/Meltano ecosystem benefits (catalog, incremental state, orchestration UI)
- Poller must implement its own retry, backoff, and health signals
- Historical backfill is a separate code path (on-demand), not unified in Meltano

**Follow-ups**
- Implement `src/` REST poller service and add to docker-compose
- Remove or repurpose Meltano container when poller is in place
- Update FR-23/FR-24 health signals to include poller stall detection
