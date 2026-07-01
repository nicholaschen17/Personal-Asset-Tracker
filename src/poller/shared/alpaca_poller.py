# Alpaca Poller class shared between last trade price and quote data

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.data.requests import StockLatestTradeRequest

from shared.logging.logging_setup import get_logger
from shared.models.models import AlpacaMarketData

log = get_logger(__name__)


def _as_symbol_map(items: dict | object, tickers: list[str]) -> dict:
    if isinstance(items, dict):
        return items
    return {tickers[0]: items}


class AlpacaPoller:
    def __init__(self, api_key_id: str, api_secret_key: str) -> None:
        self.client = StockHistoricalDataClient(api_key_id, api_secret_key)

    def get_quote_price(self, tickers: list[str]) -> list[AlpacaMarketData]:
        request = StockLatestQuoteRequest(symbol_or_symbols=tickers)
        quotes = _as_symbol_map(self.client.get_stock_latest_quote(request), tickers)
        log.info("quotes_fetched", ticker_count=len(quotes), tickers=tickers)
        return [
            AlpacaMarketData(
                ticker=ticker,
                last_price=float(quote.ask_price or quote.bid_price or 0),
                bid=float(quote.bid_price) if quote.bid_price else None,
                ask=float(quote.ask_price) if quote.ask_price else None,
                trade_at=quote.timestamp,
                quote_at=quote.timestamp,
            )
            for ticker, quote in quotes.items()
        ]

    def get_last_trade_price(self, tickers: list[str]) -> list[AlpacaMarketData]:
        request = StockLatestTradeRequest(symbol_or_symbols=tickers)
        trades = _as_symbol_map(self.client.get_stock_latest_trade(request), tickers)
        log.info("trades_fetched", ticker_count=len(trades), tickers=tickers)
        return [
            AlpacaMarketData(
                ticker=ticker,
                last_price=float(trade.price),
                trade_at=trade.timestamp,
            )
            for ticker, trade in trades.items()
        ]

    def get_last_trade_price_and_quote_price(self, tickers: list[str]) -> list[AlpacaMarketData]:
        last_trades = _as_symbol_map(
            self.client.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=tickers)),
            tickers,
        )
        log.info("trades_fetched", ticker_count=len(last_trades), tickers=tickers)

        quotes = _as_symbol_map(
            self.client.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=tickers)),
            tickers,
        )
        log.info("quotes_fetched", ticker_count=len(quotes), tickers=tickers)

        market_data = []
        for ticker in tickers:
            trade = last_trades.get(ticker)
            quote = quotes.get(ticker)
            if not trade or not quote:
                log.warning("market_data_missing", ticker=ticker, has_trade=bool(trade), has_quote=bool(quote))
                continue
            market_data.append(
                AlpacaMarketData(
                    ticker=ticker,
                    last_price=float(trade.price),
                    bid=float(quote.bid_price) if quote.bid_price else None,
                    ask=float(quote.ask_price) if quote.ask_price else None,
                    trade_at=trade.timestamp,
                    quote_at=quote.timestamp,
                )
            )

        return market_data
