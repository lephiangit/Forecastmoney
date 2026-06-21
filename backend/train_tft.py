"""
train_tft.py
Huấn luyện Temporal Fusion Transformer (TFT) toàn cục từ tất cả dữ liệu.
Sử dụng multivariate features (technical indicators) thay vì chỉ Close price.
"""

import os
import sys
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
import pickle
import matplotlib.pyplot as plt

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
import tensorflow as tf

# Ensure project root on path (one level up from backend)
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.models.tft_model import build_tft_model, compile_tft_model, get_tft_callbacks
from backend.models.feature_engineering import add_technical_indicators, get_feature_columns

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
LOOK_BACK = 60
EPOCHS = 100
BATCH_SIZE = 64


def create_tft_dataset():
    """
    Build global multivariate dataset from all CSV files.
    Each sample: (look_back, num_features) → 3 quantile targets.
    """
    all_X = []
    all_Y = []

    csv_files = [f for f in os.listdir(DATA_DIR) if f.endswith(".csv")]
    skip_files = {"merged_data", "bitcoin_data", "bitcoin_data_global"}

    print(f"📁 Tìm thấy {len(csv_files)} file CSV trong data/")

    for file in csv_files:
        ticker = file.replace(".csv", "")
        if ticker in skip_files:
            continue

        file_path = os.path.join(DATA_DIR, file)

        try:
            df = pd.read_csv(file_path, index_col="Date", parse_dates=True)
            if df.empty or len(df) < LOOK_BACK + 60:
                print(f"⚠️ Bỏ qua {ticker}: Không đủ dữ liệu ({len(df)} rows)")
                continue

            if "Close" not in df.columns:
                print(f"⚠️ Bỏ qua {ticker}: Không có cột 'Close'")
                continue

            # Add technical indicators
            df = add_technical_indicators(df)

            # Select feature columns
            feature_cols = get_feature_columns()
            available_cols = [c for c in feature_cols if c in df.columns]

            # Target column
            target_col = "Close"
            all_cols = [target_col] + available_cols

            # Clean
            df_clean = df[all_cols].dropna()
            if len(df_clean) < LOOK_BACK + 10:
                print(f"⚠️ Bỏ qua {ticker}: Dữ liệu quá ít sau indicators ({len(df_clean)} rows)")
                continue

            # Scale per-ticker (important: each asset has different price range)
            scaler = MinMaxScaler(feature_range=(0, 1))
            scaled_data = scaler.fit_transform(df_clean[all_cols].values)

            # Save scaler for this ticker (includes all features)
            scaler_path = os.path.join(MODELS_DIR, f"scaler_tft_{ticker}.pkl")
            with open(scaler_path, "wb") as f:
                pickle.dump(scaler, f)

            # Also save/update the original Close-only scaler for backward compatibility
            close_scaler = MinMaxScaler(feature_range=(0, 1))
            close_scaler.fit_transform(df_clean[[target_col]].values)
            close_scaler_path = os.path.join(MODELS_DIR, f"scaler_{ticker}.pkl")
            with open(close_scaler_path, "wb") as f:
                pickle.dump(close_scaler, f)

            # Create sequences
            X, Y = [], []
            for i in range(len(scaled_data) - LOOK_BACK):
                X.append(scaled_data[i:i + LOOK_BACK])
                # Target: Close price (column 0) — replicated for 3 quantiles during training
                Y.append(scaled_data[i + LOOK_BACK, 0])

            all_X.extend(X)
            all_Y.extend(Y)

            print(f"✅ {ticker}: {len(X)} mẫu, {len(available_cols)} features")

        except Exception as e:
            print(f"❌ Lỗi xử lý {ticker}: {e}")

    if not all_X:
        return None, None, 0

    X = np.array(all_X)
    Y = np.array(all_Y)

    # Replicate Y for 3 quantiles (quantile loss will handle them differently)
    Y_quantile = np.column_stack([Y, Y, Y])

    # Shuffle
    indices = np.arange(X.shape[0])
    np.random.shuffle(indices)
    X = X[indices]
    Y_quantile = Y_quantile[indices]

    num_features = X.shape[2]
    print(f"\n📊 Dataset: X={X.shape}, Y={Y_quantile.shape}")

    return X, Y_quantile, num_features


def plot_loss(history, filename):
    """Plot and save training loss curve."""
    plt.figure(figsize=(10, 5))
    plt.plot(history.history["loss"], label="Training Loss", color="#f0b90b")
    if "val_loss" in history.history:
        plt.plot(history.history["val_loss"], label="Validation Loss", color="#3861fb")
    plt.title("TFT Training Loss", fontsize=14)
    plt.xlabel("Epochs")
    plt.ylabel("Quantile Loss")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(MODELS_DIR, filename), dpi=150)
    plt.close()
    print(f"📈 Đồ thị loss: {filename}")


def train_tft():
    """Main training function for TFT model."""
    os.makedirs(MODELS_DIR, exist_ok=True)

    print("=" * 60)
    print("🚀 HUẤN LUYỆN TEMPORAL FUSION TRANSFORMER (TFT)")
    print("=" * 60)

    X, Y, num_features = create_tft_dataset()

    if X is None:
        print("❌ Không có dữ liệu!")
        return

    model_path = os.path.join(MODELS_DIR, "global_tft.keras")

    if os.path.exists(model_path):
        print("♻️ Nạp TFT đã huấn luyện trước đó...")
        from models.tft_model import quantile_loss
        model = tf.keras.models.load_model(
            model_path,
            custom_objects={"loss_fn": quantile_loss([0.1, 0.5, 0.9])}
        )
    else:
        print(f"🌱 Khởi tạo TFT mới: input=({LOOK_BACK}, {num_features})")
        model = build_tft_model(
            input_shape=(LOOK_BACK, num_features),
            hidden_size=64,
            num_heads=4,
            num_blocks=2,
            dropout_rate=0.2,
            num_quantiles=3,
        )
        model = compile_tft_model(model, learning_rate=0.001)

    model.summary()

    callbacks = get_tft_callbacks(model_path, patience=15)

    print("\n⏳ Bắt đầu huấn luyện TFT...")
    history = model.fit(
        X, Y,
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        validation_split=0.1,
        callbacks=callbacks,
        verbose=1,
    )

    plot_loss(history, "loss_tft.png")

    # Save feature metadata
    meta_path = os.path.join(MODELS_DIR, "tft_meta.pkl")
    with open(meta_path, "wb") as f:
        pickle.dump({
            "num_features": num_features,
            "look_back": LOOK_BACK,
            "feature_columns": get_feature_columns(),
        }, f)

    print("\n✅ HOÀN TẤT HUẤN LUYỆN TFT!")
    print(f"   Model: {model_path}")
    print(f"   Meta: {meta_path}")


if __name__ == "__main__":
    train_tft()
