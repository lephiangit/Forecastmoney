"""
main.py – FastAPI application entry point.
"""

import os
import sys
from contextlib import asynccontextmanager

# Ensure backend/ is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio
import json

from backend.config import settings
from backend.routers import market, research, forecast, admin, auth, notifications, chat
from backend.routers import backtest


# ── WebSocket Manager ─────────────────────────────────────────────────────────

class PriceWSManager:
    """Manages WebSocket connections for real-time price streaming."""

    def __init__(self):
        self.connections: list[WebSocket] = []
        self.subscriptions: dict[WebSocket, set[str]] = {}

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)
        self.subscriptions[ws] = set()

    def disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)
        self.subscriptions.pop(ws, None)

    def subscribe(self, ws: WebSocket, tickers: list[str]):
        if ws in self.subscriptions:
            self.subscriptions[ws] = set(t.upper() for t in tickers)

    async def broadcast(self, prices: dict):
        """Send price updates to subscribed clients."""
        dead = []
        for ws in self.connections:
            try:
                subs = self.subscriptions.get(ws, set())
                if subs:
                    filtered = {k: v for k, v in prices.items() if k in subs}
                else:
                    filtered = prices  # Send all if no specific subscription
                if filtered:
                    await ws.send_json({"type": "prices", "data": filtered})
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


ws_manager = PriceWSManager()


def _take_portfolio_snapshots():
    """Sync function: iterate all users in admin_config, save daily snapshot."""
    from backend.database import _get_client, save_portfolio_snapshot
    c = _get_client()
    if not c:
        return
    try:
        res = c.table("admin_config").select("user_id, current_balance, total_pnl").execute()
        for row in (res.data or []):
            save_portfolio_snapshot(
                user_id=row["user_id"],
                balance=row.get("current_balance", 0),
                total_pnl=row.get("total_pnl", 0),
            )
        print(f"📸 Portfolio snapshots saved for {len(res.data or [])} users.")
    except Exception as e:
        print(f"Snapshot error: {e}")

def _evaluate_model_predictions():
    """Evaluate pending model predictions from DB."""
    from backend.database import get_pending_evaluations, update_accuracy_evaluation
    from backend.models.forecaster import get_live_quote
    
    pending = get_pending_evaluations()
    if not pending:
        return
        
    print(f"📈 [Cron] Evaluating {len(pending)} pending model predictions...")
    for record in pending:
        ticker = record["ticker"]
        live = get_live_quote(ticker)
        if live and live["price"] > 0:
            actual = live["price"]
            predicted = record["predicted_price"]
            error_pct = abs(actual - predicted) / actual * 100
            update_accuracy_evaluation(record["id"], actual, error_pct)
            print(f"   ✓ Evaluated {ticker}: predicted={predicted:.2f}, actual={actual:.2f}, error={error_pct:.2f}%")


def _check_price_alerts():
    """Check all active price alerts and trigger notifications."""
    from backend.database import _get_client
    from backend.models.forecaster import get_live_quote
    
    c = _get_client()
    if not c:
        return
    
    try:
        # Get all non-triggered alerts
        res = c.table("price_alerts").select("*").eq("is_triggered", False).execute()
        alerts = res.data or []
        if not alerts:
            return
        
        # Cache live prices
        price_cache = {}
        triggered_count = 0
        
        for alert in alerts:
            ticker = alert["ticker"]
            if ticker not in price_cache:
                live = get_live_quote(ticker)
                if live:
                    price_cache[ticker] = live["price"]
                else:
                    continue
            
            current_price = price_cache[ticker]
            target_price = float(alert["target_price"])
            condition = alert["condition"]  # "above" or "below"
            
            triggered = False
            if condition == "above" and current_price >= target_price:
                triggered = True
            elif condition == "below" and current_price <= target_price:
                triggered = True
            
            if triggered:
                from datetime import datetime
                # Mark alert as triggered
                c.table("price_alerts").update({
                    "is_triggered": True,
                    "triggered_at": datetime.now().isoformat()
                }).eq("id", alert["id"]).execute()
                
                # Create notification for user
                direction = "vượt lên trên" if condition == "above" else "giảm xuống dưới"
                c.table("notifications").insert({
                    "user_id": alert["user_id"],
                    "title": f"🔔 Cảnh báo giá: {ticker}",
                    "message": f"{ticker} đã {direction} ${target_price:,.2f}! Giá hiện tại: ${current_price:,.2f}",
                    "is_read": False
                }).execute()
                
                triggered_count += 1
                print(f"  🔔 Alert triggered: {ticker} {condition} ${target_price} (now ${current_price:.2f})")
        
        if triggered_count > 0:
            print(f"🔔 [Cron] {triggered_count} price alerts triggered.")
    except Exception as e:
        print(f"Price alert check error: {e}")


