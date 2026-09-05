"""
train_sentiment_fusion.py – Huấn luyện SentimentFusionEngine.

────────────────────────────────────────────────────────────────────────────────
VÌ SAO DÙNG SENTIMENT "BÁN TỔNG HỢP" (SEMI-SYNTHETIC)

SentimentFusionEngine cần dữ liệu dạng (dự báo TFT, tín hiệu sentiment, giá THẬT
xảy ra sau đó) để học cách kết hợp hai nguồn tín hiệu. Vấn đề: hệ thống không có
kho sentiment lịch sử thật trải dài nhiều năm — bảng `research_reports` chỉ mới
được backfill gần đây, không có tin tức của quá khứ xa cho từng ngày cụ thể của
104 mã. Vì vậy không thể "phát lại" lịch sử với tin tức thật.

Giải pháp: GIÁ vẫn là giá THẬT 100% (không có gì tổng hợp ở đây), chỉ có
sentiment_score/confidence là được SINH RA có kiểm soát:

  - Với xác suất tỉ lệ thuận theo `confidence` (ngẫu nhiên mỗi mẫu), sentiment
    được sinh ra "đoán đúng hướng" biến động giá thật sắp xảy ra sau đó.
  - Với xác suất còn lại, sentiment bị làm nhiễu/sai (không phản ánh đúng thực tế).

Nhờ cách này, model học đúng bài học cốt lõi mà một cơ chế fusion cần có:
**"tín hiệu confidence càng cao thì càng đáng tin cậy, nên điều chỉnh dự báo TFT
mạnh hơn theo hướng đó; confidence thấp thì gần như bỏ qua, giữ nguyên TFT."**
Đây chính là hành vi cần thiết khi sau này thay bằng sentiment THẬT từ LLM
Research Agent lúc inference — hàm ánh xạ (confidence -> mức độ tin tưởng) được
học từ đây vẫn đúng, dù lúc train sentiment là giả lập.

GIỚI HẠN CẦN NÊU RÕ TRONG BÁO CÁO: vì sentiment lúc train là tổng hợp, model
không học được MỐI LIÊN HỆ GIỮA NỘI DUNG TIN TỨC CỤ THỂ và biến động giá (việc đó
là nhiệm vụ của LLM Research Agent, không phải của tầng fusion này) — tầng fusion
chỉ học cách "cân trọng số" giữa hai nguồn tín hiệu theo độ tin cậy được khai báo.

────────────────────────────────────────────────────────────────────────────────
YÊU CẦU TRƯỚC KHI CHẠY

Script này gọi `run_tft_forecast()` — tức là DÙNG CHÍNH model TFT hiện tại
(models/global_tft.keras) để sinh dự báo 7 ngày tại nhiều mốc thời gian lịch sử
(anchor date), rồi so với giá thật đã biết sau đó. Vì vậy:

  1. PHẢI chạy sau khi đã train lại TFT với target mới (% return):
         python -m backend.train_tft --fresh
     Nếu train_sentiment_fusion chạy với TFT còn dùng target giá tuyệt đối cũ,
     dữ liệu train của fusion sẽ kế thừa toàn bộ lỗi lệch scale đã sửa.

  2. Với mỗi anchor date, script CHỈ dùng dữ liệu giá TÍNH ĐẾN anchor date đó để
     dự báo (không dùng dữ liệu tương lai) — tránh rò rỉ dữ liệu.

────────────────────────────────────────────────────────────────────────────────
CÁCH DÙNG

    python -m backend.train_sentiment_fusion                       # mặc định
    python -m backend.train_sentiment_fusion --tickers AAPL,BTC-USD
    python -m backend.train_sentiment_fusion --anchors-per-ticker 15 --max-tickers 40
"""

from __future__ import annotations  # cho phép cú pháp `list[str] | None` trên Python < 3.10

import argparse
import os
import sys

import numpy as np
import pandas as pd

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

# Khi stdout được redirect ra file (vd: `python -m ... *> log.txt` trong PowerShell),
# Python KHÔNG dùng UTF-8 nữa mà rơi về bảng mã mặc định của hệ thống (cp1258 trên
# Windows tiếng Việt) — bảng mã này thiếu một số ký tự có dấu, khiến script crash
# ngay dòng print() đầu tiên có tiếng Việt. Ép UTF-8 tường minh để in ra màn hình
# lẫn ghi ra file đều hoạt động như nhau.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.train_tft import LOOK_BACK, SKIP_FILES, TRAIN_RATIO

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")

