# Models for the alpaca data poller
from datetime import datetime
from pydantic import BaseModel

class AlpacaMarketData(BaseModel):
    ticker: str
    last_price: float
    bid: float | None = None
    ask: float | None = None
    trade_at: datetime
    quote_at: datetime | None = None

class ticker(BaseModel):
    ticker: str
    delete_flg: bool
    added_at: datetime
    updated_at: datetime

class tickerList(BaseModel):
    tickers: list[ticker]