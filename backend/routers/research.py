"""
routers/research.py – Báo cáo nghiên cứu thị trường.

Ba thay đổi:

1. **`/reports` không còn hard-code 5 mã.** Bản cũ luôn trả đúng
   BTC-USD, ETH-USD, NVDA, FPT.VN, VCB.VN bất kể job nền đã phân tích bao nhiêu mã
   trong watchlist người dùng — trang Research vì thế luôn trông trống trải so với
   phần còn lại của hệ thống. Nay danh sách được lấy động từ dữ liệu thật.

2. **Gộp ba đoạn code định dạng báo cáo trùng nhau** thành một hàm duy nhất.

3. **Bỏ nhãn "mock_ai" / "Fake AI Mode".** Dữ liệu trả về là kết quả phân tích thật
   đã lưu trong DB; `source` nay phản ánh đúng nguồn (`groq`, `keyword`, `no_data`)
   để người đọc — và hội đồng chấm đồ án — biết chính xác con số đến từ đâu.

LƯU Ý THỨ TỰ ROUTE: các route tĩnh (/reports, /archive, /news/*, /history/*) phải
khai báo TRƯỚC route bắt-tất-cả /{ticker}, nếu không FastAPI sẽ hiểu "reports" là
một mã tài sản.
"""

from __future__ import annotations

import ast
import json
import time
from typing import Dict, List, Optional

from fastapi import APIRouter, Query

from backend.agents.research_agent import analyze_market, fetch_news
from backend.database import get_recent_research
from backend.models.forecaster import get_live_quote
from backend.security import validate_ticker_format

router = APIRouter()

# Số mã hiển thị tối đa trên trang Research.
MAX_REPORT_TICKERS = 24
# Số bản ghi quét để tìm ra các mã gần đây (một mã có thể có nhiều báo cáo).
REPORT_SCAN_LIMIT = 200

# Danh sách dùng khi cơ sở dữ liệu chưa có báo cáo nào (lần chạy đầu tiên).
SEED_TICKERS = ["BTC-USD", "ETH-USD", "NVDA", "FPT.VN", "VCB.VN"]

_cache: Dict[str, dict] = {}
_CACHE_TTL = 1800


# ══════════════════════════════════════════════════════════════════════════════
#  HELPER
# ══════════════════════════════════════════════════════════════════════════════

def _parse_json_field(value) -> list:
    """
    Đọc các cột JSONB có thể đang lưu ở nhiều dạng khác nhau.

    Dữ liệu lịch sử trong bảng này không đồng nhất: có bản ghi lưu JSON chuẩn,
    có bản ghi lưu chuỗi repr của Python list, có bản ghi lưu chuỗi phân tách bằng dấu phẩy.
    """
    if isinstance(value, list):
        return value
    if not isinstance(value, str) or not value.strip():
        return []

    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(value)
            if isinstance(parsed, list):
                return parsed
        except (ValueError, SyntaxError, TypeError):
            continue

    return [part.strip() for part in value.split(",") if part.strip()]


def _confidence_pct(raw) -> int:
    """Chuẩn hoá confidence về phần trăm nguyên, chấp nhận cả thang 0-1 lẫn 0-100."""
    try:
        value = float(raw if raw is not None else 0.5)
    except (TypeError, ValueError):
        return 50
    if value <= 1.0:
        value *= 100
    return int(max(0, min(100, value)))


def _format_report(record: dict, ticker: Optional[str] = None) -> dict:
    """Chuyển một dòng research_reports thành cấu trúc mà frontend dùng."""
    resolved_ticker = ticker or record.get("ticker", "UNKNOWN")
    return {
        "id": str(record.get("id", resolved_ticker)),
        "ticker": resolved_ticker,
        "sentiment": str(record.get("sentiment", "neutral")).lower(),
        "confidence": _confidence_pct(record.get("confidence")),
        "title": f"Phân tích thị trường: {resolved_ticker}",
        "summary": record.get("summary", ""),
        "tags": _parse_json_field(record.get("key_factors")),
        "author": "AI Research Agent",
        "source": record.get("source", "unknown"),
        "newsCount": record.get("news_count", 0),
        "createdAt": record.get("created_at", ""),
        "readTime": 3,
        "headlines": _parse_json_field(record.get("headlines")),
    }