FORECAST_DAYS = 7

# Ngưỡng clip nhãn lấy TRỰC TIẾP từ sentiment_fusion.py thay vì viết lại hằng số
# ở đây — nếu hai nơi lệch nhau, model sẽ được dạy những nhãn nằm ngoài biên độ mà
# lớp đầu ra có thể biểu diễn (tanh * MAX_ADJUSTMENT), gây bão hoà âm thầm.
from backend.models.sentiment_fusion import MAX_ADJUSTMENT, normalize_price_sequence


# ══════════════════════════════════════════════════════════════════════════════
#  SINH SENTIMENT BÁN TỔNG HỢP
# ══════════════════════════════════════════════════════════════════════════════

def synth_sentiment(rng: np.random.Generator, actual_direction: int) -> tuple[float, float]:
    """
    Sinh (sentiment_score, confidence) có kiểm soát độ chính xác theo confidence.

    `actual_direction`: +1 nếu giá thật sau đó tăng, -1 nếu giảm, 0 nếu gần như
    đứng yên (trường hợp này sentiment không có "đáp án đúng" rõ ràng — sinh ngẫu
    nhiên hoàn toàn để tránh dạy model một hướng không có cơ sở).
    """
    confidence = float(rng.uniform(0.05, 0.98))

    if actual_direction == 0:
        sentiment = float(rng.uniform(-1, 1))
        return sentiment, confidence

    # Xác suất sentiment "đoán đúng hướng" tỉ lệ thuận với confidence được sinh ra.
    # Ở confidence ~0: gần như đoán ngẫu nhiên (50/50). Ở confidence ~1: gần như
    # luôn đoán đúng hướng. Đây là giả định cốt lõi của cách tiếp cận.
    correct_prob = 0.5 + 0.45 * confidence
    is_correct = rng.random() < correct_prob

    direction = actual_direction if is_correct else -actual_direction
    # Biên độ sentiment cũng dao động ngẫu nhiên quanh hướng đã chọn, không cố định.
    magnitude = float(rng.uniform(0.3, 1.0))
    sentiment = direction * magnitude

    return sentiment, confidence


def compute_technical_signals(df: pd.DataFrame) -> np.ndarray:
    """3 tín hiệu kỹ thuật cuối cùng của market_signals: rsi_z, macd_dir, bb_pos."""
    close = df["Close"].astype(float)

    delta = close.diff()
    gain = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
    # Ưu tiên dùng lại cột RSI đã tính sẵn bởi add_technical_indicators() — ĐÚNG như
    # đường suy luận làm (extract_market_signals đọc df["RSI"] nếu có). Nếu tự tính
    # lại ở đây bằng công thức cũ, mã có giai đoạn giá đứng yên sẽ cho rs = 0 → RSI = 0
    # → rsi_z = -1.0 ("quá bán tối đa"), trong khi lúc chạy thật cùng mã đó lại nhận
    # RSI = 50 → rsi_z = 0 (trung tính). Model học trên một phân phối đầu vào khác
    # hẳn phân phối nó gặp khi chạy thật — đúng lớp lỗi lệch train/inference đã sửa
    # ở TFT, nếu để nguyên thì bản vá RSI không hề bảo vệ được nhánh SentimentFusion.
    if "RSI" in df.columns and pd.notna(df["RSI"].iloc[-1]):
        rsi = float(df["RSI"].iloc[-1])
    else:
        rs = gain / (loss + 1e-8)
        rsi = (100 - 100 / (1 + rs)).iloc[-1]
    rsi_z = (rsi - 50) / 50

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    macd_dir = float(np.sign((macd - macd_signal).iloc[-1]))

    ma20 = close.rolling(20).mean().iloc[-1]
    std20 = close.rolling(20).std().iloc[-1]
    current = close.iloc[-1]
    band_width = 4 * std20
    bb_pos = float(np.clip((current - ma20) / (band_width / 2), -1, 1)) if band_width > 0 else 0.0

    return np.array([rsi_z, macd_dir, bb_pos], dtype=np.float32)


# ══════════════════════════════════════════════════════════════════════════════
#  DỰNG DATASET
# ══════════════════════════════════════════════════════════════════════════════

