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

ĐỘ CHÍNH XÁC GIẢ LẬP ĐƯỢC ĐO: xác suất "đoán đúng hướng" theo confidence không còn là
hằng số tự đặt (0.45) mà được đo trên research_reports thật của LLM khi đủ mẫu — xem
`measure_sentiment_accuracy`. Giá trị đã dùng được ghi vào
models/sentiment_fusion_<days>d_meta.json để trích vào báo cáo.

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

from backend.train_tft import LOOK_BACK, SKIP_FILES, TRAIN_RATIO, split_indices

# Phần vùng TEST của TFT được dùng để HUẤN LUYỆN tầng fusion. Phần còn lại giữ
# nguyên, chưa từng bị chạm tới, dành cho đánh giá end-to-end.
FUSION_TRAIN_FRACTION = 0.5

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

# ── ĐỘ CHÍNH XÁC CỦA SENTIMENT GIẢ LẬP: ĐO, KHÔNG GIẢ ĐỊNH ────────────────────
#
# LỖI PHƯƠNG PHÁP ĐÃ SỬA: `synth_sentiment()` từng dùng cứng
#     P(sentiment đúng hướng) = 0.5 + 0.45 × confidence
# tức sentiment confidence 0.98 đoán đúng hướng giá 7 phiên tới 94% số lần. Không
# có số đo nào đứng sau con số 0.45 đó. Tầng fusion học đúng thứ nó được cho: "tin
# sentiment gần như tuyệt đối khi confidence cao" — rồi đem niềm tin ấy áp lên
# sentiment THẬT của LLM lúc chạy, thứ chắc chắn kém xa 94%. Đây là phần "học kèm
# đáp án" còn sót lại của tầng fusion.
#
# Nay hệ số đó được ĐO trên chính `research_reports` thật (báo cáo do LLM sinh ra,
# đã đủ `days` phiên để biết giá đi đâu). Chưa đủ mẫu thì mới dùng giả định cũ, và
# in cảnh báo rõ để không ai nhầm đó là số đo.
ASSUMED_ACCURACY_SLOPE = 0.45
MAX_ACCURACY_SLOPE = 0.45          # trần: không bao giờ tin hơn giả định cũ
MIN_CALIBRATION_SAMPLES = 100
REAL_SENTIMENT_SOURCES = ("groq", "custom", "local")  # KHÔNG gồm 'keyword'


def measure_sentiment_accuracy(days: int = FORECAST_DAYS, min_move: float = 0.002) -> dict | None:
    """
    Đo sentiment THẬT trong `research_reports` đoán đúng hướng giá `days` phiên sau
    bao nhiêu phần trăm, theo từng mức confidence, rồi khớp đúng dạng mà
    `synth_sentiment` dùng: P(đúng) = 0.5 + slope × confidence.

    Chỉ lấy nguồn LLM thật (groq/custom/local) — bản ghi 'keyword' là bộ đếm từ khoá,
    đo nó rồi gán cho LLM là sai đối tượng. Trả về None nếu không đọc được DB.
    """
    from backend.database import _get_client
    from backend.models.forecaster import fetch_ohlcv

    c = _get_client()
    if c is None:
        print("  [calibrate] Không kết nối được Supabase — bỏ qua bước đo.")
        return None

    rows, page = [], 1000
    try:
        start = 0
        while True:
            res = (
                c.table("research_reports")
                .select("ticker, sentiment_score, confidence, source, created_at")
                .in_("source", list(REAL_SENTIMENT_SOURCES))
                .order("created_at")
                .range(start, start + page - 1)
                .execute()
            )
            batch = res.data or []
            rows.extend(batch)
            if len(batch) < page:
                break
            start += page
    except Exception as e:
        print(f"  [calibrate] Lỗi đọc research_reports: {e}")
        return None

    by_ticker: dict = {}
    for r in rows:
        by_ticker.setdefault(r.get("ticker"), []).append(r)

    confs, hits = [], []
    for ticker, reports in by_ticker.items():
        if not ticker:
            continue
        prices = fetch_ohlcv(ticker, period="6mo", use_cache=False)
        if prices is None or prices.empty:
            continue
        closes = prices["Close"].astype(float)
        idx = pd.DatetimeIndex(closes.index).normalize()
        for r in reports:
            try:
                score = float(r.get("sentiment_score") or 0.0)
                conf = float(r.get("confidence") or 0.0)
                day = pd.to_datetime(r["created_at"], utc=True).tz_convert(None).normalize()
            except Exception:
                continue
            if score == 0.0:
                continue
            base = int(idx.searchsorted(day, side="right")) - 1   # phiên cuối <= ngày báo cáo
            fut = base + days
            if base < 0 or fut >= len(closes):
                continue                                          # chưa đủ `days` phiên
            p0, p1 = float(closes.iloc[base]), float(closes.iloc[fut])
            if p0 <= 0:
                continue
            ret = (p1 - p0) / p0
            if abs(ret) < min_move:
                continue                                          # giống synth: không có "đáp án"
            confs.append(min(max(conf, 0.0), 1.0))
            hits.append(1.0 if (ret > 0) == (score > 0) else 0.0)

    n = len(hits)
    if n == 0:
        return {"n": 0}
    confs_a, hits_a = np.asarray(confs), np.asarray(hits)
    denom = float(np.sum(confs_a ** 2))
    slope = float(np.sum(confs_a * (hits_a - 0.5)) / denom) if denom > 0 else 0.0
    buckets = {}
    for lo, hi in ((0.0, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)):
        m = (confs_a >= lo) & (confs_a < hi)
        if m.any():
            buckets[f"{lo:.1f}-{min(hi, 1.0):.1f}"] = {
                "n": int(m.sum()), "hit_rate": round(float(hits_a[m].mean()), 4)
            }
    return {
        "n": n,
        "hit_rate": round(float(hits_a.mean()), 4),
        "slope_raw": round(slope, 4),
        "slope": round(float(np.clip(slope, 0.0, MAX_ACCURACY_SLOPE)), 4),
        "by_confidence": buckets,
    }