def _recent_tickers(limit: int = MAX_REPORT_TICKERS) -> List[str]:
    """
    Lấy các mã đã được phân tích gần đây nhất.

    PostgREST không hỗ trợ SELECT DISTINCT trực tiếp, nên ta quét một lô bản ghi
    mới nhất rồi khử trùng lặp ở tầng ứng dụng — vẫn rẻ vì bảng chỉ lưu tóm tắt.
    """
    from backend.database import _get_client

    c = _get_client()
    if c is None:
        return SEED_TICKERS

    try:
        res = (
            c.table("research_reports")
            .select("ticker, created_at")
            .order("created_at", desc=True)
            .limit(REPORT_SCAN_LIMIT)
            .execute()
        )
    except Exception as e:
        print(f"[research] Lỗi lấy danh sách mã: {e}")
        return SEED_TICKERS

    seen: List[str] = []
    for row in res.data or []:
        ticker = row.get("ticker")
        if ticker and ticker not in seen:
            seen.append(ticker)
        if len(seen) >= limit:
            break

    return seen or SEED_TICKERS


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTE TĨNH (phải đứng trước /{ticker})
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/reports")
def get_all_reports(limit: int = Query(default=MAX_REPORT_TICKERS, ge=1, le=50)):
    """Báo cáo mới nhất của từng mã đã được phân tích."""
    reports = []
    for ticker in _recent_tickers(limit):
        records = get_recent_research(ticker, limit=1)
        if records:
            reports.append(_format_report(records[0], ticker))
    return reports


@router.get("/archive")
def get_research_archive(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    ticker: Optional[str] = Query(default=None, max_length=20),
    sentiment: Optional[str] = Query(default=None, pattern="^(?i)(BULLISH|BEARISH|NEUTRAL)$"),
):
    """Kho lưu trữ báo cáo, có phân trang và bộ lọc."""
    from backend.database import get_all_research_history

    clean_ticker = validate_ticker_format(ticker) if ticker else None
    records = get_all_research_history(limit, offset, clean_ticker, sentiment)

    return {
        "items": [_format_report(r) for r in records],
        "limit": limit,
        "offset": offset,
        "count": len(records),
        "hasMore": len(records) == limit,
    }


@router.get("/news/{ticker}")
def get_news_only(ticker: str):
    """Tiêu đề tin tức thời gian thực. Không lưu gì xuống DB."""
    clean_ticker = validate_ticker_format(ticker)
    headlines = fetch_news(clean_ticker, max_items=15)
    return {
        "ticker": clean_ticker,
        "headlines": headlines,
        "count": len(headlines),
        "fetched_at": __import__("datetime").datetime.now().isoformat(),
    }


@router.get("/history/{ticker}")
def get_sentiment_history(ticker: str, limit: int = Query(default=20, ge=1, le=100)):
    """Diễn biến tâm lý thị trường theo thời gian của một mã."""
    clean_ticker = validate_ticker_format(ticker)
    records = get_recent_research(clean_ticker, limit=limit)

    return {
        "ticker": clean_ticker,
        "records": [
            {
                "id": r.get("id"),
                "sentiment": r.get("sentiment"),
                "confidence": _confidence_pct(r.get("confidence")),
                "sentiment_score": r.get("sentiment_score"),
                "source": r.get("source"),
                "news_count": r.get("news_count"),
                "created_at": r.get("created_at"),
            }
            for r in records
        ],
        "count": len(records),
        "note": "Chỉ điểm số tâm lý được lưu trữ — nội dung bài báo gốc không lưu.",
    }


