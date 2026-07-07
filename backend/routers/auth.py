"""
routers/auth.py – Simple custom JWT-like token auth router using standard libraries.
"""

import time
import hmac
import hashlib
import base64
import json
from fastapi import APIRouter, HTTPException, Depends, Header, BackgroundTasks
from pydantic import BaseModel
from typing import Optional

from backend.config import settings
from backend.database import get_user_by_username, create_user

router = APIRouter()

SECRET_KEY = settings.admin_secret_key.encode()

class AuthRequest(BaseModel):
    username: str
    password: str

class GoogleAuthRequest(BaseModel):
    access_token: str


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
    """Verify custom JWT only. All login methods (email/password, Google) produce custom JWTs."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication token required")
    token = authorization.split(" ")[1]
    
    payload = verify_token(token)
    if payload:
        # Fire and forget update last_active
        try:
            from backend.database import _get_client
            c = _get_client()
            if c:
                c.table("users").update({"last_active": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}).eq("id", payload["user_id"]).execute()
        except:
            pass
        return payload
        
    raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_current_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/register")
async def register(req: AuthRequest):
    username = req.username.strip()
    if len(username) < 3 or len(req.password) < 4:
        raise HTTPException(400, "Username (>=3 chars) or password (>=4 chars) too short")
        
    try:
        existing = get_user_by_username(username)
    except Exception as e:
        raise HTTPException(500, f"DB error checking user: {str(e)}")
        
    if existing:
        raise HTTPException(400, "Username already registered")
        
    hashed = hash_password(req.password)
    try:
        user = create_user(username, hashed)
    except Exception as e:
        raise HTTPException(500, f"DB error creating user: {str(e)}")
        
    if not user:
        raise HTTPException(500, "Could not create user in database")
        
    # Generate token immediately
    token = create_token(user["id"], user["username"], user.get("role", "user"))
    return {
        "success": True,
        "token": token,
        "user_id": user["id"],
        "username": user["username"],
        "role": user.get("role", "user"),
        "message": "User registered successfully"
    }


@router.post("/login")
async def login(req: AuthRequest):
    try:
        user = get_user_by_username(req.username.strip())
    except Exception as e:
        raise HTTPException(500, f"DB error fetching user: {str(e)}")
        
    if not user:
        raise HTTPException(400, "Invalid username or password")
        
    hashed = hash_password(req.password)
    if user["password_hash"] != hashed:
        raise HTTPException(400, "Invalid username or password")
        
    token = create_token(user["id"], user["username"], user.get("role", "user"))
    return {
        "success": True,
        "token": token,
        "user_id": user["id"],
        "username": user["username"],
        "role": user.get("role", "user"),
        "message": "Logged in successfully"
    }


@router.post("/google")
async def google_auth(req: GoogleAuthRequest):
    """Exchange a Supabase access_token (from Google OAuth) for a custom JWT."""
    try:
        from backend.database import _get_client, get_user_by_username, create_user
        supabase = _get_client()
        if not supabase:
            raise HTTPException(503, "Database unavailable")

        # Verify the Supabase token once
        user_response = supabase.auth.get_user(req.access_token)
        if not user_response or not user_response.user:
            raise HTTPException(401, "Invalid Google token")

        email = user_response.user.email
        if not email:
            email = "google_user_" + user_response.user.id[:8]

        # Find or create user in local DB
        existing_user = get_user_by_username(email)
        if not existing_user:
            dummy_hash = "GOOGLE_OAUTH_USER"
            create_user(email, dummy_hash)
            existing_user = get_user_by_username(email)

        if not existing_user:
            raise HTTPException(500, "Could not create user")

        # Issue custom JWT — same as email/password login
        token = create_token(existing_user["id"], existing_user["username"], existing_user.get("role", "user"))
        return {
            "success": True,
            "token": token,
            "user_id": existing_user["id"],
            "username": existing_user["username"],
            "role": existing_user.get("role", "user"),
            "message": "Google login successful"
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Google auth error: {e}")
        raise HTTPException(401, f"Google authentication failed: {str(e)}")


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

@router.put("/change-password")
async def change_password(req: ChangePasswordRequest, current_user: dict = Depends(get_current_user)):
    """Change password for the currently authenticated user."""
    if len(req.new_password) < 4:
        raise HTTPException(400, "New password must be at least 4 characters")

    user = get_user_by_username(current_user["username"])
    if not user:
        raise HTTPException(404, "User not found")

    old_hashed = hash_password(req.old_password)
    if user["password_hash"] != old_hashed:
        raise HTTPException(400, "Current password is incorrect")

    new_hashed = hash_password(req.new_password)
    from backend.database import _get_client
    c = _get_client()
    if c is None:
        raise HTTPException(503, "Database unavailable")

    c.table("users").update({"password_hash": new_hashed}).eq("id", current_user["user_id"]).execute()
    return {"success": True, "message": "Password changed successfully"}

# NOTE: Watchlist endpoints are in admin.py under /admin/watchlist.
# Frontend exclusively calls /admin/watchlist endpoints.



class ForgotPasswordRequest(BaseModel):
    email: str

@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest):
    """Trigger Supabase to send a magic link/password reset email."""
    try:
        from backend.database import _get_client
        supabase = _get_client()
        if not supabase:
            raise HTTPException(503, "Database unavailable")
            
        # Send password reset email via Supabase Auth
        # Note: frontend needs to handle the callback at /auth/reset-password
        res = supabase.auth.reset_password_email(
            req.email,
            options={"redirect_to": f"{settings.allowed_origins.split(',')[0]}/auth/reset-password"}
        )
        return {"success": True, "message": "Password reset email sent (if account exists)"}
    except Exception as e:
        print(f"Forgot password error: {e}")
        # Return success anyway to prevent email enumeration
        return {"success": True, "message": "Password reset email sent (if account exists)"}


class ResetPasswordRequest(BaseModel):
    email: str
    new_password: str
    supabase_token: str

@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest):
    """Update password hash in our DB after verifying Supabase token."""
    if len(req.new_password) < 4:
        raise HTTPException(400, "New password must be at least 4 characters")
        
    try:
        from backend.database import _get_client, get_user_by_username
        supabase = _get_client()
        if not supabase:
            raise HTTPException(503, "Database unavailable")
            
        # Verify the token is valid for this user
        user_response = supabase.auth.get_user(req.supabase_token)
        if not user_response or not user_response.user or user_response.user.email != req.email:
            raise HTTPException(401, "Invalid or expired reset token")
            
        user = get_user_by_username(req.email)
        if not user:
            raise HTTPException(404, "User not found")
            
        new_hashed = hash_password(req.new_password)
        supabase.table("users").update({"password_hash": new_hashed}).eq("id", user["id"]).execute()
        
        return {"success": True, "message": "Password reset successfully"}
    except Exception as e:
        print(f"Reset password error: {e}")
        raise HTTPException(500, f"Failed to reset password: {str(e)}")
