Constraints
===========
Hard limits and boundaries the design MUST respect. These are not goals (see
non-functional-requirements.md) or behaviors (see functional-requirements.md); they are
fixed realities that shape the architecture. Each has an ID (C-N) for reference.

External API limits
--------------------
C-1  Alpaca free Market Data API allows ~200 requests per minute. Ingestion (polling,
     batching, backfills) must stay within this rate limit and degrade gracefully when
     approaching it (throttle/back off rather than fail).
C-2  Free-tier Alpaca market data may be delayed and/or limited in history and symbol
     coverage; "near real-time" is bounded by what the free feed provides.
C-3  Alpaca market data is licensed for personal use; it is not redistributed or exposed
     publicly.

Hardware / resource limits
--------------------------
C-4  Must be lightweight: the full stack runs on a single machine with less than 16GB of
     RAM (Postgres x2 + REST poller + app + notifications).
C-5  Runs on a single host (developer laptop / small VM); no multi-node cluster, no
     managed cloud data platform assumed. This rules out heavyweight stacks (e.g.
     Kafka + Spark clusters) for core data flow.
C-6  Storage is finite local disk; retention/compaction of historical price data must be
     bounded rather than growing unbounded.

Cost
----
C-7  The project targets free / no-cost tiers wherever possible (Alpaca free tier,
     self-hosted Postgres, free notification quotas). Any paid service must be a
     deliberate, documented decision (ADR).
C-8  Notification providers (SMS via the chosen provider, Discord webhooks) have their
     own free-tier rate/volume limits the alerting logic must respect.

Technology / platform
---------------------
C-9  Data stores are PostgreSQL (two instances); replication uses Postgres-native
     log-based replication (CDC), per the chosen architecture.
C-10 Live ingestion is done through a long-running Python REST poller. The poller
     batches active watchlist tickers into Alpaca latest-quotes requests and spaces
     calls to stay within C-1 (~one request every ⅓ second, 200 req/min max). WebSocket
     ingestion and heavyweight stream processors (Flink, Spark) are out of scope for
     the core data path.
C-11 The system is containerized (Docker / docker-compose) and must run via the existing
     compose setup.
C-12 Secrets (Alpaca token, DB credentials, notification keys) are provided via
     environment/.env and never committed to the repo.

Scope / operational
--------------------
C-13 Single-user, personal system; no multi-tenancy or external user auth.
C-14 No automated trading or order execution (read/alert only).
C-15 Best-effort availability: this is a personal project, not a 24/7 SLA-backed
     service; downtime is acceptable as long as it is recoverable without data loss.
