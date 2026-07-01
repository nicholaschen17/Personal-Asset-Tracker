The purpose of this project is to:

Product goal
------------
Build a personal tracker that keeps near real-time updates on my stock portfolio and
alerts me when the market or an individual holding starts dropping, delivered via SMS
and Discord notifications.

"Near real-time" and "dropping" are defined as measurable targets in
non-functional-requirements.txt and functional-requirements.txt respectively (e.g. a
percentage move over a rolling time window, with a target end-to-end alert latency).

Scope
-----
In scope:
  - Publicly traded equities I hold or watch (sourced from the Alpaca API).
  - A watchlist of tickers I manage myself.
  - Price/market-data ingestion, storage, and drop-detection alerting.

Out of scope (for now):
  - Full net worth across all asset classes (cash, crypto, real estate, liabilities).
  - Multi-user support; this is a single-user, personal system.

What the project touches end to end
-----------------------------------
  1) Ingestion: pull market and asset data from the Alpaca API into a source database
     (Postgres) via a long-running REST poller (batched latest-quotes calls).
  2) Replication: stream changes from the source database to a second database through
     log-based replication (CDC), so downstream reads/alerting work off a synced copy.
  3) Detection & alerting: evaluate price movements and send SMS / Discord alerts.
  4) Operations: secrets handling (API tokens, DB credentials), since this involves
     personal financial data.

Things to learn (the real motivation)
-------------------------------------
  1) Data Engineer: streaming, log-based replication, syncing, and latency, plus
     monitoring pipeline health and replication lag.
  2) Software / Backend Engineer: structured logging and mature observability
     (metrics, tracing, dashboards), distinguishing business alerts (a stock dropped)
     from system alerts (the pipeline broke or fell behind).
  3) SDLC: AI-powered workflows, linting, pre-deployment checks, containerization, and
     mature environments (dev / staging / prod).

Note: structural, database, and tech-stack decisions made while building toward this
vision should be recorded as ADRs under docs/adr/ (see skills/manage-architecture.md).
