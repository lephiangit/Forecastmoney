"""
database.py – Minimal Supabase client.
Only persists: research_reports, paper_trades, admin_config, model_accuracy.
Price data and forecasts are NEVER saved — always fetched/computed live.
"""

from __future__ import annotations
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

_client = None
_available: Optional[bool] = None


def _get_client():
    global _client, _available
    if _available is False:
        return None
    if _client is not None:
        return _client

    from backend.config import settings
    if not settings.supabase_url or not settings.supabase_key:
        _available = False
        return None

    try:
        from supabase import create_client
        _client = create_client(settings.supabase_url, settings.supabase_key)
        _available = True
        print("✅ Supabase connected.")
        return _client
    except Exception as e:
        print(f"❌ Supabase error: {e}")
        _available = False
        return None


def is_available() -> bool:
    return _get_client() is not None


# ── Research Reports ───────────────────────────────────────────────────────────

def save_research(ticker: str, analysis: Dict, source: str = "gemini") -> bool:
    c = _get_client()
    if c is None:
        return False
    try:
        c.table("research_reports").insert({
            "ticker": ticker,
            "sentiment": analysis.get("sentiment", "NEUTRAL"),
            "confidence": float(analysis.get("confidence", 0.5)),
            "sentiment_score": float(analysis.get("sentiment_score", 0.0)),
            "summary": analysis.get("summary", ""),
            "key_factors": json.dumps(analysis.get("key_factors", []), ensure_ascii=False),
            "recommendation": analysis.get("recommendation", ""),
            "risk_level": analysis.get("risk_level", "MEDIUM"),
            "source": source,
            "news_count": analysis.get("news_count", 0),
            "headlines": json.dumps(analysis.get("headlines", []), ensure_ascii=False),
        }).execute()
        return True
    except Exception as e:
        print(f"DB save_research error: {e}")
        return False


def get_recent_research(ticker: str, limit: int = 10) -> List[Dict]:
    c = _get_client()
    if c is None:
        return []
    try:
        res = (c.table("research_reports").select("*")
               .eq("ticker", ticker).order("created_at", desc=True)
               .limit(limit).execute())
        return res.data or []
    except Exception as e:
        print(f"DB get_recent_research error: {e}")
        return []


# ── User Auth ─────────────────────────────────────────────────────────────────

def create_user(username: str, password_hash: str) -> Optional[Dict]:
    c = _get_client()
    if c is None:
        raise Exception("Supabase client is None (not configured or unavailable)")
    try:
        res = c.table("users").insert({
            "username": username,
            "password_hash": password_hash,
            "role": "user",
            "status": "active"
        }).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"DB create_user error: {e}")
        raise e


def get_user_by_username(username: str) -> Optional[Dict]:
    c = _get_client()
    if c is None:
        raise Exception("Supabase client is None (not configured or unavailable)")
    try:
        res = c.table("users").select("*").eq("username", username).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"DB get_user_by_username error: {e}")
        raise e


# ── Paper Trading ──────────────────────────────────────────────────────────────

def save_trade(user_id: int, ticker: str, action: str, quantity: float, price: float,
               total_value: float, model_signal: str = "MANUAL") -> bool:
    c = _get_client()
    if c is None:
        return False
    try:
        c.table("paper_trades").insert({
            "user_id": user_id,
            "ticker": ticker,
            "action": action,
            "quantity": quantity,
            "price": price,
            "total_value": total_value,
            "model_signal": model_signal,
        }).execute()
        return True
    except Exception as e:
        print(f"DB save_trade error: {e}")
        return False


def get_trades(user_id: int, limit: int = 100) -> List[Dict]:
    c = _get_client()
    if c is None:
        return []
    try:
        res = (c.table("paper_trades").select("*")
               .eq("user_id", user_id)
               .order("trade_time", desc=True).limit(limit).execute())
        return res.data or []
    except Exception as e:
        print(f"DB get_trades error: {e}")
        return []


# ── Admin Config (User Portfolio) ──────────────────────────────────────────────

