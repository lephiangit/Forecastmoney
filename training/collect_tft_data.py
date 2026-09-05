"""
training/collect_tft_data.py – Tải lại TOÀN BỘ dữ liệu OHLCV cho model TFT, thay thế
các file CSV cũ trong data/ bằng dữ liệu SẠCH và ĐẦY ĐỦ hơn (lấy tối đa lịch sử có sẵn
từ yfinance thay vì khoảng thời gian ngắn như trước).

LÝ DO PHẢI CHẠY SCRIPT NÀY (không chỉ là "thêm cho vui")
---------------------------------------------------------
44/107 file CSV hiện có trong data/ đang bị HỎNG: các cột Close/High/Low/Open/Volume
bị TRÙNG TÊN nhiều lần (ví dụ FPT.VN.csv có tới 7 cột "Close" khác nhau). Đây là hậu
quả của một lần tải dữ liệu nhiều mã cùng lúc qua yfinance trước đây mà không tách
đúng cột theo từng mã — dữ liệu của NHIỀU MÃ KHÁC NHAU bị gộp lẫn vào chung một file.

Hậu quả cụ thể: `backend/train_tft.py` gọi `add_technical_indicators()` trên các file
này sẽ CRASH với lỗi:
    ValueError: Cannot set a DataFrame with multiple columns to the single column RSI
Vì `AAPL.csv` (xếp đầu theo alphabet) nằm trong số bị hỏng, script train sẽ crash
NGAY LẬP TỨC ở file đầu tiên — nghĩa là hiện tại KHÔNG THỂ chạy train_tft.py thành
công cho tới khi sửa xong việc này. Đã tự kiểm chứng bằng pandas thật, không phải suy
đoán.

Không có cách nào "cứu" dữ liệu cũ trong các file hỏng — vì không thể biết chắc cột
nào trong số các cột trùng tên mới thực sự là dữ liệu của đúng mã trong tên file (có
thể là dữ liệu của 2-3 mã hoàn toàn khác nhau bị gộp lẫn). Cách an toàn duy nhất là
TẢI LẠI TỪ ĐẦU cho mọi mã, không chỉ 44 mã hỏng.

CHẠY Ở ĐÂU: máy bạn (venv), không chạy được từ môi trường Claude (mạng bị chặn).

CÁCH DÙNG
---------
    cd ForecastAI
    venv\\Scripts\\activate
    python training/collect_tft_data.py

Mặc định GHI ĐÈ trực tiếp vào thư mục data/ ở gốc dự án (đúng nơi train_tft.py đọc).
File cũ được backup trước khi ghi đè vào data/_backup_<timestamp>/ — lỡ có gì bất
thường vẫn khôi phục lại được.

Muốn tải thêm mã khác ngoài danh sách mặc định, sửa EXTRA_TICKERS bên dưới.
"""

import io
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print("Thiếu pandas. Cài bằng: pip install pandas")
    sys.exit(1)

try:
    import yfinance as yf
except ImportError:
    print("Thiếu yfinance. Cài bằng: pip install yfinance")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# Danh sách mã HIỆN CÓ trong data/ (giữ nguyên độ phủ đang có, chỉ tải lại cho sạch +