def build_dataset(
    tickers: list[str],
    anchors_per_ticker: int,
    days: int = FORECAST_DAYS,
    seed: int = 42,
):
    """
    Với mỗi mã, chọn nhiều mốc thời gian (anchor) trong lịch sử, tại mỗi mốc:
      1. Chỉ dùng dữ liệu TÍNH ĐẾN mốc đó -> chạy run_tft_forecast (autoregressive,
         y hệt cách production dùng) để lấy dự báo `days` ngày tới.
      2. So dự báo đó với giá THẬT đã biết sau mốc đó -> tính adjustment mục tiêu:
             target[k] = clip((giá_thật[k] - giá_TFT[k]) / giá_TFT[k], -0.05, 0.05)
      3. Sinh sentiment bán tổng hợp dựa trên hướng biến động thật (xem synth_sentiment).
    """
    from backend.models.feature_engineering import add_technical_indicators
    from backend.models.forecaster import run_tft_forecast

    rng = np.random.default_rng(seed)

    X_prices, X_signals, Y_adjust = [], [], []
    n_used_tickers = 0

    for ticker in tickers:
        path = os.path.join(DATA_DIR, f"{ticker}.csv")
        if not os.path.exists(path):
            continue
        try:
            df = pd.read_csv(path, index_col="Date", parse_dates=True).sort_index()
        except Exception:
            continue
        if df.empty or "Close" not in df.columns:
            continue

        # Chỉ lấy mốc thời gian nằm trong phần dữ liệu "chưa từng dùng để train TFT"
        # (giống VALIDATION_GAP+15% cuối) để cách đánh giá nhất quán với evaluate_tft.py,
        # đồng thời để lại đủ `days` phiên phía sau mỗi anchor để biết giá thật.
        split_idx = int(len(df) * TRAIN_RATIO)
        usable_end = len(df) - days - 1
        usable_start = split_idx + LOOK_BACK
        if usable_start >= usable_end:
            continue

        candidate_positions = np.arange(usable_start, usable_end)
        if len(candidate_positions) == 0:
            continue
        n_pick = min(anchors_per_ticker, len(candidate_positions))
        anchor_positions = rng.choice(candidate_positions, size=n_pick, replace=False)

        ticker_used = False
        for pos in sorted(anchor_positions):
            history_df = df.iloc[: pos + 1]  # chỉ dữ liệu TÍNH ĐẾN anchor, không rò rỉ tương lai
            future_closes = df["Close"].iloc[pos + 1 : pos + 1 + days].values
            if len(future_closes) < days:
                continue

            tft_median, _, _ = run_tft_forecast(ticker, days=days, df=history_df)
            if tft_median is None or len(tft_median) < days:
                continue
            tft_prices = tft_median.values[:days].astype(np.float64)

            actual_return_pct = (future_closes[-1] - history_df["Close"].iloc[-1]) / history_df["Close"].iloc[-1]
            if abs(actual_return_pct) < 0.002:
                actual_direction = 0
            else:
                actual_direction = 1 if actual_return_pct > 0 else -1

            sentiment, confidence = synth_sentiment(rng, actual_direction)

            try:
                featured = add_technical_indicators(history_df)
                tech = compute_technical_signals(featured.dropna())
            except Exception:
                tech = np.zeros(3, dtype=np.float32)

            signals = np.array([sentiment, confidence, *tech], dtype=np.float32)

            target = np.clip((future_closes - tft_prices) / tft_prices, -MAX_ADJUSTMENT, MAX_ADJUSTMENT)

            # Đầu vào phải chuẩn hoá y hệt lúc suy luận — dùng chung hàm với
            # SentimentFusionEngine.predict() để hai bên không bao giờ lệch nhau.
            X_prices.append(normalize_price_sequence(tft_prices))
            X_signals.append(signals)
            Y_adjust.append(target.astype(np.float32))
            ticker_used = True

        if ticker_used:
            n_used_tickers += 1
            print(f"  {ticker}: OK")

    # Chú ý: phải trả về ĐÚNG 2 giá trị ở mọi nhánh, vì hàm gọi unpack thành
    # `data, n_tickers`. Trả về (None, None, None) ở nhánh lỗi sẽ gây
    # ValueError: too many values to unpack — crash ngay khi không dựng được mẫu nào.
    if not X_prices:
        return None, 0

    return (
        np.array(X_prices, dtype=np.float32),
        np.array(X_signals, dtype=np.float32),
        np.array(Y_adjust, dtype=np.float32),
    ), n_used_tickers


# ══════════════════════════════════════════════════════════════════════════════
#  HUẤN LUYỆN
# ══════════════════════════════════════════════════════════════════════════════

