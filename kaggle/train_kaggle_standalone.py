"""
feature_engineering.py – Technical indicator computation for enhanced model inputs.
Generates RSI, MACD, Bollinger Bands, ATR, OBV, rolling stats, and time features.
"""

import numpy as np
import pandas as pd


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add comprehensive technical indicators to OHLCV DataFrame.
    Expects columns: Open, High, Low, Close, Volume.
    Returns a copy with new indicator columns.
    """
    df = df.copy()

    close = df["Close"].astype(float)
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    volume = df["Volume"].astype(float) if "Volume" in df.columns else pd.Series(0, index=df.index)

    # ── RSI (Relative Strength Index) ────────────────────────────────────
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=13, adjust=False).mean()
    avg_loss = loss.ewm(com=13, adjust=False).mean()
    rs = avg_gain / avg_loss
    df["RSI"] = 100 - (100 / (1 + rs))

    # ── MACD ──────────────────────────────────────────────────────────────
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]

    # ── Bollinger Bands ──────────────────────────────────────────────────
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    df["BB_Upper"] = sma20 + (std20 * 2)
    df["BB_Lower"] = sma20 - (std20 * 2)
    df["BB_Width"] = (df["BB_Upper"] - df["BB_Lower"]) / sma20  # Normalized

    # ── ATR (Average True Range) ──────────────────────────────────────────
    tr = pd.DataFrame({
        "hl": high - low,
        "hc": abs(high - close.shift(1)),
        "lc": abs(low - close.shift(1)),
    }).max(axis=1)
    df["ATR"] = tr.rolling(14).mean()

    # ── OBV (On-Balance Volume) ──────────────────────────────────────────
    obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()
    df["OBV"] = obv

    # ── Moving Averages ──────────────────────────────────────────────────
    for window in [5, 10, 20, 50]:
        df[f"MA{window}"] = close.rolling(window).mean()

    # ── Rolling Statistics ───────────────────────────────────────────────
    df["Volatility_10d"] = close.pct_change().rolling(10).std() * 100
    df["Volatility_30d"] = close.pct_change().rolling(30).std() * 100
    df["Momentum_5d"] = close.pct_change(5) * 100
    df["Momentum_10d"] = close.pct_change(10) * 100

    # ── Price Ratios ─────────────────────────────────────────────────────
    df["Close_to_MA20"] = close / sma20
    df["Close_to_MA50"] = close / close.rolling(50).mean()

    # ── Time Features ────────────────────────────────────────────────────
    if hasattr(df.index, 'dayofweek'):
        df["DayOfWeek"] = df.index.dayofweek
        df["Month"] = df.index.month
        df["DayOfMonth"] = df.index.day
        df["IsMonthEnd"] = df.index.is_month_end.astype(int)
        df["IsQuarterEnd"] = df.index.is_quarter_end.astype(int)

    return df


def get_feature_columns() -> list:
    """Return list of feature columns used for model training (excluding target)."""
    return [
        "RSI", "MACD", "MACD_Signal", "MACD_Hist",
        "BB_Upper", "BB_Lower", "BB_Width",
        "ATR", "OBV",
        "MA5", "MA10", "MA20", "MA50",
        "Volatility_10d", "Volatility_30d",
        "Momentum_5d", "Momentum_10d",
        "Close_to_MA20", "Close_to_MA50",
        "DayOfWeek", "Month",
    ]


def prepare_multivariate_data(df: pd.DataFrame, look_back: int = 60,
                               target_col: str = "Close",
                               split_ratio: float = 0.8):
    """
    Prepare multivariate dataset for TFT/advanced model training.
    Returns X_train, Y_train, X_test, Y_test, feature_scaler, target_scaler.
    """
    from sklearn.preprocessing import MinMaxScaler

    # Add indicators
    df = add_technical_indicators(df)

    feature_cols = get_feature_columns()

    # Filter to available columns
    available_features = [c for c in feature_cols if c in df.columns]

    # Drop NaN rows (from rolling windows)
    df_clean = df[[target_col] + available_features].dropna()

    if len(df_clean) < look_back + 10:
        raise ValueError(f"Dữ liệu quá ít sau khi tính indicators: {len(df_clean)} rows")

    # Scale features
    feature_scaler = MinMaxScaler(feature_range=(0, 1))
    target_scaler = MinMaxScaler(feature_range=(0, 1))

    features_scaled = feature_scaler.fit_transform(df_clean[available_features].values)
    target_scaled = target_scaler.fit_transform(df_clean[[target_col]].values)

    # Combine: target + features
    combined = np.hstack([target_scaled, features_scaled])

    # Create sequences
    X, Y = [], []
    for i in range(len(combined) - look_back):
        X.append(combined[i:i + look_back])
        Y.append(target_scaled[i + look_back, 0])

    X = np.array(X)
    Y = np.array(Y)

    # Train/Test split
    train_size = int(len(X) * split_ratio)
    X_train = X[:train_size]
    Y_train = Y[:train_size]
    X_test = X[train_size:]
    Y_test = Y[train_size:]

    return X_train, Y_train, X_test, Y_test, feature_scaler, target_scaler, available_features
"""
tft_model.py – Temporal Fusion Transformer implementation using TensorFlow/Keras.
A lightweight TFT architecture suitable for financial time series with:
  - Variable Selection Network (feature importance)
  - Multi-Head Attention for temporal patterns
  - Gated Residual Networks
  - Quantile outputs for confidence intervals