# lấy thêm lịch sử) — loại bỏ 3 file rác cũ (bitcoin_data, bitcoin_data_global,
# merged_data) vốn đã bị train_tft.py bỏ qua từ trước (xem SKIP_FILES trong đó).
EXISTING_TICKERS = [
    "AAPL", "ABBV", "ABNB", "ACB.VN", "ADA-USD", "ADBE", "ALGO-USD", "AMD", "AMZN",
    "ARKK", "ATOM-USD", "AVAX-USD", "AVGO", "BAC", "BCH-USD", "BID.VN", "BNB-USD",
    "BRK-B", "BTC-USD", "BVH.VN", "COIN", "COST", "CRM", "CRWD", "CSCO", "CTG.VN",
    "CVX", "DIA", "DIS", "DOCU", "DOGE-USD", "DOT-USD", "ETH-USD", "FPT.VN", "GAS.VN",
    "GLD", "GOOGL", "GVR.VN", "HD", "HOOD", "HPG.VN", "INTC", "IWM", "JNJ", "JPM",
    "KO", "LINK-USD", "LLY", "LTC-USD", "MA", "MANA-USD", "MATIC-USD", "MBB.VN",
    "MCD", "META", "MRK", "MSFT", "MSN.VN", "MWG.VN", "NFLX", "NVDA", "PEP", "PFE",
    "PG", "PLTR", "PLX.VN", "PNJ.VN", "POW.VN", "PYPL", "QCOM", "QQQ", "ROKU",
    "SAB.VN", "SAND-USD", "SHOP", "SNOW", "SOL-USD", "SPY", "SSI.VN", "STB.VN",
    "TCB.VN", "THETA-USD", "TMO", "TSLA", "TXN", "UBER", "UNH", "V", "VCB.VN", "VEA",
    "VET-USD", "VHM.VN", "VIC.VN", "VJC.VN", "VNM.VN", "VOO", "VPB.VN", "VRE.VN",
    "VTI", "VWO", "WMT", "XLM-USD", "XRP-USD", "ZM",
]

# ══════════════════════════════════════════════════════════════════════════════
#  MỞ RỘNG DỮ LIỆU HUẤN LUYỆN
# ══════════════════════════════════════════════════════════════════════════════
#
# Vì sao mở rộng: mô hình TFT là GLOBAL (một bộ trọng số dùng chung cho mọi mã), nên
# thêm mã là thêm mẫu huấn luyện thật chứ không phải thêm nhiễu — mô hình học được
# các dạng vận động giá phổ biến trên nhiều loại tài sản, nhiều mức biến động và
# nhiều chế độ thị trường khác nhau.
#
# Ưu tiên chọn mã có LỊCH SỬ DÀI (blue-chip Mỹ và ETF chỉ số có hàng chục năm dữ
# liệu) vì mỗi mã như vậy đóng góp vài nghìn phiên, trong khi một mã mới niêm yết
# chỉ đóng góp vài trăm. Sau khi chuyển sang chia ba tập, mỗi mã cần tối thiểu
# ~1.224 phiên (~5 năm) mới dùng được — xem MIN_ROWS_FOR_SPLIT trong train_tft.py.
#
# Mã nào yfinance không trả về dữ liệu sẽ được báo ở cuối và bỏ qua, không làm hỏng
# lượt chạy. Danh sách .VN có rủi ro cao nhất vì Yahoo phủ thị trường Việt Nam
# không đầy đủ.

# ── Cổ phiếu Mỹ vốn hoá lớn, lịch sử dài (mỗi mã thường 5.000-15.000 phiên) ──
_US_STOCKS = [
    "ORCL", "IBM", "GE", "F", "GM", "T", "VZ", "XOM", "COP", "SLB",
    "CAT", "DE", "BA", "LMT", "RTX", "HON", "MMM", "UPS", "FDX", "NKE",
    "SBUX", "TGT", "LOW", "CVS", "ABT", "DHR", "BMY", "AMGN", "GILD", "ISRG",
    "SYK", "MDT", "BLK", "GS", "MS", "C", "WFC", "AXP", "SCHW", "SPGI",
    "ADP", "INTU", "MU", "ADI", "AMAT", "LRCX", "KLAC", "NOW", "SNPS", "CDNS",
    "EA", "TTWO", "MAR", "BKNG", "ORLY", "AZO", "DG", "DLTR", "KR", "SYY",
    "MDLZ", "GIS", "HSY", "CL", "KMB", "STZ", "MO", "PM", "DUK", "SO",
    "NEE", "D", "AEP", "PLD", "AMT", "CCI", "SPG", "O", "WM", "EMR",
    "ITW", "GD", "NOC", "TRV", "ALL", "PGR", "MET", "PRU", "AIG", "USB",
    "PNC", "TFC", "COF",
]

