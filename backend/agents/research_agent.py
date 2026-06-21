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

def fetch_news(ticker: str, max_items: int = 12) -> List[Dict]:
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


# ── GEMINI ────────────────────────────────────────────────────────────────────

_gemini_model = None
_gemini_last_call: float = 0.0
_GEMINI_MIN_INTERVAL = 5.0  # 15 RPM free tier → 4s min, use 5s for safety margin
_GEMINI_MAX_RETRIES = 2


def _get_gemini():
    global _gemini_model
    if _gemini_model is not None:
        return _gemini_model

    from backend.config import settings
    if not settings.gemini_api_key:
        return None

    try:
        from google import genai
        client = genai.Client(api_key=settings.gemini_api_key)
        # Store a tuple (client, model_name) so we can call generate_content
        _gemini_model = (client, "gemini-2.0-flash")
        return _gemini_model
    except ImportError:
        # Fallback to deprecated library if google-genai not installed
        try:
            import google.generativeai as genai_old
            genai_old.configure(api_key=settings.gemini_api_key)
            _gemini_model = genai_old.GenerativeModel("gemini-2.0-flash")
            return _gemini_model
        except Exception as e:
            print(f"Gemini init error: {e}")
            return None
    except Exception as e:
        print(f"Gemini init error: {e}")
        return None


def _call_gemini(prompt: str) -> Optional[str]:
    """Call Gemini with rate limiting and retry on 429/transient errors."""
    global _gemini_last_call

    model = _get_gemini()
    if model is None:
        return None

    for attempt in range(_GEMINI_MAX_RETRIES + 1):
        # Rate limiting
        elapsed = time.time() - _gemini_last_call
        if elapsed < _GEMINI_MIN_INTERVAL:
            time.sleep(_GEMINI_MIN_INTERVAL - elapsed)

        try:
            # Support both new (client, model_name) tuple and old GenerativeModel
            if isinstance(model, tuple):
                client, model_name = model
                response = client.models.generate_content(
                    model=model_name, contents=prompt
                )
                text = response.text
            else:
                response = model.generate_content(prompt)
                text = response.text

            _gemini_last_call = time.time()
            return text.strip() if text else None
        except Exception as e:
            _gemini_last_call = time.time()
            err_str = str(e).lower()
            is_retryable = any(kw in err_str for kw in ["429", "resource", "quota", "rate", "503", "unavailable"])

            if is_retryable and attempt < _GEMINI_MAX_RETRIES:
                wait = _GEMINI_MIN_INTERVAL * (attempt + 2)  # 10s, 15s backoff
                print(f"Gemini rate-limited, retrying in {wait:.0f}s (attempt {attempt + 1}/{_GEMINI_MAX_RETRIES})")
                time.sleep(wait)
                continue

            print(f"Gemini call error: {e}")
            return None



def _parse_gemini_json(text: str) -> Optional[Dict]:
    """Extract JSON from Gemini response text."""
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


def _gemini_analysis(ticker: str, headlines: List[Dict], price_info: str) -> Optional[Dict]:
    """Full Gemini-powered market analysis."""
    headlines_text = "\n".join([
        f"- [{h['source']}] {h['title']}: {h.get('summary','')[:150]}"
        for h in headlines[:8]
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

    text = _call_gemini(prompt)
    if text is None:
        return None
    return _parse_gemini_json(text)


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
        analysis = _gemini_analysis(ticker, headlines, price_info)
        if analysis is not None:
            result = analysis
            source = "gemini"
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
            for h in headlines[:6]
        ],
    })

    # Persist to DB
    try:
        from backend.database import save_research
        save_research(ticker, result, source)
    except Exception:
        pass

    return result