def _fetch_live_prices_for_ws() -> dict:
    """Fetch prices for top tickers (for WebSocket broadcast)."""
    from backend.models.forecaster import get_live_quote
    from concurrent.futures import ThreadPoolExecutor
    
    top_tickers = [
        "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "ADA-USD", "XRP-USD",
        "DOGE-USD", "AVAX-USD", "AAPL", "NVDA", "TSLA"
    ]
    
    # Collect all subscribed tickers from WS clients
    all_subs = set()
    for subs in ws_manager.subscriptions.values():
        all_subs.update(subs)
    
    # Merge with defaults
    tickers_to_fetch = list(set(top_tickers) | all_subs)[:20]  # Cap at 20
    
    prices = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(get_live_quote, tickers_to_fetch))
    
    for i, q in enumerate(results):
        if q:
            prices[tickers_to_fetch[i]] = {
                "price": q["price"],
                "change": q.get("change", 0),
                "change_pct": q.get("change_pct", 0),
                "volume": q.get("volume", 0),
            }
    
    return prices


# ── Lifespan: load heavy models once at startup ───────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load TFT model and other resources at startup."""
    print("ForecastAI API starting up...")
    try:
        from backend.models.forecaster import _load_tft_model
        _load_tft_model()
    except Exception as e:
        print(f"⚠️ TFT preload skipped: {e}")
        
    async def auto_trader_loop():
        from backend.cron_auto_trader import run_auto_trade
        while True:
            try:
                await asyncio.to_thread(run_auto_trade)
            except Exception as e:
                print(f"Auto-trader loop error: {e}")
            await asyncio.sleep(60)

    async def portfolio_snapshot_loop():
        """Save daily portfolio snapshots for all users (runs every hour)."""
        while True:
            try:
                await asyncio.to_thread(_take_portfolio_snapshots)
            except Exception as e:
                print(f"Portfolio snapshot error: {e}")
            await asyncio.sleep(3600)

    async def model_evaluation_loop():
        """Evaluate model accuracy (runs every 1 hour)."""
        while True:
            try:
                await asyncio.to_thread(_evaluate_model_predictions)
            except Exception as e:
                print(f"Model evaluation error: {e}")
            await asyncio.sleep(3600)

    async def price_alert_loop():
        """Check price alerts every 30 seconds."""
        while True:
            try:
                await asyncio.to_thread(_check_price_alerts)
            except Exception as e:
                print(f"Price alert loop error: {e}")
            await asyncio.sleep(30)

    async def ws_price_broadcast_loop():
        """Broadcast live prices to WebSocket clients every 5 seconds."""
        while True:
            try:
                if ws_manager.connections:
                    prices = await asyncio.to_thread(_fetch_live_prices_for_ws)
                    if prices:
                        await ws_manager.broadcast(prices)
            except Exception as e:
                print(f"WS broadcast error: {e}")
            await asyncio.sleep(5)

    task1 = asyncio.create_task(auto_trader_loop())
    task2 = asyncio.create_task(portfolio_snapshot_loop())
    task3 = asyncio.create_task(model_evaluation_loop())
    task4 = asyncio.create_task(price_alert_loop())
    task5 = asyncio.create_task(ws_price_broadcast_loop())
    yield
    task1.cancel()
    task2.cancel()
    task3.cancel()
    task4.cancel()
    task5.cancel()
    print("ForecastAI API shutting down...")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="ForecastAI API",
    description="Market research + AI-powered crypto/stock forecasting",
    version="1.3.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────

_origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(market.router,    prefix="/market",    tags=["Market"])
app.include_router(research.router,  prefix="/research",  tags=["Research"])
app.include_router(forecast.router,  prefix="/forecast",  tags=["Forecast"])
app.include_router(admin.router,     prefix="/admin",     tags=["Admin"])
app.include_router(auth.router,      prefix="/auth",      tags=["Auth"])
app.include_router(backtest.router,  prefix="/backtest",  tags=["Backtest"])

app.include_router(notifications.router, tags=["Notifications"])
app.include_router(chat.router,      prefix="/chat",      tags=["Chat"])


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws/prices")
async def ws_prices(ws: WebSocket):
    """WebSocket endpoint for real-time price streaming."""
    await ws_manager.connect(ws)
    try:
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "subscribe" and isinstance(msg.get("tickers"), list):
                    ws_manager.subscribe(ws, msg["tickers"])
                    await ws.send_json({"type": "subscribed", "tickers": msg["tickers"]})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)


# ── Root ─────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
@app.head("/", tags=["Health"])
async def root():
    return {
        "name": "ForecastAI API",
        "version": "1.3.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
@app.head("/health", tags=["Health"])
async def health():
    from backend.database import is_available
    return {
        "status": "ok",
        "db_connected": is_available(),
        "gemini_configured": bool(settings.gemini_api_key),
        "ws_clients": len(ws_manager.connections),
    }


# ── Run (dev) ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
