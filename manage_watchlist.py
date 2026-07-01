"""
Manage the watchlist of tracked stocks.

This module is explicitly meant to add stocks into a watchlist table with the
following columns:

    id           - Primary key
    ticker       - Stock ticker symbol (e.g. AAPL, MSFT)
    asset_class  - Asset classification (e.g. equity)
    delete_flg   - Soft-delete flag
    added_at     - Timestamp when the row was created
    updated_at   - Timestamp when the row was last updated
"""

from app_logging.logging_setup import get_logger

# Initializes the logger
log = get_logger(__name__)


# Function to add a stock to the watchlist
def add_stock_to_watchlist(ticker: str, asset_class: str):

    log.info("stock_added", ticker=ticker, asset_class=asset_class)

    return True





def main():
    log.info("stock_added", ticker="AAPL", asset_class="equity")


if __name__ == "__main__":
    main()