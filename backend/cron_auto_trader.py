"""
cron_auto_trader.py – Intelligent Auto-Trading Bot with Strategy Tiers & Risk Management.

Strategies:
  - Conservative: confidence >= 80%, expected return >= 3%, smaller positions
  - Balanced:     confidence >= 70%, expected return >= 1.5%
  - Aggressive:   confidence >= 60%, expected return >= 0.5%, larger positions

Risk Management:
  - Stop-Loss:   Auto-sell when price drops below stop_loss% of avg cost
  - Take-Profit: Auto-sell when price rises above take_profit% of avg cost
"""

from datetime import datetime
from backend.database import (
    _get_client, get_admin_config, update_admin_config,
    save_trade, get_watchlist, get_bot_config, get_trades
)
from backend.models.forecaster import get_live_quote, run_combined_forecast

# ── Strategy Tiers ────────────────────────────────────────────────────────────

STRATEGY_PARAMS = {
    "conservative": {
        "min_confidence": 80,
        "min_expected_return": 3.0,   # percent
        "position_scale": 0.7,       # trade 70% of configured amount
    },
    "balanced": {
        "min_confidence": 70,
        "min_expected_return": 1.5,
        "position_scale": 1.0,
    },
    "aggressive": {
        "min_confidence": 60,
        "min_expected_return": 0.5,
        "position_scale": 1.3,       # trade 130% of configured amount
    },
}


def _get_strategy_params(bot_cfg: dict) -> dict:
    """Get strategy parameters, merging user overrides."""
    strategy = bot_cfg.get("strategy", "balanced")
    params = STRATEGY_PARAMS.get(strategy, STRATEGY_PARAMS["balanced"]).copy()
    # User can override min_confidence from UI
    if bot_cfg.get("min_confidence"):
        params["min_confidence"] = float(bot_cfg["min_confidence"])
    return params


def _calculate_position(ticker: str, user_id: int, trades: list) -> dict:
    """Calculate current position for a ticker from trade history."""
    qty = 0.0
    total_cost = 0.0
    for t in trades:
        if t.get("ticker") == ticker:
            if t.get("action") == "BUY":
                qty += t.get("quantity", 0)
                total_cost += t.get("total_value", 0)
            elif t.get("action") == "SELL":
                sell_qty = t.get("quantity", 0)
                if qty > 0:
                    # Reduce cost proportionally
                    cost_per_unit = total_cost / qty if qty > 0 else 0
                    total_cost -= cost_per_unit * sell_qty
                qty -= sell_qty
    qty = max(0, qty)
    avg_cost = total_cost / qty if qty > 0 else 0
    return {"qty": qty, "avg_cost": avg_cost, "total_cost": total_cost}


def _check_stop_loss_take_profit(
    user_id: int, ticker: str, current_price: float,
    position: dict, stop_loss_pct: float, take_profit_pct: float,
    balance: float, config: dict
) -> tuple:
    """Check and execute stop-loss or take-profit if triggered.
    Returns (new_balance, trade_executed, trade_type)."""
    qty = position["qty"]
    avg_cost = position["avg_cost"]
    if qty <= 0 or avg_cost <= 0:
        return balance, False, None

    price_change_pct = ((current_price - avg_cost) / avg_cost) * 100

    # Stop-Loss: price dropped below threshold
    if stop_loss_pct > 0 and price_change_pct <= -stop_loss_pct:
        sell_value = current_price * qty
        balance += sell_value
        save_trade(user_id, ticker, "SELL", qty, current_price, sell_value, "AUTO_SL")
        # This is a loss trade
        update_admin_config(user_id, {
            "current_balance": balance,
            "loss_trades": config.get("loss_trades", 0) + 1,
            "total_pnl": balance - config["initial_balance"],
        })
        print(f"     🛑 STOP-LOSS User {user_id}: SELL {qty:.4f} {ticker} @ {current_price:.2f} (loss: {price_change_pct:.1f}%)")
        return balance, True, "STOP_LOSS"

    # Take-Profit: price rose above threshold
    if take_profit_pct > 0 and price_change_pct >= take_profit_pct:
        sell_value = current_price * qty
        balance += sell_value
        save_trade(user_id, ticker, "SELL", qty, current_price, sell_value, "AUTO_TP")
        # This is a win trade
        update_admin_config(user_id, {
            "current_balance": balance,
            "win_trades": config.get("win_trades", 0) + 1,
            "total_pnl": balance - config["initial_balance"],
        })
        print(f"     🎯 TAKE-PROFIT User {user_id}: SELL {qty:.4f} {ticker} @ {current_price:.2f} (gain: {price_change_pct:.1f}%)")
        return balance, True, "TAKE_PROFIT"

    return balance, False, None


