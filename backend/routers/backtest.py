"""
routers/backtest.py – Backtesting engine for paper trading strategies.

Simulates trading on historical OHLCV data using technical indicators
(RSI, MACD, Bollinger Bands) to generate BUY/SELL signals. Returns
performance metrics: Win Rate, Total PnL, Max Drawdown, Sharpe Ratio.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
import numpy as np

router = APIRouter()


class BacktestRequest(BaseModel):
    ticker: str
    days_back: int = 90               # 30 | 60 | 90 | 180 | 365
    strategy: str = "balanced"         # conservative | balanced | aggressive
    initial_balance: float = 10000.0
    trade_amount: float = 500.0


class BacktestTrade(BaseModel):
    date: str
    action: str        # BUY | SELL
    price: float
    quantity: float
    total: float
    balance_after: float
    reason: str


class BacktestSummary(BaseModel):
    ticker: str
    strategy: str
    days_back: int
    initial_balance: float
    final_balance: float
    total_pnl: float
    total_pnl_pct: float
    total_trades: int
    win_trades: int
    loss_trades: int
    win_rate: float
    max_drawdown: float
    sharpe_ratio: float


class BacktestResponse(BaseModel):
    summary: BacktestSummary
    trades: List[BacktestTrade]
    equity_curve: List[dict]  # [{date, balance}]


# Strategy thresholds matching cron_auto_trader.py
STRATEGY_PARAMS = {
    "conservative": {"rsi_buy": 30, "rsi_sell": 70, "macd_weight": 0.8, "bb_weight": 0.7, "min_score": 2.5},
    "balanced":     {"rsi_buy": 35, "rsi_sell": 65, "macd_weight": 0.6, "bb_weight": 0.5, "min_score": 2.0},
    "aggressive":   {"rsi_buy": 40, "rsi_sell": 60, "macd_weight": 0.4, "bb_weight": 0.3, "min_score": 1.5},
}


def _generate_signals(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Generate BUY/SELL signals from technical indicators."""
    df = df.copy()
    df["signal"] = 0  # 0 = hold, 1 = buy, -1 = sell
    df["reason"] = ""
    df["score"] = 0.0

    for i in range(1, len(df)):
        score = 0.0
        reasons = []

        rsi = df["RSI"].iloc[i] if pd.notna(df["RSI"].iloc[i]) else 50
        macd = df["MACD"].iloc[i] if pd.notna(df["MACD"].iloc[i]) else 0
        macd_signal = df["MACD_Signal"].iloc[i] if pd.notna(df["MACD_Signal"].iloc[i]) else 0
        close = df["Close"].iloc[i]
        bb_lower = df["BB_Lower"].iloc[i] if pd.notna(df["BB_Lower"].iloc[i]) else close
        bb_upper = df["BB_Upper"].iloc[i] if pd.notna(df["BB_Upper"].iloc[i]) else close
        ma20 = df["MA20"].iloc[i] if "MA20" in df.columns and pd.notna(df["MA20"].iloc[i]) else close
        ma50 = df["MA50"].iloc[i] if "MA50" in df.columns and pd.notna(df["MA50"].iloc[i]) else close

        # RSI signal
        if rsi < params["rsi_buy"]:
            score += 1.0
            reasons.append(f"RSI oversold ({rsi:.0f})")
        elif rsi > params["rsi_sell"]:
            score -= 1.0
            reasons.append(f"RSI overbought ({rsi:.0f})")

        # MACD crossover
        prev_macd = df["MACD"].iloc[i-1] if pd.notna(df["MACD"].iloc[i-1]) else 0
        prev_signal = df["MACD_Signal"].iloc[i-1] if pd.notna(df["MACD_Signal"].iloc[i-1]) else 0
        if prev_macd <= prev_signal and macd > macd_signal:
            score += params["macd_weight"]
            reasons.append("MACD bullish crossover")
        elif prev_macd >= prev_signal and macd < macd_signal:
            score -= params["macd_weight"]
            reasons.append("MACD bearish crossover")

        # Bollinger Band signal
        if close <= bb_lower:
            score += params["bb_weight"]
            reasons.append("Price at BB lower")
        elif close >= bb_upper:
            score -= params["bb_weight"]
            reasons.append("Price at BB upper")

        # MA crossover
        if ma20 > ma50:
            score += 0.3
            reasons.append("MA20 > MA50")
        elif ma20 < ma50:
            score -= 0.3
            reasons.append("MA20 < MA50")

        df.iloc[i, df.columns.get_loc("score")] = score

        if score >= params["min_score"]:
            df.iloc[i, df.columns.get_loc("signal")] = 1
            df.iloc[i, df.columns.get_loc("reason")] = " | ".join(reasons)
        elif score <= -params["min_score"]:
            df.iloc[i, df.columns.get_loc("signal")] = -1
            df.iloc[i, df.columns.get_loc("reason")] = " | ".join(reasons)

    return df


