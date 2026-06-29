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
from backend.routers import market, research, forecast, admin, auth, superadmin, notifications

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

    task1 = asyncio.create_task(auto_trader_loop())
    yield
    task1.cancel()
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


# ── Root ─────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    return {
        "name": "ForecastAI API",
        "version": "1.2.1",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
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
