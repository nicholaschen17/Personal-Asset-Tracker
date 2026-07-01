Functional Requirements
=======================
What the system must DO. Each requirement has an ID (FR-N) so it can be referenced
from ADRs, tests, and issues. Measurable targets (latency, uptime, etc.) live in
non-functional-requirements.txt; this file defines behavior.

Watchlist management
--------------------
FR-1  The user can add a stock to a watchlist by ticker and asset class.
FR-2  The user can soft-delete a stock from the watchlist (delete_flg) without losing
      its history.
FR-3  Each watchlist row tracks id, ticker, asset_class, delete_flg, added_at, and
      updated_at; updated_at changes on every modification.
FR-4  The watchlist is the source of truth for which tickers the system ingests and
      monitors.

Data ingestion (Alpaca API -> source DB)
----------------------------------------
FR-5  The system pulls market/asset data for watchlisted tickers from the Alpaca API
      via a long-running REST poller that batches symbols per request.
FR-6  Live ingestion runs continuously; historical backfill can be triggered on demand.
FR-7  Each poll fetches the latest quote for all active watchlist tickers; writes to
      DB1 include an observation timestamp so downstream stages can detect new data.
FR-8  Ingested records are written to the source database (Postgres DB1) with the
      ticker, price/quote fields, and an event/observation timestamp.
FR-9  Ingestion failures (auth, rate limit, network) are logged and retried without
      crashing the pipeline or producing partial/duplicate committed rows.

Replication (source DB -> serving DB)
-------------------------------------
FR-10 Changes (insert/update/delete) to the selected source tables are streamed to the
      second database (DB2) via log-based replication (CDC).
FR-11 The set of replicated tables is explicit and configurable (at minimum: the
      watchlist table and the Alpaca price/asset tables).
FR-12 Replication recovers automatically after a restart or short outage and resumes
      from the last confirmed position without manual re-seeding.
FR-13 The serving database (DB2) is the read source for detection and alerting.

Drop detection
--------------
FR-14 The system continuously evaluates price movements for each watchlisted ticker.
FR-15 An alert condition is defined as a price decline of at least a configurable
      threshold (percent) over a configurable rolling time window.
FR-16 Detection supports both single-stock drops and a broad market drop (e.g. a
      tracked index/benchmark crossing the same kind of threshold).
FR-17 Thresholds and windows are configurable per ticker and globally, without code
      changes.
FR-18 The system de-duplicates alerts so a single sustained drop does not spam repeated
      notifications (cooldown / one alert per event until conditions reset).

Alerting & notifications
------------------------
FR-19 When an alert condition is met, the system sends a notification via SMS and/or
      Discord.
FR-20 A notification includes the ticker, the magnitude of the move, the time window,
      and the observation time.
FR-21 Notification channels are individually configurable and can be enabled/disabled.
FR-22 Failed notification delivery is logged and retried; a delivery failure never
      silently drops an alert.

Observability (user-facing behavior)
------------------------------------
FR-23 All pipeline stages (ingest, replicate, detect, alert) emit structured logs with
      enough context to trace a single ticker's data end to end.
FR-24 The system exposes/records health signals for pipeline status and replication lag
      so a stalled or lagging pipeline is detectable.
FR-25 System/operational alerts (pipeline broken or replication lag over threshold) are
      distinct from business alerts (a stock dropped).

Configuration & secrets
------------------------
FR-26 Credentials (Alpaca auth token, database credentials, notification API keys) are
      supplied via environment/secret configuration, never hard-coded.
FR-27 Runtime behavior (thresholds, schedules, enabled channels, replicated tables) is
      configurable without modifying source code.

Out of scope (current version)
------------------------------
FR-OOS-1 Tracking non-equity assets (cash, crypto, real estate, liabilities).
FR-OOS-2 Multi-user accounts and authentication.
FR-OOS-3 Automated trading or order execution.
