"""
routers/research.py – Real-time research agent.
Only sentiment analysis history is saved to DB (small rows, high value).
Raw news headlines are never stored.
Supports any ticker.
"""

from fastapi import APIRouter, HTTPException, Query
import time

from backend.agents.research_agent import analyze_market, fetch_news
from backend.database import get_recent_research
from backend.models.forecaster import get_live_quote

router = APIRouter()

# In-memory cache: 30min TTL per ticker
_cache: dict = {}
_CACHE_TTL = 1800


def _is_fresh(ticker: str) -> bool:
    entry = _cache.get(ticker)
    if not entry:
        return False
    return (time.time() - entry["ts"]) < _CACHE_TTL


@router.get("/{ticker}")
def get_research(
    ticker: str,
    force: bool = Query(default=False, description="Force refresh, bypass 30min cache"),
):
    """
    Real-time market research for any ticker.
    - Fetches fresh news each call (no news stored in DB)
    - Sentiment analysis cached 30min in memory
    - Only summary + sentiment score saved to DB for trend tracking
    """
    ticker = ticker.upper()

    if not force and _is_fresh(ticker):
        return _cache[ticker]["data"]

    live = get_live_quote(ticker)
    price_info = f"Giá: {live['price']:,.4f}" if live else ""

    analysis = analyze_market(ticker, price_info)

    _cache[ticker] = {"data": analysis, "ts": time.time()}
    return analysis


@router.get("/news/{ticker}")
def get_news_only(ticker: str):
    """
    Fetch raw news headlines in real-time. Nothing saved to DB.
    """
    ticker = ticker.upper()
    headlines = fetch_news(ticker, max_items=15)
    return {
        "ticker": ticker,
        "headlines": headlines,
        "count": len(headlines),
        "fetched_at": __import__("datetime").datetime.now().isoformat(),
    }


@router.get("/history/{ticker}")
def get_sentiment_history(
    ticker: str,
    limit: int = Query(default=20, ge=1, le=100),
):
    """
    Historical sentiment trend from DB.
    Only sentiment scores stored — no raw news or article text.
    """
    ticker = ticker.upper()
    records = get_recent_research(ticker, limit=limit)
    return {
        "ticker": ticker,
        "records": records,
        "count": len(records),
        "note": "Lịch sử sentiment AI — tin tức không được lưu trữ"
    }
