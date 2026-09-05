"""
forecaster.py – Bộ máy dự báo real-time, không lưu trạng thái dữ liệu.

Triết lý giữ nguyên từ bản trước: không bao giờ ghi dữ liệu giá hay kết quả dự báo
xuống đĩa; chỉ giữ trọng số mô hình trong RAM.

Bốn thay đổi đáng kể:

1. **Cache có thời hạn cho dữ liệu giá.** Vòng lặp WebSocket + job nền + mỗi
   request của người dùng đều gọi yfinance. Không có cache, một phiên vài người
   dùng đủ khiến IP của Render bị yfinance chặn tạm thời. Cache TTL ngắn giữ
   dữ liệu vẫn "gần như real-time" mà giảm số lượt gọi đi hàng chục lần.

2. **Dự báo nhiều bước tính lại chỉ báo kỹ thuật ở từng bước.** Bản cũ chỉ cập nhật
   cột Close còn RSI/MACD/Bollinger... giữ nguyên giá trị của ngày cuối có dữ liệu
   thật. Với horizon 30-60 ngày, mô hình "nhìn" chỉ báo của một tháng trước trong khi
   giá đã trôi rất xa — sai số tích luỹ rất nhanh.

3. **Ngày dự báo bám theo lịch giao dịch.** Cổ phiếu không giao dịch cuối tuần;
   bản cũ sinh cả T+6 là Chủ nhật. Crypto thì ngược lại, chạy đủ 7 ngày.

4. **Cache mô hình an toàn với đa luồng và có thể nạp lại** — cần thiết vì job
   online-learning ghi đè file mô hình trong lúc server vẫn đang phục vụ request.
"""

from __future__ import annotations

import os
import re
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

from backend.metrics import track_inference

MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models")
LOOK_BACK = 60

# Thời hạn cache (giây). Chọn ngắn để dữ liệu vẫn tươi, đủ dài để không bị chặn.
QUOTE_CACHE_TTL = 30       # Giá live — WebSocket broadcast mỗi 10s vẫn dùng lại cache
OHLCV_CACHE_TTL = 900      # Lịch sử OHLCV — dữ liệu ngày, 15 phút là quá đủ

_model_lock = threading.Lock()
_model_cache: Dict[str, object] = {}

_quote_cache: Dict[str, Tuple[float, dict]] = {}
_ohlcv_cache: Dict[str, Tuple[float, pd.DataFrame]] = {}
_cache_lock = threading.Lock()


# ══════════════════════════════════════════════════════════════════════════════
#  LẤY DỮ LIỆU THỊ TRƯỜNG (có cache TTL)
# ══════════════════════════════════════════════════════════════════════════════

