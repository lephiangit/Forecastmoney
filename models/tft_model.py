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
        for i, q in enumerate(quantiles):
            error = y_true - y_pred[:, i]
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
