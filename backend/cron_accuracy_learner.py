"""
cron_accuracy_learner.py – Đánh giá sai số dự báo và fine-tune mô hình định kỳ.

Ba vấn đề được xử lý ở bản này:

1. **Fine-tune xong nhưng không có tác dụng.**
   Bản cũ ghi đè `models/global_tft.keras` rồi kết thúc. Nhưng tiến trình web đang
   phục vụ request bằng một instance đã nạp sẵn trong RAM (`_model_cache`), và biến
   đó không hề được làm mới. Trên Render free tier, service hiếm khi tự khởi động lại,
   nên mô hình "đã học" chỉ thực sự được dùng sau lần deploy kế tiếp — có thể là vài tuần.
   Nay sau khi lưu, hàm gọi `reload_tft_model()` để nạp lại ngay.

2. **Ghi đè mô hình production mà không kiểm chứng.**
   Fine-tune 3 epoch trên một lô dữ liệu nhỏ có thể làm mô hình tệ đi (catastrophic
   forgetting), đặc biệt khi thị trường vừa qua một giai đoạn bất thường. Bản cũ ghi đè
   vô điều kiện và không có đường lùi. Nay mô hình mới phải vượt qua kiểm tra trên tập
   giữ lại thì mới được chấp nhận, và bản cũ luôn được sao lưu trước khi ghi đè.

3. **Phụ thuộc vào file scaler đã lỗi thời.**
   Bản cũ đọc `models/scaler_tft_{ticker}.pkl` — các file này do phiên bản cũ của
   train_tft.py sinh ra và không còn được tạo nữa, nên vòng lặp thường xuyên `continue`
   và không học được gì. Nay scaler được khớp tại chỗ trên dữ liệu lịch sử, đúng như
   cách `forecaster.py` làm lúc inference.
"""

from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime, timezone
from typing import List

import numpy as np
import pandas as pd

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.database import get_pending_evaluations, update_accuracy_evaluation
from backend.models.forecaster import LOOK_BACK, fetch_ohlcv, reload_tft_model

MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
MODEL_PATH = os.path.join(MODELS_DIR, "global_tft.keras")
BACKUP_PATH = os.path.join(MODELS_DIR, "global_tft.backup.keras")

FINE_TUNE_EPOCHS = 3
FINE_TUNE_LR = 1e-4
# Số cửa sổ gần nhất lấy từ mỗi mã cho một lượt fine-tune.
RECENT_WINDOWS_PER_TICKER = 14
# Mô hình mới chỉ được chấp nhận nếu loss trên tập giữ lại không tệ hơn quá ngưỡng này.
MAX_ACCEPTABLE_REGRESSION = 1.05  # tệ hơn tối đa 5%


# ══════════════════════════════════════════════════════════════════════════════
#  BƯỚC 1: ĐÁNH GIÁ DỰ BÁO CŨ
# ══════════════════════════════════════════════════════════════════════════════

def run_evaluations() -> List[str]:
    """
    Đối chiếu các dự báo đã ghi với giá đóng cửa thực tế của đúng phiên được dự báo.

    Trả về danh sách mã đã đánh giá được — đây chính là đầu vào cho bước fine-tune,
    vì đó là những mã hệ thống vừa có thêm thông tin mới về chất lượng dự báo.
    """
    print(f"[{datetime.now().isoformat()}] Bắt đầu đánh giá sai số mô hình...")

    pending = get_pending_evaluations()
    if not pending:
        print("Không có dự báo nào chờ đánh giá.")
        return []

    print(f"Tìm thấy {len(pending)} dự báo chờ đánh giá.")

    # Gom theo mã để mỗi mã chỉ tải dữ liệu lịch sử một lần.
    by_ticker: dict = {}
    for record in pending:
        by_ticker.setdefault(record["ticker"], []).append(record)

    evaluated: set = set()

    for ticker, records in by_ticker.items():
        df = fetch_ohlcv(ticker, period="3mo", use_cache=False)
        if df is None or df.empty:
            print(f"  {ticker}: không tải được dữ liệu, bỏ qua.")
            continue

        df.index = df.index.normalize()

        for record in records:
            try:
                target_date = pd.to_datetime(record["forecast_date"]).normalize()
            except (ValueError, TypeError):
                continue

            if target_date not in df.index:
                # Phiên chưa diễn ra, hoặc là ngày nghỉ — để lại đánh giá lần sau.
                continue

            actual = float(df.loc[target_date, "Close"])
            predicted = float(record["predicted_price"])
            if actual <= 0:
                continue

            error_pct = abs(actual - predicted) / actual * 100
            if update_accuracy_evaluation(record["id"], actual, error_pct):
                print(
                    f"  {ticker} {record['forecast_date']}: dự báo {predicted:.2f}, "
                    f"thực tế {actual:.2f}, sai số {error_pct:.2f}%"
                )
                evaluated.add(ticker)

    print(f"Đã đánh giá xong {len(evaluated)} mã.")
    return sorted(evaluated)


# ══════════════════════════════════════════════════════════════════════════════
#  BƯỚC 2: FINE-TUNE
# ══════════════════════════════════════════════════════════════════════════════

