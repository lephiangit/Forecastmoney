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

import json
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

# Số mẫu tối thiểu để một lượt fine-tune có ý nghĩa.
MIN_SAMPLES_FOR_FINETUNE = 200
# Số mẫu giữ lại tối thiểu để cổng kiểm chứng không chỉ là nhiễu.
MIN_HOLDOUT_SAMPLES = 50

META_PATH = os.path.join(MODELS_DIR, "tft_meta.json")
LOCK_PATH = os.path.join(MODELS_DIR, ".online_learning.lock")


def _today_normalized() -> "pd.Timestamp":
    """Nửa đêm hôm nay, để so sánh với `forecast_date` đã normalize."""
    return pd.Timestamp(datetime.now().date())


def _mark_online_finetuned() -> None:
    """
    Ghi dấu vào tft_meta.json rằng mô hình production đã bị fine-tune online.

    VÌ SAO CẦN: `_collect_recent_samples` lấy dữ liệu `period="1y"`, trong khi tập
    TEST của `evaluate_tft.py` là 15% cuối lịch sử — với một mã có ~2000 phiên thì
    15% khoảng 300 phiên, tức hơn một năm. Hai vùng này TRÙNG NHAU gần hết. Chạy
    cron một lần rồi chạy `evaluate_tft` sẽ cho MAPE thấp giả tạo, trong khi báo cáo
    vẫn in dòng "Tập kiểm thử chưa từng được dùng trong huấn luyện".
    """
    try:
        meta = {}
        if os.path.exists(META_PATH):
            with open(META_PATH, encoding="utf-8") as f:
                meta = json.load(f)
        meta["online_finetuned_at"] = datetime.now().isoformat()
        meta["online_finetune_count"] = int(meta.get("online_finetune_count") or 0) + 1
        with open(META_PATH, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Cảnh báo: không ghi được dấu online_finetuned_at ({type(e).__name__}: {e}).")


class _SingleRunLock:
    """
    Khoá liên tiến trình cho online_learning.

    VÌ SAO CẦN: `/admin/trigger-learner` đẩy `online_learning` vào BackgroundTasks
    mà không có cờ "đang chạy". Gọi endpoint hai lần liên tiếp là hai tác vụ cùng
    chạy: một bên `shutil.copy2(MODEL_PATH, BACKUP_PATH)` trong khi bên kia đang ghi
    MODEL_PATH — bản sao lưu trở thành file .keras dở dang, không mở được. Đúng lúc
    cần khôi phục thì không còn gì để khôi phục.
    """

    def __init__(self, path: str):
        self.path = path
        self.fd = None

    def __enter__(self):
        try:
            self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(self.fd, str(os.getpid()).encode())
            return True
        except FileExistsError:
            # Khoá cũ quá 2 tiếng coi như tiến trình đã chết.
            try:
                if datetime.now().timestamp() - os.path.getmtime(self.path) > 7200:
                    os.remove(self.path)
                    return self.__enter__()
            except OSError:
                pass
            return False

    def __exit__(self, *exc):
        if self.fd is not None:
            try:
                os.close(self.fd)
                os.remove(self.path)
            except OSError:
                pass
        return False


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

            # CHỈ CHẤM ĐIỂM PHIÊN ĐÃ ĐÓNG CỬA.
            #
            # LỖI ĐÃ SỬA: `get_pending_evaluations` lấy `forecast_date <= today`, tức
            # gồm cả HÔM NAY, và yfinance có sẵn dòng của phiên đang diễn ra với
            # `Close` là giá hiện tại. Chạy cron lúc 14:00 → `actual` = giá lúc 14:00,
            # rồi `update_accuracy_evaluation` ghi `actual_price` khác NULL nên bản
            # ghi KHÔNG BAO GIỜ được chấm lại bằng giá đóng cửa thật. Toàn bộ số liệu
            # độ chính xác trên trang Admin — và tập mã dùng để fine-tune — đều dựa
            # trên nhãn sai.
            if target_date >= _today_normalized():
                continue

            # Bọc riêng phần này: chỉ một bản ghi hỏng (predicted_price là None, hay
            # chỉ số ngày bị trùng khiến .loc trả về Series thay vì một số) cũng đủ
            # ném ngoại lệ và giết cả vòng lặp — mọi mã đứng sau bị bỏ qua im lặng
            # cho tới lần chạy sau.
            try:
                close_val = df.loc[target_date, "Close"]
                if isinstance(close_val, pd.Series):
                    close_val = close_val.iloc[-1]
                actual = float(close_val)
                predicted = float(record["predicted_price"])
            except (TypeError, ValueError, KeyError, IndexError) as e:
                print(f"  {ticker} {record.get('forecast_date')}: bỏ qua bản ghi lỗi ({type(e).__name__})")
                continue

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
    from backend.models.feature_engineering import (
        TARGET_COLUMN,
        FeatureScaler,
        build_model_frame,
    )

    all_X, all_Y, all_T = [], [], []
    ticker_order: List[str] = []

    for ticker in tickers:
        df = fetch_ohlcv(ticker, period="1y")
        if df is None or df.empty:
            continue

        try:
            df_clean, available = build_model_frame(df)
        except ValueError:
            continue

        if len(df_clean) < look_back + 5:
            continue
        # So SỐ ĐẶC TRƯNG, không phải số cột của khung: khung còn có thêm cột giá
        # thô để tính nhãn. Bản cũ so `df_clean.shape[1]` nên vô tình cộng thêm 1.
        if len(available) != expected_features:
            print(
                f"  {ticker}: số đặc trưng ({len(available)}) không khớp mô hình "
                f"({expected_features}), bỏ qua."
            )
            continue

        scaler = FeatureScaler()
        scaled = scaler.fit_transform(df_clean[available].values)
        # Nhãn phải cùng ngữ nghĩa với target hiện tại của TFT: % thay đổi giá (return),
        # KHÔNG PHẢI giá tuyệt đối đã scale như trước. Dùng lại đúng công thức trong
        # backend/train_tft.py::_build_sequences — tính trên giá THÔ (raw_close), không
        # phải giá đã qua scaler. Nếu giữ nhãn cũ, fine-tune sẽ kéo model quay lại dự
        # đoán "giá tuyệt đối" và phá hỏng model đã sửa lỗi lệch scale.
        raw_close = df_clean[TARGET_COLUMN].values

        start = max(0, len(scaled) - look_back - RECENT_WINDOWS_PER_TICKER)
        n_before = len(all_X)
        for i in range(start, len(scaled) - look_back):
            last_close = raw_close[i + look_back - 1]
            next_close = raw_close[i + look_back]
            # Giá 0 (dữ liệu lỗi thỉnh thoảng gặp ở mã .VN) cho pct_change = inf mà
            # numpy KHÔNG ném lỗi. Một nhãn inf làm loss thành NaN, và `NaN >
            # loss_before * 1.05` là False — nghĩa là cổng kiểm chứng bị VƯỢT QUA và
            # một mô hình NaN được ghi đè lên production.
            if last_close <= 0:
                continue
            pct_change = (next_close - last_close) / last_close * 100.0
            if not np.isfinite(pct_change):
                continue
            all_X.append(scaled[i : i + look_back])
            all_Y.append(pct_change)
            # Ghi mã của từng mẫu để chia holdout PHÂN TẦNG theo mã (xem dưới).
            all_T.append(len(ticker_order))
        if len(all_X) > n_before:
            ticker_order.append(ticker)

    if not all_X:
        return None, None, None

    X = np.array(all_X, dtype=np.float32)
    Y = np.column_stack([all_Y] * 3).astype(np.float32)
    T = np.array(all_T, dtype=np.int32)
    return X, Y, T


def online_learning(tickers: List[str]) -> bool:
    """Bọc `_online_learning_locked` bằng khoá một-lượt-một-lần."""
    with _SingleRunLock(LOCK_PATH) as acquired:
        if not acquired:
            print("Một lượt online-learning khác đang chạy — bỏ qua lượt này.")
            return False
        return _online_learning_locked(tickers)


def _online_learning_locked(tickers: List[str]) -> bool:
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

    # Chốt an toàn: model hiện tại phải đúng target_type "return_pct_1step" (% return)
    # thì nhãn fine-tune ở trên mới có cùng ngữ nghĩa. Nếu model đang chạy vẫn là bản
    # cũ (dự đoán giá tuyệt đối) hoặc target_type nào khác, TỪ CHỐI fine-tune thay vì
    # âm thầm học sai — tránh lặp lại đúng lớp lỗi đã sửa ở train_tft.py.
    meta_path = os.path.join(MODELS_DIR, "tft_meta.json")
    try:
        import json

        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        current_target_type = meta.get("target_type")
        if current_target_type != "return_pct_1step":
            print(
                f"TỪ CHỐI fine-tune: model hiện tại có target_type='{current_target_type}', "
                "khác với nhãn %return mà script này sinh ra ('return_pct_1step'). "
                "Chạy lại backend/train_tft.py để đưa model về đúng phiên bản trước khi bật "
                "online-learning."
            )
            return False
    except Exception as e:
        print(
            f"Cảnh báo: không đọc được tft_meta.json để kiểm tra target_type ({e}). "
            "TỪ CHỐI fine-tune để an toàn."
        )
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

    X, Y, T = _collect_recent_samples(tickers, look_back, expected_features)
    if X is None or len(X) < MIN_SAMPLES_FOR_FINETUNE:
        print(
            f"Không đủ dữ liệu mới để học (có {0 if X is None else len(X)}, "
            f"cần tối thiểu {MIN_SAMPLES_FOR_FINETUNE} mẫu)."
        )
        return False

    # ── Giữ lại một phần để kiểm chứng ──
    #
    # LỖI ĐÃ SỬA: bản cũ cắt `X[:split]` / `X[split:]` với chú thích "tập giữ lại
    # luôn là phần MỚI NHẤT". Sai — `_collect_recent_samples` nối các cửa sổ THEO
    # THỨ TỰ MÃ, không theo thời gian toàn cục. Với tickers = [BTC, ETH, NVDA] thì
    # holdout = toàn bộ mẫu của NVDA, còn train = BTC + ETH. Cổng kiểm chứng vì thế
    # đo khả năng khái quát sang một mã CHƯA fine-tune, không đo chất lượng trên dữ
    # liệu mới. Tệ hơn, với ngưỡng cũ `len(X) >= 10` thì holdout chỉ còn 2 mẫu —
    # `loss_after <= loss_before * 1.05` trên 2 mẫu là nhiễu thuần tuý, và mô hình
    # production bị ghi đè dựa trên đó.
    #
    # Nay chia PHÂN TẦNG: với MỖI mã, 20% cửa sổ mới nhất vào holdout.
    train_idx, hold_idx = [], []
    for t in np.unique(T):
        idx = np.flatnonzero(T == t)          # đã theo thứ tự thời gian trong từng mã
        cut = max(1, int(len(idx) * 0.8))
        train_idx.extend(idx[:cut].tolist())
        hold_idx.extend(idx[cut:].tolist())

    if len(hold_idx) < MIN_HOLDOUT_SAMPLES:
        print(
            f"TỪ CHỐI fine-tune: chỉ có {len(hold_idx)} mẫu giữ lại, cần tối thiểu "
            f"{MIN_HOLDOUT_SAMPLES} để cổng kiểm chứng có ý nghĩa thống kê."
        )
        return False

    X_train, Y_train = X[train_idx], Y[train_idx]
    X_holdout, Y_holdout = X[hold_idx], Y[hold_idx]

    loss_before = float(model.evaluate(X_holdout, Y_holdout, verbose=0)[0])
    print(f"Loss trước khi học: {loss_before:.6f} (trên {len(X_holdout)} mẫu giữ lại)")

    print(f"Fine-tune trên {len(X_train)} mẫu mới...")
    # tf.keras.backend.set_value() la API kieu TF1, khong tuong thich voi optimizer
    # cua Keras 3 (loi "'str' object has no attribute 'name'" — da kiem chung thuc te).
    # Gan truc tiep thuoc tinh la cach chuan trong Keras 3.
    model.optimizer.learning_rate = FINE_TUNE_LR
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
    # Loss không hữu hạn phải bị TỪ CHỐI tường minh: mọi phép so sánh với NaN đều
    # trả False, nên nếu chỉ viết `if loss_after > ...` thì một mô hình NaN sẽ đi
    # thẳng qua cổng và được ghi đè lên production.
    if not np.isfinite(loss_before) or not np.isfinite(loss_after):
        print(
            f"TỪ CHỐI cập nhật: loss không hữu hạn (trước={loss_before}, sau={loss_after}). "
            "Giữ nguyên mô hình đang chạy."
        )
        return False

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

    # Ghi NGUYÊN TỬ: ghi ra file tạm rồi os.replace(). Bản cũ `model.save()` thẳng
    # vào MODEL_PATH, nên một request dự báo đọc trúng lúc đang ghi sẽ nạp phải file
    # dở dang; hai lượt fine-tune song song (timer + /admin/trigger-learner) còn có
    # thể làm hỏng cả bản sao lưu.
    tmp_path = MODEL_PATH + ".tmp.keras"
    model.save(tmp_path)
    os.replace(tmp_path, MODEL_PATH)

    # ĐÁNH DẤU: mô hình production đã bị fine-tune trên dữ liệu 1 năm gần nhất, vốn
    # TRÙNG với vùng tập test của evaluate_tft.py. Mọi số liệu "ngoài mẫu" đo sau
    # thời điểm này đều không còn là ngoài mẫu. `evaluate_tft.py` đọc cờ này và từ
    # chối chạy, để số liệu sai không lọt vào báo cáo.
    _mark_online_finetuned()

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