@router.post("/{report_id}/translate")
def translate_report(report_id: str):
    """
    Dựng bản tiếng Việt của một báo cáo.

    Lưu ý: đây không phải dịch máy thật. Nội dung phân tích vốn đã được LLM sinh ra
    bằng tiếng Việt; hàm này chỉ định dạng lại các trường đã lưu thành một khối
    Markdown liền mạch. Tên "translate" giữ nguyên vì frontend đang gọi theo tên đó.
    """
    from datetime import datetime

    clean_id = validate_ticker_format(report_id)
    records = get_recent_research(clean_id, limit=1)

    if not records:
        return {
            "content_vi": (
                f"## {clean_id}\n\n"
                "Chưa có dữ liệu phân tích cho mã này trong cơ sở dữ liệu. "
                "Báo cáo sẽ xuất hiện sau khi tác vụ nghiên cứu nền chạy lần kế tiếp."
            ),
            "translated_at": datetime.now().isoformat(),
        }

    record = records[0]
    return {
        "content_vi": _build_markdown(clean_id, record, language="vi"),
        "translated_at": datetime.now().isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  NỘI DUNG MARKDOWN
# ══════════════════════════════════════════════════════════════════════════════

_LABELS = {
    "vi": {
        "title": "Phân tích thị trường",
        "sentiment": "Tâm lý thị trường",
        "sentiment_text": "Tâm lý hiện tại là **{sentiment}** với độ tin cậy {confidence}%.",
        "recommendation": "Nhận định",
        "risk": "Mức độ rủi ro",
        "factors": "Các yếu tố chính",
        "disclaimer": (
            "> Nội dung do hệ thống AI tổng hợp từ tin tức công khai, phục vụ mục đích "
            "học thuật và tham khảo. Đây **không phải** lời khuyên đầu tư."
        ),
    },
    "en": {
        "title": "Market Analysis",
        "sentiment": "Market Sentiment",
        "sentiment_text": "Current sentiment is **{sentiment}** with {confidence}% confidence.",
        "recommendation": "Assessment",
        "risk": "Risk Level",
        "factors": "Key Factors",
        "disclaimer": (
            "> Generated by an AI system from public news sources, for academic and "
            "reference purposes only. This is **not** investment advice."
        ),
    },
}


def _build_markdown(ticker: str, record: dict, language: str = "vi") -> str:
    labels = _LABELS.get(language, _LABELS["vi"])
    confidence = _confidence_pct(record.get("confidence"))

    parts = [
        f"## {labels['title']}: {ticker}\n",
        f"{record.get('summary', '')}\n",
        f"### {labels['sentiment']}",
        labels["sentiment_text"].format(
            sentiment=record.get("sentiment", "NEUTRAL"), confidence=confidence
        )
        + "\n",
        f"### {labels['recommendation']}",
        f"{record.get('recommendation', '—')}\n",
        f"### {labels['risk']}",
        f"**{record.get('risk_level', 'MEDIUM')}**\n",
    ]

    factors = _parse_json_field(record.get("key_factors"))
    if factors:
        parts.append(f"### {labels['factors']}")
        parts.extend(f"- {f}" for f in factors)
        parts.append("")

    parts.append(labels["disclaimer"])
    return "\n".join(parts)


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTE BẮT-TẤT-CẢ (phải đứng cuối cùng)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/{ticker}")
def get_research(ticker: str):
    """
    Báo cáo chi tiết cho một mã.

    Ưu tiên dùng báo cáo đã lưu (do job nền tạo). Nếu chưa có, chạy phân tích ngay —
    lượt gọi này chậm hơn vì phải tải RSS và gọi LLM.
    """
    clean_ticker = validate_ticker_format(ticker)

    live = get_live_quote(clean_ticker)
    price_info = f"Giá hiện tại: {live['price']:,.2f}" if live else ""

    records = get_recent_research(clean_ticker, limit=1)
    if not records:
        analysis = analyze_market(clean_ticker, price_info)
        analysis["content_vi"] = _build_markdown(clean_ticker, analysis, "vi")
        analysis["content_en"] = _build_markdown(clean_ticker, analysis, "en")
        analysis["live"] = live
        return analysis

    record = records[0]
    return {
        "id": str(record.get("id", clean_ticker)),
        "ticker": clean_ticker,
        "sentiment": record.get("sentiment", "NEUTRAL"),
        "confidence": _confidence_pct(record.get("confidence")),
        "sentiment_score": record.get("sentiment_score", 0.0),
        "summary": record.get("summary", ""),
        "key_factors": _parse_json_field(record.get("key_factors")),
        "recommendation": record.get("recommendation", ""),
        "risk_level": record.get("risk_level", "MEDIUM"),
        "source": record.get("source", "unknown"),
        "news_count": record.get("news_count", 0),
        "createdAt": record.get("created_at", ""),
        "readTime": 3,
        "author": "AI Research Agent",
        "headlines": _parse_json_field(record.get("headlines")),
        "content_vi": _build_markdown(clean_ticker, record, "vi"),
        "content_en": _build_markdown(clean_ticker, record, "en"),
        "live": live,
    }
