"""
routers/admin.py – User portfolio and paper trading endpoints.
Scoped to the authenticated user.

NOTE: All endpoints are sync `def` so FastAPI runs them in a threadpool,
preventing blocking calls from freezing the event loop.
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import List
from datetime import datetime

from backend.config import settings
from backend.database import (
    get_admin_config, update_admin_config,
    save_trade, get_trades,
)
from backend.routers.auth import get_current_user

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class TradeRequest(BaseModel):
    ticker: str
    action: str  # "BUY" | "SELL"
    quantity: float


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/portfolio")
def get_portfolio(user=Depends(get_current_user)):
    """Get current user's paper trading state: balance, positions, P&L."""
    user_id = user["user_id"]
    config = get_admin_config(user_id)
    trades = get_trades(user_id, limit=50)

    # Build positions from trades
    positions = {}
    for t in reversed(trades):
        ticker = t["ticker"]
        if ticker not in positions:
            positions[ticker] = {"qty": 0.0, "avg_cost": 0.0, "total_cost": 0.0}

        if t["action"] == "BUY":
            old_cost = positions[ticker]["avg_cost"] * positions[ticker]["qty"]
            positions[ticker]["qty"] += t["quantity"]
            positions[ticker]["total_cost"] = old_cost + t["total_value"]
            if positions[ticker]["qty"] > 0:
                positions[ticker]["avg_cost"] = positions[ticker]["total_cost"] / positions[ticker]["qty"]
        elif t["action"] == "SELL":
            positions[ticker]["qty"] = max(0, positions[ticker]["qty"] - t["quantity"])

    # Remove zeroed positions
    positions = {k: v for k, v in positions.items() if v["qty"] > 0}

    total_trades = len(trades)
    win_trades = config.get("win_trades", 0)
    loss_trades = config.get("loss_trades", 0)
    win_rate = win_trades / total_trades * 100 if total_trades > 0 else 0

    return {
        "initial_balance": config.get("initial_balance", 10000.0),
        "current_balance": config.get("current_balance", 10000.0),
        "total_pnl": config.get("total_pnl", 0.0),
        "win_rate": round(win_rate, 1),
        "win_trades": win_trades,
        "loss_trades": loss_trades,
        "is_running": config.get("is_running", False),
        "positions": positions,
        "recent_trades": trades[:20],
    }


@router.post("/trade")
def execute_trade(req: TradeRequest, user=Depends(get_current_user)):
    """Execute a manual paper trade for the current user."""
    from backend.models.forecaster import get_live_quote

    user_id = user["user_id"]
    ticker = req.ticker.upper()
    if req.action not in ("BUY", "SELL"):
        raise HTTPException(400, "action must be 'BUY' or 'SELL'")
    if req.quantity <= 0:
        raise HTTPException(400, "quantity must be positive")

    live = get_live_quote(ticker)
    if not live:
        raise HTTPException(503, f"Cannot get price for {ticker}")

    price = live["price"]
    total = price * req.quantity
    config = get_admin_config(user_id)
    current_balance = config.get("current_balance", 10000.0)

    if req.action == "BUY" and total > current_balance:
        raise HTTPException(400, f"Insufficient balance: need {total:.2f}, have {current_balance:.2f}")

    new_balance = current_balance - total if req.action == "BUY" else current_balance + total
    update_admin_config(user_id, {"current_balance": new_balance})

    save_trade(
        user_id=user_id,
        ticker=ticker,
        action=req.action,
        quantity=req.quantity,
        price=price,
        total_value=total,
        model_signal="MANUAL",
    )

    return {
        "success": True,
        "ticker": ticker,
        "action": req.action,
        "quantity": req.quantity,
        "price": price,
        "total": total,
        "new_balance": new_balance,
    }


