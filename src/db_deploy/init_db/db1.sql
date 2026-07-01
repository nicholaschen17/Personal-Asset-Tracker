DROP SCHEMA IF EXISTS poller CASCADE;
CREATE SCHEMA IF NOT EXISTS poller;


-- Required tables for the poller to run
CREATE TABLE IF NOT EXISTS poller.tickers (
    id SERIAL PRIMARY KEY,
    ticker TEXT NOT NULL,
    delete_flg BOOLEAN NOT NULL DEFAULT FALSE,
    added_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ticker)
);

CREATE TABLE IF NOT EXISTS poller.market_data (
    id SERIAL PRIMARY KEY,
    ticker TEXT NOT NULL,
    last_price DECIMAL(10, 2) NOT NULL,
    bid DECIMAL(10, 2) NOT NULL DEFAULT 0,
    ask DECIMAL(10, 2) NOT NULL DEFAULT 0,
    trade_at TIMESTAMP NOT NULL,
    quote_at TIMESTAMP NOT NULL,
    UNIQUE (ticker, trade_at),
    UNIQUE (ticker, quote_at)
);