import os
import ccxt
import finnhub
from dotenv import load_dotenv
import sys

# Fix cho Terminal Windows bị lỗi font Tiếng Việt
sys.stdout.reconfigure(encoding='utf-8')

# Tải các biến môi trường từ file .env
# Chỉnh lại đường dẫn tới .env (vì script này nằm trong thư mục services)
current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(os.path.dirname(current_dir), '.env')
load_dotenv(env_path)

class MarketDataService:
    def __init__(self):
        # 1. Khởi tạo CCXT cho Binance (lấy dữ liệu Crypto)
        self.crypto_exchange = ccxt.binance({
            'enableRateLimit': True, # Tự động kiểm soát tốc độ gọi API để tránh bị chặn
        })
        
        # 2. Khởi tạo Finnhub (lấy dữ liệu Chứng khoán)
        finnhub_key = os.getenv("FINNHUB_API_KEY")
        if not finnhub_key:
            print("Cảnh báo: Không tìm thấy FINNHUB_API_KEY trong file .env")
        self.stock_client = finnhub.Client(api_key=finnhub_key)

    def get_crypto_candles(self, symbol="BTC/USDT", timeframe="1m", limit=5):
        """
        Lấy nến (OHLCV) của Crypto từ CCXT (Mặc định: Binance)
        """
        try:
            print(f"Đang lấy dữ liệu {symbol} khung {timeframe} từ Binance...")
            # Trả về list: [Timestamp, Open, High, Low, Close, Volume]
            candles = self.crypto_exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            return candles
        except Exception as e:
            print(f"Lỗi CCXT: {e}")
            return None

    def get_stock_quote(self, symbol="AAPL"):
        """
        Lấy giá hiện tại của Chứng khoán từ Finnhub
        """
        try:
            print(f"Đang lấy dữ liệu giá của cổ phiếu {symbol} từ Finnhub...")
            quote = self.stock_client.quote(symbol)
            return quote
        except Exception as e:
            print(f"Lỗi Finnhub: {e}")
            return None

# Đoạn code chạy thử (khi bạn chạy trực tiếp file này)
if __name__ == "__main__":
    service = MarketDataService()
    
    print("\n--- 1. TEST CRYPTO (CCXT) ---")
    # Lấy 3 cây nến gần nhất của BTC/USDT theo phút (1m)
    btc_candles = service.get_crypto_candles("BTC/USDT", "1m", limit=3)
    if btc_candles:
        for c in btc_candles:
            # c[0]: timestamp, c[1]: open, c[4]: close
            print(f"Timestamp: {c[0]} | Giá mở: {c[1]} | Giá đóng: {c[4]}")
            
    print("\n--- 2. TEST CHỨNG KHOÁN (Finnhub) ---")
    # Lấy giá trị hiện tại của cổ phiếu Apple
    aapl_quote = service.get_stock_quote("AAPL")
    if aapl_quote:
        print(f"Dữ liệu đầy đủ (AAPL): {aapl_quote}")
        print(f"=> Giá hiện tại (Current Price - c): {aapl_quote.get('c')}")