def run_auto_trade():
    """Execute auto trading for all users who have is_running = True."""
    print("🤖 [Cron] Auto-Trader started...")
    c = _get_client()
    if not c:
        print("❌ [Cron] Auto-Trader: Database not available.")
        return

    # Get all users with is_running = True
    configs_res = c.table("admin_config").select("*").eq("is_running", True).execute()
    running_users = configs_res.data or []

    if not running_users:
        print("ℹ️ [Cron] Auto-Trader: No users are currently running auto-trade.")
        return

    print(f"📊 [Cron] Auto-Trader: Found {len(running_users)} active users.")

    # Cache forecasts to avoid calling the model repeatedly for the same ticker
    forecast_cache = {}
    live_price_cache = {}

    for config in running_users:
        user_id = config["user_id"]
        balance = config["current_balance"]

        bot_cfg = get_bot_config(user_id) or {}
        end_time = bot_cfg.get("end_time")

        # Check if duration expired
        if end_time and datetime.now().isoformat() > end_time:
            print(f"  🛑 Bot for User {user_id} expired. Stopping.")
            update_admin_config(user_id, {"is_running": False})
            continue

        # Strategy params
        strategy_params = _get_strategy_params(bot_cfg)
        trade_amount = float(bot_cfg.get("amount", 500)) * strategy_params["position_scale"]
        stop_loss_pct = float(bot_cfg.get("stop_loss", 5))
        take_profit_pct = float(bot_cfg.get("take_profit", 15))
        min_confidence = strategy_params["min_confidence"]
        min_return = strategy_params["min_expected_return"]

        strategy_name = bot_cfg.get("strategy", "balanced")
        print(f"  👤 User {user_id} | Strategy: {strategy_name} | SL: {stop_loss_pct}% | TP: {take_profit_pct}%")

        # We need to find what this user wants to trade.
        watchlist = bot_cfg.get("assets") or get_watchlist(user_id)
        if not watchlist:
            continue

        # Pre-fetch all trades for risk management checks
        all_trades = get_trades(user_id, limit=500)

        for ticker in watchlist:
            ticker = ticker.upper()

            # Fetch Live Price
            if ticker not in live_price_cache:
                live = get_live_quote(ticker)
                if not live:
                    continue
                live_price_cache[ticker] = live["price"]

            current_price = live_price_cache[ticker]

            # ── Risk Management: Check Stop-Loss / Take-Profit first ──
            position = _calculate_position(ticker, user_id, all_trades)
            if position["qty"] > 0:
                balance, sl_tp_executed, trade_type = _check_stop_loss_take_profit(
                    user_id, ticker, current_price, position,
                    stop_loss_pct, take_profit_pct, balance, config
                )
                if sl_tp_executed:
                    continue  # Skip normal trading for this ticker

            # ── Forecast-based Trading ──
            if ticker not in forecast_cache:
                try:
                    from backend.database import get_recent_research
                    sentiment_score = None
                    research_records = get_recent_research(ticker, limit=1)
                    if research_records:
                        latest = research_records[0]
                        s_map = {"bullish": 0.8, "bearish": 0.2, "neutral": 0.5}
                        sentiment_score = s_map.get(latest.get("sentiment", "neutral").lower(), 0.5)

                    fc = run_combined_forecast(
                        ticker,
                        days=1,
                        research_analysis={"sentiment_score": sentiment_score} if sentiment_score else None
                    )

                    predicted_price = None
                    confidence = 50  # default

                    if fc and fc.get("sentiment_fusion") and fc["sentiment_fusion"].get("median"):
                        predicted_price = fc["sentiment_fusion"]["median"][0]["price"]
                    elif fc and fc.get("tft") and fc["tft"].get("median"):
                        predicted_price = fc["tft"]["median"][0]["price"]

                    # Get confidence from research if available
                    if fc and fc.get("research") and fc["research"].get("confidence"):
                        confidence = fc["research"]["confidence"]

                    if predicted_price:
                        forecast_cache[ticker] = {"price": predicted_price, "confidence": confidence}
                    else:
                        continue
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    print(f"     Forecast error for {ticker}: {e}")
                    continue

            forecast_data = forecast_cache[ticker]
            predicted_price = forecast_data["price"]
            confidence = forecast_data["confidence"]

            # Calculate expected return
            expected_return = ((predicted_price - current_price) / current_price) * 100 if current_price > 0 else 0

            # ── Strategy Gate: Check confidence and expected return thresholds ──
            if confidence < min_confidence:
                print(f"     ⏩ {ticker}: Confidence {confidence:.0f}% < {min_confidence:.0f}% threshold. Skipping.")
                continue

            if abs(expected_return) < min_return:
                print(f"     ⏩ {ticker}: Expected return {expected_return:.2f}% < {min_return:.1f}% threshold. Skipping.")
                continue

            qty = round(trade_amount / current_price, 4) if current_price > 0 else 0
            if qty <= 0:
                continue

            total_value = current_price * qty
            trade_executed = False

            if expected_return > 0:
                # BUY Signal
                if balance >= total_value:
                    balance -= total_value
                    save_trade(user_id, ticker, "BUY", qty, current_price, total_value, "AUTO")
                    trade_executed = True
                    print(f"     ✅ BUY {qty} {ticker} @ {current_price} (conf: {confidence:.0f}%, exp: +{expected_return:.1f}%)")

            elif expected_return < 0:
                # SELL Signal — only sell if we have a position
                position = _calculate_position(ticker, user_id, all_trades)
                if position["qty"] > 0:
                    sell_qty = min(qty, position["qty"])
                    sell_value = current_price * sell_qty
                    balance += sell_value
                    save_trade(user_id, ticker, "SELL", sell_qty, current_price, sell_value, "AUTO")
                    trade_executed = True

                    # Determine win/loss based on avg cost
                    if current_price >= position["avg_cost"]:
                        update_admin_config(user_id, {"win_trades": config.get("win_trades", 0) + 1})
                    else:
                        update_admin_config(user_id, {"loss_trades": config.get("loss_trades", 0) + 1})

                    print(f"     ✅ SELL {sell_qty:.4f} {ticker} @ {current_price:.2f} (conf: {confidence:.0f}%, exp: {expected_return:.1f}%)")
                else:
                    print(f"     ⏩ SELL Skipped: No position for {ticker}")

            if trade_executed:
                total_pnl = balance - config["initial_balance"]
                update_admin_config(user_id, {
                    "current_balance": balance,
                    "total_pnl": total_pnl
                })

    print("✅ [Cron] Auto-Trader finished.")

if __name__ == "__main__":
    run_auto_trade()
