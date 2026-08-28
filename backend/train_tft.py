"""
train_tft.py – Huấn luyện Temporal Fusion Transformer toàn cục.

╔══════════════════════════════════════════════════════════════════════════════╗
║  LỖI PHƯƠNG PHÁP ĐÃ SỬA: RÒ RỈ DỮ LIỆU KHI CHIA TẬP VALIDATION              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Bản trước làm thế này:

    np.random.shuffle(indices)          # trộn toàn bộ mẫu của mọi mã
    model.fit(X, Y, validation_split=0.1)

Keras cắt 10% CUỐI của mảng làm tập validation. Vì mảng đã bị trộn ngẫu nhiên
trước đó, tập validation chứa các cửa sổ thời gian nằm xen kẽ với tập train —
ví dụ train có cửa sổ ngày 100-160 và ngày 102-162, còn validation có ngày 101-161.
Ba cửa sổ này chồng lấn gần như hoàn toàn.

Hệ quả: val_loss trông rất đẹp, nhưng nó đo khả năng nội suy giữa những ngày mô hình
ĐÃ THẤY, chứ không đo khả năng dự báo tương lai. Với một đồ án, đây là loại lỗi mà
hội đồng sẽ hỏi ngay khi nhìn đường loss quá mượt — và mọi con số MAE/RMSE báo cáo
dựa trên nó đều không dùng được.

Bản này chia theo THỜI GIAN cho từng mã: 85% đầu tiên của lịch sử mỗi mã dùng để
huấn luyện, 15% cuối dùng để validate. Ngoài ra bỏ hẳn `VALIDATION_GAP` cửa sổ ở
ranh giới để cửa sổ cuối của tập train không chạm sang vùng validation.

Chỉ tập train mới được trộn; tập validation giữ nguyên thứ tự thời gian.

────────────────────────────────────────────────────────────────────────────────
GHI CHÚ VỀ QUANTILE LOSS

`Y_quantile = np.column_stack([Y, Y, Y])` là ĐÚNG, không phải lỗi. Trong hồi quy
quantile, mỗi quantile τ được học từ chính giá trị thực tế quan sát được, thông qua
hàm mất mát bất đối xứng (pinball loss). Việc ba cột giống nhau là bình thường —
sự khác biệt giữa p10/p50/p90 sinh ra từ trọng số bất đối xứng của loss, không phải
từ nhãn khác nhau.

Điều CẦN kiểm chứng là dải tin cậy có được hiệu chỉnh đúng hay không: khoảng
[p10, p90] lẽ ra phải bao phủ khoảng 80% số quan sát thực tế. Phép đo đó nằm ở
`backend/evaluate_tft.py`.
────────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import os
import pickle
import sys
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
import tensorflow as tf

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.models.feature_engineering import add_technical_indicators, get_feature_columns
from backend.models.tft_model import build_tft_model, compile_tft_model, get_tft_callbacks

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")

LOOK_BACK = 60
EPOCHS = 100
BATCH_SIZE = 64

# Tỷ lệ dữ liệu (theo thời gian) dùng để huấn luyện; phần còn lại để validate.
TRAIN_RATIO = 0.85

# Số cửa sổ bỏ trống ở ranh giới train/validation.
# Cửa sổ cuối cùng của tập train kết thúc ngay sát điểm cắt; nếu không có khoảng
# trống này, mẫu validation đầu tiên vẫn dùng chung phần lớn dữ liệu với nó.
VALIDATION_GAP = LOOK_BACK

# Các file dữ liệu tổng hợp / trùng lặp — bỏ qua khi build dataset.
SKIP_FILES = {"merged_data", "bitcoin_data", "bitcoin_data_global"}


# ══════════════════════════════════════════════════════════════════════════════
#  DỰNG DATASET
# ══════════════════════════════════════════════════════════════════════════════

def _build_sequences(scaled: np.ndarray, look_back: int):
    """Cắt chuỗi đã chuẩn hoá thành các cặp (cửa sổ đầu vào, giá trị kế tiếp)."""
    X, Y = [], []
    for i in range(len(scaled) - look_back):
        X.append(scaled[i : i + look_back])
        Y.append(scaled[i + look_back, 0])  # Cột 0 là Close
    return X, Y


def create_tft_dataset(verbose: bool = True):
    """
    Dựng dataset toàn cục từ mọi file CSV trong data/.

    Trả về (X_train, Y_train, X_val, Y_val, num_features, report).

    Việc chuẩn hoá được thực hiện RIÊNG cho từng mã. Đây là lựa chọn có chủ ý:
    BTC giá hàng chục nghìn USD còn FPT.VN vài chục nghìn VND — đưa chung vào một
    thang đo sẽ khiến mô hình chỉ học được đặc điểm của mã có biên độ lớn nhất.

    Scaler KHÔNG được lưu ra file. Lúc inference, `forecaster.py` khớp scaler mới
    trên chính dữ liệu lịch sử của mã đang dự báo — nhờ vậy hệ thống chạy được với
    bất kỳ mã nào, kể cả mã chưa từng xuất hiện lúc huấn luyện.
    """
    train_X, train_Y, val_X, val_Y = [], [], [], []
    report = {"tickers_used": [], "tickers_skipped": [], "feature_columns": []}

    if not os.path.isdir(DATA_DIR):
        print(f"Không tìm thấy thư mục dữ liệu: {DATA_DIR}")
        return None, None, None, None, 0, report

    csv_files = sorted(f for f in os.listdir(DATA_DIR) if f.endswith(".csv"))
    if verbose:
        print(f"Tìm thấy {len(csv_files)} file CSV trong data/")

    feature_cols_reference = None

    for filename in csv_files:
        ticker = filename[:-4]
        if ticker in SKIP_FILES:
            continue

        try:
            df = pd.read_csv(os.path.join(DATA_DIR, filename), index_col="Date", parse_dates=True)
        except Exception as e:
            report["tickers_skipped"].append({"ticker": ticker, "reason": f"đọc lỗi: {e}"})
            continue

        if df.empty or "Close" not in df.columns:
            report["tickers_skipped"].append({"ticker": ticker, "reason": "thiếu cột Close"})
            continue

        df = df.sort_index()
        df = add_technical_indicators(df)

        available = [c for c in get_feature_columns() if c in df.columns]
        all_cols = ["Close"] + available

        df_clean = df[all_cols].dropna()

        # Cần đủ dữ liệu cho: cửa sổ train + khoảng trống + cửa sổ validation.
        min_rows = LOOK_BACK * 2 + VALIDATION_GAP + 40
        if len(df_clean) < min_rows:
            report["tickers_skipped"].append(
                {"ticker": ticker, "reason": f"chỉ có {len(df_clean)} phiên, cần {min_rows}"}
            )
            continue

        # Số chiều đặc trưng phải giống nhau ở mọi mã — mô hình có input shape cố định.
        if feature_cols_reference is None:
            feature_cols_reference = all_cols
        elif all_cols != feature_cols_reference:
            report["tickers_skipped"].append({"ticker": ticker, "reason": "tập đặc trưng không khớp"})
            continue

        # ── Cắt theo thời gian TRƯỚC khi chuẩn hoá ──
        split_idx = int(len(df_clean) * TRAIN_RATIO)
        train_slice = df_clean.iloc[:split_idx]
        val_slice = df_clean.iloc[split_idx + VALIDATION_GAP :]

        if len(train_slice) < LOOK_BACK + 10 or len(val_slice) < LOOK_BACK + 5:
            report["tickers_skipped"].append({"ticker": ticker, "reason": "không đủ dữ liệu sau khi cắt"})
            continue

        # Scaler khớp CHỈ trên phần train. Khớp trên toàn bộ dữ liệu sẽ để lộ
        # giá trị min/max của tương lai vào quá trình huấn luyện — cũng là một
        # dạng rò rỉ, tinh vi hơn nhưng vẫn làm kết quả đẹp giả tạo.
        scaler = MinMaxScaler(feature_range=(0, 1))
        scaler.fit(train_slice.values)

        tx, ty = _build_sequences(scaler.transform(train_slice.values), LOOK_BACK)
        vx, vy = _build_sequences(scaler.transform(val_slice.values), LOOK_BACK)

        train_X.extend(tx)
        train_Y.extend(ty)
        val_X.extend(vx)
        val_Y.extend(vy)

        report["tickers_used"].append(
            {"ticker": ticker, "train_samples": len(tx), "val_samples": len(vx)}
        )
        if verbose:
            print(f"  {ticker}: {len(tx)} mẫu train, {len(vx)} mẫu validation")

    if not train_X:
        return None, None, None, None, 0, report

    X_train = np.array(train_X, dtype=np.float32)
    X_val = np.array(val_X, dtype=np.float32)
    # Pinball loss cần y_true có cùng số cột với y_pred (3 quantile).
    Y_train = np.column_stack([train_Y] * 3).astype(np.float32)
    Y_val = np.column_stack([val_Y] * 3).astype(np.float32)

    # Chỉ trộn tập TRAIN. Tập validation giữ nguyên thứ tự thời gian.
    rng = np.random.default_rng(seed=42)
    perm = rng.permutation(len(X_train))
    X_train, Y_train = X_train[perm], Y_train[perm]

    report["feature_columns"] = feature_cols_reference or []
    num_features = X_train.shape[2]

    if verbose:
        print(f"\nDataset: train={X_train.shape}, validation={X_val.shape}")
        print(f"Số mã dùng được: {len(report['tickers_used'])}, bỏ qua: {len(report['tickers_skipped'])}")

    return X_train, Y_train, X_val, Y_val, num_features, report


# ══════════════════════════════════════════════════════════════════════════════
#  HUẤN LUYỆN
# ══════════════════════════════════════════════════════════════════════════════

def plot_loss(history, filename: str = "loss_tft.png") -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")  # Không cần màn hình — quan trọng khi chạy trên Colab/Kaggle
        import matplotlib.pyplot as plt

        plt.figure(figsize=(10, 5))
        plt.plot(history.history["loss"], label="Train loss", color="#f0b90b")
        if "val_loss" in history.history:
            plt.plot(history.history["val_loss"], label="Validation loss", color="#3861fb")
        plt.title("TFT Training Loss (chia tập theo thời gian)")
        plt.xlabel("Epoch")
        plt.ylabel("Quantile (pinball) loss")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(os.path.join(MODELS_DIR, filename), dpi=150)
        plt.close()
        print(f"Đã lưu đồ thị loss: {filename}")
    except Exception as e:
        print(f"Bỏ qua vẽ đồ thị loss: {e}")


def train_tft(fresh: bool = False) -> None:
    """
    Huấn luyện mô hình.

    `fresh=True` bỏ qua checkpoint cũ và khởi tạo lại từ đầu — nên dùng khi
    tập đặc trưng hoặc cách chia dữ liệu thay đổi, vì lúc đó tiếp tục huấn luyện
    từ trọng số cũ sẽ trộn lẫn hai chế độ dữ liệu khác nhau.
    """
    os.makedirs(MODELS_DIR, exist_ok=True)

    print("=" * 70)
    print("HUẤN LUYỆN TEMPORAL FUSION TRANSFORMER")
    print("=" * 70)

    X_train, Y_train, X_val, Y_val, num_features, report = create_tft_dataset()
    if X_train is None:
        print("Không dựng được dataset. Kiểm tra lại thư mục data/.")
        return

    model_path = os.path.join(MODELS_DIR, "global_tft.keras")

    if os.path.exists(model_path) and not fresh:
        print("Nạp lại checkpoint đã có để huấn luyện tiếp...")
        from backend.models.tft_model import quantile_loss

        model = tf.keras.models.load_model(
            model_path, custom_objects={"loss_fn": quantile_loss([0.1, 0.5, 0.9])}
        )
        # Kiến trúc cũ có thể không khớp số đặc trưng hiện tại.
        if model.input_shape[-1] != num_features:
            print(
                f"Số đặc trưng đã thay đổi ({model.input_shape[-1]} -> {num_features}). "
                "Khởi tạo mô hình mới."
            )
            model = compile_tft_model(
                build_tft_model(input_shape=(LOOK_BACK, num_features)), learning_rate=0.001
            )
    else:
        print(f"Khởi tạo mô hình mới: input=({LOOK_BACK}, {num_features})")
        model = compile_tft_model(
            build_tft_model(
                input_shape=(LOOK_BACK, num_features),
                hidden_size=64,
                num_heads=4,
                num_blocks=2,
                dropout_rate=0.2,
                num_quantiles=3,
            ),
            learning_rate=0.001,
        )

    model.summary()

    print("\nBắt đầu huấn luyện...")
    history = model.fit(
        X_train,
        Y_train,
        validation_data=(X_val, Y_val),  # Tập validation tách theo thời gian, không dùng validation_split
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        callbacks=get_tft_callbacks(model_path, patience=15),
        verbose=1,
    )

    plot_loss(history)

    # Lưu metadata để các script khác (đánh giá, fine-tune) biết mô hình được
    # huấn luyện với cấu hình nào.
    meta = {
        "num_features": int(num_features),
        "look_back": LOOK_BACK,
        "feature_columns": report["feature_columns"],
        "train_ratio": TRAIN_RATIO,
        "validation_gap": VALIDATION_GAP,
        "split_strategy": "chronological-per-ticker",
        "train_samples": int(len(X_train)),
        "val_samples": int(len(X_val)),
        "tickers_used": [t["ticker"] for t in report["tickers_used"]],
        "trained_at": datetime.now().isoformat(),
        "best_val_loss": float(min(history.history.get("val_loss", [float("nan")]))),
    }

    with open(os.path.join(MODELS_DIR, "tft_meta.pkl"), "wb") as f:
        pickle.dump(meta, f)
    # Lưu thêm bản JSON để đọc được bằng mắt và trích thẳng vào báo cáo.
    with open(os.path.join(MODELS_DIR, "tft_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print("HOÀN TẤT HUẤN LUYỆN")
    print(f"  Mô hình:      {model_path}")
    print(f"  Val loss tốt nhất: {meta['best_val_loss']:.6f}")
    print(f"  Số mã:        {len(meta['tickers_used'])}")
    print(f"  Mẫu train:    {meta['train_samples']:,}")
    print(f"  Mẫu val:      {meta['val_samples']:,}")
    print("=" * 70)
    print("\nBước tiếp theo: chạy `python -m backend.evaluate_tft` để so sánh với")
    print("baseline (naive forecast, moving average) và lấy số liệu cho báo cáo.")


if __name__ == "__main__":
    train_tft(fresh="--fresh" in sys.argv)
