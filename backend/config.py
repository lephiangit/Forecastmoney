"""
config.py – Central config for ForecastAI V2.
"""
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    admin_password: str = "admin123"
    admin_secret_key: str = "change-this-in-production"  # ⚠️ MUST change in production
    allowed_origins: str = "*"  # Comma-separated origins, e.g. "https://your-app.netlify.app"
    crypto_feeds: list[str] = [
        "https://cointelegraph.com/rss",
        "https://www.coindesk.com/arc/outboundfeeds/rss/"
    ]
    vn_feeds: list[str] = [
        "https://vnexpress.net/rss/kinh-doanh.rss",
        "https://cafef.vn/rss/thi-truong-chung-khoan.rss"
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()

# Friendly display names for common tickers
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