def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """yfinance >= 0.2.40 trả về MultiIndex kể cả khi chỉ tải một mã."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def fetch_ohlcv(
    ticker: str, period: str = "1y", interval: str = "1d", use_cache: bool = True
) -> Optional[pd.DataFrame]:
    """Tải OHLCV từ yfinance. Trả về DataFrame đã làm sạch, hoặc None."""
    cache_key = f"{ticker}|{period}|{interval}"

    if use_cache:
        with _cache_lock:
            entry = _ohlcv_cache.get(cache_key)
            if entry and time.time() - entry[0] < OHLCV_CACHE_TTL:
                return entry[1].copy()

    try:
        df = yf.download(
            ticker,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=True,
            threads=False,
        )
        if df is None or df.empty:
            return None

        df = _flatten_columns(df)

        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        df.index.name = "Date"

        df = df.interpolate("linear").ffill().bfill()
        df = df.dropna(subset=["Close"])
        if df.empty:
            return None

        with _cache_lock:
            _ohlcv_cache[cache_key] = (time.time(), df.copy())
            _prune_cache(_ohlcv_cache, max_entries=120)

        return df
    except Exception as e:
        print(f"[yfinance] Lỗi khi tải {ticker}: {type(e).__name__}: {e}")
        return None


def get_live_quote(ticker: str, use_cache: bool = True) -> Optional[Dict]:
    """Giá mới nhất của một mã. Có cache TTL ngắn dùng chung toàn ứng dụng."""
    if use_cache:
        with _cache_lock:
            entry = _quote_cache.get(ticker)
            if entry and time.time() - entry[0] < QUOTE_CACHE_TTL:
                return dict(entry[1])

    def _scalar(val) -> float:
        if isinstance(val, pd.Series):
            val = val.iloc[0]
        return float(val)

    try:
        df = yf.download(
            ticker, period="5d", interval="1d", progress=False, auto_adjust=True, threads=False
        )
        if df is None or df.empty or len(df) < 2:
            return None

        df = _flatten_columns(df)
        latest, prev = df.iloc[-1], df.iloc[-2]

        close = _scalar(latest["Close"])
        prev_close = _scalar(prev["Close"])
        change = close - prev_close

        volume = 0.0
        try:
            raw_volume = _scalar(latest.get("Volume", 0))
            volume = 0.0 if np.isnan(raw_volume) else raw_volume
        except (TypeError, ValueError):
            volume = 0.0

        quote = {
            "ticker": ticker,
            "price": close,
            "open": _scalar(latest.get("Open", close)),
            "high": _scalar(latest.get("High", close)),
            "low": _scalar(latest.get("Low", close)),
            "volume": volume,
            "prev_close": prev_close,
            "change": change,
            "change_pct": (change / prev_close * 100) if prev_close else 0.0,
            "timestamp": datetime.now().isoformat(),
        }

        with _cache_lock:
            _quote_cache[ticker] = (time.time(), dict(quote))
            _prune_cache(_quote_cache, max_entries=300)

        return quote
    except Exception as e:
        print(f"[yfinance] Lỗi lấy giá {ticker}: {type(e).__name__}")
        return None


def _prune_cache(cache: dict, max_entries: int) -> None:
    """Giữ cache khỏi phình vô hạn — bỏ các entry cũ nhất khi vượt ngưỡng."""
    if len(cache) <= max_entries:
        return
    for key in sorted(cache, key=lambda k: cache[k][0])[: len(cache) - max_entries]:
        cache.pop(key, None)


def validate_ticker(ticker: str) -> bool:
    """Kiểm tra mã có tải được dữ liệu hay không."""
    return get_live_quote(ticker) is not None


# Cùng bộ quy tắc định dạng mã với backend/security.py::validate_ticker_format.
_TICKER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-]{0,19}$")


def search_tickers(query: str) -> List[Dict]:
    """
    Tìm mã theo từ khoá.

    Vì sao có nhiều tầng dự phòng: API tìm kiếm của Yahoo (`yf.Search`) rất hay bị
    chặn khi gọi từ IP trung tâm dữ liệu (Render, Vercel...) — trả 403/429 hoặc
    timeout. Bản cũ khi đó rơi thẳng xuống một danh sách CỨNG 9 mã, nên gõ bất kỳ
    mã nào ngoài 9 mã đó (MSFT, GOOGL, TSM, VIC.VN...) đều ra "không tìm thấy",
    dù mã đó hoàn toàn hợp lệ và hệ thống vẫn tải được dữ liệu giá của nó.

    Nay khi API tìm kiếm hỏng, ta thử coi chính từ khoá là mã chứng khoán và xác
    minh bằng một lượt lấy giá thật. Cách này không cần API tìm kiếm nên vẫn chạy
    được ngay cả khi Yahoo chặn tra cứu.
    """
    try:
        search = yf.Search(query, max_results=10, enable_fuzzy_query=True)
        results = [
            {
                "symbol": item.get("symbol", ""),
                "name": item.get("longname") or item.get("shortname", ""),
                "exchange": item.get("exchange", ""),
                "type": item.get("quoteType", ""),
            }
            for item in search.quotes
        ]
        if results:
            return results[:8]
    except Exception as e:
        print(f"[yfinance] Lỗi tìm kiếm: {type(e).__name__}")

    # ── Dự phòng 1: coi từ khoá là mã và kiểm chứng bằng dữ liệu giá thật ──
    # Bao gồm cả các biến thể thường gặp: người dùng gõ "BTC" thay vì "BTC-USD",
    # "FPT" thay vì "FPT.VN".
    raw = query.strip().upper()
    if _TICKER_RE.match(raw):
        candidates = [raw]
        if "-" not in raw and "." not in raw:
            candidates += [f"{raw}-USD", f"{raw}.VN"]
        for symbol in candidates:
            try:
                quote = get_live_quote(symbol)
            except Exception:
                quote = None
            if quote:
                return [{
                    "symbol": symbol,
                    "name": symbol,
                    "exchange": "",
                    "type": "CRYPTOCURRENCY" if symbol.endswith("-USD") else "EQUITY",
                }]

    # ── Dự phòng 2: danh sách gợi ý phổ biến (chỉ khi cả hai cách trên đều hỏng) ──
    query_lower = query.lower()
    fallback = [
        {"symbol": "BTC-USD", "name": "Bitcoin", "exchange": "CCC", "type": "CRYPTOCURRENCY"},
        {"symbol": "ETH-USD", "name": "Ethereum", "exchange": "CCC", "type": "CRYPTOCURRENCY"},
        {"symbol": "BNB-USD", "name": "BNB", "exchange": "CCC", "type": "CRYPTOCURRENCY"},
        {"symbol": "SOL-USD", "name": "Solana", "exchange": "CCC", "type": "CRYPTOCURRENCY"},
        {"symbol": "ADA-USD", "name": "Cardano", "exchange": "CCC", "type": "CRYPTOCURRENCY"},
        {"symbol": "XRP-USD", "name": "XRP", "exchange": "CCC", "type": "CRYPTOCURRENCY"},
        {"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NMS", "type": "EQUITY"},
        {"symbol": "NVDA", "name": "NVIDIA Corporation", "exchange": "NMS", "type": "EQUITY"},
        {"symbol": "FPT.VN", "name": "FPT Corp", "exchange": "HOSE", "type": "EQUITY"},
    ]
    return [s for s in fallback if query_lower in s["name"].lower() or query_lower in s["symbol"].lower()]


# ══════════════════════════════════════════════════════════════════════════════
#  MÔ HÌNH TFT
# ══════════════════════════════════════════════════════════════════════════════

def _model_path() -> str:
    return os.path.join(MODELS_DIR, "global_tft.keras")


def load_tft_model(force_reload: bool = False):
    """
    Nạp mô hình TFT vào RAM (chỉ một lần).

    `force_reload=True` dùng sau khi job online-learning ghi đè file mô hình —
    nếu không, tiến trình web vẫn phục vụ bằng phiên bản cũ trong RAM cho tới lần
    khởi động lại tiếp theo, khiến việc "tự học" không hề có tác dụng thực tế.
    """
    with _model_lock:
        if not force_reload and "tft" in _model_cache:
            return _model_cache["tft"]

        path = _model_path()
        if not os.path.exists(path):
            return None

        try:
            import tensorflow as tf

            from backend.models.tft_model import quantile_loss

            model = tf.keras.models.load_model(
                path, custom_objects={"loss_fn": quantile_loss([0.1, 0.5, 0.9])}
            )
            _model_cache["tft"] = model
            _model_cache["loaded_at"] = time.time()
            print(f"[tft] Đã nạp mô hình vào bộ nhớ{' (nạp lại)' if force_reload else ''}.")
            return model
        except Exception as e:
            print(f"[tft] Không nạp được mô hình: {e}")
            return None


def reload_tft_model():
    """Buộc nạp lại mô hình từ đĩa. Gọi sau khi fine-tune xong."""
    return load_tft_model(force_reload=True)


def is_tft_loaded() -> bool:
    return "tft" in _model_cache


# Giữ tên cũ để các đoạn code/notebook cũ không vỡ.
_load_tft_model = load_tft_model


# ══════════════════════════════════════════════════════════════════════════════
#  LỊCH GIAO DỊCH
# ══════════════════════════════════════════════════════════════════════════════

def _is_24_7_market(ticker: str) -> bool:
    """Crypto giao dịch cả cuối tuần; cổ phiếu và ETF thì không."""
    return ticker.upper().endswith("-USD")


def build_forecast_dates(ticker: str, last_date: pd.Timestamp, days: int) -> pd.DatetimeIndex:
    """
    Sinh dãy ngày cho các bước dự báo.

    Cổ phiếu dùng ngày làm việc (bỏ thứ Bảy, Chủ nhật). Đây là xấp xỉ — vẫn chưa
    loại các ngày nghỉ lễ của từng sàn, nhưng đã đúng hơn hẳn so với việc dùng
    ngày dương lịch liên tiếp như bản cũ.
    """
    freq = "D" if _is_24_7_market(ticker) else "B"
    return pd.date_range(start=last_date, periods=days + 1, freq=freq, inclusive="right")


# ══════════════════════════════════════════════════════════════════════════════
#  DỰ BÁO TFT
# ══════════════════════════════════════════════════════════════════════════════

def _append_synthetic_bar(df: pd.DataFrame, predicted_close: float, next_date) -> pd.DataFrame:
    """
    Thêm một phiên giả lập ứng với giá vừa dự báo, để bước sau tính lại được chỉ báo.

    Với một phiên chưa xảy ra ta không biết Open/High/Low, nên dùng chính giá dự báo
    cho cả bốn giá và lấy khối lượng trung bình 20 phiên gần nhất. Đây là giả định
    đơn giản hoá cần được nêu rõ trong báo cáo: nó khiến các chỉ báo dựa trên biên độ
    (ATR, Bollinger) bị "phẳng" dần ở các bước xa.
    """
    recent_volume = float(df["Volume"].tail(20).mean()) if "Volume" in df.columns else 0.0
    new_row = pd.DataFrame(
        {
            "Open": [predicted_close],
            "High": [predicted_close],
            "Low": [predicted_close],
            "Close": [predicted_close],
            "Volume": [recent_volume],
        },
        index=[next_date],
    )
    return pd.concat([df, new_row])


def run_tft_forecast(
    ticker: str, days: int = 7, df: Optional[pd.DataFrame] = None
) -> Tuple[Optional[pd.Series], Optional[pd.Series], Optional[pd.Series]]:
    """
    Chạy dự báo TFT cho một mã bất kỳ.

    Trả về (median p50, lower p10, upper p90) dưới dạng pd.Series, hoặc (None, None, None)
    nếu thiếu dữ liệu hoặc chưa có mô hình.
    """
    from sklearn.preprocessing import MinMaxScaler

    from backend.models.feature_engineering import add_technical_indicators, get_feature_columns

    if df is None:
        df = fetch_ohlcv(ticker, period="2y")
    if df is None or len(df) < LOOK_BACK + 30:
        print(f"[tft] Không đủ dữ liệu cho {ticker}: {0 if df is None else len(df)} phiên")
        return None, None, None

    model = load_tft_model()
    if model is None:
        print("[tft] Chưa có mô hình — chạy backend/train_tft.py trước.")
        return None, None, None

    try:
        # Cột đặc trưng được chốt MỘT LẦN từ dữ liệu lịch sử, để số chiều đầu vào
        # không đổi giữa các bước lặp (mô hình có input shape cố định).
        base_features = add_technical_indicators(df)
        feature_cols = [c for c in get_feature_columns() if c in base_features.columns]
        all_cols = ["Close"] + feature_cols

        history_clean = base_features[all_cols].dropna()
        if len(history_clean) < LOOK_BACK:
            return None, None, None

        # Scaler khớp MỘT LẦN trên dữ liệu lịch sử và giữ nguyên suốt quá trình dự báo.
        # Khớp lại ở từng bước sẽ làm thang đo trôi và kết quả mất tính so sánh.
        scaler = MinMaxScaler(feature_range=(0, 1))
        scaler.fit(history_clean.values)

        working_df = df.copy()
        forecast_dates = build_forecast_dates(ticker, df.index[-1], days)

        preds_price_q10: List[float] = []
        preds_price_q50: List[float] = []
        preds_price_q90: List[float] = []

        def return_to_price(pct_return: float, last_close: float) -> float:
            """Model dự đoán % thay đổi giá (return), không phải mức giá tuyệt đối —
            xem ghi chú TARGET_TYPE trong backend/train_tft.py. Tái tạo lại giá bằng
            cách áp % thay đổi lên giá cuối cùng đã biết, thay vì inverse_transform
            qua scaler (cách cũ này là nguyên nhân gây lệch scale nghiêm trọng khi
            giá vượt phạm vi scaler từng thấy)."""
            price = last_close * (1.0 + pct_return / 100.0)
            # Đầu ra phân vị đến từ một lớp Dense tuyến tính không bị chặn, nên về
            # lý thuyết có thể trả về return <= -100%, cho ra giá 0 hoặc ÂM. Giá đó
            # lại được nạp ngược vào chuỗi làm nến giả cho bước sau, phá hỏng mọi
            # chỉ báo kỹ thuật của phần còn lại trong vòng lặp. Chặn ở một sàn dương.
            return max(price, last_close * 0.01)

        with track_inference():
            for step in range(days):
                featured = add_technical_indicators(working_df)
                window = featured[all_cols].dropna().tail(LOOK_BACK)
                if len(window) < LOOK_BACK:
                    break

                # Giá cuối cùng đã biết trong cửa sổ — mốc để quy đổi % return -> giá.
                last_close = float(window["Close"].iloc[-1])

                scaled = scaler.transform(window.values)
                model_input = scaled.reshape(1, LOOK_BACK, scaled.shape[1])

                pred = model.predict(model_input, verbose=0)
                r10, r50, r90 = float(pred[0, 0]), float(pred[0, 1]), float(pred[0, 2])

                # Quantile phải không giảm dần: p10 <= p50 <= p90. Mạng có thể vi phạm
                # ràng buộc này (quantile crossing) nên ta sắp lại cho chắc chắn.
                # (Sắp xếp trên % return tương đương sắp xếp trên giá vì quy đổi là
                # hàm đơn điệu tăng theo return.)
                r10, r50, r90 = sorted((r10, r50, r90))

                price_q10 = return_to_price(r10, last_close)
                price_q50 = return_to_price(r50, last_close)
                price_q90 = return_to_price(r90, last_close)

                preds_price_q10.append(price_q10)
                preds_price_q50.append(price_q50)
                preds_price_q90.append(price_q90)

                # Nạp giá vừa dự báo vào chuỗi để bước sau tính lại toàn bộ chỉ báo.
                working_df = _append_synthetic_bar(working_df, price_q50, forecast_dates[step])

        if not preds_price_q50:
            return None, None, None

        actual_days = len(preds_price_q50)
        dates = forecast_dates[:actual_days]

        return (
            pd.Series(preds_price_q50, index=dates, name="tft_median"),
            pd.Series(preds_price_q10, index=dates, name="tft_lower"),
            pd.Series(preds_price_q90, index=dates, name="tft_upper"),
        )

    except Exception as e:
        print(f"[tft] Lỗi inference {ticker}: {type(e).__name__}: {e}")
        return None, None, None


# ══════════════════════════════════════════════════════════════════════════════
#  FEATURE IMPORTANCE (permutation importance — KHÔNG PHẢI trọng số VSN)
# ══════════════════════════════════════════════════════════════════════════════

def compute_feature_importance(
    ticker: str, df: Optional[pd.DataFrame] = None, n_repeats: int = 8
) -> Optional[List[Dict]]:
    """
    Đo mức ảnh hưởng của từng đặc trưng đầu vào lên dự báo T+1 (p50).

    ĐÍNH CHÍNH QUAN TRỌNG: đây KHÔNG phải trọng số của lớp
    `VariableSelectionNetwork` trong tft_model.py. Lớp đó có tồn tại trong code
    nhưng `build_tft_model()` không hề gọi tới nó trong đồ thị model thực tế
    (chỉ có `Dense(name="input_projection")` chiếu thẳng input) — nghĩa là nó
    chưa từng ảnh hưởng tới bất kỳ dự báo nào, dù docstring liệt kê nó như một
    tính năng. Nếu báo cáo đồ án ghi "TFT có Variable Selection Network cho khả
    năng diễn giải" thì cần sửa lại cho khớp thực tế, hoặc nêu rõ đây là hướng
    "future work" chưa hoàn thiện.

    Thay vào đó, hàm này dùng PERMUTATION IMPORTANCE — kỹ thuật diễn giải mô
    hình chuẩn, không phụ thuộc kiến trúc: xáo trộn thứ tự 60 phiên gần nhất
    của TỪNG đặc trưng (giữ nguyên các đặc trưng khác), đo dự báo p50 lệch bao
    nhiêu so với dự báo gốc. Đặc trưng càng quan trọng thì xáo trộn nó càng làm
    dự báo lệch nhiều. Lặp `n_repeats` lần mỗi đặc trưng để giảm nhiễu ngẫu
    nhiên, và gộp toàn bộ các lượt xáo trộn thành MỘT lượt gọi model.predict()
    duy nhất (batch) để không bị chậm bởi overhead gọi hàm nhiều lần.

    Trả về danh sách [{feature, importance, raw_delta}] sắp giảm dần theo
    importance (đã chuẩn hoá về tổng = 1), hoặc None nếu thiếu dữ liệu/model.
    """
    from sklearn.preprocessing import MinMaxScaler

    from backend.models.feature_engineering import add_technical_indicators, get_feature_columns

    if df is None:
        df = fetch_ohlcv(ticker, period="2y")
    if df is None or len(df) < LOOK_BACK + 30:
        return None

    model = load_tft_model()
    if model is None:
        return None

    try:
        base_features = add_technical_indicators(df)
        feature_cols = [c for c in get_feature_columns() if c in base_features.columns]
        all_cols = ["Close"] + feature_cols

        history_clean = base_features[all_cols].dropna()
        if len(history_clean) < LOOK_BACK:
            return None

        scaler = MinMaxScaler(feature_range=(0, 1))
        scaler.fit(history_clean.values)

        window = history_clean.tail(LOOK_BACK)
        scaled = scaler.transform(window.values)
        n_features = scaled.shape[1]

        rng = np.random.default_rng(42)

        # Hàng 0 = dự báo gốc (không xáo trộn). Các hàng sau: mỗi đặc trưng
        # được xáo trộn n_repeats lần — gộp hết vào MỘT batch duy nhất.
        batch_rows = [scaled]
        row_feature: List[Optional[str]] = [None]
        for i, col in enumerate(all_cols):
            for _ in range(n_repeats):
                permuted = scaled.copy()
                order = rng.permutation(LOOK_BACK)
                permuted[:, i] = permuted[order, i]
                batch_rows.append(permuted)
                row_feature.append(col)

        batch = np.stack(batch_rows, axis=0)

        with track_inference():
            preds = model.predict(batch, verbose=0)

        base_q50 = float(preds[0, 1])

        diffs_by_feature: Dict[str, List[float]] = {c: [] for c in all_cols}
        for row_idx in range(1, len(row_feature)):
            col = row_feature[row_idx]
            diffs_by_feature[col].append(abs(float(preds[row_idx, 1]) - base_q50))

        deltas = {c: float(np.mean(v)) if v else 0.0 for c, v in diffs_by_feature.items()}
        total = sum(deltas.values())

        if total <= 0:
            # Không đặc trưng nào ảnh hưởng đo được (hiếm, nhưng tránh chia 0).
            share = 1.0 / len(deltas)
            results = [{"feature": c, "importance": share, "raw_delta": 0.0} for c in deltas]
        else:
            results = [
                {"feature": c, "importance": v / total, "raw_delta": v} for c, v in deltas.items()
            ]

        results.sort(key=lambda r: r["importance"], reverse=True)
        return results

    except Exception as e:
        print(f"[feature-importance] Lỗi khi tính cho {ticker}: {type(e).__name__}: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
#  SENTIMENT FUSION
# ══════════════════════════════════════════════════════════════════════════════

def run_sentiment_fusion_forecast(
    ticker: str,
    days: int = 7,
    research_analysis: Optional[Dict] = None,
    df: Optional[pd.DataFrame] = None,
    tft_result: Optional[Tuple] = None,
) -> Tuple[Optional[pd.Series], Optional[pd.Series], Optional[pd.Series]]:
    """
    Điều chỉnh dự báo TFT theo tín hiệu tâm lý thị trường.

    `tft_result` cho phép truyền vào kết quả TFT đã tính sẵn. Không có tham số này,
    `run_combined_forecast()` chạy TFT HAI LẦN cho cùng một request: một lần cho khối
    kết quả "tft", một lần nữa ở đây làm nền cho sentiment fusion — trong khi cả hai
    dùng chung `df` và cho ra kết quả y hệt nhau (mô hình tất định). Dự báo tự hồi quy
    là phần tốn thời gian nhất của toàn pipeline nên đây là lãng phí gấp đôi vô ích,
    và cũng làm chỉ số "thời gian inference" trên trang Giám sát bị đội lên gấp đôi.
    """
    from backend.models.sentiment_fusion import SentimentFusionEngine, extract_market_signals

    if df is None:
        df = fetch_ohlcv(ticker, period="2y")

    if tft_result is not None:
        tft_m, tft_l, tft_u = tft_result
    else:
        tft_m, tft_l, tft_u = run_tft_forecast(ticker, days, df)
    if tft_m is None:
        return None, None, None
    if df is None:
        return tft_m, tft_l, tft_u

    try:
        from backend.models.feature_engineering import add_technical_indicators

        df_feat = add_technical_indicators(df)
    except Exception:
        df_feat = df

    signals = extract_market_signals(df_feat, research_analysis)
    engine = SentimentFusionEngine.get_instance(MODELS_DIR)
    adjusted = engine.predict(tft_m.values, signals, len(tft_m))

    # Giữ nguyên độ rộng dải tin cậy của TFT, chỉ dịch chuyển tâm theo sentiment.
    if tft_l is not None and tft_u is not None:
        band_half = (tft_u.values - tft_l.values) / 2
    else:
        band_half = adjusted * 0.03

    return (
        pd.Series(adjusted, index=tft_m.index, name="sf_median"),
        pd.Series(adjusted - band_half, index=tft_m.index, name="sf_lower"),
        pd.Series(adjusted + band_half, index=tft_m.index, name="sf_upper"),
    )


# ══════════════════════════════════════════════════════════════════════════════
#  PIPELINE ĐẦY ĐỦ
# ══════════════════════════════════════════════════════════════════════════════

_HISTORICAL_INDICATORS = ["RSI", "MACD", "MACD_Signal", "BB_Upper", "BB_Lower", "MA20", "MA50"]


def _series_to_list(s: Optional[pd.Series]) -> Optional[List[dict]]:
    if s is None:
        return None
    return [{"date": str(d.date()), "price": round(float(v), 6)} for d, v in s.items()]


def _build_historical(df: pd.DataFrame, bars: int = 90) -> List[dict]:
    """Đóng gói OHLCV + chỉ báo gần nhất cho biểu đồ ở frontend."""
    try:
        from backend.models.feature_engineering import add_technical_indicators

        # Tính chỉ báo trên TOÀN BỘ lịch sử rồi mới cắt — nếu cắt trước, các chỉ báo
        # có cửa sổ dài (MA50) sẽ toàn NaN ở đầu đoạn.
        featured = add_technical_indicators(df).tail(bars)
    except Exception:
        featured = df.tail(bars)

    historical = []
    for idx, row in featured.iterrows():
        bar = {
            "date": str(idx.date()),
            "open": round(float(row.get("Open", 0)), 6),
            "high": round(float(row.get("High", 0)), 6),
            "low": round(float(row.get("Low", 0)), 6),
            "close": round(float(row.get("Close", 0)), 6),
            "volume": float(row.get("Volume", 0)) if pd.notna(row.get("Volume", 0)) else 0.0,
        }
        for col in _HISTORICAL_INDICATORS:
            if col in row.index and pd.notna(row[col]):
                bar[col.lower()] = round(float(row[col]), 4)
        historical.append(bar)
    return historical


def run_combined_forecast(
    ticker: str, days: int = 7, research_analysis: Optional[Dict] = None
) -> Dict:
    """
    Pipeline đầy đủ: tải dữ liệu → TFT → SentimentFusion → đóng gói kết quả.

    Một lượt tải dữ liệu duy nhất được dùng chung cho cả hai mô hình.

    Kết quả LUÔN có khoá `research` (có thể là None) để phía gọi — kể cả job nền —
    không phải đoán xem khoá đó có tồn tại hay không. Chính chỗ thiếu khoá này ở
    bản cũ đã khiến bot auto-trade luôn nhận confidence mặc định 50 và không bao giờ
    vượt được ngưỡng vào lệnh.
    """
    df = fetch_ohlcv(ticker, period="2y")

    tft_m, tft_l, tft_u = run_tft_forecast(ticker, days, df)
    # Truyen lai ket qua TFT vua tinh — neu khong, ham duoi se chay lai toan bo
    # du bao tu hoi quy lan thu hai cho cung mot request.
    sf_m, sf_l, sf_u = run_sentiment_fusion_forecast(
        ticker, days, research_analysis, df, tft_result=(tft_m, tft_l, tft_u)
    )

    current_price = float(df["Close"].iloc[-1]) if df is not None and len(df) else None

    research_block = None
    if research_analysis:
        research_block = {
            "sentiment": research_analysis.get("sentiment"),
            "confidence": research_analysis.get("confidence"),
            "sentiment_score": research_analysis.get("sentiment_score"),
            "summary": research_analysis.get("summary"),
            "recommendation": research_analysis.get("recommendation"),
            "risk_level": research_analysis.get("risk_level"),
            "key_factors": research_analysis.get("key_factors", []),
            "headlines": (research_analysis.get("headlines") or [])[:5],
            "source": research_analysis.get("source"),
            "analyzed_at": research_analysis.get("analyzed_at"),
        }

    return {
        "ticker": ticker,
        "days": days,
        "current_price": current_price,
        "tft": {
            "median": _series_to_list(tft_m),
            "lower_q10": _series_to_list(tft_l),
            "upper_q90": _series_to_list(tft_u),
            "available": tft_m is not None,
        },
        "sentiment_fusion": {
            "median": _series_to_list(sf_m),
            "lower_q10": _series_to_list(sf_l),
            "upper_q90": _series_to_list(sf_u),
            "available": sf_m is not None,
        },
        "historical": _build_historical(df) if df is not None else None,
        "research": research_block,
        "research_used": research_analysis is not None,
        "generated_at": datetime.now().isoformat(),
    }
