from datetime import datetime
from backend.database import _get_client, get_admin_config, update_admin_config, save_trade, get_watchlist, get_bot_config
from backend.models.forecaster import get_live_quote, run_combined_forecast

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

        trade_amount = float(bot_cfg.get("amount", 500))
        
        # We need to find what this user wants to trade.
        watchlist = bot_cfg.get("assets") or get_watchlist(user_id)
        if not watchlist:
            continue
            
        print(f"  👤 Processing User {user_id} with assets: {watchlist}")
        
        for ticker in watchlist:
            ticker = ticker.upper()
            
            # Fetch Live Price
            if ticker not in live_price_cache:
                live = get_live_quote(ticker)
                if not live:
                    continue
                live_price_cache[ticker] = live["price"]
                
            current_price = live_price_cache[ticker]
            
            # Fetch Forecast
            if ticker not in forecast_cache:
                try:
                    # Try to fetch the latest research report from DB to get sentiment_score
                    from backend.database import get_recent_research
                    sentiment_score = None
                    research_records = get_recent_research(ticker, limit=1)
                    if research_records:
                        latest = research_records[0]
                        # map 'bullish'/'bearish'/'neutral' to numerical score
                        s_map = {"bullish": 0.8, "bearish": 0.2, "neutral": 0.5}
                        sentiment_score = s_map.get(latest.get("sentiment", "neutral").lower(), 0.5)

                    # We just need 1 day forecast to decide, injecting the stored sentiment score
                    fc = run_combined_forecast(
                        ticker, 
                        days=1, 
                        research_analysis={"sentiment_score": sentiment_score} if sentiment_score else None
                    )
                    
                    # SentimentFusion predictions are stored in "sentiment_fusion"
                    # If SF failed, fallback to TFT
                    if fc and fc.get("sentiment_fusion") and fc["sentiment_fusion"]["median"]:
                        forecast_cache[ticker] = fc["sentiment_fusion"]["median"][0]["price"]
                    elif fc and fc.get("tft") and fc["tft"]["median"]:
                        forecast_cache[ticker] = fc["tft"]["median"][0]["price"]
                    else:
                        continue
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    print(f"     Forecast error for {ticker}: {e}")
                    continue
                    
            predicted_price = forecast_cache[ticker]
            
            # Decision Logic:
            # We buy if predicted > current * 1.01 (1% gain expected)
            # We sell if predicted < current * 0.99 (1% drop expected)
            
            qty = round(trade_amount / current_price, 4) if current_price > 0 else 0
            if qty <= 0: continue
            
            total_value = current_price * qty
            
            trade_executed = False
            
            if predicted_price > current_price:
                # BUY Signal
                if balance >= total_value:
                    balance -= total_value
                    save_trade(user_id, ticker, "BUY", qty, current_price, total_value, "AUTO")
                    trade_executed = True
                    print(f"     ✅ User {user_id} AUTO BUY {qty} {ticker} @ {current_price}")
                    
            elif predicted_price < current_price:
                # SELL Signal
                # Ideally we check if they own it, but for simple paper trading we just allow selling (shorting or reducing position)
                balance += total_value
                save_trade(user_id, ticker, "SELL", qty, current_price, total_value, "AUTO")
                trade_executed = True
                print(f"     ✅ User {user_id} AUTO SELL {qty} {ticker} @ {current_price}")
                
            if trade_executed:
                # Update user's PnL config
                # Actually, to update PnL properly, we should calculate win/loss.
                # Since this is a simple paper trade where PnL is based on current_balance vs initial,
                # we just update the balance.
                total_pnl = balance - config["initial_balance"]
                update_admin_config(user_id, {
                    "current_balance": balance,
                    "total_pnl": total_pnl
                })
                
    print("✅ [Cron] Auto-Trader finished.")

if __name__ == "__main__":
    run_auto_trade()
