"""
routers/forecast.py – Stateless real-time forecasting. No saving to DB.
Supports any valid ticker symbol.

NOTE: All endpoints are sync `def` so FastAPI runs them in a threadpool,
preventing blocking calls (yfinance, TFT inference, Gemini) from freezing the event loop.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from backend.models.forecaster import run_combined_forecast, run_tft_forecast, run_sentiment_fusion_forecast, fetch_ohlcv, get_live_quote

router = APIRouter()


@router.get("/combined/{ticker}")
def combined_forecast(
    ticker: str,
    days: int = Query(default=7, ge=1, le=60),
):
    """
    Full real-time pipeline: fetch data → TFT → SentimentFusion → return.
    No data is stored. Supports any yfinance ticker.
    Includes last 90 days historical OHLCV for chart display.
    """
    ticker = ticker.upper()

    # Run research first for context
    from backend.agents.research_agent import analyze_market
    live = get_live_quote(ticker)
    price_info = f"Giá: {live['price']:,.4f}" if live else ""

    research = analyze_market(ticker, price_info)

    result = run_combined_forecast(ticker, days, research)

    if result["current_price"] is None:
        raise HTTPException(404, f"Cannot fetch data for '{ticker}'")

    # Add research context to response
    result["research"] = {
        "sentiment": research.get("sentiment"),
        "confidence": research.get("confidence"),
        "sentiment_score": research.get("sentiment_score"),
        "summary": research.get("summary"),
        "recommendation": research.get("recommendation"),
        "risk_level": research.get("risk_level"),
        "key_factors": research.get("key_factors", []),
        "headlines": research.get("headlines", [])[:5],
        "source": research.get("source"),
        "analyzed_at": research.get("analyzed_at"),
    }
    result["live"] = live

    return result


@router.get("/tft/{ticker}")
def tft_only_forecast(
    ticker: str,
    days: int = Query(default=7, ge=1, le=60),
):
    """TFT forecast only — fastest endpoint, no research agent."""
    ticker = ticker.upper()

    df = fetch_ohlcv(ticker, period="2y")
    if df is None:
        raise HTTPException(404, f"Cannot fetch data for '{ticker}'")

    median, lower, upper = run_tft_forecast(ticker, days, df)

    if median is None:
        raise HTTPException(503, "TFT model not available. Run backend/train_tft.py first.")

    def to_list(s):
        if s is None: return None
        return [{"date": str(d.date()), "price": round(float(v), 6)} for d, v in s.items()]

    live = get_live_quote(ticker)
    return {
        "ticker": ticker,
        "model": "TFT",
        "days": days,
        "current_price": live["price"] if live else float(df["Close"].iloc[-1]),
        "forecast": {
            "median": to_list(median),
            "lower_q10": to_list(lower),
            "upper_q90": to_list(upper),
        },
        "generated_at": __import__("datetime").datetime.now().isoformat(),
    }


@router.get("/accuracy/{ticker}")
def forecast_accuracy(
    ticker: str,
    model: str = Query(default="tft", pattern="^(tft|sentiment_fusion)$"),
):
    """Get historical accuracy records from DB (only stored metric)."""
    from backend.database import _get_client
    ticker = ticker.upper()
    c = _get_client()
    if c is None:
        return {"ticker": ticker, "model": model, "records": [], "db_available": False}
    try:
        res = (c.table("model_accuracy").select("*")
               .eq("ticker", ticker).eq("model_name", model)
               .order("created_at", desc=True).limit(30).execute())
        return {"ticker": ticker, "model": model, "records": res.data or []}
    except Exception as e:
        return {"ticker": ticker, "model": model, "records": [], "error": str(e)}
