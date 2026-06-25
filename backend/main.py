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

from backend.config import settings
from backend.routers import market, research, forecast, admin, auth, superadmin


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
    yield
    print("ForecastAI API shutting down...")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="ForecastAI API",
    description="Market research + AI-powered crypto/stock forecasting",
    version="2.0.0",
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


# ── Root ─────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    return {
        "name": "ForecastAI API",
        "version": "2.0.0",
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