# ── ETF theo ngành và lớp tài sản: bổ sung chế độ thị trường mà cổ phiếu đơn lẻ
#    không có (trái phiếu, hàng hoá, bất động sản) ──
_ETFS = [
    "EFA", "EEM", "AGG", "BND", "TLT", "LQD", "HYG", "XLK", "XLF", "XLE",
    "XLV", "XLI", "XLY", "XLP", "XLU", "XLB", "SMH", "VNQ", "SLV", "IJH",
    "IJR", "MDY", "RSP", "VUG", "VTV", "VIG", "SCHD", "VYM",
]

# ── Crypto: biến động cao, giao dịch 7 ngày/tuần — chế độ hoàn toàn khác cổ phiếu ──
_CRYPTO = [
    "TRX-USD", "EOS-USD", "XTZ-USD", "NEO-USD", "IOTA-USD", "QTUM-USD",
    "ZIL-USD", "ENJ-USD", "BAT-USD", "ZEC-USD", "DASH-USD", "WAVES-USD",
    "ONT-USD", "ICX-USD", "OMG-USD", "DGB-USD", "RVN-USD", "HBAR-USD",
    "FIL-USD", "GRT-USD", "AAVE-USD", "UNI-USD", "SNX-USD", "CRV-USD",
    "COMP-USD", "MKR-USD", "YFI-USD", "SUSHI-USD", "EGLD-USD", "NEAR-USD",
    "FTM-USD", "RUNE-USD", "KAVA-USD", "CHZ-USD",
]

# ── Cổ phiếu Việt Nam: quan trọng cho phần liên hệ thị trường trong nước của đồ án.
#    Yahoo phủ thị trường VN không đầy đủ nên nhóm này dễ tải hỏng nhất — mã nào
#    không có dữ liệu sẽ tự bị bỏ qua. ──
_VN_STOCKS = [
    "HDB.VN", "TPB.VN", "SHB.VN", "LPB.VN", "EIB.VN", "MSB.VN", "VIB.VN",
    "OCB.VN", "NVL.VN", "PDR.VN", "DXG.VN", "KDH.VN", "DIG.VN", "CII.VN",
    "REE.VN", "PC1.VN", "NT2.VN", "PPC.VN", "BSR.VN", "PVD.VN", "PVS.VN",
    "PVT.VN", "DCM.VN", "DPM.VN", "DGC.VN", "HSG.VN", "NKG.VN", "HT1.VN",
    "KDC.VN", "DBC.VN", "ANV.VN", "VHC.VN", "PTB.VN", "TCM.VN", "TNG.VN",
    "GMD.VN", "VSC.VN", "HAH.VN", "HVN.VN", "SCS.VN", "DGW.VN", "FRT.VN",
    "PET.VN", "VGC.VN", "VCI.VN", "HCM.VN", "VND.VN", "SHS.VN", "MBS.VN",
    "VIX.VN",
]

EXTRA_TICKERS: list = _US_STOCKS + _ETFS + _CRYPTO + _VN_STOCKS

TICKERS = sorted(set(EXISTING_TICKERS + EXTRA_TICKERS))

# yfinance hỗ trợ tối đa "max" cho hầu hết mã — lấy toàn bộ lịch sử có sẵn thay vì
# giới hạn 1-2 năm như trước, để model có nhiều dữ liệu train hơn.
PERIOD = "max"
INTERVAL = "1d"