def get_admin_config(user_id: int) -> Dict[str, Any]:
    c = _get_client()
    default = {
        "user_id": user_id, "initial_balance": 0.0, "current_balance": 0.0,
        "total_pnl": 0.0, "win_trades": 0, "loss_trades": 0,
        "is_running": False, "started_at": None,
    }
    if c is None:
        return default
    try:
        res = c.table("admin_config").select("*").eq("user_id", user_id).limit(1).execute()
        if res.data:
            return res.data[0]
        # Create a portfolio config for the user if it doesn't exist
        insert_res = c.table("admin_config").insert(default).execute()
        return insert_res.data[0] if insert_res.data else default
    except Exception as e:
        print(f"DB get_admin_config error: {e}")
        return default


def update_admin_config(user_id: int, updates: Dict[str, Any]) -> bool:
    c = _get_client()
    if c is None:
        return False
    try:
        updates["updated_at"] = datetime.now().isoformat()
        c.table("admin_config").update(updates).eq("user_id", user_id).execute()
        return True
    except Exception as e:
        print(f"DB update_admin_config error: {e}")
        return False


# ── Forecast Cache ─────────────────────────────────────────────────────────────

def get_forecast_cache(ticker: str, days: int) -> Optional[Dict]:
    c = _get_client()
    if c is None:
        return None
    try:
        # Check cache from last 6 hours
        res = (c.table("forecast_cache").select("*")
               .eq("ticker", ticker).eq("days", days)
               .order("created_at", desc=True).limit(1).execute())
        if res.data:
            cache_record = res.data[0]
            # Verify if it's within 6 hours
            created_at = datetime.fromisoformat(cache_record["created_at"].replace("Z", "+00:00"))
            # We use naive dt comparison for simplicity if timezones are matched, or just let python handle it
            # But let's be safe: simple string comparison if datetime isn't easily comparable
            import time
            from datetime import timezone
            now = datetime.now(timezone.utc)
            diff = (now - created_at).total_seconds()
            if diff < 6 * 3600:  # 6 hours
                return cache_record["response_json"]
        return None
    except Exception as e:
        print(f"DB get_forecast_cache error: {e}")
        return None


def save_forecast_cache(ticker: str, days: int, response_json: Dict) -> bool:
    c = _get_client()
    if c is None:
        return False
    try:
        c.table("forecast_cache").insert({
            "ticker": ticker,
            "days": days,
            "response_json": response_json
        }).execute()
        return True
    except Exception as e:
        print(f"DB save_forecast_cache error: {e}")
        return False

def get_bot_config(user_id: int) -> Optional[Dict]:
    c = _get_client()
    if c is None: return None
    try:
        res = c.table("forecast_cache").select("response_json").eq("ticker", "USER_BOT_CONFIG").eq("days", user_id).order("created_at", desc=True).limit(1).execute()
        return res.data[0]["response_json"] if res.data else None
    except: return None

def save_bot_config(user_id: int, config: Dict) -> bool:
    c = _get_client()
    if c is None: return False
    try:
        c.table("forecast_cache").insert({"ticker": "USER_BOT_CONFIG", "days": user_id, "response_json": config}).execute()
        return True
    except: return False


# ── User Watchlists ────────────────────────────────────────────────────────────

def get_watchlist(user_id: int) -> List[str]:
    c = _get_client()
    if c is None:
        return []
    try:
        res = c.table("user_watchlists").select("ticker").eq("user_id", user_id).execute()
        return [row["ticker"] for row in res.data] if res.data else []
    except Exception as e:
        print(f"DB get_watchlist error: {e}")
        return []

def add_to_watchlist(user_id: int, ticker: str) -> bool:
    c = _get_client()
    if c is None:
        return False
    try:
        c.table("user_watchlists").insert({
            "user_id": user_id,
            "ticker": ticker.upper()
        }).execute()
        return True
    except Exception as e:
        # Might fail if already exists (UNIQUE constraint)
        print(f"DB add_to_watchlist error (or duplicate): {e}")
        return False

def remove_from_watchlist(user_id: int, ticker: str) -> bool:
    c = _get_client()
    if c is None:
        return False
    try:
        c.table("user_watchlists").delete().eq("user_id", user_id).eq("ticker", ticker.upper()).execute()
        return True
    except Exception as e:
        print(f"DB remove_from_watchlist error: {e}")
        return False


