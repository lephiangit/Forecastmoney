"""
cron_researcher.py - Automated research script
Fetches news for active tickers, runs Gemini sentiment analysis, and saves to research_reports.
"""
from datetime import datetime
from backend.database import _get_client

def run_research():
    print(f"[{datetime.now()}] Running background research job...")
    c = _get_client()
    if not c:
        print("Database not available")
        return

    # Get unique tickers from user watchlists + default MARKET_ASSETS if empty
    res = c.table("user_watchlists").select("ticker").execute()
    tickers = set([r["ticker"] for r in (res.data or [])])
    
    # Also include auto-trade bot config assets
    try:
        bot_res = c.table("bot_configs").select("config").execute()
        for r in (bot_res.data or []):
            cfg = r.get("config", {})
            if isinstance(cfg, dict) and "assets" in cfg:
                tickers.update(cfg["assets"])
    except Exception:
        pass
    
    if not tickers:
        tickers = {"BTC-USD", "ETH-USD", "NVDA", "TSLA"} # Fallback defaults
        
    # Import the Groq-powered research agent
    from backend.agents.research_agent import analyze_market
    
    for ticker in tickers:
        try:
            print(f"Researching {ticker} with Groq...")
            # analyze_market automatically fetches news, analyzes with Groq, and saves to DB
            analyze_market(ticker)
        except Exception as e:
            print(f"Failed to research {ticker}: {e}")
            
    print(f"[{datetime.now()}] Research job completed.")
