"""
routers/research.py – Real-time research agent.
Only sentiment analysis history is saved to DB (small rows, high value).
Raw news headlines are never stored.
Supports any ticker.
"""

from fastapi import APIRouter, HTTPException, Query
import time

from backend.agents.research_agent import analyze_market, fetch_news
from backend.database import get_recent_research
from backend.models.forecaster import get_live_quote

router = APIRouter()

# In-memory cache: 30min TTL per ticker
_cache: dict = {}
_CACHE_TTL = 1800


def _is_fresh(ticker: str) -> bool:
    entry = _cache.get(ticker)
    if not entry:
        return False
    return (time.time() - entry["ts"]) < _CACHE_TTL


@router.get("/reports")
def get_all_reports():
    """
    Return all recent reports for the frontend Research page.
    """
    from backend.database import get_recent_research
    # Lấy danh sách ticker có sẵn
    tickers = ["BTC-USD", "ETH-USD", "NVDA", "FPT.VN", "VCB.VN"]
    reports = []
    for t in tickers:
        records = get_recent_research(t, limit=1)
        if records:
            r = records[0]
            headlines = []
            if "headlines" in r and r["headlines"]:
                import json
                try:
                    val = r["headlines"]
                    headlines = json.loads(val) if isinstance(val, str) else val
                except:
                    pass
            reports.append({
                "id": str(r.get("id", t)),
                "ticker": t,
                "sentiment": r.get("sentiment", "neutral").lower(),
                "confidence": int(r.get("confidence", 0.5) * 100),
                "title": r.get("title", f"Báo cáo AI: {t}"),
                "summary": r.get("summary", ""),
                "tags": r.get("key_factors", []),
                "author": "Groq Agent",
                "createdAt": r.get("created_at", ""),
                "readTime": 3,
                "headlines": headlines
            })
    return reports


@router.get("/{ticker}")
def get_research(ticker: str):
    """
    Fake AI Mode:
    - Lấy báo cáo mới nhất từ Database (đã được tổng hợp bởi Groq chạy ngầm)
    - Lấy giá live hiện tại để xào nấu thêm vào
    """
    ticker = ticker.upper()

    live = get_live_quote(ticker)
    price_info = f"Giá hiện hành: {live['price']:,.2f}" if live else ""

    # Lấy dữ liệu tóm tắt từ Database
    records = get_recent_research(ticker, limit=1)
    
    if not records:
        # Nếu chưa có trong DB thì đành gọi phân tích cơ bản (bằng từ khóa) 
        # Vì hiện chưa có AI Key
        analysis = analyze_market(ticker, price_info)
        return analysis

    record = records[0]
    
    # Fake AI "xào nấu" lại câu chữ
    summary = f"Theo dữ liệu tổng hợp gần đây nhất từ {record.get('news_count', 0)} bài báo, kết hợp với mức {price_info}. " + \
              f"AI nhận định {record.get('summary', '')}"
              
    # Lấy link tham khảo từ DB (chúng ta vừa thêm cột headlines)
    headlines = []
    if "headlines" in record and record["headlines"]:
        import json
        try:
            val = record["headlines"]
            headlines = json.loads(val) if isinstance(val, str) else val
        except:
            pass

    return {
        "ticker": ticker,
        "sentiment": record.get("sentiment", "NEUTRAL"),
        "confidence": record.get("confidence", 0.5),
        "sentiment_score": record.get("sentiment_score", 0.0),
        "summary": summary,
        "key_factors": record.get("key_factors", []),
        "recommendation": record.get("recommendation", ""),
        "risk_level": record.get("risk_level", "MEDIUM"),
        "source": "mock_ai",
        "news_count": record.get("news_count", 0),
        "analyzed_at": record.get("created_at", ""),
        "headlines": headlines
    }


@router.get("/news/{ticker}")
def get_news_only(ticker: str):
    """
    Fetch raw news headlines in real-time. Nothing saved to DB.
    """
    ticker = ticker.upper()
    headlines = fetch_news(ticker, max_items=15)
    return {
        "ticker": ticker,
        "headlines": headlines,
        "count": len(headlines),
        "fetched_at": __import__("datetime").datetime.now().isoformat(),
    }


@router.get("/history/{ticker}")
def get_sentiment_history(
    ticker: str,
    limit: int = Query(default=20, ge=1, le=100),
):
    """
    Historical sentiment trend from DB.
    Only sentiment scores stored — no raw news or article text.
    """
    ticker = ticker.upper()
    records = get_recent_research(ticker, limit=limit)
    return {
        "ticker": ticker,
        "records": records,
        "count": len(records),
        "note": "Lịch sử sentiment AI — tin tức không được lưu trữ"
    }
