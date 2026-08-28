"""
routers/auth.py – Xác thực người dùng bằng token tự ký (HMAC-SHA256).

Thay đổi quan trọng so với bản trước:

1. **Salt mật khẩu tách khỏi khoá ký JWT.**
   Bản cũ lấy salt từ `ADMIN_SECRET_KEY`, nghĩa là mỗi lần đổi khoá JWT thì
   TOÀN BỘ mật khẩu người dùng trở thành không đăng nhập được. Bản này dùng
   salt ngẫu nhiên riêng cho từng user, lưu kèm trong chuỗi hash.

2. **Tự động nâng cấp hash cũ.** Hash theo định dạng cũ vẫn đăng nhập được;
   ngay sau lần đăng nhập thành công đầu tiên nó được ghi đè bằng định dạng mới.
   Nhờ vậy không cần bắt người dùng đặt lại mật khẩu khi triển khai bản này.

3. **Không trả `str(e)` ra client** — chi tiết lỗi chỉ nằm ở log server.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Optional, Tuple

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from backend.config import settings
from backend.database import create_user, get_user_by_username
from backend.security import log_and_raise

router = APIRouter()

SECRET_KEY = settings.admin_secret_key.encode()

TOKEN_TTL_SECONDS = 86400 * 7  # 7 ngày
PBKDF2_ITERATIONS = 200_000    # Gấp đôi bản cũ; vẫn dưới 200ms trên CPU của Render
MIN_PASSWORD_LENGTH = 8


# ══════════════════════════════════════════════════════════════════════════════
#  SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class AuthRequest(BaseModel):
    username: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=256)


class GoogleAuthRequest(BaseModel):
    access_token: str = Field(min_length=10, max_length=4096)


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=256)


class ProfileUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)


class ResetPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=256)
    supabase_token: str = Field(min_length=10, max_length=4096)


# ══════════════════════════════════════════════════════════════════════════════
#  MẬT KHẨU
# ══════════════════════════════════════════════════════════════════════════════

def _pbkdf2(password: str, salt: bytes, iterations: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations).hex()


def hash_password(password: str) -> str:
    """
    Sinh hash mới theo định dạng: pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>

    Salt ngẫu nhiên cho từng user — hai người dùng đặt cùng mật khẩu sẽ có hash
    khác nhau, và rainbow table dựng sẵn trở thành vô dụng.
    """
    salt = os.urandom(16)
    digest = _pbkdf2(password, salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest}"


def _legacy_hash(password: str) -> str:
    """Tái tạo hash theo định dạng cũ để xác thực tài khoản tạo trước bản này."""
    salt = hashlib.sha256(SECRET_KEY + b"_password_salt").digest()
    return _pbkdf2(password, salt, 100_000)


def verify_password(password: str, stored: str) -> Tuple[bool, bool]:
    """
    Kiểm tra mật khẩu.

    Trả về (hợp_lệ, cần_nâng_cấp_hash). `cần_nâng_cấp_hash` bằng True khi mật khẩu
    đúng nhưng đang lưu ở định dạng cũ — caller nên ghi đè bằng `hash_password()`.
    """
    if not stored:
        return False, False

    if stored.startswith("pbkdf2_sha256$"):
        try:
            _, iterations_s, salt_hex, digest = stored.split("$", 3)
            candidate = _pbkdf2(password, bytes.fromhex(salt_hex), int(iterations_s))
            return hmac.compare_digest(candidate, digest), False
        except (ValueError, TypeError):
            return False, False

    # Định dạng cũ: hex thuần, salt suy ra từ SECRET_KEY.
    is_valid = hmac.compare_digest(_legacy_hash(password), stored)
    return is_valid, is_valid


def _validate_password_strength(password: str) -> None:
    """Yêu cầu tối thiểu. Cố ý giữ nhẹ nhàng cho đồ án, nhưng chặn các mật khẩu tệ nhất."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(400, f"Mật khẩu phải có ít nhất {MIN_PASSWORD_LENGTH} ký tự.")
    if password.lower() in {"password", "12345678", "qwertyui", "admin123", "11111111"}:
        raise HTTPException(400, "Mật khẩu quá phổ biến, vui lòng chọn mật khẩu khác.")
    if len(set(password)) < 4:
        raise HTTPException(400, "Mật khẩu quá đơn giản, vui lòng dùng nhiều ký tự khác nhau hơn.")


def _upgrade_hash_if_needed(user_id: int, password: str, needs_upgrade: bool) -> None:
    """Ghi đè hash cũ bằng định dạng mới. Thất bại ở đây không được chặn đăng nhập."""
    if not needs_upgrade:
        return
    try:
        from backend.database import _get_client

        c = _get_client()
        if c:
            c.table("users").update({"password_hash": hash_password(password)}).eq("id", user_id).execute()
            print(f"[auth] Đã nâng cấp định dạng hash mật khẩu cho user {user_id}.")
    except Exception as e:
        print(f"[auth] Không nâng cấp được hash cho user {user_id}: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  TOKEN
# ══════════════════════════════════════════════════════════════════════════════

def create_token(user_id: int, username: str, role: str = "user") -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": time.time() + TOKEN_TTL_SECONDS,
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
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

        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())

        if payload.get("exp", 0) < time.time():
            return None
        if "user_id" not in payload or "username" not in payload:
            return None
        return payload
    except Exception:
        # Token hỏng là chuyện bình thường (hết hạn, bị sửa) — không cần log ồn ào.
        return None