# ── Model Accuracy Tracking ───────────────────────────────────────────────────

def save_accuracy_prediction(ticker: str, model_name: str, forecast_date: str, predicted_price: float) -> bool:
    c = _get_client()
    if c is None:
        return False
    try:
        # Check if we already have a prediction for this exact ticker/date/model to avoid spam
        res = c.table("model_accuracy").select("id").eq("ticker", ticker.upper()).eq("model_name", model_name).eq("forecast_date", forecast_date).execute()
        if res.data:
            return True # Already exists, don't duplicate
            
        c.table("model_accuracy").insert({
            "ticker": ticker.upper(),
            "model_name": model_name,
            "forecast_date": forecast_date,
            "predicted_price": float(predicted_price)
        }).execute()
        return True
    except Exception as e:
        print(f"DB save_accuracy_prediction error: {e}")
        return False

def get_pending_evaluations() -> List[Dict]:
    c = _get_client()
    if c is None:
        return []
    try:
        today_str = datetime.now().date().isoformat()
        # Fetch rows where actual_price is null and forecast_date is today or in the past
        res = (c.table("model_accuracy").select("*")
               .is_("actual_price", "null")
               .lte("forecast_date", today_str)
               .execute())
        return res.data or []
    except Exception as e:
        print(f"DB get_pending_evaluations error: {e}")
        return []

def update_accuracy_evaluation(record_id: int, actual_price: float, error_pct: float) -> bool:
    c = _get_client()
    if c is None:
        return False
    try:
        c.table("model_accuracy").update({
            "actual_price": float(actual_price),
            "error_pct": float(error_pct)
        }).eq("id", record_id).execute()
        return True
    except Exception as e:
        print(f"DB update_accuracy_evaluation error: {e}")
        return False


# ── Portfolio Snapshots ────────────────────────────────────────────────────────

def save_portfolio_snapshot(user_id: int, balance: float, total_pnl: float) -> bool:
    """Save or update daily portfolio snapshot (upsert by user_id + snapshot_date)."""
    c = _get_client()
    if c is None:
        return False
    try:
        today = datetime.now().date().isoformat()
        # Try to update existing snapshot for today
        existing = (c.table("portfolio_snapshots")
                    .select("id")
                    .eq("user_id", user_id)
                    .eq("snapshot_date", today)
                    .execute())
        if existing.data:
            c.table("portfolio_snapshots").update({
                "balance": balance,
                "total_pnl": total_pnl,
            }).eq("id", existing.data[0]["id"]).execute()
        else:
            c.table("portfolio_snapshots").insert({
                "user_id": user_id,
                "balance": balance,
                "total_pnl": total_pnl,
                "snapshot_date": today,
            }).execute()
        return True
    except Exception as e:
        print(f"DB save_portfolio_snapshot error: {e}")
        return False


def get_portfolio_history(user_id: int, days: int = 90) -> List[Dict]:
    """Get portfolio balance history for the last N days."""
    c = _get_client()
    if c is None:
        return []
    try:
        res = (c.table("portfolio_snapshots")
               .select("snapshot_date, balance, total_pnl")
               .eq("user_id", user_id)
               .order("snapshot_date", desc=True)
               .limit(days)
               .execute())
        # Return in chronological order
        data = res.data or []
        data.reverse()
        return data
    except Exception as e:
        print(f"DB get_portfolio_history error: {e}")
        return []


# ── Research Archive ───────────────────────────────────────────────────────────

def get_all_research_history(
    limit: int = 50,
    offset: int = 0,
    ticker: Optional[str] = None,
    sentiment: Optional[str] = None,
) -> List[Dict]:
    """Get paginated research history with optional filters."""
    c = _get_client()
    if c is None:
        return []
    try:
        query = (c.table("research_reports")
                 .select("*")
                 .order("created_at", desc=True))
        if ticker:
            query = query.eq("ticker", ticker.upper())
        if sentiment:
            query = query.eq("sentiment", sentiment.upper())
        query = query.range(offset, offset + limit - 1)
        res = query.execute()
        return res.data or []
    except Exception as e:
        print(f"DB get_all_research_history error: {e}")
        return []