def _collect_recent_samples(tickers: List[str], look_back: int, expected_features: int):
    """
    Thu thập các cửa sổ dữ liệu gần nhất của những mã vừa được đánh giá.

    Scaler được khớp tại chỗ trên chính lịch sử của từng mã — nhất quán với cách
    `forecaster.py` chuẩn hoá lúc inference, nên mô hình được fine-tune trên đúng
    phân phối dữ liệu mà nó sẽ gặp khi chạy thật.
    """
    from sklearn.preprocessing import MinMaxScaler

    from backend.models.feature_engineering import add_technical_indicators, get_feature_columns

    all_X, all_Y = [], []

    for ticker in tickers:
        df = fetch_ohlcv(ticker, period="1y")
        if df is None or df.empty:
            continue

        df = add_technical_indicators(df)
        available = [c for c in get_feature_columns() if c in df.columns]
        df_clean = df[["Close"] + available].dropna()

        if len(df_clean) < look_back + 5:
            continue
        if df_clean.shape[1] != expected_features:
            print(
                f"  {ticker}: số đặc trưng ({df_clean.shape[1]}) không khớp mô hình "
                f"({expected_features}), bỏ qua."
            )
            continue

        scaler = MinMaxScaler(feature_range=(0, 1))
        scaled = scaler.fit_transform(df_clean.values)

        start = max(0, len(scaled) - look_back - RECENT_WINDOWS_PER_TICKER)
        for i in range(start, len(scaled) - look_back):
            all_X.append(scaled[i : i + look_back])
            all_Y.append(scaled[i + look_back, 0])

    if not all_X:
        return None, None

    X = np.array(all_X, dtype=np.float32)
    Y = np.column_stack([all_Y] * 3).astype(np.float32)
    return X, Y


def online_learning(tickers: List[str]) -> bool:
    """
    Fine-tune nhẹ mô hình trên dữ liệu mới nhất của các mã vừa được đánh giá.

    Trả về True nếu mô hình production thực sự được cập nhật.
    """
    if not tickers:
        return False

    print(f"\nBắt đầu học tăng cường cho: {', '.join(tickers)}")

    if not os.path.exists(MODEL_PATH):
        print("Chưa có mô hình đã huấn luyện. Chạy backend/train_tft.py trước.")
        return False

    import tensorflow as tf

    from backend.models.tft_model import quantile_loss

    try:
        model = tf.keras.models.load_model(
            MODEL_PATH, custom_objects={"loss_fn": quantile_loss([0.1, 0.5, 0.9])}
        )
    except Exception as e:
        print(f"Không nạp được mô hình để fine-tune: {e}")
        return False

    expected_features = model.input_shape[-1]
    look_back = model.input_shape[1] or LOOK_BACK

    X, Y = _collect_recent_samples(tickers, look_back, expected_features)
    if X is None or len(X) < 10:
        print("Không đủ dữ liệu mới để học (cần tối thiểu 10 mẫu).")
        return False

    # ── Giữ lại một phần để kiểm chứng ──
    # Tách theo thứ tự (không trộn) để tập giữ lại luôn là phần MỚI NHẤT —
    # đúng thứ mà ta muốn mô hình cải thiện.
    split = max(1, int(len(X) * 0.8))
    X_train, Y_train = X[:split], Y[:split]
    X_holdout, Y_holdout = X[split:], Y[split:]

    if len(X_holdout) == 0:
        X_holdout, Y_holdout = X_train, Y_train

    loss_before = float(model.evaluate(X_holdout, Y_holdout, verbose=0)[0])
    print(f"Loss trước khi học: {loss_before:.6f} (trên {len(X_holdout)} mẫu giữ lại)")

    print(f"Fine-tune trên {len(X_train)} mẫu mới...")
    tf.keras.backend.set_value(model.optimizer.learning_rate, FINE_TUNE_LR)
    model.fit(
        X_train,
        Y_train,
        epochs=FINE_TUNE_EPOCHS,
        batch_size=min(32, len(X_train)),
        verbose=1,
    )

    loss_after = float(model.evaluate(X_holdout, Y_holdout, verbose=0)[0])
    print(f"Loss sau khi học:  {loss_after:.6f}")

    # ── Cổng kiểm chứng ──
    if loss_after > loss_before * MAX_ACCEPTABLE_REGRESSION:
        print(
            f"TỪ CHỐI cập nhật: mô hình sau fine-tune tệ hơn {loss_after / loss_before - 1:.1%}, "
            f"vượt ngưỡng cho phép {MAX_ACCEPTABLE_REGRESSION - 1:.0%}. "
            "Giữ nguyên mô hình đang chạy."
        )
        return False

    # ── Sao lưu rồi mới ghi đè ──
    try:
        shutil.copy2(MODEL_PATH, BACKUP_PATH)
    except Exception as e:
        print(f"Cảnh báo: không sao lưu được mô hình cũ ({e}). Vẫn tiếp tục.")

    model.save(MODEL_PATH)

    # Nạp lại vào tiến trình đang phục vụ — nếu thiếu bước này, toàn bộ việc học
    # ở trên sẽ không có tác dụng gì cho tới lần khởi động lại tiếp theo.
    reload_tft_model()

    improvement = (loss_before - loss_after) / loss_before * 100 if loss_before else 0.0
    print(f"Đã cập nhật mô hình (cải thiện {improvement:+.2f}%) và nạp lại vào bộ nhớ.")
    return True


def restore_backup() -> bool:
    """Khôi phục mô hình từ bản sao lưu gần nhất. Dùng khi mô hình mới có vấn đề."""
    if not os.path.exists(BACKUP_PATH):
        print("Không có bản sao lưu để khôi phục.")
        return False
    shutil.copy2(BACKUP_PATH, MODEL_PATH)
    reload_tft_model()
    print("Đã khôi phục mô hình từ bản sao lưu.")
    return True


if __name__ == "__main__":
    if "--restore" in sys.argv:
        restore_backup()
    else:
        online_learning(run_evaluations())