"""

import numpy as np
import os

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import tensorflow as tf
from tensorflow.keras.models import Model
from tensorflow.keras.layers import (
    Input, Dense, Dropout, LayerNormalization,
    MultiHeadAttention, GlobalAveragePooling1D,
    Concatenate, Multiply, Activation, Add,
    Conv1D, Flatten, Lambda
)
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint, ReduceLROnPlateau


# ──────────────────────────────────────────────────────────────────────────────
#  BUILDING BLOCKS
# ──────────────────────────────────────────────────────────────────────────────

class GatedResidualNetwork(tf.keras.layers.Layer):
    """
    Gated Residual Network (GRN) – Core building block of TFT.
    Applies non-linear processing with gating to control information flow.
    """
    def __init__(self, hidden_size, output_size=None, dropout_rate=0.1, **kwargs):
        super().__init__(**kwargs)
        self.hidden_size = hidden_size
        self.output_size = output_size or hidden_size
        self.dropout_rate = dropout_rate

    def build(self, input_shape):
        self.dense1 = Dense(self.hidden_size, activation="elu")
        self.dense2 = Dense(self.hidden_size)
        self.gate = Dense(self.output_size, activation="sigmoid")
        self.projection = Dense(self.output_size)
        self.dropout = Dropout(self.dropout_rate)
        self.layer_norm = LayerNormalization()

        input_dim = input_shape[-1]
        if input_dim != self.output_size:
            self.skip_proj = Dense(self.output_size)
        else:
            self.skip_proj = None

    def call(self, x, training=False):
        skip = x
        if self.skip_proj is not None:
            skip = self.skip_proj(skip)

        h = self.dense1(x)
        h = self.dropout(h, training=training)
        h = self.dense2(h)

        gate = self.gate(x)
        h = self.projection(h)
        h = gate * h

        return self.layer_norm(skip + h)


class VariableSelectionNetwork(tf.keras.layers.Layer):
    """
    Variable Selection Network – Learns which input features are most important.
    Provides interpretability by outputting feature importance weights.
    """
    def __init__(self, num_features, hidden_size, dropout_rate=0.1, **kwargs):
        super().__init__(**kwargs)
        self.num_features = num_features
        self.hidden_size = hidden_size
        self.dropout_rate = dropout_rate

    def build(self, input_shape):
        self.grns = [
            GatedResidualNetwork(self.hidden_size, dropout_rate=self.dropout_rate)
            for _ in range(self.num_features)
        ]
        self.softmax_dense = Dense(self.num_features, activation="softmax")
        self.flatten_grn = GatedResidualNetwork(
            self.hidden_size, dropout_rate=self.dropout_rate
        )

    def call(self, x, training=False):
        # x shape: (batch, time, features)
        # Compute variable weights using flattened input
        batch_size = tf.shape(x)[0]
        time_steps = tf.shape(x)[1]

        # Global context for selection
        x_flat = tf.reshape(x, [batch_size * time_steps, self.num_features])
        weights = self.softmax_dense(x_flat)
        weights = tf.reshape(weights, [batch_size, time_steps, self.num_features])

        # Process each variable through its own GRN
        processed = []
        for i in range(self.num_features):
            var_input = x[:, :, i:i+1]
            processed.append(self.grns[i](var_input, training=training))

        # Stack and apply selection weights
        stacked = tf.concat(processed, axis=-1)

        # Weight and sum
        weighted = stacked * weights
        output = tf.reduce_sum(
            tf.reshape(weighted, [batch_size, time_steps, self.num_features, -1]),
            axis=2
        )

        return output, weights


# ──────────────────────────────────────────────────────────────────────────────
#  TFT MODEL
# ──────────────────────────────────────────────────────────────────────────────

def build_tft_model(
    input_shape,       # (look_back, num_features)
    hidden_size=64,
    num_heads=4,
    num_blocks=2,
    dropout_rate=0.2,
    num_quantiles=3,   # p10, p50, p90
):
    """
    Build a lightweight Temporal Fusion Transformer.

    Args:
        input_shape: (time_steps, num_features) tuple
        hidden_size: Hidden dimension size
        num_heads: Number of attention heads
        num_blocks: Number of transformer blocks
        dropout_rate: Dropout probability
        num_quantiles: Number of quantile outputs (3 = p10, p50, p90)

    Returns:
        Keras Model with quantile outputs
    """
    time_steps, num_features = input_shape

    inputs = Input(shape=(time_steps, num_features), name="input")

    # ── Variable Selection ────────────────────────────────────────────────
    # Project input features to hidden size via linear embedding
    x = Dense(hidden_size, name="input_projection")(inputs)
    x = Dropout(dropout_rate)(x)

    # ── Temporal Processing (Transformer Encoder Blocks) ──────────────────
    for i in range(num_blocks):
        # Pre-LayerNorm
        attn_input = LayerNormalization(name=f"pre_norm_{i}")(x)

        # Multi-Head Self-Attention
        attn_output = MultiHeadAttention(
            key_dim=hidden_size // num_heads,
            num_heads=num_heads,
            dropout=dropout_rate,
            name=f"attention_{i}"
        )(attn_input, attn_input)
        attn_output = Dropout(dropout_rate)(attn_output)

        # Residual connection
        x = Add(name=f"attn_residual_{i}")([x, attn_output])

        # Feed-Forward GRN
        ff_input = LayerNormalization(name=f"ff_norm_{i}")(x)
        ff_output = Dense(hidden_size * 4, activation="gelu", name=f"ff_dense1_{i}")(ff_input)
        ff_output = Dropout(dropout_rate)(ff_output)
        ff_output = Dense(hidden_size, name=f"ff_dense2_{i}")(ff_output)
        ff_output = Dropout(dropout_rate)(ff_output)

        # Gating
        gate = Dense(hidden_size, activation="sigmoid", name=f"ff_gate_{i}")(ff_input)
        ff_output = Multiply(name=f"ff_gated_{i}")([ff_output, gate])

        # Residual
        x = Add(name=f"ff_residual_{i}")([x, ff_output])

    # ── Final normalization ───────────────────────────────────────────────
    x = LayerNormalization(name="final_norm")(x)

    # ── Temporal aggregation (last time step + global avg) ────────────────
    last_step = x[:, -1, :]  # Take last time step
    global_avg = GlobalAveragePooling1D()(x)
    combined = Concatenate(name="temporal_combine")([last_step, global_avg])
    combined = Dense(hidden_size, activation="gelu", name="combine_proj")(combined)
    combined = Dropout(dropout_rate)(combined)

    # ── Quantile Outputs ──────────────────────────────────────────────────
    # Output multiple quantiles for confidence intervals
    outputs = Dense(num_quantiles, name="quantile_output")(combined)

    model = Model(inputs=inputs, outputs=outputs, name="TFT_Forecaster")

    return model


def quantile_loss(quantiles=[0.1, 0.5, 0.9]):
    """
    Quantile loss function for prediction intervals.
    Produces calibrated confidence bounds instead of fixed ±3%.
    """
    def loss_fn(y_true, y_pred):
        losses = []
        # Ensure y_true has the same shape as y_pred (e.g., if passing single column, broadcast it)
        if len(y_true.shape) == 1 or y_true.shape[-1] == 1:
            y_true_expanded = tf.repeat(tf.reshape(y_true, [-1, 1]), len(quantiles), axis=-1)
        else:
            y_true_expanded = y_true

        for i, q in enumerate(quantiles):
            error = y_true_expanded[:, i] - y_pred[:, i]
            losses.append(tf.maximum(q * error, (q - 1) * error))
        return tf.reduce_mean(tf.stack(losses, axis=-1))
    return loss_fn


def compile_tft_model(model, learning_rate=0.001):
    """Compile TFT model with quantile loss and Adam optimizer."""
    optimizer = tf.keras.optimizers.Adam(learning_rate=learning_rate)
    model.compile(
        optimizer=optimizer,
        loss=quantile_loss([0.1, 0.5, 0.9]),
        metrics=["mae"]
    )
    return model


def get_tft_callbacks(model_path, patience=15):
    """Get standard callbacks for TFT training."""
    return [
        EarlyStopping(
            monitor="val_loss",
            patience=patience,
            restore_best_weights=True,
            verbose=1,
        ),
        ModelCheckpoint(
            model_path,
            save_best_only=True,
            monitor="val_loss",
            verbose=1,
        ),
        ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.5,
            patience=7,
            min_lr=1e-6,
            verbose=1,
        ),
    ]
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
# BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
# PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
# if PROJECT_ROOT not in sys.path:
#     sys.path.insert(0, PROJECT_ROOT)

# from backend.models.tft_model import build_tft_model, compile_tft_model, get_tft_callbacks
# from backend.models.feature_engineering import add_technical_indicators, get_feature_columns

# Kaggle Dataset paths
import glob
import sys

# Tự động tìm thư mục chứa file CSV để khỏi phải đoán đường dẫn
DATA_DIR = None
if os.path.exists("/kaggle/input"):
    for path in glob.glob("/kaggle/input/**/*.csv", recursive=True):
        DATA_DIR = os.path.dirname(path)
        break
    if DATA_DIR is None:
        print("❌ KHÔNG TÌM THẤY FILE DATA NÀO! Bạn nhớ Add Data ở góc phải nhé.")
        sys.exit(1)
else:
    # Fallback cho chạy local
    BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
    DATA_DIR = os.path.join(PROJECT_ROOT, "data")

MODELS_DIR = "/kaggle/working/models" if os.path.exists("/kaggle/working") else os.path.join(PROJECT_ROOT, "models")
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

    # Tính toán độ chính xác dự kiến dựa trên tập Validation (val_mae)
    if "val_mae" in history.history:
        final_val_mae = history.history["val_mae"][-1]
        # Vì dữ liệu đã được scale về [0, 1], MAE cũng mang ý nghĩa % sai số trên biên độ
        accuracy = max(0.0, (1.0 - final_val_mae) * 100)
        print(f"🎯 Độ chính xác dự kiến (Validation Accuracy): {accuracy:.2f}%")


if __name__ == "__main__":
    train_tft()