def synth_sentiment(
    rng: np.random.Generator,
    actual_direction: int,
    accuracy_slope: float = ASSUMED_ACCURACY_SLOPE,
) -> tuple[float, float]:
    """
    Sinh (sentiment_score, confidence) có kiểm soát độ chính xác theo confidence.

    `accuracy_slope`: P(đúng hướng) = 0.5 + accuracy_slope × confidence. Lấy từ
    `measure_sentiment_accuracy()` khi đủ dữ liệu thật — xem khối chú thích ở trên.

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
    correct_prob = 0.5 + accuracy_slope * confidence
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
    accuracy_slope: float = ASSUMED_ACCURACY_SLOPE,
):
    """
    Với mỗi mã, chọn nhiều mốc thời gian (anchor) trong lịch sử, tại mỗi mốc:
      1. Chỉ dùng dữ liệu TÍNH ĐẾN mốc đó -> chạy run_tft_forecast (autoregressive,
         y hệt cách production dùng) để lấy dự báo `days` ngày tới.
      2. So dự báo đó với giá THẬT đã biết sau mốc đó -> tính adjustment mục tiêu:
             target[k] = clip((giá_thật[k] - giá_TFT[k]) / giá_TFT[k], -0.05, 0.05)
      3. Sinh sentiment bán tổng hợp dựa trên hướng biến động thật (xem synth_sentiment).
    """
    from backend.models.feature_engineering import (
        add_technical_indicators,
        build_model_frame,
        clean_price_history,
    )
    from backend.models.forecaster import run_tft_forecast

    rng = np.random.default_rng(seed)

    X_prices, X_signals, Y_adjust = [], [], []
    sample_tickers: list = []
    n_used_tickers = 0
    holdout_starts: list = []
    clip_stats = {"total": 0, "clipped": 0}

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

        # Làm sạch GIỐNG HỆT train_tft.py trước khi tính ranh giới tập.
        df = clean_price_history(df)
        if df.empty:
            continue

        # Anchor chỉ được lấy trong vùng TFT chưa từng thấy khi huấn luyện — dùng
        # đúng hàm chia tập của train_tft.py để không tự tính lệch.
        #
        # LỖI ĐÃ SỬA — cửa sổ tương lai chồng lấn giữa train và validation.
        # Bản cũ bốc anchor ngẫu nhiên KHÔNG ràng buộc khoảng cách, rồi ở dưới lại
        # chia train/val bằng `train_test_split` có XÁO TRỘN. Hai anchor cách nhau
        # 1-3 phiên của cùng một mã có thể rơi về hai phía của lằn chia, trong khi
        # cửa sổ giá tương lai `days` phiên của chúng chồng lên nhau gần hết — đúng
        # kiểu rò rỉ đã sửa cho TFT, tái xuất hiện ở mô hình phụ. Val MSE/MAE báo
        # cáo vì thế đẹp hơn thực tế.
        #
        # Nay: (1) hai anchor liền kề của cùng một mã cách nhau tối thiểu `days`
        # phiên nên cửa sổ tương lai không chồng nhau; (2) chia train/val THEO MÃ
        # (xem dưới) chứ không trộn ngẫu nhiên.
        # LỖI ĐÃ SỬA — ranh giới tập tính trên DataFrame THÔ.
        #
        # `train_tft.py` và `evaluate_tft.py` gọi `split_indices()` trên khung ĐÃ
        # LÀM SẠCH và đã `dropna()` (bỏ ~49 dòng đầu vì cửa sổ MA50), còn ở đây gọi
        # trên `len(df)` thô. Hai ranh giới vì thế không trùng nhau: quy về toạ độ
        # thô, ranh giới test thật là 0.85N + 0.15*49 + 120, còn ở đây tính ra
        # 0.85N + 120 — sớm hơn khoảng 7 phiên. Hiện tại độ lệch đó mới ăn vào
        # khoảng trống 60 phiên nên chưa chạm vùng validation, nhưng chỉ cần thêm
        # một mã kiểu UNI-USD (nơi clean_price_history chỉ giữ đoạn cuối) là độ lệch
        # thành hàng trăm phiên và anchor rơi thẳng vào vùng TRAIN của TFT.
        frame_for_split, _ = build_model_frame(df)
        if len(frame_for_split) < LOOK_BACK * 4:
            continue
        _, _, _, test_start_clean = split_indices(len(frame_for_split))
        # Quy vị trí trong khung đã làm sạch về vị trí trong df thô.
        try:
            test_start = df.index.get_loc(frame_for_split.index[test_start_clean])
        except (KeyError, IndexError):
            continue

        usable_end = len(df) - days - 1
        usable_start = max(test_start, LOOK_BACK)
        if usable_start >= usable_end:
            continue

        # GIỮ LẠI NỬA SAU CỦA VÙNG TEST ĐỂ ĐÁNH GIÁ END-TO-END.
        #
        # LỖI ĐÃ SỬA: anchor lấy trên TOÀN BỘ vùng test của TFT, và nhãn lấy từ giá
        # tương lai của chính vùng đó. Nghĩa là mọi số liệu báo cáo cho pipeline kết
        # hợp "TFT + SentimentFusion" đo trên tập test đều đo trên dữ liệu mà tầng
        # fusion đã học thuộc.
        #
        # Nay fusion chỉ học trên NỬA ĐẦU vùng test; nửa sau chưa từng bị chạm tới và
        # là nơi duy nhất được phép lấy số liệu end-to-end cho báo cáo.
        fusion_train_end = usable_start + int((usable_end - usable_start) * FUSION_TRAIN_FRACTION)
        if fusion_train_end <= usable_start:
            continue
        holdout_starts.append(str(df.index[fusion_train_end].date()))
        usable_end = fusion_train_end

        # CẢNH BÁO PHƯƠNG PHÁP CÒN LẠI (phải nêu trong báo cáo):
        # sentiment huấn luyện vẫn được SINH từ hướng giá thật của tương lai — không
        # có sentiment lịch sử thật cho các mốc này. Mức "đoán đúng" của nó nay được
        # ĐO trên research_reports thật (xem measure_sentiment_accuracy) thay vì giả
        # định 94%, nên tầng fusion không còn học cách tin sentiment hơn mức LLM thật
        # xứng đáng. Nhưng chỉ số Val của fusion vẫn không so trực tiếp được với TFT.
        # (Vấn đề anchor rơi vào vùng test đã xử lý ở trên: fusion chỉ học nửa đầu.)

        candidate_positions = np.arange(usable_start, usable_end, days)
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

            sentiment, confidence = synth_sentiment(rng, actual_direction, accuracy_slope)

            try:
                featured = add_technical_indicators(history_df)
                tech = compute_technical_signals(featured.dropna())
            except Exception:
                tech = np.zeros(3, dtype=np.float32)

            signals = np.array([sentiment, confidence, *tech], dtype=np.float32)

            raw_deviation = (future_closes - tft_prices) / tft_prices
            target = np.clip(raw_deviation, -MAX_ADJUSTMENT, MAX_ADJUSTMENT)
            # ĐẾM TỶ LỆ NHÃN BỊ CHẠM BIÊN.
            #
            # Với mã crypto, độ lệch tích luỹ sau 7 phiên giữa dự báo tự hồi quy và
            # giá thật thường xuyên vượt 10%, trong khi biên clip chỉ ±5%. Khi phần
            # lớn nhãn nằm đúng ở biên, model học "luôn đẩy hết biên độ về một phía"
            # và tanh bão hoà — Val MSE báo cáo nhỏ một cách giả tạo vì nhãn chỉ còn
            # hai mức, chứ không phải vì model tốt. Không đếm thì không ai biết.
            clip_stats["total"] += int(target.size)
            clip_stats["clipped"] += int(np.sum(np.abs(raw_deviation) >= MAX_ADJUSTMENT))

            # Đầu vào phải chuẩn hoá y hệt lúc suy luận — dùng chung hàm với
            # SentimentFusionEngine.predict() để hai bên không bao giờ lệch nhau.
            X_prices.append(normalize_price_sequence(tft_prices))
            X_signals.append(signals)
            Y_adjust.append(target.astype(np.float32))
            # Ghi lại mã của từng mẫu để chia train/val THEO MÃ, không trộn ngẫu nhiên.
            sample_tickers.append(ticker)
            ticker_used = True

        if ticker_used:
            n_used_tickers += 1
            print(f"  {ticker}: OK")

    # Chú ý: phải trả về ĐÚNG 2 giá trị ở mọi nhánh, vì hàm gọi unpack thành
    # `data, n_tickers`. Trả về (None, None, None) ở nhánh lỗi sẽ gây
    # ValueError: too many values to unpack — crash ngay khi không dựng được mẫu nào.
    if not X_prices:
        return None, 0

    # ── Hai con số phải báo cáo, không được giấu ──
    if clip_stats["total"]:
        pct = clip_stats["clipped"] / clip_stats["total"] * 100
        print(f"\n  Nhãn chạm biên +/-{MAX_ADJUSTMENT:.0%}: {pct:.1f}% "
              f"({clip_stats['clipped']:,}/{clip_stats['total']:,})")
        if pct > 30:
            print(
                "  CẢNH BÁO: quá nhiều nhãn nằm đúng ở biên. Khi đó nhãn chỉ còn hai mức\n"
                "  và model học 'luôn đẩy hết biên độ về một phía'; Val MSE sẽ nhỏ một cách\n"
                "  giả tạo. Cân nhắc nới MAX_ADJUSTMENT hoặc loại các anchor lệch quá lớn."
            )
    if holdout_starts:
        print(
            f"  Vùng giữ lại để đánh giá end-to-end bắt đầu từ: "
            f"{min(holdout_starts)} … {max(holdout_starts)} (tuỳ mã).\n"
            f"  Tầng fusion CHƯA từng thấy dữ liệu sau các mốc này."
        )

    return (
        np.array(X_prices, dtype=np.float32),
        np.array(X_signals, dtype=np.float32),
        np.array(Y_adjust, dtype=np.float32),
        np.array(sample_tickers),
    ), n_used_tickers


# ══════════════════════════════════════════════════════════════════════════════
#  HUẤN LUYỆN
# ══════════════════════════════════════════════════════════════════════════════

def train_sentiment_fusion(
    tickers: list[str] | None = None,
    anchors_per_ticker: int = 12,
    days: int = FORECAST_DAYS,
    epochs: int = 60,
    accuracy_slope: float | None = None,
    measure: bool = True,
) -> None:
    import tensorflow as tf
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

    # ── Độ chính xác của sentiment giả lập: ưu tiên số ĐO trên dữ liệu thật ──
    calibration: dict = {"source": "assumed", "slope": ASSUMED_ACCURACY_SLOPE}
    if accuracy_slope is not None:
        calibration = {"source": "cli", "slope": float(np.clip(accuracy_slope, 0.0, MAX_ACCURACY_SLOPE))}
    elif measure:
        print("\nĐo độ chính xác sentiment THẬT trong research_reports...")
        measured = measure_sentiment_accuracy(days=days)
        if measured and measured.get("n", 0) >= MIN_CALIBRATION_SAMPLES:
            calibration = {"source": "measured", **measured}
            print(
                f"  {measured['n']} báo cáo đủ {days} phiên — đúng hướng {measured['hit_rate']:.1%}; "
                f"slope đo được {measured['slope_raw']:+.3f} → dùng {measured['slope']:.3f}"
            )
            for bucket, st in measured.get("by_confidence", {}).items():
                print(f"    confidence {bucket}: {st['n']:>4} mẫu, đúng hướng {st['hit_rate']:.1%}")
        else:
            got = 0 if not measured else measured.get("n", 0)
            print(
                f"  CẢNH BÁO: chỉ có {got} báo cáo LLM thật đủ điều kiện (cần "
                f"{MIN_CALIBRATION_SAMPLES}). Dùng GIẢ ĐỊNH slope={ASSUMED_ACCURACY_SLOPE} — "
                "sentiment confidence cao được coi là đúng hướng tới ~94%, gần như chắc chắn\n"
                "  lạc quan hơn LLM thật. Phải nêu đây là giả định trong báo cáo, hoặc chạy lại\n"
                "  sau khi backfill đủ dữ liệu, hoặc đặt tay: --accuracy-slope 0.1"
            )
    print(f"  Slope dùng để sinh sentiment: {calibration['slope']} (nguồn: {calibration['source']})")

    data, n_tickers = build_dataset(
        tickers, anchors_per_ticker, days=days, accuracy_slope=calibration["slope"]
    )
    if data is None:
        print("Không dựng được mẫu nào — kiểm tra lại models/global_tft.keras đã tồn tại chưa.")
        return

    X_prices, X_signals, Y, sample_tickers = data
    print(f"\nTổng số mẫu: {len(X_prices)} (từ {n_tickers} mã)")

    if len(X_prices) < 30:
        print("Quá ít mẫu để train một cách ổn định — tăng --anchors-per-ticker hoặc --max-tickers.")
        return

    # Chia train/val THEO MÃ, không dùng train_test_split trộn ngẫu nhiên.
    #
    # Trộn ngẫu nhiên cho phép hai mẫu của CÙNG một mã, cách nhau vài phiên, rơi về
    # hai phía của lằn chia. Cửa sổ giá tương lai của chúng chồng lấn, nên tập
    # validation không còn độc lập với tập train và Val MSE/MAE báo cáo bị đẹp giả
    # tạo. Tách theo mã đảm bảo model được đánh giá trên những mã nó CHƯA HỀ thấy —
    # đúng tình huống thật khi người dùng dự báo một mã mới.
    uniq = np.array(sorted(set(sample_tickers.tolist())))
    rng = np.random.default_rng(42)
    rng.shuffle(uniq)
    n_val_tickers = max(1, int(round(len(uniq) * 0.15)))
    val_tickers = set(uniq[:n_val_tickers].tolist())
    is_val = np.array([t in val_tickers for t in sample_tickers])

    if is_val.all() or (~is_val).all():
        print("Không tách được train/val theo mã (quá ít mã) — cần thêm mã hoặc anchor.")
        return

    Xp_train, Xs_train, Y_train = X_prices[~is_val], X_signals[~is_val], Y[~is_val]
    Xp_val, Xs_val, Y_val = X_prices[is_val], X_signals[is_val], Y[is_val]
    print(f"  Chia theo mã: {len(uniq) - n_val_tickers} mã train / {n_val_tickers} mã validation")
    print(f"  Mã dùng để validation: {', '.join(sorted(val_tickers))}")

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

    # Ghi lại giả định sentiment đã dùng — con số này quyết định tầng fusion tin
    # sentiment tới đâu, nên phải trích được vào báo cáo.
    import json
    from datetime import datetime

    with open(os.path.join(MODELS_DIR, f"sentiment_fusion_{days}d_meta.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "trained_at": datetime.now().isoformat(),
                "sentiment_calibration": calibration,
                "val_mse": float(val_loss),
                "val_mae": float(val_mae),
                "train_samples": int(len(Xp_train)),
                "val_samples": int(len(Xp_val)),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

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
    parser.add_argument(
        "--accuracy-slope", type=float, default=None,
        help="Đặt tay hệ số P(đúng)=0.5+slope*confidence cho sentiment giả lập (bỏ qua bước đo)",
    )
    parser.add_argument(
        "--no-measure", action="store_true",
        help="Không đo trên research_reports; dùng giả định cũ (0.45)",
    )
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
        accuracy_slope=args.accuracy_slope,
        measure=not args.no_measure,
    )
