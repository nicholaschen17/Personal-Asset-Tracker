from shared.alpaca_poller import AlpacaPoller
import time
import os

_shutdown = False

class Polling:
    def __init__(self, api_key_id: str, api_secret_key: str) -> None:
        self.poller = AlpacaPoller(api_key_id, api_secret_key)
        self.poll_interval_sec = 60.0 / 100

    def run_poll_loop(self, tickers: list[str]) -> None:
        while not _shutdown:
            data = self.poller.get_last_trade_price_and_quote_price(tickers)
            time.sleep(self.poll_interval_sec)
    
    def shutdown(self) -> None:
        global _shutdown
        _shutdown = True

if __name__ == "__main__":
    if not os.getenv("ALPACA_API_KEY_ID") or not os.getenv("ALPACA_API_SECRET_KEY"):
        raise ValueError("ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY must be set")
    poller = Polling(os.getenv("ALPACA_API_KEY_ID"), os.getenv("ALPACA_API_SECRET_KEY"))
    poller.run_poll_loop(["AAPL", "TSLA"])