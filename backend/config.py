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
    # "llama-3.3-70b-versatile" bị Groq khai tử ngày 16/08/2026 (xem
    # https://console.groq.com/docs/deprecations) — mọi request tới model này
    # giờ trả 404, khiến toàn bộ hệ thống (chat Copilot, /research,
    # cron_researcher, confidence cho bot auto-trade) âm thầm rơi về fallback
    # keyword-scoring mà không có cảnh báo rõ ràng nào ở log. Đổi sang
    # "openai/gpt-oss-120b" — model thay thế Groq khuyến nghị chính thức.
    groq_model: str = "openai/gpt-oss-120b"

    # ── Secrets (BẮT BUỘC set qua env ở production) ───────────────────────────
    # Ký JWT đăng nhập. Đổi giá trị này sẽ vô hiệu hoá toàn bộ token đang lưu ở client.
    admin_secret_key: str = "dev-only-insecure-secret"
    # Secret riêng cho các job nền (/admin/trigger-*). Gửi qua header X-Cron-Secret.
    cron_secret_key: str = "dev-only-insecure-secret"

    # Giá trị CŨ của ADMIN_SECRET_KEY, chỉ dùng để xác thực các mật khẩu chưa được
    # nâng cấp định dạng hash.
    #
    # Vì sao cần: trước bản 2.0, salt mật khẩu được suy ra từ ADMIN_SECRET_KEY.
    # Nếu chỉ đơn giản đổi khoá đó, MỌI tài khoản đang lưu hash theo định dạng cũ
    # sẽ không đăng nhập được nữa — kể cả khi người dùng gõ đúng mật khẩu.
    #
    # Đặt biến này bằng giá trị ADMIN_SECRET_KEY CŨ khi luân chuyển khoá. Mỗi lần
    # người dùng đăng nhập thành công, hash của họ tự động được nâng cấp sang định
    # dạng mới (salt ngẫu nhiên, độc lập hoàn toàn với mọi khoá). Khi tất cả người
    # dùng đã đăng nhập lại ít nhất một lần, có thể xoá biến này đi.
    legacy_password_secret: Optional[str] = None

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

        # Quên set ALLOWED_ORIGINS ở production là lỗi rất khó truy vết: app khởi động
        # bình thường, /health trả 200 trong log server, nhưng trình duyệt chặn sạch
        # mọi request vì thiếu header CORS. Nhìn từ phía người dùng thì giống hệt
        # "backend chết", còn log server thì lại nói mọi thứ đều ổn.
        #
        # Nếu TOÀN BỘ origin đều là localhost thì chắc chắn là cấu hình sót, vì không
        # có trình duyệt nào của người dùng thật chạy ở localhost của máy chủ.
        elif all(
            o.startswith(("http://localhost", "http://127.0.0.1", "https://localhost"))
            for o in self.origin_list
        ):
            problems.append(
                f"ALLOWED_ORIGINS chỉ chứa localhost ({', '.join(self.origin_list)}). "
                "Ở production biến này phải là domain thật của frontend, ví dụ "
                "https://ten-mien-cua-ban.com — nếu không, trình duyệt sẽ chặn toàn bộ "
                "request và giao diện chỉ hiển thị dữ liệu mẫu."
            )

        return problems

    def startup_warnings(self) -> List[str]:
        """
        Các vấn đề KHÔNG chặn khởi động nhưng làm hỏng chức năng.

        Tách khỏi `validate_for_production()` vì đây không phải lỗ hổng bảo mật —
        app vẫn chạy được, chỉ là một phần tính năng im lặng ngừng hoạt động.
        In ra lúc khởi động để không phải mò trong lúc demo.
        """
        warnings: List[str] = []

        if not self.groq_api_key:
            warnings.append(
                "GROQ_API_KEY chưa được đặt. Trợ lý AI Copilot sẽ không trả lời, và phần "
                "phân tích tin tức tự động lùi về chấm điểm từ khoá thay vì dùng mô hình ngôn ngữ."
            )

        if self.supabase_key and "publishable" in self.supabase_key:
            warnings.append(
                "SUPABASE_KEY trông giống khoá publishable (anon). Backend cần khoá "
                "service_role — nếu không, Row Level Security sẽ chặn mọi truy vấn với lỗi "
                "'permission denied for table ...'."
            )

        if not self.supabase_url or not self.supabase_key:
            warnings.append("Thiếu SUPABASE_URL hoặc SUPABASE_KEY — toàn bộ tính năng cần dữ liệu sẽ hỏng.")

        return warnings


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
