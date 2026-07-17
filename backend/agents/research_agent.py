"""
research_agent.py – Research Agent for FastAPI backend.
Fetches news, analyzes sentiment with Gemini Flash, returns structured analysis
suitable for SentimentFusion model input.
"""

import re
import json
import time
from datetime import datetime
from typing import Dict, List, Optional
from functools import lru_cache


# ── NEWS ──────────────────────────────────────────────────────────────────────

def fetch_news(ticker: str, max_items: int = 30) -> List[Dict]:
    """Fetch news headlines for a ticker via RSS."""
    from backend.config import settings

    try:
        feeds = settings.crypto_feeds if not ticker.endswith(".VN") else settings.vn_feeds
    except AttributeError:
        feeds = ["https://cointelegraph.com/rss"] if not ticker.endswith(".VN") else ["https://vnexpress.net/rss/kinh-doanh.rss"]
    headlines = []

    try:
        import feedparser
    except ImportError:
        return []

    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items // len(feeds) + 2]:
                headlines.append({
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", "")[:300],
                    "link": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "source": feed.feed.get("title", url),
                })
        except Exception:
            pass

    return headlines[:max_items]


# ── GROQ API ──────────────────────────────────────────────────────────────────

_groq_last_call: float = 0.0
_GROQ_MIN_INTERVAL = 3.0  # Groq is fast, but keep some rate limiting
_GROQ_MAX_RETRIES = 2

def _call_groq(prompt: str) -> Optional[str]:
    """Call Groq API with rate limiting and retry."""
    global _groq_last_call
    from backend.config import settings
    import requests

    if not settings.groq_api_key:
        print("Missing GROQ_API_KEY")
        return None

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2
    }

    for attempt in range(_GROQ_MAX_RETRIES + 1):
        elapsed = time.time() - _groq_last_call
        if elapsed < _GROQ_MIN_INTERVAL:
            time.sleep(_GROQ_MIN_INTERVAL - elapsed)

        try:
            res = requests.post(url, headers=headers, json=payload, timeout=20)
            _groq_last_call = time.time()
            if res.status_code == 200:
                data = res.json()
                return data["choices"][0]["message"]["content"].strip()
            elif res.status_code == 429:
                wait = _GROQ_MIN_INTERVAL * (attempt + 2)
                print(f"Groq rate-limited, retrying in {wait}s...")
                time.sleep(wait)
                continue
            else:
                print(f"Groq error {res.status_code}: {res.text}")
                return None
        except Exception as e:
            _groq_last_call = time.time()
            print(f"Groq request failed: {e}")
            return None


def _parse_groq_json(text: str) -> Optional[Dict]:
    """Extract JSON from Groq response text."""
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


# ── ANALYSIS ──────────────────────────────────────────────────────────────────

BULLISH_KW = ["tăng", "bull", "surge", "rally", "breakout", "pump", "soar",
              "positive", "growth", "lạc quan", "kỷ lục", "bứt phá", "record"]
BEARISH_KW = ["giảm", "bear", "crash", "drop", "fall", "dump", "decline",
              "plunge", "negative", "loss", "bi quan", "sụt giảm", "lao dốc"]