@router.post("/trading/start")
def start_auto_trading(
    initial_balance: float = 10000.0,
    user=Depends(get_current_user),
):
    """Start auto-trading for the current user."""
    user_id = user["user_id"]
    update_admin_config(user_id, {
        "initial_balance": initial_balance,
        "current_balance": initial_balance,
        "total_pnl": 0.0,
        "win_trades": 0,
        "loss_trades": 0,
        "is_running": True,
        "started_at": datetime.now().isoformat(),
    })
    return {"message": f"Auto-trading started with ${initial_balance:,.2f}", "is_running": True}


@router.post("/trading/stop")
def stop_auto_trading(user=Depends(get_current_user)):
    """Stop auto-trading for the current user."""
    user_id = user["user_id"]
    update_admin_config(user_id, {"is_running": False})
    config = get_admin_config(user_id)
    return {
        "message": "Auto-trading stopped",
        "is_running": False,
        "final_balance": config.get("current_balance"),
        "total_pnl": config.get("total_pnl"),
    }


@router.get("/pnl")
def get_pnl_report(user=Depends(get_current_user)):
    """Get user-specific P&L report."""
    user_id = user["user_id"]
    config = get_admin_config(user_id)
    trades = get_trades(user_id, limit=200)

    initial = config.get("initial_balance", 10000.0)
    current = config.get("current_balance", 10000.0)
    total_pnl = current - initial
    pnl_pct = total_pnl / initial * 100 if initial > 0 else 0

    return {
        "initial_balance": initial,
        "current_balance": current,
        "total_pnl": total_pnl,
        "pnl_pct": round(pnl_pct, 2),
        "win_trades": config.get("win_trades", 0),
        "loss_trades": config.get("loss_trades", 0),
        "is_running": config.get("is_running", False),
        "started_at": config.get("started_at"),
        "trade_count": len(trades),
        "trades": trades[:50],
    }

@router.get("/portfolio/chart")
def get_portfolio_chart(user=Depends(get_current_user)):
    """Get balance history for chart plotting."""
    user_id = user["user_id"]
    config = get_admin_config(user_id)
    # Fetch trades in ascending order (oldest first)
    from backend.database import _get_client
    c = _get_client()
    if c is None:
        return []
        
    res = c.table("paper_trades").select("*").eq("user_id", user_id).order("trade_time", desc=False).execute()
    trades = res.data or []
    
    initial = config.get("initial_balance", 10000.0)
    current_balance = initial
    
    history = []
    # Add initial point
    start_date = config.get("started_at") or (trades[0]["trade_time"] if trades else datetime.now().isoformat())
    history.append({
        "time": start_date,
        "balance": initial,
        "pnl": 0
    })
    
    for t in trades:
        # Simulate balance change. Note: BUY decreases cash, SELL increases cash
        val = float(t.get("total_value", 0))
        if t["action"] == "BUY":
            current_balance -= val
        else:
            current_balance += val
            
        history.append({
            "time": t["trade_time"],
            "balance": round(current_balance, 2),
            "pnl": round(current_balance - initial, 2)
        })
        
    return history


@router.get("/system/accuracy")
def get_system_accuracy(user=Depends(get_current_user)):
    """Get recent model accuracy evaluations for Admin Dashboard."""
    from backend.database import _get_client
    c = _get_client()
    if c is None:
        return {"success": False, "records": []}
    try:
        res = (c.table("model_accuracy").select("*")
               .not_.is_("actual_price", "null")
               .order("forecast_date", desc=True)
               .limit(10).execute())
        return {"success": True, "records": res.data or []}
    except Exception as e:
        print(f"Error fetching system accuracy: {e}")
        return {"success": False, "records": []}

@router.get("/trigger-learner")
def trigger_learner(background_tasks: BackgroundTasks, secret: str = None):
    """Hidden endpoint to trigger auto-learning via external cron services (e.g. cron-job.org)."""
    from backend.config import settings
    # We use admin_secret_key as the password for this cron job
    if secret != settings.admin_secret_key:
        raise HTTPException(status_code=401, detail="Unauthorized cron trigger")
        
    def run_learning_task():
        import backend.cron_accuracy_learner as learner
        try:
            tickers = learner.run_evaluations()
            learner.online_learning(tickers)
        except Exception as e:
            print(f"Cron Learner Error: {e}")
            
    # Run in background so the external cron ping doesn't timeout
    background_tasks.add_task(run_learning_task)
    return {"success": True, "message": "Accuracy evaluation and online learning started in background."}

