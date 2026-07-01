# Alpaca Poller class shared between last trade price and quote data

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.data.requests import StockLatestTradeRequest
from shared.logging.logging_setup import get_logger
import os

log = get_logger(__name__)


class AlpacaPoller:
    def __init__(self, api_key_id: str, api_secret_key: str) -> None:
        self.client = StockHistoricalDataClient(api_key_id, api_secret_key)

    def get_quote_price(self, tickers: list[str]) -> dict:
        request = StockLatestQuoteRequest(symbol_or_symbols=tickers)
        quotes = self.client.get_stock_latest_quote(request)
        if not isinstance(quotes, dict):
            quotes = {tickers[0]: quotes}
        log.info("quotes_fetched", ticker_count=len(quotes), tickers=tickers)
        return quotes

    def get_last_trade_price(self, tickers: list[str]) -> dict:
        request = StockLatestTradeRequest(symbol_or_symbols=tickers)
        trades = self.client.get_stock_latest_trade(request)
        if not isinstance(trades, dict):
            trades = {tickers[0]: trades}
        log.info("trades_fetched", ticker_count=len(trades), tickers=tickers)
        return trades

    def get_last_trade_price_and_quote_price(self, tickers: list[str]) -> dict:
        # Initialize one shared client
        ALPACA_API_KEY_ID = os.getenv("ALPACA_API_KEY_ID")
        ALPACA_API_SECRET_KEY = os.getenv("ALPACA_API_SECRET_KEY")

        client = StockHistoricalDataClient(ALPACA_API_KEY_ID, ALPACA_API_SECRET_KEY)
        last_trades = client.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=tickers))
        if not isinstance(last_trades, dict):
            last_trades = {tickers[0]: last_trades}
        log.info("trades_fetched", ticker_count=len(last_trades), tickers=tickers)
        quotes = client.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=tickers))
        if not isinstance(quotes, dict):
            quotes = {tickers[0]: quotes}
        log.info("quotes_fetched", ticker_count=len(quotes), tickers=tickers)

        result = {
            ticker: {
                "last_trade": last_trades[ticker],
                "quote": quotes[ticker],
            }
            for ticker in tickers
        }
        for ticker, prices in result.items():
            trade = prices["last_trade"]
            quote = prices["quote"]
            log.info(
                "market_data",
                ticker=ticker,
                last_price=float(trade.price),
                bid=float(quote.bid_price) if quote.bid_price else None,
                ask=float(quote.ask_price) if quote.ask_price else None,
                trade_at=str(trade.timestamp),
                quote_at=str(quote.timestamp),
            )
        return result
