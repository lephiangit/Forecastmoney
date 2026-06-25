"""
cron_researcher.py - Automated research script
Fetches news for active tickers, runs Gemini sentiment analysis, and saves to research_reports.
"""
from datetime import datetime
from backend.database import _get_client
from backend.models.forecaster import get_sentiment
from backend.services.news import get_recent_news

def run_research():
    print(f"[{datetime.now()}] Running background research job...")
    c = _get_client()
    if not c:
        print("Database not available")
        return

    # Get unique tickers from user watchlists + default MARKET_ASSETS if empty
    res = c.table("user_watchlists").select("ticker").execute()
    tickers = set([r["ticker"] for r in (res.data or [])])
    
    if not tickers:
        tickers = {"BTC-USD", "ETH-USD", "NVDA", "TSLA"} # Fallback defaults
        
    for ticker in tickers:
        try:
            print(f"Researching {ticker}...")
            # Get latest 20 articles
            news_items = get_recent_news(ticker)
            if not news_items:
                continue
                
            # Combine titles for sentiment analysis
            text_context = " ".join([n["title"] for n in news_items[:20]])
            sentiment_res = get_sentiment(text_context)
            
            # Save to database
            c.table("research_reports").insert({
                "ticker": ticker,
                "sentiment": sentiment_res["sentiment"],
                "confidence": sentiment_res["confidence"],
                "sentiment_score": sentiment_res["sentiment_score"],
                "summary": f"Analyzed {len(news_items)} recent articles.",
                "news_count": len(news_items),
                "created_at": datetime.now().isoformat()
            }).execute()
        except Exception as e:
            print(f"Failed to research {ticker}: {e}")
            
    print(f"[{datetime.now()}] Research job completed.")
