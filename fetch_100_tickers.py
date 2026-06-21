import os
import yfinance as yf
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

# Thư mục lưu dữ liệu
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Danh sách 100+ mã (US Tech, Crypto, VN30, ETF)
TICKERS = [
    # Top US Tech & Bluechips (30)
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "BRK-B", "V", "UNH",
    "JNJ", "WMT", "PG", "JPM", "MA", "HD", "CVX", "ABBV", "LLY", "MRK",
    "PEP", "KO", "BAC", "AVGO", "COST", "TMO", "CSCO", "MCD", "PFE", "CRM",
    
    # Growth & Others (20)
    "DIS", "NFLX", "AMD", "INTC", "QCOM", "TXN", "ADBE", "PYPL", "SQ", "SHOP",
    "UBER", "ABNB", "SNOW", "PLTR", "ROKU", "COIN", "HOOD", "ZM", "DOCU", "CRWD",
    
    # ETFs (10)
    "SPY", "QQQ", "DIA", "IWM", "ARKK", "VTI", "VOO", "VEA", "VWO", "GLD",
    
    # Top Crypto (20)
    "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "ADA-USD", "XRP-USD", "DOGE-USD", 
    "DOT-USD", "MATIC-USD", "AVAX-USD", "LINK-USD", "LTC-USD", "BCH-USD", "XLM-USD", 
    "ALGO-USD", "ATOM-USD", "VET-USD", "MANA-USD", "SAND-USD", "THETA-USD",
    
    # VN30 & Top Vietnam (25)
    "VCB.VN", "BID.VN", "CTG.VN", "VPB.VN", "TCB.VN", "MBB.VN", "ACB.VN", "STB.VN",
    "VIC.VN", "VHM.VN", "VRE.VN", "VNM.VN", "MSN.VN", "SAB.VN", "HPG.VN", "GVR.VN",
    "FPT.VN", "MWG.VN", "SSI.VN", "VJC.VN", "PNJ.VN", "POW.VN", "GAS.VN", "PLX.VN", "BVH.VN"
]

def fetch_and_save(ticker):
    try:
        # Lấy lịch sử tối đa (max) để có nhiều data nhất có thể
        df = yf.download(ticker, period="max", interval="1d", progress=False, auto_adjust=True, threads=False)
        
        if df is None or df.empty:
            return f"⚠️ {ticker}: Không có dữ liệu"
            
        # Clean MultiIndex for newer yfinance versions
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
            
        df = df.dropna(subset=["Close"])
        if len(df) < 100:
            return f"⚠️ {ticker}: Dữ liệu quá ít ({len(df)} dòng)"
            
        # Xóa timezone
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
            
        file_path = os.path.join(DATA_DIR, f"{ticker}.csv")
        df.to_csv(file_path)
        return f"✅ {ticker}: Đã lưu {len(df)} dòng"
        
    except Exception as e:
        return f"❌ {ticker}: Lỗi - {e}"

def main():
    print(f"🚀 Bắt đầu kéo dữ liệu cho {len(TICKERS)} mã vào thư mục data/...")
    
    # Chạy đa luồng cho lẹ
    success_count = 0
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_and_save, t): t for t in TICKERS}
        
        for future in as_completed(futures):
            result = future.result()
            print(result)
            if result.startswith("✅"):
                success_count += 1
                
    print("="*50)
    print(f"🎉 Hoàn tất! Đã tải thành công {success_count}/{len(TICKERS)} mã.")
    print(f"Dữ liệu được lưu tại: {DATA_DIR}")
    print("Bạn có thể nén thư mục data/ lại và quăng lên Kaggle được rồi!")

if __name__ == "__main__":
    main()
