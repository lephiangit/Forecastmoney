"""
security.py – Lớp bảo vệ dùng chung cho toàn bộ API.

Gồm 4 phần:
  1. RateLimiter          – giới hạn số request/phút theo IP (in-memory, không cần Redis)
  2. Error sanitizing     – không bao giờ trả stack trace / thông điệp lỗi driver cho client
  3. Input sanitizing     – giới hạn độ dài + loại bỏ mẫu prompt-injection phổ biến
  4. Cron authentication  – xác thực job nền bằng header, so sánh chống timing attack

Ghi chú kiến trúc: RateLimiter lưu state trong RAM của tiến trình. Điều này đủ cho
mô hình triển khai hiện tại (Render free tier = 1 web service, 1 worker). Nếu sau này
scale lên nhiều worker/instance, cần thay bằng Redis — interface giữ nguyên.
"""

from __future__ import annotations

import hmac
import re
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional

from fastapi import Header, HTTPException, Request

from backend.config import settings


# ══════════════════════════════════════════════════════════════════════════════
#  1. RATE LIMITER
# ══════════════════════════════════════════════════════════════════════════════

class RateLimiter:
    """
    Sliding-window rate limiter theo IP.

    Mỗi (client_ip, bucket) giữ một deque timestamp của các request trong 60s gần nhất.
    Khi số lượng vượt `limit`, request bị từ chối với HTTP 429.
    """

    WINDOW_SECONDS = 60
    # Dọn các entry cũ mỗi 5 phút để bộ nhớ không phình vô hạn.
    _CLEANUP_INTERVAL = 300

    def __init__(self) -> None:
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._last_cleanup = time.time()

    def _cleanup_if_needed(self, now: float) -> None:
        if now - self._last_cleanup < self._CLEANUP_INTERVAL:
            return
        cutoff = now - self.WINDOW_SECONDS
        empty_keys = [k for k, dq in self._hits.items() if not dq or dq[-1] < cutoff]
        for k in empty_keys:
            self._hits.pop(k, None)
        self._last_cleanup = now

    def check(self, client_id: str, bucket: str, limit: int) -> Optional[int]:
        """
        Ghi nhận một request. Trả về None nếu được phép,
        hoặc số giây cần chờ (retry_after) nếu bị chặn.
        """
        if not settings.rate_limit_enabled:
            return None

        key = f"{bucket}:{client_id}"
        now = time.time()
        cutoff = now - self.WINDOW_SECONDS

        with self._lock:
            self._cleanup_if_needed(now)
            dq = self._hits[key]
            while dq and dq[0] < cutoff:
                dq.popleft()

            if len(dq) >= limit:
                retry_after = int(dq[0] + self.WINDOW_SECONDS - now) + 1
                return max(retry_after, 1)

            dq.append(now)
            return None


rate_limiter = RateLimiter()


# Số hop proxy tin cậy đứng trước ứng dụng (Render = 1). Đổi nếu triển khai
# sau nhiều lớp proxy/CDN khác.
TRUSTED_PROXY_HOPS = 1


