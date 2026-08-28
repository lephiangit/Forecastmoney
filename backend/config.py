"""
config.py – Central config for ForecastAI.

SECURITY NOTES
--------------
1. `admin_secret_key` ký JWT đăng nhập. Nó KHÔNG được dùng cho mục đích nào khác.
2. `cron_secret_key` là secret riêng cho các endpoint /admin/trigger-*.
   Tách hai secret ra để việc lộ secret cron không dẫn tới giả mạo được token admin.
3. Ở production (ENVIRONMENT=production) hệ thống sẽ TỪ CHỐI KHỞI ĐỘNG nếu secret
   vẫn để giá trị mặc định, hoặc nếu ALLOWED_ORIGINS còn là "*".
"""

from typing import List, Optional

from pydantic_settings import BaseSettings

# Các giá trị secret mặc định — chỉ dùng được ở môi trường dev.
# Nếu gặp lại các giá trị này ở production, app sẽ dừng khởi động.
_INSECURE_DEFAULTS = {
    "change-this-in-production",
    "dev-only-insecure-secret",
    "capmot100123@",
    "admin123",
    "",
}


class Settings(BaseSettings):
    # ── Môi trường ────────────────────────────────────────────────────────────
    environment: str = "development"  # "development" | "production"

    # ── Database ──────────────────────────────────────────────────────────────
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None

    # ── LLM ───────────────────────────────────────────────────────────────────
    groq_api_key: Optional[str] = None
    groq_model: str = "llama-3.3-70b-versatile"

    # ── Secrets (BẮT BUỘC set qua env ở production) ───────────────────────────
    # Ký JWT đăng nhập. Đổi giá trị này sẽ vô hiệu hoá toàn bộ token đang lưu ở client.
    admin_secret_key: str = "dev-only-insecure-secret"
    # Secret riêng cho các job nền (/admin/trigger-*). Gửi qua header X-Cron-Secret.
    cron_secret_key: str = "dev-only-insecure-secret"

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Danh sách origin, phân tách bằng dấu phẩy.
    allowed_origins: str = "http://localhost:3000"

    # ── Rate limiting ─────────────────────────────────────────────────────────
    rate_limit_enabled: bool = True
    rate_limit_default: int = 120       # request/phút/IP cho endpoint thường
    rate_limit_auth: int = 10           # request/phút/IP cho /auth/login, /auth/register
    rate_limit_expensive: int = 20      # request/phút/IP cho forecast/research (gọi model + LLM)

    # ── Giới hạn input (chống prompt injection & abuse) ───────────────────────
    max_chat_message_chars: int = 2000
    max_ticker_chars: int = 20

    # ── News feeds ────────────────────────────────────────────────────────────
    crypto_feeds: List[str] = [
        "https://cointelegraph.com/rss",
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
    ]
    vn_feeds: List[str] = [
        "https://vnexpress.net/rss/kinh-doanh.rss",
        "https://cafef.vn/rss/thi-truong-chung-khoan.rss",
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    # ── Helpers ───────────────────────────────────────────────────────────────

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() == "production"

    @property
    def origin_list(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def docs_enabled(self) -> bool:
        """Swagger/ReDoc chỉ bật ở dev — ở production chúng phơi bày toàn bộ bề mặt API."""
        return not self.is_production

    def validate_for_production(self) -> List[str]:
        """
        Trả về danh sách vấn đề bảo mật chặn khởi động ở production.
        Rỗng nghĩa là cấu hình đạt yêu cầu.
        """
        problems: List[str] = []

        if not self.is_production:
            return problems

        if self.admin_secret_key.strip() in _INSECURE_DEFAULTS:
            problems.append(
                "ADMIN_SECRET_KEY đang để giá trị mặc định. Sinh giá trị mới: "
                'python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        if len(self.admin_secret_key) < 32:
            problems.append("ADMIN_SECRET_KEY quá ngắn (cần tối thiểu 32 ký tự).")

        if self.cron_secret_key.strip() in _INSECURE_DEFAULTS:
            problems.append("CRON_SECRET_KEY đang để giá trị mặc định.")
        if self.cron_secret_key.strip() == self.admin_secret_key.strip():
            problems.append(
                "CRON_SECRET_KEY trùng ADMIN_SECRET_KEY. Hai secret này phải khác nhau, "
                "vì secret cron được truyền qua mạng nhiều hơn hẳn."
            )

        if "*" in self.origin_list:
            problems.append(
                'ALLOWED_ORIGINS đang là "*". Ở production phải liệt kê domain cụ thể '
                "(vì API dùng allow_credentials=True)."
            )
        if not self.origin_list:
            problems.append("ALLOWED_ORIGINS đang rỗng.")

        return problems


settings = Settings()


# Tên hiển thị thân thiện cho các ticker phổ biến.
TICKER_LABELS: dict = {
    # Crypto
    "BTC-USD": "Bitcoin",
    "ETH-USD": "Ethereum",
    "BNB-USD": "BNB",
    "SOL-USD": "Solana",
    "ADA-USD": "Cardano",
    "XRP-USD": "XRP",
    "DOGE-USD": "Dogecoin",
    "AVAX-USD": "Avalanche",
    "DOT-USD": "Polkadot",
    "MATIC-USD": "Polygon",
    "LINK-USD": "Chainlink",
    "UNI-USD": "Uniswap",
    "ATOM-USD": "Cosmos",
    "LTC-USD": "Litecoin",
    "TRX-USD": "TRON",
    "SHIB-USD": "Shiba Inu",
    "TON11419-USD": "Toncoin",
    # VN Stocks
    "FPT.VN": "FPT Corp",
    "VCB.VN": "Vietcombank",
    "HPG.VN": "Hoa Phat Group",
    "VIC.VN": "Vingroup",
    "MWG.VN": "Mobile World",
    "SSI.VN": "SSI Securities",
    "TCB.VN": "Techcombank",
    "VHM.VN": "Vinhomes",
    "VNM.VN": "Vinamilk",
    "MSN.VN": "Masan Group",
}