@router.get("/trigger-autotrade")
def trigger_autotrade(background_tasks: BackgroundTasks, secret: str = None):
    """Hidden endpoint to trigger auto-trading logic via external cron services."""
    from backend.config import settings
    if secret != settings.admin_secret_key:
        raise HTTPException(status_code=401, detail="Unauthorized cron trigger")
        
    def run_autotrade_task():
        import backend.cron_auto_trader as trader
        try:
            trader.run_auto_trade()
        except Exception as e:
            print(f"Cron AutoTrader Error: {e}")
            
    background_tasks.add_task(run_autotrade_task)
    return {"success": True, "message": "Auto-trading job started in background."}

@router.get("/trigger-research")
def trigger_research(background_tasks: BackgroundTasks, secret: str = None):
    """Hidden endpoint to trigger news fetching & NLP research via external cron services."""
    from backend.config import settings
    if secret != settings.admin_secret_key:
        raise HTTPException(status_code=401, detail="Unauthorized cron trigger")
        
    def run_research_task():
        import backend.cron_researcher as researcher
        try:
            researcher.run_research()
        except Exception as e:
            print(f"Cron Researcher Error: {e}")
            
    background_tasks.add_task(run_research_task)
    return {"success": True, "message": "Research job started in background."}

@router.get("/watchlist")
def get_watchlist(user=Depends(get_current_user)):
    """Get current user's watchlist."""
    from backend.database import _get_client
    c = _get_client()
    if c is None:
        return []
    res = c.table("user_watchlists").select("ticker").eq("user_id", user["user_id"]).execute()
    return [r["ticker"] for r in (res.data or [])]

@router.post("/watchlist")
def add_to_watchlist(ticker: str, user=Depends(get_current_user)):
    """Add a ticker to the watchlist."""
    from backend.database import _get_client
    c = _get_client()
    if c is None:
        raise HTTPException(503, "Database unavailable")
    try:
        c.table("user_watchlists").insert({
            "user_id": user["user_id"],
            "ticker": ticker.upper()
        }).execute()
        return {"success": True}
    except Exception as e:
        if "duplicate key" in str(e).lower():
            return {"success": True} # Already exists
        raise HTTPException(500, str(e))

@router.delete("/watchlist/{ticker}")
def remove_from_watchlist(ticker: str, user=Depends(get_current_user)):
    """Remove a ticker from the watchlist."""
    from backend.database import _get_client
    c = _get_client()
    if c is None:
        raise HTTPException(503, "Database unavailable")
    c.table("user_watchlists").delete().eq("user_id", user["user_id"]).eq("ticker", ticker.upper()).execute()
    return {"success": True}

@router.get("/leaderboard")
def get_leaderboard():
    """Get top 10 traders by PnL."""
    from backend.database import _get_client
    c = _get_client()
    if c is None:
        return []
    
    # Query admin_config and join with users to get username
    res = c.table("admin_config").select("total_pnl, win_trades, loss_trades, users!inner(username)").order("total_pnl", desc=True).limit(10).execute()
    
    leaderboard = []
    for row in (res.data or []):
        raw_username = row.get("users", {}).get("username", "unknown")
        # Mask username
        if len(raw_username) > 4:
            masked = raw_username[:4] + "***"
        else:
            masked = raw_username + "***"
            
        leaderboard.append({
            "id": row.get("id", str(len(leaderboard))),
            "username": masked,
            "total_pnl": row.get("total_pnl", 0),
            "win_trades": row.get("win_trades", 0),
            "loss_trades": row.get("loss_trades", 0)
        })
    
    return leaderboard
