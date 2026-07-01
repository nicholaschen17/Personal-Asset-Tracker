import os
import signal
import sys
import time
from datetime import datetime, timezone

import psycopg2

from shared.alpaca_poller import AlpacaPoller
from shared.db.db import check_db_health, get_tickers, insert_market_data
from shared.logging.logging_setup import get_logger

log = get_logger(__name__)

_shutdown = False
DB_CHECK_INTERVAL_SEC = float(os.getenv("POLLER_DB_CHECK_INTERVAL_SEC", "120"))


def _handle_shutdown(signum, frame) -> None:
    global _shutdown
    _shutdown = True


signal.signal(signal.SIGTERM, _handle_shutdown)
signal.signal(signal.SIGINT, _handle_shutdown)


def _interruptible_sleep(seconds: float) -> None:
    end = time.monotonic() + seconds
    while not _shutdown and time.monotonic() < end:
        time.sleep(min(0.1, end - time.monotonic()))


def ensure_db_or_exit(db_conn) -> None:
    if check_db_health(db_conn):
        log.info("db_health_check_ok", time=datetime.now(timezone.utc).isoformat())
        return
    log.error("db_unavailable_exiting", time=datetime.now(timezone.utc).isoformat())
    sys.exit(1)


class Polling:
    def __init__(self, api_key_id: str, api_secret_key: str, db_url: str) -> None:
        self.poller = AlpacaPoller(api_key_id, api_secret_key)
        self.db_conn = None
        self.db_url = db_url
        rate_per_min = int(os.getenv("POLLER_RATE_PER_MIN", "100"))
        self.poll_interval_sec = 60.0 / rate_per_min
        self.empty_watchlist_interval_sec = float(
            os.getenv("POLLER_EMPTY_WATCHLIST_INTERVAL_SEC", "10")
        )

    def run_poll_loop(self) -> None:
        self.db_conn = psycopg2.connect(self.db_url)
        ensure_db_or_exit(self.db_conn)
        last_db_check = time.monotonic()

        log.info(
            "poller_started",
            poll_interval_sec=self.poll_interval_sec,
            empty_watchlist_interval_sec=self.empty_watchlist_interval_sec,
            db_check_interval_sec=DB_CHECK_INTERVAL_SEC,
            time=datetime.now(timezone.utc).isoformat(),
        )

        # Need to fix logic to separate polling for empty watchlist and polling for market data

        try:
            while not _shutdown:
                now = time.monotonic()
                if now - last_db_check >= DB_CHECK_INTERVAL_SEC:
                    ensure_db_or_exit(self.db_conn)
                    last_db_check = now

                tickers = get_tickers(self.db_conn, log_fetch=False)

                if not tickers:
                    log.info("poll_skipped_empty_watchlist", time=datetime.now(timezone.utc).isoformat())
                    _interruptible_sleep(self.empty_watchlist_interval_sec)
                    continue

                market_data = self.poller.get_last_trade_price_and_quote_price(tickers)
                insert_market_data(self.db_conn, market_data)
                _interruptible_sleep(self.poll_interval_sec)
        finally:
            self.db_conn.close()
            log.info("poller_shutdown", time=datetime.now(timezone.utc).isoformat())


if __name__ == "__main__":
    api_key_id = os.getenv("ALPACA_API_KEY_ID")
    api_secret_key = os.getenv("ALPACA_API_SECRET_KEY")
    db_url = os.getenv("POSTGRES_DB_1_URL")

    if not api_key_id or not api_secret_key:
        raise ValueError("ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY must be set")
    if not db_url:
        raise ValueError("POSTGRES_DB_1_URL must be set")

    poller = Polling(api_key_id, api_secret_key, db_url)
    poller.run_poll_loop()