def _keyword_sentiment(headlines: List[Dict]) -> Dict:
    """Keyword-based sentiment when Gemini unavailable."""
    b, n = 0, 0
    for h in headlines:
        txt = (h["title"] + " " + h.get("summary", "")).lower()
        b += sum(1 for kw in BULLISH_KW if kw in txt)
        n += sum(1 for kw in BEARISH_KW if kw in txt)

    total = b + n
    if total == 0:
        sentiment, confidence = "NEUTRAL", 0.5
    elif b > n:
        sentiment = "BULLISH"
        confidence = min(0.9, 0.5 + (b - n) / (total * 2))
    else:
        sentiment = "BEARISH"
        confidence = min(0.9, 0.5 + (n - b) / (total * 2))

    return {
        "sentiment": sentiment,
        "confidence": round(confidence, 2),
        "summary": f"Phân tích {len(headlines)} tin tức: {b} tín hiệu tích cực, {n} tín hiệu tiêu cực.",
        "key_factors": [h["title"] for h in headlines[:3]],
        "recommendation": (
            "Cân nhắc MUA nếu giá điều chỉnh." if sentiment == "BULLISH"
            else "Thận trọng, ưu tiên bảo toàn vốn." if sentiment == "BEARISH"
            else "Theo dõi thêm, chưa có tín hiệu rõ ràng."
        ),
        "risk_level": "LOW" if sentiment == "BULLISH" else "HIGH" if sentiment == "BEARISH" else "MEDIUM",
    }


def _groq_analysis(ticker: str, headlines: List[Dict], price_info: str) -> Optional[Dict]:
    """Full Groq-powered market analysis."""
    headlines_text = "\n".join([
        f"- [{h['source']}] {h['title']}: {h.get('summary','')[:150]}"
        for h in headlines[:20]
    ])

    prompt = f"""Bạn là chuyên gia phân tích tài chính. Phân tích tin tức sau về {ticker} và đưa ra nhận định thị trường.

**Tin tức gần đây:**
{headlines_text}

**Thông tin giá:** {price_info}

Trả lời bằng tiếng Việt theo format JSON chính xác:
{{
    "sentiment": "BULLISH" | "BEARISH" | "NEUTRAL",
    "confidence": <0.0 đến 1.0>,
    "summary": "<tóm tắt 2-3 câu>",
    "key_factors": ["<yếu tố 1>", "<yếu tố 2>", "<yếu tố 3>"],
    "recommendation": "<khuyến nghị ngắn gọn>",
    "risk_level": "LOW" | "MEDIUM" | "HIGH",
    "price_target_bias": "UP" | "DOWN" | "SIDEWAYS"
}}

Chỉ trả về JSON, không thêm text nào khác."""

    text = _call_groq(prompt)
    if text is None:
        return None
    return _parse_groq_json(text)


# ── PUBLIC API ────────────────────────────────────────────────────────────────

def analyze_market(ticker: str, price_info: str = "") -> Dict:
    """
    Full market analysis pipeline.
    1. Fetch news
    2. Try Gemini analysis
    3. Fallback to keyword analysis
    4. Save to DB
    5. Return structured result
    """
    headlines = fetch_news(ticker)
    source = "no_data"

    if not headlines:
        result = {
            "sentiment": "NEUTRAL",
            "confidence": 0.3,
            "summary": f"Không tìm thấy tin tức gần đây cho {ticker}.",
            "key_factors": [],
            "recommendation": "Dựa vào phân tích kỹ thuật.",
            "risk_level": "MEDIUM",
            "price_target_bias": "SIDEWAYS",
        }
    else:
        analysis = _groq_analysis(ticker, headlines, price_info)
        if analysis is not None:
            result = analysis
            source = "groq"
        else:
            result = _keyword_sentiment(headlines)
            source = "keyword"

    # Compute normalized sentiment_score for SentimentFusion model
    sentiment = result.get("sentiment", "NEUTRAL")
    confidence = float(result.get("confidence", 0.5))
    if sentiment == "BULLISH":
        result["sentiment_score"] = confidence
    elif sentiment == "BEARISH":
        result["sentiment_score"] = -confidence
    else:
        result["sentiment_score"] = 0.0

    result.update({
        "ticker": ticker,
        "source": source,
        "analyzed_at": datetime.now().isoformat(),
        "news_count": len(headlines),
        "headlines": [
            {"title": h["title"], "link": h["link"], "source": h["source"]}
            for h in headlines[:30]
        ],
    })

    # Persist to DB
    try:
        from backend.database import save_research
        save_research(ticker, result, source)
    except Exception:
        pass

    return result
