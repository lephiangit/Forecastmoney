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