@router.post("/run", response_model=BacktestResponse)
def run_backtest(req: BacktestRequest):
    """Run a backtest simulation on historical data."""
    from backend.models.forecaster import fetch_ohlcv
    from backend.models.feature_engineering import add_technical_indicators

    ticker = req.ticker.upper()

    # Map days_back to yfinance period
    period_map = {30: "1mo", 60: "3mo", 90: "3mo", 180: "6mo", 365: "1y"}
    period = period_map.get(req.days_back, "3mo")

    # Fetch historical data
    df = fetch_ohlcv(ticker, period=period)
    if df is None or df.empty:
        raise HTTPException(404, f"Cannot fetch historical data for '{ticker}'")

    # Add technical indicators
    try:
        df = add_technical_indicators(df)
    except Exception as e:
        raise HTTPException(500, f"Failed to compute indicators: {e}")

    # Trim to requested days
    if len(df) > req.days_back:
        df = df.iloc[-req.days_back:]

    # Get strategy params
    params = STRATEGY_PARAMS.get(req.strategy, STRATEGY_PARAMS["balanced"])

    # Generate signals
    df = _generate_signals(df, params)

    # Simulate trading
    balance = req.initial_balance
    position_qty = 0.0
    position_avg_cost = 0.0
    trades: List[BacktestTrade] = []
    equity_curve = []
    win_trades = 0
    loss_trades = 0
    peak_balance = balance

    for i, (idx, row) in enumerate(df.iterrows()):
        close = float(row["Close"])
        date_str = str(idx.date()) if hasattr(idx, 'date') else str(idx)

        signal = int(row["signal"])
        reason = str(row["reason"]) if row["reason"] else ""

        if signal == 1 and position_qty == 0 and balance >= req.trade_amount:
            # BUY
            qty = round(req.trade_amount / close, 4)
            total = close * qty
            balance -= total
            position_qty = qty
            position_avg_cost = close
            trades.append(BacktestTrade(
                date=date_str, action="BUY", price=round(close, 4),
                quantity=qty, total=round(total, 2), balance_after=round(balance, 2),
                reason=reason
            ))

        elif signal == -1 and position_qty > 0:
            # SELL
            total = close * position_qty
            balance += total
            pnl = close - position_avg_cost
            if pnl >= 0:
                win_trades += 1
            else:
                loss_trades += 1
            trades.append(BacktestTrade(
                date=date_str, action="SELL", price=round(close, 4),
                quantity=position_qty, total=round(total, 2), balance_after=round(balance, 2),
                reason=reason
            ))
            position_qty = 0.0
            position_avg_cost = 0.0

        # Track equity (balance + market value of position)
        total_equity = balance + (position_qty * close)
        equity_curve.append({"date": date_str, "balance": round(total_equity, 2)})
        peak_balance = max(peak_balance, total_equity)

    # Close any remaining position at last price
    if position_qty > 0 and len(df) > 0:
        last_close = float(df["Close"].iloc[-1])
        total = last_close * position_qty
        balance += total
        pnl = last_close - position_avg_cost
        if pnl >= 0:
            win_trades += 1
        else:
            loss_trades += 1
        last_date = str(df.index[-1].date()) if hasattr(df.index[-1], 'date') else str(df.index[-1])
        trades.append(BacktestTrade(
            date=last_date, action="SELL", price=round(last_close, 4),
            quantity=position_qty, total=round(total, 2), balance_after=round(balance, 2),
            reason="End of backtest — forced close"
        ))
        position_qty = 0.0

    # Calculate metrics
    total_trades = win_trades + loss_trades
    win_rate = (win_trades / total_trades * 100) if total_trades > 0 else 0
    total_pnl = balance - req.initial_balance
    total_pnl_pct = (total_pnl / req.initial_balance * 100) if req.initial_balance > 0 else 0

    # Max Drawdown
    if equity_curve:
        equities = [e["balance"] for e in equity_curve]
        peak = equities[0]
        max_dd = 0
        for eq in equities:
            peak = max(peak, eq)
            dd = (peak - eq) / peak * 100 if peak > 0 else 0
            max_dd = max(max_dd, dd)
    else:
        max_dd = 0

    # Sharpe Ratio (annualized, assuming daily)
    if len(equity_curve) > 1:
        equities = np.array([e["balance"] for e in equity_curve])
        daily_returns = np.diff(equities) / equities[:-1]
        if daily_returns.std() > 0:
            sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
        else:
            sharpe = 0.0
    else:
        sharpe = 0.0

    summary = BacktestSummary(
        ticker=ticker,
        strategy=req.strategy,
        days_back=req.days_back,
        initial_balance=req.initial_balance,
        final_balance=round(balance, 2),
        total_pnl=round(total_pnl, 2),
        total_pnl_pct=round(total_pnl_pct, 2),
        total_trades=total_trades,
        win_trades=win_trades,
        loss_trades=loss_trades,
        win_rate=round(win_rate, 1),
        max_drawdown=round(max_dd, 2),
        sharpe_ratio=round(float(sharpe), 2),
    )

    return BacktestResponse(
        summary=summary,
        trades=trades,
        equity_curve=equity_curve,
    )
