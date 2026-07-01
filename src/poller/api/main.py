"""FastAPI service for watchlist (ticker) management."""

from __future__ import annotations

import os
from contextlib import contextmanager

import psycopg2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.db.db import add_ticker, check_db_health, delete_ticker, get_tickers, normalize_ticker

app = FastAPI(title="Watchlist API", version="1.0.0")


class TickerRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10, examples=["AAPL"])


class TickerResponse(BaseModel):
    ticker: str


class TickerListResponse(BaseModel):
    tickers: list[str]


class DeleteTickerResponse(BaseModel):
    ticker: str
    deleted: bool


def _db_url() -> str:
    url = os.getenv("POSTGRES_DB_1_URL")
    if not url:
        raise RuntimeError("POSTGRES_DB_1_URL must be set")
    return url


@contextmanager
def db_connection():
    conn = psycopg2.connect(_db_url())
    try:
        yield conn
    finally:
        conn.close()


@app.get("/health")
def health() -> dict[str, str]:
    with db_connection() as conn:
        if check_db_health(conn):
            return {"status": "ok"}
    raise HTTPException(status_code=503, detail="database unavailable")


@app.get("/tickers", response_model=TickerListResponse)
def list_tickers() -> TickerListResponse:
    with db_connection() as conn:
        return TickerListResponse(tickers=get_tickers(conn))


@app.post("/tickers", status_code=201, response_model=TickerResponse)
def create_ticker(body: TickerRequest) -> TickerResponse:
    try:
        symbol = normalize_ticker(body.ticker)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        with db_connection() as conn:
            add_ticker(conn, symbol)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="failed to add ticker") from exc
    return TickerResponse(ticker=symbol)


@app.delete("/tickers/{ticker}", response_model=DeleteTickerResponse)
def remove_ticker(ticker: str) -> DeleteTickerResponse:
    try:
        symbol = normalize_ticker(ticker)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        with db_connection() as conn:
            deleted = delete_ticker(conn, symbol)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="failed to delete ticker") from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="ticker not found")
    return DeleteTickerResponse(ticker=symbol, deleted=True)
