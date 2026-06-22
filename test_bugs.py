import urllib.request
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8000"

def print_header(title):
    print(f"\n{'='*50}\n🚀 ĐANG TEST: {title}\n{'='*50}")

def test_endpoint(name, path):
    url = f"{BASE_URL}{path}"
    print(f"\n👉 Gửi request tới: {url}")
    try:
        start_time = time.time()
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode())
            elapsed = time.time() - start_time
            print(f"✅ TRẠNG THÁI: Thành công (200 OK) trong {elapsed:.2f}s")
            
            # Print a snippet of the data
            data_str = json.dumps(data, ensure_ascii=False, indent=2)
            if len(data_str) > 300:
                print(f"📦 DỮ LIỆU TRẢ VỀ (Trích xuất):\n{data_str[:300]}...\n  [... CÒN NỮA ...]")
            else:
                print(f"📦 DỮ LIỆU TRẢ VỀ:\n{data_str}")
            return True
    except urllib.error.HTTPError as e:
        print(f"❌ THẤT BẠI: Lỗi HTTP {e.code} - {e.reason}")
        print(f"Chi tiết: {e.read().decode('utf-8', errors='ignore')}")
        return False
    except Exception as e:
        print(f"❌ THẤT BẠI: Không thể kết nối. Lỗi: {str(e)}")
        return False

def main():
    print("BẮT ĐẦU CHƯƠNG TRÌNH TEST BUG FORECAST AI V2\n" + "-"*50)
    
    # 1. Test YFinance / Market Overview
    print_header("1. MARKET OVERVIEW (Test Lỗi Float/NaN của YFinance)")
    test_endpoint("Market Overview", "/market/overview")
    
    # 2. Test Forecasting
    print_header("2. FORECASTING ENGINE (Test Lỗi Model TFT & Crypto_Feeds)")
    test_endpoint("Forecast BTC-USD", "/forecast/combined/BTC-USD?days=7")
    
    # 3. Test Research Agent (Gemini API)
    print_header("3. GEMINI AI RESEARCH (Test Lỗi Thiếu API Key & 500 Error)")
    test_endpoint("Research BTC-USD", "/research/BTC-USD?force=false")

    print("\n" + "="*50)
    print("✅ HOÀN TẤT KIỂM TRA!")

if __name__ == "__main__":
    main()