MIN_ROWS_OK = 200  # dưới mức này coi là đáng ngờ (mã mới niêm yết, hoặc lỗi ticker)


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Giống hệt backend/models/forecaster.py::_flatten_columns — yfinance trả về
    MultiIndex cột kể cả khi chỉ tải một mã ở các phiên bản mới. Đây chính xác là
    bước bị THIẾU trong lần tải dữ liệu cũ gây ra lỗi trùng cột đang phải sửa hôm nay."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def fetch_one(ticker: str) -> "pd.DataFrame | None":
    try:
        df = yf.download(ticker, period=PERIOD, interval=INTERVAL, progress=False, auto_adjust=True)
    except Exception as e:
        print(f"  [lỗi] {ticker}: {type(e).__name__}: {e}")
        return None

    if df is None or df.empty:
        print(f"  [rỗng] {ticker}: không có dữ liệu trả về")
        return None

    df = _flatten_columns(df)

    # Xác nhận không còn trùng cột — đây chính là lỗi đã gây hỏng dữ liệu cũ, kiểm
    # tra lại một lần nữa cho chắc trước khi ghi file.
    if len(df.columns) != len(set(df.columns)):
        print(f"  [cảnh báo] {ticker}: vẫn phát hiện cột trùng tên sau khi flatten — bỏ qua, không ghi đè.")
        return None

    required = {"Open", "High", "Low", "Close", "Volume"}
    if not required.issubset(set(df.columns)):
        print(f"  [cảnh báo] {ticker}: thiếu cột bắt buộc {required - set(df.columns)} — bỏ qua.")
        return None

    df.index.name = "Date"
    return df


def main():
    if not DATA_DIR.exists():
        print(f"Không tìm thấy thư mục '{DATA_DIR}' — chạy script từ đúng thư mục gốc dự án.")
        sys.exit(1)

    # Backup nằm NGOÀI data/ (không phải data/_backup_...) để train_tft.py (đọc mọi
    # *.csv trong data/) không vô tình đọc nhầm file backup làm dữ liệu training.
    backup_dir = PROJECT_ROOT / f"data_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    print(f"Backup {len(list(DATA_DIR.glob('*.csv')))} file CSV hiện có vào '{backup_dir}' trước khi ghi đè...")
    for f in DATA_DIR.glob("*.csv"):
        shutil.copy2(f, backup_dir / f.name)

    print(f"\nTải lại {len(TICKERS)} mã, period='{PERIOD}', interval='{INTERVAL}'...\n")

    ok, failed, suspicious = [], [], []
    for i, ticker in enumerate(TICKERS, start=1):
        df = fetch_one(ticker)
        if df is None:
            failed.append(ticker)
            continue

        out_path = DATA_DIR / f"{ticker}.csv"
        df.to_csv(out_path)

        date_range = f"{df.index[0].date()} → {df.index[-1].date()}"
        flag = ""
        if len(df) < MIN_ROWS_OK:
            suspicious.append(ticker)
            flag = "  [ÍT DỮ LIỆU — kiểm tra lại mã này]"
        print(f"  [{i}/{len(TICKERS)}] {ticker}: {len(df)} phiên ({date_range}){flag}")
        ok.append(ticker)

        # yfinance giới hạn tốc độ nếu gọi quá dồn dập — nghỉ nhẹ giữa các mã.
        time.sleep(0.3)

    print(f"\n{'=' * 60}")
    print(f"Hoàn tất: {len(ok)}/{len(TICKERS)} mã tải thành công.")
    if suspicious:
        print(f"Ít dữ liệu bất thường ({len(suspicious)}): {', '.join(suspicious)}")
    if failed:
        print(f"Thất bại ({len(failed)}): {', '.join(failed)}")
        print("(mã thất bại giữ nguyên file cũ trong data/ — không bị xoá, chỉ là chưa được làm mới)")
    print(f"\nBackup dữ liệu cũ nằm ở: {backup_dir}")
    print("Kiểm tra ổn rồi thì có thể xoá thư mục backup này để đỡ tốn dung lượng.")
    print("\nGiờ chạy 'python backend/train_tft.py' để train lại với dữ liệu đã sạch + đầy đủ hơn.")


if __name__ == "__main__":
    main()
