"""
cron_researcher.py – Job nền thu thập và phân tích tin tức thị trường.

Lỗi đã sửa: bản cũ đọc `c.table("bot_configs").select("config")`, nhưng bảng
`bot_configs` không hề có cột tên `config` — nó lưu từng trường riêng biệt
(`assets`, `strategy`, `amount`, ...). Câu truy vấn luôn ném lỗi và bị nuốt bởi
`except: pass`, nên các mã mà người dùng cấu hình cho bot KHÔNG BAO GIỜ được
đưa vào danh sách nghiên cứu. Hệ quả dây chuyền: bot auto-trade không có báo cáo
tin tức cho chính những mã nó đang giao dịch.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Set

from backend.database import _get_client

# Danh sách dùng khi chưa có người dùng nào cấu hình gì.
DEFAULT_TICKERS = ["BTC-USD", "ETH-USD", "NVDA", "TSLA", "FPT.VN"]

# Chặn số mã mỗi lượt chạy: mỗi mã tốn một lượt gọi Groq và ít nhất 3 giây chờ
# rate limit, nên 40 mã đã là khoảng 3 phút chạy liên tục.
MAX_TICKERS_PER_RUN = 40


def _collect_active_tickers() -> List[str]:
    """Gom các mã đang được người dùng quan tâm: watchlist + cấu hình bot."""
    c = _get_client()
    if not c:
        return DEFAULT_TICKERS

    tickers: Set[str] = set()

    try:
        res = c.table("user_watchlists").select("ticker").execute()
        tickers.update(r["ticker"] for r in (res.data or []) if r.get("ticker"))
    except Exception as e:
        print(f"[researcher] Không đọc được watchlist: {e}")

    try:
        # Cột đúng là `assets` (JSONB mảng mã), không phải `config`.
        res = c.table("bot_configs").select("assets").execute()
        for row in res.data or []:
            assets = row.get("assets")
            if isinstance(assets, list):
                tickers.update(a for a in assets if isinstance(a, str) and a.strip())
    except Exception as e:
        print(f"[researcher] Không đọc được cấu hình bot: {e}")

    if not tickers:
        return DEFAULT_TICKERS

    return sorted(t.upper() for t in tickers)[:MAX_TICKERS_PER_RUN]


def run_research() -> None:
    """Chạy một lượt nghiên cứu cho toàn bộ mã đang được quan tâm."""
    started = datetime.now()
    print(f"[{started.isoformat()}] Bắt đầu job nghiên cứu tin tức...")

    tickers = _collect_active_tickers()
    print(f"Sẽ phân tích {len(tickers)} mã: {', '.join(tickers)}")

    from backend.agents.research_agent import analyze_market

    succeeded = failed = 0
    for ticker in tickers:
        try:
            result = analyze_market(ticker)
            print(
                f"  {ticker}: {result.get('sentiment')} "
                f"(tin cậy {result.get('confidence')}, nguồn {result.get('source')}, "
                f"{result.get('news_count')} tin)"
            )
            succeeded += 1
        except Exception as e:
            print(f"  {ticker}: lỗi — {type(e).__name__}: {e}")
            failed += 1

    duration = (datetime.now() - started).total_seconds()
    print(
        f"[{datetime.now().isoformat()}] Hoàn tất: {succeeded} thành công, "
        f"{failed} lỗi, mất {duration:.0f}s."
    )


if __name__ == "__main__":
    run_research()
