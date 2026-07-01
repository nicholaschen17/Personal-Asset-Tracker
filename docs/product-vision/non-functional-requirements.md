Non-Functional Requirements
===========================
Quality targets: how fast, how reliable, how well. Each is measurable and has an ID
(NFR-N). Behaviors live in functional-requirements.md; fixed limits live in
constraints.md. Numbers below are starting targets, tune as the system is measured.

Latency & freshness
-------------------
NFR-1  Ingestion polls the Alpaca API at the highest cadence that stays within the
       ~200 req/min free-tier limit (see constraints C-1); polling is batched across
       watchlisted tickers to maximize coverage per request.
NFR-2  Replication from DB1 to DB2 is streaming (log-based CDC) with p95 lag < 1s.
       Note: true sub-millisecond delivery is not achievable over Postgres logical
       replication; sub-second is the realistic real-time target.
NFR-3  Serving-database (DB2) data freshness is <= 1s behind DB1 under normal load.
NFR-4  End-to-end alert latency (market move -> notification delivered) target < 60s,
       bounded mainly by API polling cadence rather than internal processing.

Data correctness & consistency
------------------------------
NFR-5  Alert delivery is effectively exactly-once: a single drop event yields exactly
       one notification per enabled channel (de-dup + idempotent send).
NFR-6  No missed drop events for watchlisted tickers; false positives are bounded and
       tunable via thresholds/windows.
NFR-7  DB2 converges to DB1 (eventual consistency); a periodic reconciliation check
       (e.g. row counts / checksums on replicated tables) detects drift.
NFR-8  Ingestion does not produce duplicate or partial committed rows on retry.

Reliability & recovery
----------------------
NFR-9  Best-effort availability (personal project, no 24/7 SLA per constraint C-15);
       the system must be recoverable rather than always-on.
NFR-10 Recovery Point Objective (RPO) = zero data loss: after a restart or outage,
       replication resumes from the last confirmed WAL position with no gaps.
NFR-11 Recovery Time Objective (RTO): the pipeline returns to normal operation within
       a few minutes of a host/container restart, without manual re-seeding.
NFR-12 If DB2 is unavailable, WAL retention on DB1 is bounded/monitored so the source
       disk cannot fill from an unconsumed replication slot.

Observability
-------------
NFR-13 100% of pipeline stages (ingest, replicate, detect, alert) emit structured logs
       that can be traced for a single ticker end to end.
NFR-14 Metrics and replication-lag monitoring are in place; system/operational alerts
       (pipeline down, lag over threshold) are distinct from business alerts.
NFR-15 Mean time to detect a stalled or lagging pipeline is < 1 minute.

Security & privacy
------------------
NFR-16 Secrets (Alpaca token, DB credentials, notification keys) are supplied via
       environment/.env and never committed (see constraint C-12).
NFR-17 The replication and application database users run with least privilege (not
       superuser); the replication role only has the rights CDC requires.
NFR-18 All external connections (Alpaca API, SMS/Discord) use encryption in transit.

Resource efficiency
-------------------
NFR-19 The whole stack (2x Postgres + REST poller + app + notifications) fits in < 16GB RAM
       and runs on a single host (see constraints C-4/C-5).
NFR-20 Historical data retention is bounded so local disk usage stays within the host's
       limits over time.

Maintainability & SDLC
----------------------
NFR-21 Linting and automated checks must pass before deploy.
NFR-22 The environment is reproducible and containerized (Docker / docker-compose), with
       dev / staging / prod parity.
NFR-23 Changes are covered by automated tests sufficient to catch regressions in the
       ingest -> replicate -> detect -> alert path.

Cost
----
NFR-24 Operating cost stays within free tiers (Alpaca, notifications, self-hosted
       Postgres); any paid dependency is a deliberate, ADR-documented decision (C-7).
