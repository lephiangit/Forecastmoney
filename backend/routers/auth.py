"""
routers/auth.py – Simple custom JWT-like token auth router using standard libraries.
"""

import time
import hmac
import hashlib
import base64
import json
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional

from backend.config import settings
from backend.database import get_user_by_username, create_user

router = APIRouter()

SECRET_KEY = settings.admin_secret_key.encode()

class AuthRequest(BaseModel):
    username: str
    password: str


def hash_password(password: str) -> str:
    # PBKDF2 HMAC SHA-256 — salt derived from SECRET_KEY for per-deployment uniqueness
    salt = hashlib.sha256(SECRET_KEY + b"_password_salt").digest()
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    return hashed.hex()


def create_token(user_id: int, username: str) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": time.time() + 86400 * 7  # 7 days
    }
    payload_json = json.dumps(payload)
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode().rstrip("=")
    signature = hmac.new(SECRET_KEY, payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def verify_token(token: str) -> Optional[dict]:
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, signature = parts
        expected_sig = hmac.new(SECRET_KEY, payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None
        
        # Add padding back if necessary
        rem = len(payload_b64) % 4
        if rem > 0:
            payload_b64 += "=" * (4 - rem)
            
        payload_data = base64.urlsafe_b64decode(payload_b64.encode()).decode()
        payload = json.loads(payload_data)
        if payload["exp"] < time.time():
            return None
        return payload
    except Exception as e:
        print(f"Token verification error: {e}")
        return None


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication token required")
    token = authorization.split(" ")[1]
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/register")
async def register(req: AuthRequest):
    username = req.username.strip()
    if len(username) < 3 or len(req.password) < 4:
        raise HTTPException(400, "Username (>=3 chars) or password (>=4 chars) too short")
        
    existing = get_user_by_username(username)
    if existing:
        raise HTTPException(400, "Username already registered")
        
    hashed = hash_password(req.password)
    user = create_user(username, hashed)
    if not user:
        raise HTTPException(500, "Could not create user in database")
        
    # Generate token immediately
    token = create_token(user["id"], user["username"])
    return {
        "success": True,
        "token": token,
        "username": user["username"],
        "message": "User registered successfully"
    }


@router.post("/login")
async def login(req: AuthRequest):
    user = get_user_by_username(req.username.strip())
    if not user:
        raise HTTPException(400, "Invalid username or password")
        
    hashed = hash_password(req.password)
    if user["password_hash"] != hashed:
        raise HTTPException(400, "Invalid username or password")
        
    token = create_token(user["id"], user["username"])
    return {
        "success": True,
        "token": token,
        "username": user["username"],
        "message": "Logged in successfully"
    }


@router.get("/watchlist")
async def get_user_watchlist(current_user: dict = Depends(get_current_user)):
    from backend.database import get_watchlist
    tickers = get_watchlist(current_user["user_id"])
    return {"success": True, "watchlist": tickers}


@router.post("/watchlist")
async def add_user_watchlist(req: dict, current_user: dict = Depends(get_current_user)):
    ticker = req.get("ticker")
    if not ticker:
        raise HTTPException(400, "Ticker is required")
    from backend.database import add_to_watchlist
    success = add_to_watchlist(current_user["user_id"], ticker)
    if not success:
        raise HTTPException(500, "Could not add to watchlist (maybe already exists)")
    return {"success": True, "ticker": ticker.upper()}


@router.delete("/watchlist/{ticker}")
async def remove_user_watchlist(ticker: str, current_user: dict = Depends(get_current_user)):
    from backend.database import remove_from_watchlist
    success = remove_from_watchlist(current_user["user_id"], ticker)
    if not success:
        raise HTTPException(500, "Could not remove from watchlist")
    return {"success": True, "ticker": ticker.upper()}
