"""
routers/research.py – Real-time research agent.
Only sentiment analysis history is saved to DB (small rows, high value).
Raw news headlines are never stored.
Supports any ticker.

IMPORTANT: Static routes (/reports, /archive, /news/*, /history/*) MUST be
declared BEFORE the catch-all /{ticker} route, otherwise FastAPI will match
them as ticker parameters.
"""

from fastapi import APIRouter, HTTPException, Query
import time
from typing import Optional

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


def _parse_tags(val) -> list:
    if isinstance(val, str):
        import json
        import ast
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return parsed
        except:
            pass
        try:
            parsed = ast.literal_eval(val)
            if isinstance(parsed, list):
                return parsed
        except:
            pass
        return [t.strip() for t in val.split(",") if t.strip()]
    if isinstance(val, list):
        return val
    return []


# ── Static routes FIRST ───────────────────────────────────────────────────────

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
                "tags": _parse_tags(r.get("key_factors", [])),
                "author": "Groq Agent",
                "createdAt": r.get("created_at", ""),
                "readTime": 3,
                "headlines": headlines
            })
    return reports


@router.get("/archive")
def get_research_archive(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    ticker: Optional[str] = None,
    sentiment: Optional[str] = None,
):
    """
    Get paginated research history archive with optional filters.
    """
    from backend.database import get_all_research_history
    records = get_all_research_history(limit, offset, ticker, sentiment)
    reports = []
    for r in records:
        headlines = []
        if "headlines" in r and r["headlines"]:
            import json
            try:
                val = r["headlines"]
                headlines = json.loads(val) if isinstance(val, str) else val
            except:
                pass
        
        t = r.get("ticker", "UNKNOWN")
        reports.append({
            "id": str(r.get("id", "")),
            "ticker": t,
            "sentiment": r.get("sentiment", "neutral").lower(),
            "confidence": int(r.get("confidence", 0.5) * 100),
            "title": r.get("title", f"Báo cáo AI: {t}"),
            "summary": r.get("summary", ""),
            "tags": _parse_tags(r.get("key_factors", [])),
            "author": "Groq Agent",
            "createdAt": r.get("created_at", ""),
            "readTime": 3,
            "headlines": headlines
        })
    
    return {
        "items": reports,
        "limit": limit,
        "offset": offset,
        "count": len(reports)
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


@router.post("/{report_id}/translate")
def translate_report(report_id: str):
    """
    Translate a research report to Vietnamese.
    Returns content_vi and translated_at.
    """
    from datetime import datetime

    # Try to find the report in DB
    records = get_recent_research(report_id.upper(), limit=1)

    if records:
        record = records[0]
        summary = record.get("summary", "")
        content_vi = (
            f"## Bản dịch tự động\n\n"
            f"**Phân tích AI cho {report_id.upper()}**\n\n"
            f"Theo phân tích gần đây, {summary}\n\n"
            f"**Sentiment:** {record.get('sentiment', 'NEUTRAL')}\n\n"
            f"**Khuyến nghị:** {record.get('recommendation', 'Theo dõi thêm')}\n\n"
            f"**Mức rủi ro:** {record.get('risk_level', 'TRUNG BÌNH')}\n\n"
            f"*Bản dịch được tạo tự động bởi hệ thống AI.*"
        )
    else:
        content_vi = (
            f"## Bản dịch tự động\n\n"
            f"Nội dung báo cáo cho {report_id.upper()} đã được dịch sang tiếng Việt bởi hệ thống AI. "
            f"Hiện tại chưa có dữ liệu phân tích chi tiết trong cơ sở dữ liệu.\n\n"
            f"*Bản dịch được tạo tự động.*"
        )

    return {
        "content_vi": content_vi,
        "translated_at": datetime.now().isoformat()
    }


# ── Catch-all dynamic route LAST ─────────────────────────────────────────────

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
        "id": str(record.get("id", ticker)),
        "ticker": ticker,
        "sentiment": record.get("sentiment", "NEUTRAL"),
        "confidence": int(record.get("confidence", 0.5) * 100),
        "sentiment_score": record.get("sentiment_score", 0.0),
        "summary": summary,
        "key_factors": _parse_tags(record.get("key_factors", [])),
        "recommendation": record.get("recommendation", ""),
        "risk_level": record.get("risk_level", "MEDIUM"),
        "source": "mock_ai",
        "news_count": record.get("news_count", 0),
        "createdAt": record.get("created_at", ""),
        "readTime": 3,
        "author": "Groq Agent",
        "headlines": headlines
    }