def get_client_ip(request: Request) -> str:
    """
    Địa chỉ IP của client, dùng làm khoá cho bộ giới hạn tần suất.

    LỖI ĐÃ SỬA — vượt rate limit bằng header tự đặt.
    Bản cũ lấy phần TRÁI NHẤT của `X-Forwarded-For`. Đó lại đúng là phần mà client
    tự điền được: header này là một chuỗi các hop, mỗi proxy nối thêm vào bên phải,
    nên phần trái nhất không hề được xác thực. Kẻ tấn công chỉ cần gửi mỗi request
    kèm một `X-Forwarded-For` ngẫu nhiên là mỗi lần lại rơi vào một "xô" đếm khác
    nhau — hạn mức 10 lần/phút cho /auth/login không bao giờ chạm tới, tức là dò
    mật khẩu không giới hạn.

    Nay lấy hop do CHÍNH hạ tầng của mình nối thêm: phần PHẢI NHẤT, trừ đi số hop
    proxy tin cậy (Render đứng trước app đúng 1 hop). Nếu header không hợp lệ thì
    quay về `request.client.host`.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        hops = [h.strip() for h in forwarded.split(",") if h.strip()]
        if hops:
            # TRUSTED_PROXY_HOPS = 1: Render nối thêm đúng một hop (IP thật của client
            # nhìn từ phía Render). Mọi thứ bên trái hop đó đều do client bịa ra được.
            idx = max(0, len(hops) - TRUSTED_PROXY_HOPS)
            return hops[idx]
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(request: Request, bucket: str, limit: int) -> None:
    """Raise HTTP 429 nếu client vượt giới hạn. Dùng trực tiếp trong endpoint."""
    retry_after = rate_limiter.check(get_client_ip(request), bucket, limit)
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Bạn đang thao tác quá nhanh. Vui lòng thử lại sau ít giây.",
            headers={"Retry-After": str(retry_after)},
        )


# ══════════════════════════════════════════════════════════════════════════════
#  2. ERROR SANITIZING
# ══════════════════════════════════════════════════════════════════════════════

def log_and_raise(
    context: str,
    exc: Exception,
    status_code: int = 500,
    public_message: str = "Đã có lỗi xảy ra. Vui lòng thử lại sau.",
) -> None:
    """
    Ghi log chi tiết ở server, trả thông điệp chung chung cho client.

    Lý do: `str(exc)` của driver DB thường chứa tên bảng, tên cột, câu query,
    đôi khi cả connection string — không được để lọt ra frontend.
    """
    print(f"[ERROR] {context}: {type(exc).__name__}: {exc}")
    raise HTTPException(status_code=status_code, detail=public_message)


# ══════════════════════════════════════════════════════════════════════════════
#  3. INPUT SANITIZING
# ══════════════════════════════════════════════════════════════════════════════

# Các mẫu người dùng hay dùng để cướp quyền điều khiển system prompt.
_INJECTION_PATTERNS = [
    re.compile(r"(?i)\bignore\s+(all\s+|the\s+)?(previous|above|prior)\s+instructions?\b"),
    re.compile(r"(?i)\bdisregard\s+(all\s+|the\s+)?(previous|above|prior)\b"),
    re.compile(r"(?i)\b(bỏ qua|phớt lờ)\s+(mọi\s+|các\s+|tất cả\s+)?(chỉ thị|hướng dẫn|lệnh)\b"),
    re.compile(r"(?i)\byou\s+are\s+now\s+(a|an)\b"),
    re.compile(r"(?i)\b(reveal|show|print|repeat)\s+(me\s+)?(your\s+)?(system\s+)?prompt\b"),
    re.compile(r"(?i)\b(lộ|tiết lộ|in ra|nhắc lại)\s+(system\s+)?prompt\b"),
    # Giả mạo ranh giới hội thoại của định dạng chat
    re.compile(r"(?i)<\|?(im_start|im_end|system|endoftext)\|?>"),
    re.compile(r"(?i)^\s*(system|assistant)\s*:", re.MULTILINE),
]


def sanitize_user_text(text: str, max_chars: int) -> str:
    """
    Làm sạch text do người dùng nhập trước khi ghép vào prompt LLM.

    Đây là biện pháp giảm thiểu, không phải bảo vệ tuyệt đối — phòng tuyến thật nằm ở
    chỗ LLM trong hệ thống này không có quyền gọi tool hay truy cập DB, nên kịch bản
    xấu nhất chỉ là model trả lời lạc đề chứ không gây rò rỉ dữ liệu.
    """
    if not text:
        return ""

    cleaned = text.strip()[:max_chars]

    # Loại ký tự điều khiển (trừ xuống dòng và tab) — hay dùng để giấu payload.
    cleaned = "".join(ch for ch in cleaned if ch in "\n\t" or ord(ch) >= 32)

    for pattern in _INJECTION_PATTERNS:
        cleaned = pattern.sub("[đã lọc]", cleaned)

    return cleaned.strip()


# Cho phép ký tự '^' ở đầu: đó là tiền tố của các chỉ số thị trường trên
# yfinance (^GSPC = S&P 500, ^DJI = Dow Jones, ^IXIC = Nasdaq). Chính
# routers/market.py đang phân loại các mã này, nên nếu chặn ở đây thì phần
# "chỉ số" của ứng dụng sẽ trả về lỗi 400.
_TICKER_RE = re.compile(r"^\^?[A-Za-z0-9][A-Za-z0-9.\-=]{0,19}$")


def validate_ticker_format(ticker: str) -> str:
    """
    Kiểm tra định dạng ticker trước khi đưa vào yfinance hoặc câu query DB.
    Trả về dạng chuẩn hoá (viết hoa) hoặc raise HTTP 400.
    """
    if not ticker or not _TICKER_RE.match(ticker.strip()):
        raise HTTPException(
            status_code=400,
            detail="Mã tài sản không hợp lệ. Ví dụ hợp lệ: BTC-USD, AAPL, FPT.VN",
        )
    return ticker.strip().upper()


# ══════════════════════════════════════════════════════════════════════════════
#  4. CRON AUTHENTICATION
# ══════════════════════════════════════════════════════════════════════════════

def verify_cron_secret(x_cron_secret: Optional[str] = Header(default=None)) -> bool:
    """
    Xác thực job nền bằng header `X-Cron-Secret`.

    Vì sao là header chứ không phải query param như trước: query string bị ghi lại
    trong access log của Render, trong lịch sử trình duyệt, và trong header Referer
    khi điều hướng — nghĩa là secret sẽ rò rỉ dần theo thời gian mà không ai hay.

    Dùng `hmac.compare_digest` để so sánh trong thời gian hằng định, tránh
    timing attack cho phép dò từng ký tự của secret.
    """
    expected = settings.cron_secret_key
    if not x_cron_secret or not hmac.compare_digest(x_cron_secret, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True
