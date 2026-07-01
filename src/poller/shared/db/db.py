"""Database connectivity helpers for the poller."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import psycopg2
from psycopg2.extensions import connection as Connection
from psycopg2.extras import execute_values

from shared.logging.logging_setup import get_logger
from shared.models.models import AlpacaMarketData

log = get_logger(__name__)

_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.]{0,9}$")


def normalize_ticker(ticker: str) -> str:
    normalized = ticker.strip().upper()
    if not _TICKER_RE.match(normalized):
        raise ValueError(f"invalid ticker: {ticker!r}")
    return normalized


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_db_timestamp(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _ping(db_conn: Connection) -> bool:
    try:
        with db_conn.cursor() as cur:
            cur.execute("SELECT 1")
            return cur.fetchone()[0] == 1
    except Exception as exc:
        log.error("db_health_check_failed", error=str(exc))
        return False


def check_db_health(db_conn: Connection) -> bool:
    """Return True if DB1 accepts connections and responds to SELECT 1."""
    return _ping(db_conn)


def insert_market_data(db_conn: Connection, market_data: list[AlpacaMarketData]) -> None:
    if not market_data:
        log.info("no_market_data_to_insert", time=_utc_now().isoformat())
        return
    rows = [
        (
            row.ticker,
            row.last_price,
            row.bid if row.bid is not None else 0,
            row.ask if row.ask is not None else 0,
            _to_db_timestamp(row.trade_at),
            _to_db_timestamp(row.quote_at or row.trade_at),
        )
        for row in market_data
    ]
    try:
        with db_conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO poller.market_data (ticker, last_price, bid, ask, trade_at, quote_at)
                VALUES %s
                ON CONFLICT (ticker, trade_at) DO NOTHING
                """,
                rows,
            )
            rows_inserted = cur.rowcount
        db_conn.commit()
        log.info(
            "market_data_inserted",
            rows_inserted=rows_inserted,
            rows_skipped=len(market_data) - rows_inserted,
            time=_utc_now().isoformat(),
        )
    except Exception as exc:
        db_conn.rollback()
        log.error("market_data_insert_failed", error=str(exc))
        raise exc


def get_tickers(db_conn: Connection, *, log_fetch: bool = True) -> list[str]:
    try:
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT ticker FROM poller.tickers WHERE delete_flg = FALSE ORDER BY ticker"
            )
            tickers = [row[0] for row in cur.fetchall()]
        if log_fetch:
            log.info(
                "tickers_fetched",
                ticker_count=len(tickers),
                tickers=tickers,
                time=_utc_now().isoformat(),
            )
        return tickers
    except Exception as exc:
        log.error("tickers_fetch_failed", error=str(exc))
        raise exc


def add_ticker(db_conn: Connection, ticker: str) -> None:
    """Add a ticker or reactivate a soft-deleted one."""
    symbol = normalize_ticker(ticker)
    now = _to_db_timestamp(_utc_now())
    try:
        with db_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO poller.tickers (ticker, delete_flg, added_at, updated_at)
                VALUES (%s, FALSE, %s, %s)
                ON CONFLICT (ticker) DO UPDATE SET
                    delete_flg = FALSE,
                    updated_at = EXCLUDED.updated_at
                """,
                (symbol, now, now),
            )
        db_conn.commit()
        log.info("ticker_added", ticker=symbol, time=_utc_now().isoformat())
    except Exception as exc:
        db_conn.rollback()
        log.error("ticker_add_failed", error=str(exc), ticker=symbol, time=_utc_now().isoformat())
        raise exc


def delete_ticker(db_conn: Connection, ticker: str) -> bool:
    """Soft-delete a ticker. Returns False if the ticker was not active."""
    symbol = normalize_ticker(ticker)
    now = _to_db_timestamp(_utc_now())
    try:
        with db_conn.cursor() as cur:
            cur.execute(
                """
                UPDATE poller.tickers
                SET delete_flg = TRUE, updated_at = %s
                WHERE ticker = %s AND delete_flg = FALSE
                """,
                (now, symbol),
            )
            deleted = cur.rowcount > 0
        db_conn.commit()
        if deleted:
            log.info("ticker_deleted", ticker=symbol, time=_utc_now().isoformat())
        else:
            log.info("ticker_delete_not_found", ticker=symbol, time=_utc_now().isoformat())
        return deleted
    except Exception as exc:
        db_conn.rollback()
        log.error("ticker_delete_failed", error=str(exc), ticker=symbol, time=_utc_now().isoformat())
        raise exc
