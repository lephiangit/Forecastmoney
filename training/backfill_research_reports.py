"""
training/backfill_research_reports.py – Tạo dữ liệu THẬT cho research_reports
để build_llm_dataset.py không phải rơi 100% vào nhánh tổng hợp (synthetic).

BỐI CẢNH
--------
`training/build_llm_dataset.py --source both` chạy được, nhưng nếu bảng
`research_reports` trống (dự án ít người dùng thật, chưa tích luỹ được gì),
toàn bộ dataset fine-tune sẽ là câu mẫu tự sinh theo template — model học
xong chỉ biết lặp lại đúng những câu đó, không thể trình bày như năng lực
phân tích tin tức thật khi bảo vệ đồ án.

Script này gọi THẲNG `analyze_market()` (chính hàm cron_researcher.py và
router /research đang dùng) cho một loạt mã — mỗi lượt gọi lấy tin tức thật
đã cào được (RSS) + giá thật (yfinance) rồi phân tích bằng Groq, và tự động
lưu vào research_reports (persist=True, tham số mặc định của analyze_market).
Chạy xong, các bản ghi này trở thành dữ liệu THẬT cho build_llm_dataset.py
ở lần chạy tiếp theo.

CÁCH DÙNG
---------
    python -m training.backfill_research_reports
    python -m training.backfill_research_reports --limit 30
    python -m training.backfill_research_reports --tickers BTC-USD,AAPL,FPT.VN

Mặc định lấy toàn bộ mã có sẵn trong data/*.csv (bỏ 3 file rác — xem
backend/train_tft.py::SKIP_FILES).

TỐN THỜI GIAN & HẠN MỨC GROQ: mỗi mã tốn một lượt gọi Groq. Script tự nghỉ
`SLEEP_SECONDS` giữa các mã để tránh dội hạn mức free-tier. Với ~100 mã,
tổng thời gian khoảng 8-10 phút. Nếu bị lỗi hạn mức (429) giữa chừng, script
DỪNG NGAY và ghi lại các mã đã xong vào file checkpoint — chạy lại lệnh y hệt
sẽ tự bỏ qua các mã đã xong, không phân tích lại từ đầu.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CHECKPOINT_FILE = PROJECT_ROOT / "training" / ".backfill_research_done.txt"

SKIP_FILES = {"merged_data", "bitcoin_data", "bitcoin_data_global"}
SLEEP_SECONDS = 4.0  # khoảng nghỉ giữa các lượt gọi Groq, giống cadence của cron_researcher.py


def _default_tickers() -> List[str]:
    if not DATA_DIR.exists():
        return []
    return sorted(
        f.stem for f in DATA_DIR.glob("*.csv") if f.stem not in SKIP_FILES
    )


def _load_done() -> set:
    if not CHECKPOINT_FILE.exists():
        return set()
    return set(CHECKPOINT_FILE.read_text(encoding="utf-8").splitlines())


def _mark_done(ticker: str) -> None:
    with open(CHECKPOINT_FILE, "a", encoding="utf-8") as f:
        f.write(ticker + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tickers", type=str, default=None, help="Danh sách mã, phân tách bằng dấu phẩy")
    parser.add_argument("--limit", type=int, default=None, help="Chỉ chạy N mã đầu tiên")
    args = parser.parse_args()

    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        tickers = _default_tickers()

    if args.limit:
        tickers = tickers[: args.limit]

    if not tickers:
        print("Không có mã nào để chạy — kiểm tra lại data/*.csv hoặc dùng --tickers.")
        sys.exit(1)

    done = _load_done()
    remaining = [t for t in tickers if t not in done]

    if done:
        print(f"Đã hoàn tất {len(done)} mã ở lần chạy trước (checkpoint: {CHECKPOINT_FILE.name}), bỏ qua.")

    if not remaining:
        print("Toàn bộ mã đã được phân tích rồi. Xoá file checkpoint nếu muốn chạy lại từ đầu.")
        return

    print(f"Sẽ phân tích {len(remaining)} mã còn lại (trong tổng {len(tickers)} mã)...\n")

    from backend.agents.research_agent import analyze_market
    from backend.models.forecaster import get_live_quote

    succeeded = failed = 0
    for i, ticker in enumerate(remaining, start=1):
        try:
            live = get_live_quote(ticker)
            price_info = f"Giá: {live['price']:,.4f}" if live else ""

            result = analyze_market(ticker, price_info)  # persist=True mặc định
            print(
                f"  [{i}/{len(remaining)}] {ticker}: {result.get('sentiment')} "
                f"(tin cậy {result.get('confidence')}, nguồn {result.get('source')}, "
                f"{result.get('news_count')} tin)"
            )
            _mark_done(ticker)
            succeeded += 1

        except Exception as e:
            msg = str(e)
            print(f"  [{i}/{len(remaining)}] {ticker}: lỗi — {type(e).__name__}: {msg}")
            failed += 1
            if "429" in msg or "rate" in msg.lower():
                print("\nCó vẻ đã chạm hạn mức Groq — dừng lại tại đây.")
                print(f"Chạy lại y nguyên lệnh này sau vài phút, script sẽ tự bỏ qua {succeeded} mã đã xong.")
                break

        time.sleep(SLEEP_SECONDS)

    print(f"\nHoàn tất: {succeeded} thành công, {failed} lỗi.")
    print("Bước tiếp theo: chạy lại `python -m training.build_llm_dataset --source both --count 3000`")
    print("để dataset lần này chứa dữ liệu THẬT thay vì 100% tổng hợp.")


if __name__ == "__main__":
    main()
