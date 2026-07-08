"""
main.py – FastAPI application entry point.
"""

import os
import sys
from contextlib import asynccontextmanager

# Ensure backend/ is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio

from backend.config import settings
from backend.routers import market, research, forecast, admin, auth, superadmin, notifications, chat


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
                # Run the synchronous function in a threadpool
                await asyncio.to_thread(run_auto_trade)
            except Exception as e:
                print(f"Auto-trader loop error: {e}")
            await asyncio.sleep(60) # Run every 60 seconds

    async def portfolio_snapshot_loop():
        """Save daily portfolio snapshots for all users (runs every hour)."""
        while True:
            try:
                await asyncio.to_thread(_take_portfolio_snapshots)
            except Exception as e:
                print(f"Portfolio snapshot error: {e}")
            await asyncio.sleep(3600)  # Run every 1 hour

    async def model_evaluation_loop():
        """Evaluate model accuracy by checking actual prices against predictions (runs every 1 hour)."""
        while True:
            try:
                await asyncio.to_thread(_evaluate_model_predictions)
            except Exception as e:
                print(f"Model evaluation error: {e}")
            await asyncio.sleep(3600)  # Run every 1 hour

    task1 = asyncio.create_task(auto_trader_loop())
    task2 = asyncio.create_task(portfolio_snapshot_loop())
    task3 = asyncio.create_task(model_evaluation_loop())
    yield
    task1.cancel()
    task2.cancel()
    task3.cancel()
    print("ForecastAI API shutting down...")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="ForecastAI API",
    description="Market research + AI-powered crypto/stock forecasting",
    version="1.2.1",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────

# Parse comma-separated origins from env var, e.g. "https://app.netlify.app,http://localhost:3000"
_origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(market.router,   prefix="/market",   tags=["Market"])
app.include_router(research.router, prefix="/research", tags=["Research"])
app.include_router(forecast.router, prefix="/forecast", tags=["Forecast"])
app.include_router(admin.router,    prefix="/admin",    tags=["Admin"])
app.include_router(auth.router,     prefix="/auth",     tags=["Auth"])
app.include_router(superadmin.router, prefix="/superadmin", tags=["Superadmin"])
app.include_router(notifications.router, tags=["Notifications"])
app.include_router(chat.router,     prefix="/chat",     tags=["Chat"])


# ── Root ─────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
@app.head("/", tags=["Health"])
async def root():
    return {
        "name": "ForecastAI API",
        "version": "1.2.1",
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
    }


# ── Run (dev) ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
