"""
cron_accuracy_learner.py
A standalone script meant to run daily (e.g., via cron) to:
1. Evaluate past predictions against actual closing prices.
2. Calculate the % Error and save it to the `model_accuracy` table.
3. Automatically fine-tune the TFT model on recent data (Online Learning).
"""

import os
import sys
from datetime import datetime, timezone

# Ensure project root is in path
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.database import get_pending_evaluations, update_accuracy_evaluation
from backend.models.forecaster import fetch_ohlcv

def run_evaluations():
    print(f"[{datetime.now().isoformat()}] Starting Model Accuracy Evaluation...")
    
    pending = get_pending_evaluations()
    if not pending:
        print("✅ No pending evaluations. Everything is up to date.")
        return []

    print(f"🔍 Found {len(pending)} predictions pending evaluation.")
    
    evaluated_tickers = set()

    for record in pending:
        record_id = record["id"]
        ticker = record["ticker"]
        forecast_date = record["forecast_date"]
        predicted_price = float(record["predicted_price"])
        
        # We need historical data up to today to check the forecast_date
        # If forecast_date is today or earlier, we can evaluate
        df = fetch_ohlcv(ticker, period="1mo")
        if df is None or df.empty:
            print(f"⚠️ Cannot fetch data for {ticker}. Skipping.")
            continue
            
        # Ensure the index is just the date string for easy comparison
        df.index = df.index.tz_localize(None).normalize()
        
        # Convert forecast_date to pandas datetime
        import pandas as pd
        target_date = pd.to_datetime(forecast_date).normalize()
        
        if target_date in df.index:
            actual_price = float(df.loc[target_date, "Close"])
            error_pct = abs(actual_price - predicted_price) / actual_price * 100
            
            success = update_accuracy_evaluation(record_id, actual_price, error_pct)
            if success:
                print(f"📈 Evaluated {ticker} for {forecast_date}: Pred=${predicted_price:.2f}, Act=${actual_price:.2f} -> Err: {error_pct:.2f}%")
                evaluated_tickers.add(ticker)
            else:
                print(f"❌ Failed to update DB for record {record_id}")
        else:
            print(f"⏳ Market data for {ticker} on {forecast_date} not yet available.")
            
    return list(evaluated_tickers)

def online_learning(tickers: list):
    """
    Briefly fine-tune the existing TFT model using the most recent data of the evaluated tickers.
    This fulfills the 'tự động học hỏi' requirement.
    """
    if not tickers:
        return
        
    print(f"\n🧠 Starting Online Learning for: {', '.join(tickers)}")
    
    import tensorflow as tf
    from backend.models.feature_engineering import add_technical_indicators, get_feature_columns
    from backend.models.tft_model import quantile_loss
    import pickle
    import numpy as np
    
    MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
    model_path = os.path.join(MODELS_DIR, "global_tft.keras")
    meta_path = os.path.join(MODELS_DIR, "tft_meta.pkl")
    
    if not os.path.exists(model_path) or not os.path.exists(meta_path):
        print("❌ Pre-trained model or metadata not found. Run training first.")
        return
        
    # Load model
    try:
        model = tf.keras.models.load_model(
            model_path,
            custom_objects={"loss_fn": quantile_loss([0.1, 0.5, 0.9])}
        )
    except Exception as e:
        print(f"❌ Failed to load model for learning: {e}")
        return
        
    # Load Meta
    with open(meta_path, "rb") as f:
        meta = pickle.load(f)
    look_back = meta["look_back"]
    
    all_X = []
    all_Y = []
    
    # Collect fresh data for fine-tuning
    for ticker in tickers:
        df = fetch_ohlcv(ticker, period="3mo") # Get recent data
        if df is None or df.empty:
            continue
            
        df = add_technical_indicators(df)
        feature_cols = get_feature_columns()
        available_cols = [c for c in feature_cols if c in df.columns]
        
        target_col = "Close"
        all_cols = [target_col] + available_cols
        df_clean = df[all_cols].dropna()
        
        if len(df_clean) < look_back + 5: # Just need a few samples
            continue
            
        scaler_path = os.path.join(MODELS_DIR, f"scaler_tft_{ticker}.pkl")
        if not os.path.exists(scaler_path):
            continue
            
        with open(scaler_path, "rb") as f:
            scaler = pickle.load(f)
            
        scaled_data = scaler.transform(df_clean[all_cols].values)
        
        # Create sequences (only the most recent ones for fast learning)
        X, Y = [], []
        # Take the last 14 days of possible sequences
        start_idx = max(0, len(scaled_data) - look_back - 14)
        for i in range(start_idx, len(scaled_data) - look_back):
            X.append(scaled_data[i:i + look_back])
            Y.append(scaled_data[i + look_back, 0])
            
        all_X.extend(X)
        all_Y.extend(Y)
        
    if not all_X:
        print("⚠️ Not enough new data generated for learning.")
        return
        
    X = np.array(all_X)
    Y = np.array(all_Y)
    Y_quantile = np.column_stack([Y, Y, Y])
    
    print(f"📊 Fine-tuning on {len(X)} new recent samples...")
    
    # Fine-tune for a very small number of epochs so it doesn't overfit/forget
    # We use a smaller learning rate for fine-tuning
    import tensorflow.keras.backend as K
    K.set_value(model.optimizer.learning_rate, 1e-4)
    
    model.fit(
        X, Y_quantile,
        epochs=3,
        batch_size=min(32, len(X)),
        verbose=1
    )
    
    # Save the updated model
    model.save(model_path)
    print("✅ Online Learning completed and model updated successfully.")

if __name__ == "__main__":
    tickers_evaluated = run_evaluations()
    online_learning(tickers_evaluated)