def train_sentiment_fusion(
    tickers: list[str] | None = None,
    anchors_per_ticker: int = 12,
    days: int = FORECAST_DAYS,
    epochs: int = 60,
) -> None:
    import tensorflow as tf
    from sklearn.model_selection import train_test_split
    from tensorflow.keras.callbacks import EarlyStopping

    from backend.models.sentiment_fusion import build_sentiment_fusion_model

    # Cố định seed cho TensorFlow/Keras: khởi tạo trọng số và mặt nạ Dropout vốn lấy
    # từ RNG toàn cục CHƯA seed của TF, nên chạy lại cùng script trên cùng dữ liệu
    # vẫn ra Val MSE/MAE khác. Số liệu báo cáo phải tái lập được.
    tf.keras.utils.set_random_seed(42)

    if tickers is None:
        tickers = sorted(
            f[:-4] for f in os.listdir(DATA_DIR) if f.endswith(".csv") and f[:-4] not in SKIP_FILES
        )

    print("=" * 70)
    print("DỰNG DỮ LIỆU HUẤN LUYỆN SENTIMENT FUSION")
    print(f"  Số mã ứng viên:        {len(tickers)}")
    print(f"  Anchor mỗi mã:         {anchors_per_ticker}")
    print(f"  Horizon dự báo:        {days} ngày")
    print("  (mỗi anchor chạy 1 lượt run_tft_forecast autoregressive — có thể mất nhiều phút)")
    print("=" * 70)

    data, n_tickers = build_dataset(tickers, anchors_per_ticker, days=days)
    if data is None:
        print("Không dựng được mẫu nào — kiểm tra lại models/global_tft.keras đã tồn tại chưa.")
        return

    X_prices, X_signals, Y = data
    print(f"\nTổng số mẫu: {len(X_prices)} (từ {n_tickers} mã)")

    if len(X_prices) < 30:
        print("Quá ít mẫu để train một cách ổn định — tăng --anchors-per-ticker hoặc --max-tickers.")
        return

    Xp_train, Xp_val, Xs_train, Xs_val, Y_train, Y_val = train_test_split(
        X_prices, X_signals, Y, test_size=0.15, random_state=42
    )

    model = build_sentiment_fusion_model(forecast_days=days)
    model.summary()

    print("\nBắt đầu huấn luyện SentimentFusion...")
    model.fit(
        [Xp_train, Xs_train],
        Y_train,
        validation_data=([Xp_val, Xs_val], Y_val),
        epochs=epochs,
        batch_size=32,
        callbacks=[EarlyStopping(monitor="val_loss", patience=10, restore_best_weights=True)],
        verbose=1,
    )

    os.makedirs(MODELS_DIR, exist_ok=True)
    model_path = os.path.join(MODELS_DIR, f"sentiment_fusion_{days}d.keras")
    model.save(model_path)

    val_loss, val_mae = model.evaluate([Xp_val, Xs_val], Y_val, verbose=0)

    print("\n" + "=" * 70)
    print("HOÀN TẤT HUẤN LUYỆN SENTIMENT FUSION")
    print(f"  Mô hình:       {model_path}")
    print(f"  Val MSE:       {val_loss:.6f}")
    print(f"  Val MAE:       {val_mae:.6f}  (đơn vị: tỷ lệ điều chỉnh, 0.01 = 1%)")
    print(f"  Số mẫu train:  {len(Xp_train)}")
    print(f"  Số mẫu val:    {len(Xp_val)}")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Huấn luyện SentimentFusionEngine")
    parser.add_argument("--tickers", type=str, default=None, help="Danh sách mã, phân tách bằng dấu phẩy")
    parser.add_argument("--max-tickers", type=int, default=None, help="Giới hạn số mã (để chạy nhanh thử nghiệm)")
    parser.add_argument("--anchors-per-ticker", type=int, default=12, help="Số mốc thời gian lấy mẫu mỗi mã")
    parser.add_argument("--days", type=int, default=FORECAST_DAYS, help="Horizon dự báo (mặc định 7)")
    parser.add_argument("--epochs", type=int, default=60)
    args = parser.parse_args()

    if args.tickers:
        tick_list = [t.strip() for t in args.tickers.split(",") if t.strip()]
    else:
        tick_list = sorted(
            f[:-4] for f in os.listdir(DATA_DIR) if f.endswith(".csv") and f[:-4] not in SKIP_FILES
        )
        if args.max_tickers:
            tick_list = tick_list[: args.max_tickers]

    train_sentiment_fusion(
        tickers=tick_list,
        anchors_per_ticker=args.anchors_per_ticker,
        days=args.days,
        epochs=args.epochs,
    )
