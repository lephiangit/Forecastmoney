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


def create_token(user_id: int, username: str, role: str = "user") -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
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
    
    # 1. Try custom token
    payload = verify_token(token)
    if payload:
        return payload
        
    # 2. Try Supabase token (Google Auth)
    try:
        from backend.database import _get_client, get_user_by_username, create_user
        supabase = _get_client()
        if not supabase:
            raise Exception("Supabase client not available")
            
        # Verify token by fetching user
        user_response = supabase.auth.get_user(token)
        if user_response and user_response.user:
            email = user_response.user.email
            if not email:
                email = "google_user_" + user_response.user.id[:8]
                
            # Check if user exists in our DB
            existing_user = get_user_by_username(email)
            if not existing_user:
                # Auto create
                # We use a dummy hash since they login via Google
                dummy_hash = "GOOGLE_OAUTH_USER"
                create_user(email, dummy_hash)
                existing_user = get_user_by_username(email)
                
            if existing_user:
                return {
                    "user_id": existing_user["id"],
                    "username": existing_user["username"],
                    "role": existing_user.get("role", "user"),
                    "exp": time.time() + 3600
                }
    except Exception as e:
        print(f"Supabase auth check error: {e}")
        
    raise HTTPException(status_code=401, detail="Invalid or expired token")


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
    token = create_token(user["id"], user["username"], user.get("role", "user"))
    return {
        "success": True,
        "token": token,
        "username": user["username"],
        "role": user.get("role", "user"),
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
        
    token = create_token(user["id"], user["username"], user.get("role", "user"))
    return {
        "success": True,
        "token": token,
        "username": user["username"],
        "role": user.get("role", "user"),
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