# ── Ghi nhận hoạt động, có tiết chế ───────────────────────────────────────────
# Bản cũ UPDATE bảng users trên MỖI request đã xác thực, tức là mỗi lần load trang
# tốn thêm vài round-trip tới DB. Ở đây ta chỉ ghi tối đa 5 phút một lần cho mỗi user.

_last_active_writes: dict = {}
_LAST_ACTIVE_THROTTLE = 300


def _touch_last_active(user_id: int) -> None:
    now = time.time()
    if now - _last_active_writes.get(user_id, 0) < _LAST_ACTIVE_THROTTLE:
        return
    _last_active_writes[user_id] = now
    try:
        from backend.database import _get_client

        c = _get_client()
        if c:
            c.table("users").update(
                {"last_active": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            ).eq("id", user_id).execute()
    except Exception as e:
        print(f"[auth] Không cập nhật được last_active: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  DEPENDENCIES
# ══════════════════════════════════════════════════════════════════════════════

def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Cần đăng nhập để thực hiện thao tác này.")

    payload = verify_token(authorization[7:])
    if not payload:
        raise HTTPException(401, "Phiên đăng nhập không hợp lệ hoặc đã hết hạn.")

    _touch_last_active(payload["user_id"])
    return payload


def get_current_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(403, "Bạn không có quyền truy cập chức năng này.")
    return user


def _auth_response(user: dict, token: str, message: str) -> dict:
    from backend.database import get_user_profile

    profile = get_user_profile(user["id"])
    return {
        "success": True,
        "token": token,
        "user_id": user["id"],
        "username": user["username"],
        "name": profile.get("name") or user["username"],
        "role": user.get("role", "user"),
        "is_oauth": user.get("password_hash") == "GOOGLE_OAUTH_USER",
        "message": message,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/register")
def register(req: AuthRequest):
    username = req.username.strip().lower()
    if len(username) < 3:
        raise HTTPException(400, "Tên đăng nhập phải có ít nhất 3 ký tự.")
    _validate_password_strength(req.password)

    try:
        existing = get_user_by_username(username)
    except Exception as e:
        log_and_raise("register/lookup", e, 503, "Không kết nối được cơ sở dữ liệu.")
        return

    if existing:
        raise HTTPException(400, "Tên đăng nhập đã tồn tại.")

    try:
        user = create_user(username, hash_password(req.password))
    except Exception as e:
        log_and_raise("register/create", e, 503, "Không tạo được tài khoản. Vui lòng thử lại.")
        return

    if not user:
        raise HTTPException(500, "Không tạo được tài khoản. Vui lòng thử lại.")

    token = create_token(user["id"], user["username"], user.get("role", "user"))
    return _auth_response(user, token, "Đăng ký thành công")


@router.post("/login")
def login(req: AuthRequest):
    generic_error = "Tên đăng nhập hoặc mật khẩu không đúng."

    try:
        user = get_user_by_username(req.username.strip().lower())
    except Exception as e:
        log_and_raise("login/lookup", e, 503, "Không kết nối được cơ sở dữ liệu.")
        return

    if not user:
        # Vẫn tốn thời gian băm để thời gian phản hồi giống trường hợp sai mật khẩu,
        # tránh việc kẻ tấn công dò được username nào tồn tại qua độ trễ.
        hash_password(req.password)
        raise HTTPException(400, generic_error)

    if user.get("status") == "suspended":
        raise HTTPException(403, "Tài khoản của bạn đang bị tạm khoá.")

    is_valid, needs_upgrade = verify_password(req.password, user.get("password_hash", ""))
    if not is_valid:
        raise HTTPException(400, generic_error)

    _upgrade_hash_if_needed(user["id"], req.password, needs_upgrade)

    token = create_token(user["id"], user["username"], user.get("role", "user"))
    return _auth_response(user, token, "Đăng nhập thành công")


@router.post("/google")
def google_auth(req: GoogleAuthRequest):
    """Đổi access_token của Supabase (Google OAuth) lấy token nội bộ."""
    try:
        from backend.database import _get_client

        supabase = _get_client()
        if not supabase:
            raise HTTPException(503, "Dịch vụ đăng nhập tạm thời không khả dụng.")

        user_response = supabase.auth.get_user(req.access_token)
        if not user_response or not user_response.user:
            raise HTTPException(401, "Token Google không hợp lệ.")

        email = (user_response.user.email or f"google_user_{user_response.user.id[:8]}").lower()

        existing_user = get_user_by_username(email)
        if not existing_user:
            create_user(email, "GOOGLE_OAUTH_USER")
            existing_user = get_user_by_username(email)
        if not existing_user:
            raise HTTPException(500, "Không tạo được tài khoản.")

        token = create_token(existing_user["id"], existing_user["username"], existing_user.get("role", "user"))
        return _auth_response(existing_user, token, "Đăng nhập Google thành công")

    except HTTPException:
        raise
    except Exception as e:
        log_and_raise("google_auth", e, 401, "Đăng nhập Google thất bại.")


@router.put("/change-password")
def change_password(req: ChangePasswordRequest, current_user: dict = Depends(get_current_user)):
    _validate_password_strength(req.new_password)

    try:
        user = get_user_by_username(current_user["username"])
    except Exception as e:
        log_and_raise("change_password/lookup", e, 503, "Không kết nối được cơ sở dữ liệu.")
        return

    if not user:
        raise HTTPException(404, "Không tìm thấy tài khoản.")

    is_valid, _ = verify_password(req.old_password, user.get("password_hash", ""))
    if not is_valid:
        raise HTTPException(400, "Mật khẩu hiện tại không đúng.")

    try:
        from backend.database import _get_client

        c = _get_client()
        if c is None:
            raise HTTPException(503, "Không kết nối được cơ sở dữ liệu.")
        c.table("users").update({"password_hash": hash_password(req.new_password)}).eq(
            "id", current_user["user_id"]
        ).execute()
    except HTTPException:
        raise
    except Exception as e:
        log_and_raise("change_password/update", e, 500, "Không đổi được mật khẩu.")

    return {"success": True, "message": "Đổi mật khẩu thành công"}


@router.get("/profile")
def get_profile(current_user: dict = Depends(get_current_user)):
    from backend.database import get_user_profile

    p = get_user_profile(current_user["user_id"])
    return {"success": True, "name": p.get("name") or current_user["username"]}


@router.put("/profile")
def update_profile(req: ProfileUpdateRequest, current_user: dict = Depends(get_current_user)):
    from backend.database import get_user_profile, save_user_profile

    profile = get_user_profile(current_user["user_id"])
    profile["name"] = req.name.strip()

    if not save_user_profile(current_user["user_id"], profile):
        raise HTTPException(500, "Không lưu được thông tin cá nhân.")
    return {"success": True, "message": "Đã cập nhật thông tin"}


@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest, request: Request):
    """
    Gửi email đặt lại mật khẩu qua Supabase Auth.

    Luôn trả về thành công dù email có tồn tại hay không — nếu phản hồi khác nhau,
    endpoint này trở thành công cụ dò xem địa chỉ nào đã đăng ký.
    """
    success_response = {
        "success": True,
        "message": "Nếu email tồn tại trong hệ thống, liên kết đặt lại mật khẩu đã được gửi.",
    }

    try:
        from backend.database import _get_client

        supabase = _get_client()
        if not supabase:
            return success_response

        origin = request.headers.get("origin")
        allowed = settings.origin_list
        # Chỉ chấp nhận origin nằm trong danh sách cho phép — nếu không, kẻ tấn công
        # có thể ép link đặt lại mật khẩu trỏ về domain của họ.
        if origin not in allowed:
            origin = allowed[0] if allowed and allowed[0] != "*" else "http://localhost:3000"

        supabase.auth.reset_password_email(
            req.email.strip().lower(),
            options={"redirect_to": f"{origin}/auth/reset-password"},
        )
    except Exception as e:
        print(f"[auth] forgot_password: {e}")

    return success_response


@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest):
    _validate_password_strength(req.new_password)

    try:
        from backend.database import _get_client

        supabase = _get_client()
        if not supabase:
            raise HTTPException(503, "Dịch vụ tạm thời không khả dụng.")

        email = req.email.strip().lower()
        user_response = supabase.auth.get_user(req.supabase_token)
        if (
            not user_response
            or not user_response.user
            or (user_response.user.email or "").lower() != email
        ):
            raise HTTPException(401, "Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.")

        user = get_user_by_username(email)
        if not user:
            raise HTTPException(404, "Không tìm thấy tài khoản.")

        supabase.table("users").update({"password_hash": hash_password(req.new_password)}).eq(
            "id", user["id"]
        ).execute()

    except HTTPException:
        raise
    except Exception as e:
        log_and_raise("reset_password", e, 500, "Không đặt lại được mật khẩu.")

    return {"success": True, "message": "Đặt lại mật khẩu thành công"}


# ── Tiện ích dòng lệnh ────────────────────────────────────────────────────────
# Dùng để sinh hash khi cần seed tài khoản admin thẳng vào Supabase:
#   python -m backend.routers.auth "MatKhauCuaBan"

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print('Cách dùng: python -m backend.routers.auth "<mật khẩu>"')
        sys.exit(1)
    print(hash_password(sys.argv[1]))
