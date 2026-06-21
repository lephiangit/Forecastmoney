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
        return None
    try:
        res = c.table("users").insert({
            "username": username,
            "password_hash": password_hash
        }).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"DB create_user error: {e}")
        return None


def get_user_by_username(username: str) -> Optional[Dict]:
    c = _get_client()
    if c is None:
        return None
    try:
        res = c.table("users").select("*").eq("username", username).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"DB get_user_by_username error: {e}")
        return None


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
        "user_id": user_id, "initial_balance": 10000.0, "current_balance": 10000.0,
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
