"""
routers/market.py – Real-time market data. No saving, any ticker supported.

NOTE: All endpoints are sync `def` so FastAPI runs them in a threadpool,
preventing blocking calls (yfinance I/O) from freezing the event loop.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

from backend.models.forecaster import fetch_ohlcv, get_live_quote, validate_ticker, search_tickers
from backend.config import settings, TICKER_LABELS

router = APIRouter()

# Default watchlist — shown on dashboard by default
DEFAULT_TICKERS = [
    "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "ADA-USD", "XRP-USD",
    "DOGE-USD", "AVAX-USD",
]


@router.get("/search")
def search(q: str = Query(..., min_length=1, description="Ticker or name to search")):
    """
    Search for any ticker symbol (crypto, stocks, ETFs, etc.)
    Returns yfinance search results.
    """
    results = search_tickers(q.strip())
    return {"query": q, "results": results, "count": len(results)}


@router.get("/validate/{ticker}")
def validate(ticker: str):
    """Check if a ticker is valid and fetchable."""
    ticker = ticker.upper()
    valid = validate_ticker(ticker)
    return {"ticker": ticker, "valid": valid}


@router.get("/overview")
def get_overview(tickers: Optional[str] = Query(
    default=None,
    description="Comma-separated ticker list. Defaults to common crypto watchlist."
)):
    """
    Fetch live prices for a list of tickers in parallel.
    Each call is fresh — no caching, no DB.
    """
    if tickers:
        ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
        ticker_list = ticker_list[:20]  # Max 20 to avoid rate limits
    else:
        ticker_list = DEFAULT_TICKERS

    # Parallel fetch using thread pool (sync context — no asyncio needed)
    with ThreadPoolExecutor(max_workers=8) as pool:
        quotes = list(pool.map(get_live_quote, ticker_list))

    results = []
    for i, q in enumerate(quotes):
        if q:
            ticker = ticker_list[i]
            q["name"] = TICKER_LABELS.get(ticker, q.get("name", ticker))
            q["type"] = "crypto" if ticker.endswith("-USD") else "vn_stock" if ticker.endswith(".VN") else "stock"
            results.append(q)

    return {
        "data": results,
        "count": len(results),
        "fetched_at": pd.Timestamp.now().isoformat(),
    }


@router.get("/ticker/{ticker}")
def get_ticker_detail(
    ticker: str,
    period: str = Query(default="1y", pattern="^(5d|1mo|3mo|6mo|1y|2y|5y)$"),
    indicators: bool = Query(default=True, description="Include technical indicators"),
):
    """
    Fetch full OHLCV + technical indicators for any ticker.
    Always real-time from yfinance — no DB lookup.
    """
    ticker = ticker.upper()

    df = fetch_ohlcv(ticker, period=period)
    if df is None or df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Cannot fetch data for '{ticker}'. Check ticker symbol."
        )

    if indicators:
        try:
            from backend.models.feature_engineering import add_technical_indicators
            df = add_technical_indicators(df)
        except Exception:
            pass

    # Get live quote for current price
    live = get_live_quote(ticker)

    # Build OHLCV response
    ohlcv = []
    for idx, row in df.iterrows():
        bar = {
            "date": str(idx.date()),
            "open": round(float(row.get("Open", 0)), 6),
            "high": round(float(row.get("High", 0)), 6),
            "low": round(float(row.get("Low", 0)), 6),
            "close": round(float(row.get("Close", 0)), 6),
            "volume": float(row.get("Volume", 0)) if pd.notna(row.get("Volume", 0)) else 0,
        }
        if indicators:
            for col in ["RSI", "MACD", "MACD_Signal", "BB_Upper", "BB_Lower", "MA20", "MA50", "ATR"]:
                if col in row.index and pd.notna(row[col]):
                    bar[col.lower()] = round(float(row[col]), 4)
        ohlcv.append(bar)

    return {
        "ticker": ticker,
        "name": TICKER_LABELS.get(ticker, ticker),
        "period": period,
        "live": live,
        "ohlcv": ohlcv,
        "total_bars": len(ohlcv),
        "fetched_at": pd.Timestamp.now().isoformat(),
    }


@router.get("/live/{ticker}")
def get_live(ticker: str):
    """Get single live quote for any ticker."""
    ticker = ticker.upper()
    quote = get_live_quote(ticker)
    if quote is None:
        raise HTTPException(404, f"Cannot fetch live price for '{ticker}'")
    quote["name"] = TICKER_LABELS.get(ticker, ticker)
    return quote
