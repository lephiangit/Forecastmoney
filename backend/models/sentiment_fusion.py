"""
sentiment_fusion.py – SentimentFusion prediction model.
Combines TFT technical price prediction with research/news sentiment signals
to produce a refined, sentiment-aware forecast.

Architecture:
  Input 1: TFT predicted prices (normalized)
  Input 2: Sentiment score (-1.0 to +1.0)
  Input 3: Confidence score (0.0 to 1.0)
  Input 4: Technical signals (RSI z-score, MACD direction, BB position)
  → Dense Fusion Layers
  → Output: Adjusted price deltas (percentage adjustments per day)
"""

import numpy as np
import os
import pickle
from typing import Optional, Tuple, Dict
import pandas as pd

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
import tensorflow as tf
from tensorflow.keras.models import Model, load_model, Sequential
from tensorflow.keras.layers import (
    Input, Dense, Dropout, LayerNormalization,
    Concatenate, BatchNormalization
)
from tensorflow.keras.callbacks import EarlyStopping


# ──────────────────────────────────────────────────────────────────────────────
#  MODEL ARCHITECTURE
# ──────────────────────────────────────────────────────────────────────────────

def build_sentiment_fusion_model(
    forecast_days: int = 7,
    hidden_size: int = 32,
    dropout_rate: float = 0.1,
):
    """
    Build a lightweight SentimentFusion model.

    Inputs:
      - tft_prices: (forecast_days,) — normalized TFT price predictions
      - market_signals: (5,) — [sentiment_score, confidence, rsi_z, macd_dir, bb_pos]

    Output:
      - adjustments: (forecast_days,) — price adjustment factors (multiplicative)
    """
    # Price sequence input (TFT predictions)
    price_input = Input(shape=(forecast_days,), name="tft_prices")

    # Market signal input
    signal_input = Input(shape=(5,), name="market_signals")

    # Process price sequence
    price_h = Dense(hidden_size, activation="gelu")(price_input)
    price_h = Dropout(dropout_rate)(price_h)
    price_h = Dense(hidden_size // 2, activation="gelu")(price_h)

    # Process market signals
    signal_h = Dense(hidden_size // 2, activation="gelu")(signal_input)
    signal_h = Dense(hidden_size // 4, activation="gelu")(signal_h)

    # Fusion
    fused = Concatenate()([price_h, signal_h])
    fused = Dense(hidden_size, activation="gelu")(fused)
    fused = Dropout(dropout_rate)(fused)
    fused = LayerNormalization()(fused)
    fused = Dense(hidden_size // 2, activation="gelu")(fused)

    # Output: multiplicative adjustment factors
    # Using tanh to bound adjustments to [-1, 1] then scale to small adjustments
    raw_adj = Dense(forecast_days, activation="tanh")(fused)

    # Bound to [-0.05, 0.05] — max ±5% sentiment-driven adjustment
    adjustments = tf.keras.layers.Lambda(
        lambda x: x * 0.05, name="adjustments"
    )(raw_adj)

    model = Model(
        inputs=[price_input, signal_input],
        outputs=adjustments,
        name="SentimentFusion"
    )

    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
        loss="mse",
        metrics=["mae"]
    )

    return model


# ──────────────────────────────────────────────────────────────────────────────
#  SIGNAL EXTRACTION
# ──────────────────────────────────────────────────────────────────────────────

def extract_market_signals(df: pd.DataFrame, research_analysis: Optional[Dict] = None) -> np.ndarray:
    """
    Extract 5-dimensional market signal vector from price data + research.

    Returns np.array of shape (5,):
      [sentiment_score, confidence, rsi_z, macd_direction, bb_position]
    """
    signals = np.zeros(5)

    # Signal 0 & 1: From Research Agent
    if research_analysis is not None:
        sentiment = research_analysis.get("sentiment", "NEUTRAL")
        confidence = float(research_analysis.get("confidence", 0.5))

        if sentiment == "BULLISH":
            signals[0] = confidence
        elif sentiment == "BEARISH":
            signals[0] = -confidence
        else:
            signals[0] = 0.0

        signals[1] = confidence
    else:
        signals[0] = 0.0
        signals[1] = 0.5  # Neutral confidence

    # Technical signals from price data
    try:
        close = df["Close"].astype(float)

        # Signal 2: RSI z-score (normalized RSI, centered around 50)
        if "RSI" in df.columns:
            rsi = df["RSI"].iloc[-1]
            signals[2] = (rsi - 50) / 50  # -1 to +1
        else:
            delta = close.diff()
            gain = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
            loss = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
            rs = gain / (loss + 1e-8)
            rsi = (100 - 100 / (1 + rs)).iloc[-1]
            signals[2] = (rsi - 50) / 50

        # Signal 3: MACD direction
        if "MACD" in df.columns and "MACD_Signal" in df.columns:
            macd_diff = df["MACD"].iloc[-1] - df["MACD_Signal"].iloc[-1]
            signals[3] = np.sign(macd_diff)
        else:
            ema12 = close.ewm(span=12).mean()
            ema26 = close.ewm(span=26).mean()
            macd = ema12 - ema26
            macd_signal = macd.ewm(span=9).mean()
            signals[3] = np.sign((macd - macd_signal).iloc[-1])

        # Signal 4: Bollinger Band position (where is price relative to bands)
        ma20 = close.rolling(20).mean().iloc[-1]
        std20 = close.rolling(20).std().iloc[-1]
        current = close.iloc[-1]
        upper = ma20 + 2 * std20
        lower = ma20 - 2 * std20
        band_width = upper - lower
        if band_width > 0:
            signals[4] = (current - ma20) / (band_width / 2)
            signals[4] = np.clip(signals[4], -1, 1)

    except Exception as e:
        print(f"⚠️ Signal extraction error: {e}")

    return signals.astype(np.float32)


# ──────────────────────────────────────────────────────────────────────────────
#  INFERENCE ENGINE
# ──────────────────────────────────────────────────────────────────────────────

class SentimentFusionEngine:
    """Inference wrapper for the SentimentFusion model."""

    _instance: Optional["SentimentFusionEngine"] = None

    def __init__(self, model_dir: str):
        self.model_dir = model_dir
        self._models: Dict[int, Model] = {}  # Keyed by forecast_days

    @classmethod
    def get_instance(cls, model_dir: str) -> "SentimentFusionEngine":
        if cls._instance is None:
            cls._instance = cls(model_dir)
        return cls._instance

    def _load_or_create(self, days: int) -> Model:
        """Load existing SentimentFusion model or create a new one."""
        if days in self._models:
            return self._models[days]

        model_path = os.path.join(self.model_dir, f"sentiment_fusion_{days}d.keras")
        if os.path.exists(model_path):
            try:
                self._models[days] = load_model(model_path)
                print(f"✅ SentimentFusion {days}d loaded.")
                return self._models[days]
            except Exception as e:
                print(f"⚠️ Failed to load SentimentFusion {days}d: {e}")

        # Create a new untrained model (will use rule-based fallback)
        model = build_sentiment_fusion_model(forecast_days=days)
        self._models[days] = model
        return model

    def predict(
        self,
        tft_prices: np.ndarray,        # shape (days,)
        market_signals: np.ndarray,    # shape (5,)
        days: int,
    ) -> np.ndarray:
        """
        Apply sentiment fusion adjustments to TFT prices.
        Returns adjusted prices of shape (days,).
        """
        model_path = os.path.join(self.model_dir, f"sentiment_fusion_{days}d.keras")

        if os.path.exists(model_path):
            # Use trained model
            model = self._load_or_create(days)
            try:
                prices_input = tft_prices[:days].reshape(1, -1)
                signals_input = market_signals.reshape(1, -1)
                adjustments = model.predict([prices_input, signals_input], verbose=0)[0]
                return tft_prices[:days] * (1 + adjustments)
            except Exception as e:
                print(f"⚠️ SentimentFusion inference error: {e}")

        # Fallback: rule-based sentiment adjustment
        return self._rule_based_adjust(tft_prices[:days], market_signals)

    def _rule_based_adjust(self, tft_prices: np.ndarray, signals: np.ndarray) -> np.ndarray:
        """
        Rule-based sentiment adjustment when model is not trained.
        Applies a smooth sentiment-driven momentum to TFT predictions.
        """
        sentiment_score = signals[0]   # -1 to +1
        confidence = signals[1]        # 0 to 1
        days = len(tft_prices)

        # Create a smooth adjustment curve that fades over time
        time_factor = np.linspace(1.0, 0.3, days)  # Stronger near-term, weaker long-term

        # Max adjustment: ±3% for high confidence, scaled down for low
        max_adj = 0.03 * confidence
        adjustments = sentiment_score * max_adj * time_factor

        return tft_prices * (1 + adjustments)
