"""
forecaster.py – Stateless real-time ForecastEngine.
Philosophy:
  - NEVER save price data or forecast results to disk/DB
  - ALWAYS fetch fresh from yfinance on each request
  - Support ANY valid yfinance ticker symbol
  - Cache only the heavy TFT model weights in memory (not data)
"""

import os
import io
import pickle
import numpy as np
import pandas as pd
import yfinance as yf
from typing import Optional, Tuple, Dict, List
from datetime import datetime, timedelta
from functools import lru_cache

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models")
LOOK_BACK = 60

# In-memory model cache only (no data cache)
_model_cache: Dict = {}


# ── Live Data Fetch (always fresh, never saved) ───────────────────────────────

def fetch_ohlcv(ticker: str, period: str = "1y", interval: str = "1d") -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV data directly from yfinance.
    Returns clean DataFrame or None. NEVER writes to disk or DB.
    Supports any ticker symbol yfinance understands.
    """
    try:
        df = yf.download(
            ticker,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=True,
            threads=False,
        )
        if df is None or df.empty:
            return None

        # Flatten MultiIndex columns (yfinance ≥ 0.2.40 behavior)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)

        # Normalize timezone
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        df.index.name = "Date"

        # Basic cleaning
        df = df.interpolate("linear").ffill().bfill()
        df = df.dropna(subset=["Close"])

        return df
    except Exception as e:
        print(f"⚠️ yfinance error [{ticker}]: {e}")
        return None


def get_live_quote(ticker: str) -> Optional[Dict]:
    """
    Get the latest price quote for a ticker.
    Uses short period for speed. Returns None if unavailable.
    """
    def _scalar(val):
        """Safely convert a pandas scalar or 1-element Series to float."""
        if isinstance(val, pd.Series):
            val = val.iloc[0]
        return float(val)

    try:
        df = yf.download(
            ticker,
            period="5d",
            interval="1d",
            progress=False,
            auto_adjust=True,
            threads=False,
        )
        if df is None or df.empty or len(df) < 2:
            return None

        # Flatten MultiIndex columns (ticker symbol level) if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        latest = df.iloc[-1]
        prev   = df.iloc[-2]
        close      = _scalar(latest["Close"])
        prev_close = _scalar(prev["Close"])
        change = close - prev_close
        pct    = change / prev_close * 100 if prev_close else 0

        vol_raw = latest.get("Volume", 0)
        # Use scalar() to avoid ambiguous truth value on Series
        vol_scalar = _scalar(vol_raw) if vol_raw is not None else 0.0
        volume = vol_scalar if not (isinstance(vol_scalar, float) and __import__('math').isnan(vol_scalar)) else 0.0

        return {
            "ticker":     ticker,
            "price":      close,
            "open":       _scalar(latest.get("Open",   close)),
            "high":       _scalar(latest.get("High",   close)),
            "low":        _scalar(latest.get("Low",    close)),
            "volume":     volume,
            "prev_close": prev_close,
            "change":     change,
            "change_pct": pct,
            "timestamp":  datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"Quote error [{ticker}]: {e}")
        return None


def validate_ticker(ticker: str) -> bool:
    """
    Check if a ticker is valid by attempting a minimal fetch.
    Avoids polluting API with bad symbols.
    """
    try:
        df = yf.download(ticker, period="5d", progress=False, auto_adjust=True, threads=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        return df is not None and not df.empty and len(df) > 0
    except Exception:
        return False


def search_tickers(query: str) -> List[Dict]:
    """
    Search for ticker symbols matching a query using yfinance.
    Returns list of {symbol, name, exchange, type}.
    """
    try:
        results = []
        search = yf.Search(query, max_results=10, enable_fuzzy_query=True)
        for item in search.quotes:
            results.append({
                "symbol": item.get("symbol", ""),
                "name": item.get("longname") or item.get("shortname", ""),
                "exchange": item.get("exchange", ""),
                "type": item.get("quoteType", ""),
            })
        return results[:8]
    except Exception as e:
        print(f"⚠️ Search error: {e}")
        # Fallback: common crypto suggestions if search fails
        query_lower = query.lower()
        suggestions = [
            {"symbol": "BTC-USD", "name": "Bitcoin", "exchange": "CCC", "type": "CRYPTOCURRENCY"},
            {"symbol": "ETH-USD", "name": "Ethereum", "exchange": "CCC", "type": "CRYPTOCURRENCY"},
            {"symbol": "BNB-USD", "name": "BNB", "exchange": "CCC", "type": "CRYPTOCURRENCY"},
            {"symbol": "SOL-USD", "name": "Solana", "exchange": "CCC", "type": "CRYPTOCURRENCY"},
            {"symbol": "ADA-USD", "name": "Cardano", "exchange": "CCC", "type": "CRYPTOCURRENCY"},
            {"symbol": "XRP-USD", "name": "XRP", "exchange": "CCC", "type": "CRYPTOCURRENCY"},
            {"symbol": "DOGE-USD", "name": "Dogecoin", "exchange": "CCC", "type": "CRYPTOCURRENCY"},
            {"symbol": "AVAX-USD", "name": "Avalanche", "exchange": "CCC", "type": "CRYPTOCURRENCY"},
            {"symbol": "DOT-USD", "name": "Polkadot", "exchange": "CCC", "type": "CRYPTOCURRENCY"},
            {"symbol": "MATIC-USD", "name": "Polygon", "exchange": "CCC", "type": "CRYPTOCURRENCY"},
        ]
        return [s for s in suggestions if query_lower in s["name"].lower() or query_lower in s["symbol"].lower()]


# ── TFT Model (memory-cached, stateless inference) ────────────────────────────

def _load_tft_model():
    """Load TFT model into memory once (weights only, no data)."""
    if "tft" in _model_cache:
        return _model_cache["tft"]

    model_path = os.path.join(MODELS_DIR, "global_tft.keras")
    if not os.path.exists(model_path):
        return None

    try:
        from backend.models.tft_model import quantile_loss
        import tensorflow as tf
        model = tf.keras.models.load_model(
            model_path,
            custom_objects={"loss_fn": quantile_loss([0.1, 0.5, 0.9])}
        )
        _model_cache["tft"] = model
        print("✅ TFT loaded into memory.")
        return model
    except Exception as e:
        print(f"❌ TFT load error: {e}")
        return None


def _fit_scaler_on_the_fly(data: np.ndarray):
    """Fit a fresh MinMaxScaler on-the-fly — no pickle files needed."""
    from sklearn.preprocessing import MinMaxScaler
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaler.fit(data)
    return scaler


# ── TFT Forecast (stateless) ──────────────────────────────────────────────────

def run_tft_forecast(
    ticker: str,
    days: int = 7,
    df: Optional[pd.DataFrame] = None,
) -> Tuple[Optional[pd.Series], Optional[pd.Series], Optional[pd.Series]]:
    """
    Run TFT forecast for any ticker.
    Fits scalers fresh each time — no saved .pkl files needed.
    Returns (median, lower_q10, upper_q90) as pd.Series or (None, None, None).
    """
    from backend.models.feature_engineering import add_technical_indicators, get_feature_columns

    # Fetch data if not provided
    if df is None:
        df = fetch_ohlcv(ticker, period="2y")
    if df is None or len(df) < LOOK_BACK + 10:
        print(f"⚠️ Insufficient data for TFT [{ticker}]: {len(df) if df is not None else 0} rows")
        return None, None, None

    model = _load_tft_model()
    if model is None:
        print(f"⚠️ TFT model not found — run backend/train_tft.py first")
        return None, None, None

    try:
        df_feat = add_technical_indicators(df)
        feature_cols = get_feature_columns()
        available = [c for c in feature_cols if c in df_feat.columns]
        all_cols = ["Close"] + available

        df_clean = df_feat[all_cols].dropna()
        if len(df_clean) < LOOK_BACK:
            return None, None, None

        # Fit scaler fresh — no saved pkl
        scaler = _fit_scaler_on_the_fly(df_clean[all_cols].values)
        scaled = scaler.transform(df_clean[all_cols].values)
        current_input = scaled[-LOOK_BACK:].copy()
        n_features = current_input.shape[1]

        preds_q10, preds_q50, preds_q90 = [], [], []

        for _ in range(days):
            inp = current_input.reshape(1, LOOK_BACK, n_features)
            pred = model.predict(inp, verbose=0)
            # pred shape: (1, 3) → [q10, q50, q90]
            q10, q50, q90 = float(pred[0, 0]), float(pred[0, 1]), float(pred[0, 2])
            preds_q10.append(q10)
            preds_q50.append(q50)
            preds_q90.append(q90)
            # Roll: update Close column with q50 prediction
            new_row = current_input[-1:].copy()
            new_row[0, 0] = q50
            current_input = np.vstack([current_input[1:], new_row])

        def inverse_close(vals: np.ndarray) -> np.ndarray:
            dummy = np.zeros((len(vals), scaler.n_features_in_))
            dummy[:, 0] = vals
            return scaler.inverse_transform(dummy)[:, 0]

        prices_q50 = inverse_close(np.array(preds_q50))
        prices_q10 = inverse_close(np.array(preds_q10))
        prices_q90 = inverse_close(np.array(preds_q90))

        dates = pd.date_range(df.index[-1], periods=days + 1, inclusive="right")
        return (
            pd.Series(prices_q50, index=dates, name="tft_median"),
            pd.Series(prices_q10, index=dates, name="tft_lower"),
            pd.Series(prices_q90, index=dates, name="tft_upper"),
        )

    except Exception as e:
        print(f"❌ TFT inference error [{ticker}]: {e}")
        return None, None, None


# ── SentimentFusion (stateless) ───────────────────────────────────────────────

def run_sentiment_fusion_forecast(
    ticker: str,
    days: int = 7,
    research_analysis: Optional[Dict] = None,
    df: Optional[pd.DataFrame] = None,
) -> Tuple[Optional[pd.Series], Optional[pd.Series], Optional[pd.Series]]:
    """
    Adjust TFT forecast with sentiment signals.
    Everything computed in memory — nothing saved.
    """
    from backend.models.sentiment_fusion import SentimentFusionEngine, extract_market_signals

    tft_m, tft_l, tft_u = run_tft_forecast(ticker, days, df)
    if tft_m is None:
        return None, None, None

    if df is None:
        df = fetch_ohlcv(ticker, period="2y")
    if df is None:
        return tft_m, tft_l, tft_u

    try:
        from backend.models.feature_engineering import add_technical_indicators
        df_feat = add_technical_indicators(df)
    except Exception:
        df_feat = df

    signals = extract_market_signals(df_feat, research_analysis)
    engine = SentimentFusionEngine.get_instance(MODELS_DIR)
    adjusted = engine.predict(tft_m.values, signals, days)

    if tft_l is not None and tft_u is not None:
        band_half = (tft_u.values - tft_l.values) / 2
        adj_lower = adjusted - band_half
        adj_upper = adjusted + band_half
    else:
        adj_lower = adjusted * 0.97
        adj_upper = adjusted * 1.03

    dates = tft_m.index
    return (
        pd.Series(adjusted, index=dates, name="sf_median"),
        pd.Series(adj_lower, index=dates, name="sf_lower"),
        pd.Series(adj_upper, index=dates, name="sf_upper"),
    )


# ── Combined (full pipeline, stateless) ───────────────────────────────────────

def run_combined_forecast(
    ticker: str,
    days: int = 7,
    research_analysis: Optional[Dict] = None,
) -> Dict:
    """
    Full pipeline: fetch data → compute TFT + SentimentFusion → return.
    No data is saved anywhere. Supports any yfinance ticker.
    """
    # Single data fetch shared between both models
    df = fetch_ohlcv(ticker, period="2y")

    tft_m, tft_l, tft_u = run_tft_forecast(ticker, days, df)
    sf_m, sf_l, sf_u = run_sentiment_fusion_forecast(ticker, days, research_analysis, df)

    def to_list(s: Optional[pd.Series]) -> Optional[List]:
        if s is None:
            return None
        return [{"date": str(d.date()), "price": round(float(v), 6)} for d, v in s.items()]

    # Historical OHLCV for chart (last 90 days)
    historical = None
    if df is not None:
        hist = df.tail(90)
        try:
            from backend.models.feature_engineering import add_technical_indicators
            hist = add_technical_indicators(hist)
        except Exception:
            pass
        historical = []
        for idx, row in hist.iterrows():
            bar = {
                "date": str(idx.date()),
                "open": round(float(row.get("Open", 0)), 6),
                "high": round(float(row.get("High", 0)), 6),
                "low": round(float(row.get("Low", 0)), 6),
                "close": round(float(row.get("Close", 0)), 6),
                "volume": float(row.get("Volume", 0)) if pd.notna(row.get("Volume", 0)) else 0,
            }
            for col in ["RSI", "MACD", "BB_Upper", "BB_Lower", "MA20", "MA50"]:
                if col in row.index and pd.notna(row[col]):
                    bar[col.lower()] = round(float(row[col]), 4)
            historical.append(bar)

    current_price = float(df["Close"].iloc[-1]) if df is not None and len(df) > 0 else None

    return {
        "ticker": ticker,
        "days": days,
        "current_price": current_price,
        "tft": {
            "median": to_list(tft_m),
            "lower_q10": to_list(tft_l),
            "upper_q90": to_list(tft_u),
            "available": tft_m is not None,
        },
        "sentiment_fusion": {
            "median": to_list(sf_m),
            "lower_q10": to_list(sf_l),
            "upper_q90": to_list(sf_u),
            "available": sf_m is not None,
        },
        "historical": historical,
        "research_used": research_analysis is not None,
        "generated_at": datetime.now().isoformat(),
    }
