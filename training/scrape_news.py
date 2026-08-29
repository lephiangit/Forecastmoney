"""
training/scrape_news.py – Cào tin tức tài chính từ nhiều nguồn RSS (quốc tế + trong
nước), lưu thành JSON + CSV thẳng vào Google Drive (Drive Desktop đồng bộ theo kiểu
"Thư mục" — một thư mục thật trên ổ C:, không phải ổ ảo "Tên ổ" kiểu G:\\ nữa).

LƯU Ý: danh sách nguồn ở đây RỘNG HƠN backend/config.py (crypto_feeds/vn_feeds) —
backend chỉ dùng 2+2 nguồn cho tính năng Research/Chatbot real-time (ít nguồn để trả
lời nhanh), còn script này dùng để gom kho dữ liệu lưu trữ nên cứ lấy nhiều nguồn nhất
có thể. Đổi nguồn ở đây KHÔNG ảnh hưởng gì tới backend đang chạy, và ngược lại.

Vài feed dưới đây tui chưa tự kiểm tra được URL còn sống hay không (môi trường của
Claude bị chặn mạng ra ngoài) — feed nào lỗi/đổi URL thì script chỉ in cảnh báo rồi bỏ
qua, không dừng cả script. Chạy xong nhìn dòng nào báo lỗi thì gửi tui, tui thay bằng
nguồn khác tương đương.

CHẠY Ở ĐÂU: script này chạy trên MÁY BẠN (venv backend), KHÔNG chạy được từ môi
trường của Claude — mạng của Claude bị chặn domain ngoài (403 khi thử gọi thẳng các
RSS này), còn máy bạn thì gọi bình thường vì đó cũng là cách backend đang chạy sống
lấy tin cho tính năng Research/Chatbot.

DỮ LIỆU CHI TIẾT HƠN (để sau này dùng train/fine-tune LLM): ngoài tiêu đề + tóm tắt
ngắn từ RSS, script còn TẢI TOÀN VĂN bài viết (mở link, trích nội dung chính, bỏ
quảng cáo/menu — bằng thư viện `trafilatura`), lấy thêm tác giả, thẻ phân loại
(category) nếu nguồn có cung cấp, và tự gắn nhãn MÃ TÀI SẢN liên quan (vd: bài nhắc
"Bitcoin" hoặc "BTC" → gắn nhãn "BTC-USD") dựa theo từ khoá. Có `trafilatura` thì mới
tải được toàn văn — thiếu thì script vẫn chạy bình thường, chỉ là "content" sẽ dùng
tạm đoạn tóm tắt ngắn từ RSS thay vì bài đầy đủ.

CÁCH DÙNG
---------
    cd ForecastAI
    venv\\Scripts\\activate          (Windows)  hoặc  source venv/bin/activate (khác)
    pip install feedparser trafilatura   (trafilatura để tải toàn văn bài viết —
                                           không bắt buộc, thiếu thì bỏ qua bước đó)
    python training/scrape_news.py

Mặc định lưu vào:
    C:\\Users\\ann28\\Drive của tôi\\ForecastAI\\data\\news_scraped\\

(Trước đây dùng ổ ảo "G:\\..." kiểu "Tên ổ" — chập chờn, thư mục lúc có lúc không với
các lệnh ghi file (mkdir báo thành công nhưng open() vẫn báo "No such file or
directory"). Sau khi đổi Drive Desktop sang kiểu "Thư mục" trong Cài đặt, đường dẫn
đổi sang một thư mục thật trên C:, ổn định như thư mục bình thường.)

Muốn đổi thư mục lưu, truyền đường dẫn qua biến môi trường NEWS_OUTPUT_DIR:
    set NEWS_OUTPUT_DIR=D:\\noi_khac & python training/scrape_news.py     (Windows cmd)
    $env:NEWS_OUTPUT_DIR="D:\\noi_khac"; python training/scrape_news.py   (PowerShell)

Mỗi lần chạy tạo ra 1 file JSON + 1 file CSV mới, có timestamp trong tên — không ghi
đè file cũ, nên chạy nhiều lần (mỗi ngày một lần chẳng hạn) sẽ tích luỹ dần thành kho
dữ liệu tin tức theo thời gian, dùng được sau này cho phần fine-tune LLM
(xem training/build_llm_dataset.py) hoặc phân tích thủ công trên Google Sheets.
"""

import csv
import io
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

try:
    import feedparser
except ImportError:
    print("Thiếu thư viện feedparser. Cài bằng lệnh: pip install feedparser")
    sys.exit(1)

try:
    import trafilatura
    _HAS_TRAFILATURA = True
except ImportError:
    _HAS_TRAFILATURA = False
    print(
        "[thông báo] Chưa cài trafilatura — sẽ KHÔNG tải được toàn văn bài viết, "
        "'content' sẽ dùng tạm đoạn tóm tắt ngắn từ RSS. Cài bằng: pip install trafilatura"
    )

# ── Nguồn quốc tế: crypto + tài chính/thị trường nói chung ───────────────────────
CRYPTO_FEEDS = [
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cryptoslate.com/feed/",
    "https://decrypt.co/feed",
    "https://bitcoinmagazine.com/feed",
    "https://cryptopotato.com/feed/",
]
INTL_FINANCE_FEEDS = [
    "https://finance.yahoo.com/news/rssindex",
    "https://www.investing.com/rss/news.rss",
    "https://feeds.marketwatch.com/marketwatch/topstories/",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
]

# ── Nguồn trong nước ──────────────────────────────────────────────────────────
VN_FEEDS = [
    "https://vnexpress.net/rss/kinh-doanh.rss",
    "https://vnexpress.net/rss/chung-khoan.rss",
    "https://cafef.vn/rss/thi-truong-chung-khoan.rss",  # từng lỗi XML, để lại xem CafeF có sửa không
    "https://cafebiz.vn/rss/kinh-doanh.rss",
    "https://vneconomy.vn/tai-chinh.rss",
    "https://vietstock.vn/830/chung-khoan.rss",
]

# Từ khoá -> mã ticker, để tự gắn nhãn "bài này đang nói về tài sản nào" — hữu ích khi
# sau này lọc dữ liệu train theo từng coin/mã cổ phiếu cụ thể. Rút gọn từ
# backend/config.py::TICKER_LABELS (đảo ngược tên hiển thị -> mã) + vài từ khoá phổ
# biến mà tên hiển thị không có (vd "BTC" ngoài "Bitcoin").
TICKER_KEYWORDS = {
    "BTC-USD": ["bitcoin", "btc"],
    "ETH-USD": ["ethereum", "eth", "ether"],
    "BNB-USD": ["bnb", "binance coin"],
    "SOL-USD": ["solana", "sol"],
    "ADA-USD": ["cardano", "ada"],
    "XRP-USD": ["xrp", "ripple"],
    "DOGE-USD": ["dogecoin", "doge"],
    "AVAX-USD": ["avalanche", "avax"],
    "DOT-USD": ["polkadot", "dot"],
    "LINK-USD": ["chainlink", "link"],
    "FPT.VN": ["fpt corp", "cổ phiếu fpt", "tập đoàn fpt"],
    "VCB.VN": ["vietcombank", "vcb"],
    "HPG.VN": ["hoà phát", "hoa phat", "hpg"],
    "VIC.VN": ["vingroup", "vic"],
    "MWG.VN": ["thế giới di động", "mobile world", "mwg"],
    "VNM.VN": ["vinamilk", "vnm"],
    "TCB.VN": ["techcombank", "tcb"],
    "VHM.VN": ["vinhomes", "vhm"],
    "MSN.VN": ["masan", "msn"],
}


def tag_tickers(title: str, summary: str) -> list:
    """Quét tiêu đề + tóm tắt, trả về danh sách mã ticker được nhắc tới (không phân
    biệt hoa thường). Chỉ dựa trên khớp từ khoá đơn giản — không phải NLP, nên có thể
    bỏ sót hoặc bắt nhầm vài trường hợp hiếm, đủ dùng để lọc thô ban đầu."""
    text = f"{title} {summary}".lower()
    return [ticker for ticker, keywords in TICKER_KEYWORDS.items() if any(kw in text for kw in keywords)]


MAX_SUMMARY_CHARS = 500
MAX_CONTENT_CHARS = 8000
FULL_TEXT_TIMEOUT = 10
FULL_TEXT_WORKERS = 8

DEFAULT_OUTPUT_DIR = r"C:\Users\ann28\Drive của tôi\ForecastAI\data\news_scraped"

# Một số RSS (CafeF là ví dụ điển hình) chặn request không có User-Agent giống trình
# duyệt thật, trả về trang lỗi HTML thay vì XML — feedparser đọc thành "syntax error".
_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def _clean(text: str, max_chars: int) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


# Một số CMS Việt Nam (CafeF, CafeBiz, cả VnExpress đôi lúc) xuất RSS với ký tự XML
# không hợp lệ trong tiêu đề/nội dung: dấu "&" đứng một mình (không phải &amp; hay
# &lt;...) hoặc ký tự điều khiển ASCII (mã 0x00-0x08, 0x0B-0x0C, 0x0E-0x1F) lọt vào
# — cả hai đều làm trình phân tích XML dừng giữa chừng với lỗi "not well-formed" /
# "syntax error". Đây không phải lỗi do thiếu User-Agent (đã thử ở bản trước, không
# ăn thua) — sửa bằng cách tự tải XML thô rồi "vá" 2 lỗi này trước khi đưa cho
# feedparser, thay vì để nó tự tải qua URL.
_INVALID_XML_CTRL_CHARS = re.compile(
    "[\x00-\x08\x0b\x0c\x0e-\x1f]"
)
_BARE_AMPERSAND = re.compile(r"&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9a-fA-F]+;)")


def _sanitize_xml(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace")
    text = _INVALID_XML_CTRL_CHARS.sub("", text)
    text = _BARE_AMPERSAND.sub("&amp;", text)
    return text


def _fetch_raw(url: str) -> "bytes | None":
    import urllib.request

    req = urllib.request.Request(url, headers=_REQUEST_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read()
    except Exception as e:
        print(f"    [cảnh báo] tải thô để vá XML thất bại: {type(e).__name__}: {e}")
        return None


def fetch_group(feeds: list, group: str) -> list:
    items = []
    for url in feeds:
        try:
            feed = feedparser.parse(url, request_headers=_REQUEST_HEADERS)
            if feed.bozo and not feed.entries:
                # Thử lại: tải XML thô, vá lỗi ký tự không hợp lệ, parse lại từ chuỗi
                # đã vá — trước khi bỏ cuộc hẳn với nguồn này.
                raw = _fetch_raw(url)
                if raw is not None:
                    feed = feedparser.parse(_sanitize_xml(raw))
                if feed.bozo and not feed.entries:
                    print(f"  [cảnh báo] không đọc được feed {url} (đã thử vá XML): {feed.get('bozo_exception')}")
                    continue
                print(f"  {url} -> đọc được sau khi vá XML")
            source_name = _clean(feed.feed.get("title", url), 80)
            for entry in feed.entries:
                title = _clean(entry.get("title", ""), 300)
                if not title:
                    continue
                summary = _clean(entry.get("summary", ""), MAX_SUMMARY_CHARS)
                categories = [
                    _clean(tag.get("term", ""), 60)
                    for tag in entry.get("tags", [])
                    if tag.get("term")
                ]
                items.append({
                    "id": entry.get("id") or entry.get("link", ""),
                    "group": group,
                    "source": source_name,
                    "title": title,
                    "author": _clean(entry.get("author", ""), 100),
                    "categories": categories,
                    "tickers": tag_tickers(title, summary),
                    "rss_summary": summary,
                    # "content" tạm = rss_summary — được thay bằng toàn văn thật ở
                    # bước fetch_full_content() sau đó, nếu tải được (xem main()).
                    "content": summary,
                    "content_source": "rss_summary",
                    "link": entry.get("link", "")[:500],
                    "published": entry.get("published", "")[:100],
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                })
            print(f"  {url} -> {len(feed.entries)} tin")
        except Exception as e:
            print(f"  [cảnh báo] lỗi khi đọc {url}: {type(e).__name__}: {e}")
    return items


def _fetch_one_full_text(link: str) -> str | None:
    try:
        downloaded = trafilatura.fetch_url(link)
        if not downloaded:
            return None
        text = trafilatura.extract(downloaded, favor_precision=True)
        if not text:
            return None
        return re.sub(r"\s+", " ", text).strip()[:MAX_CONTENT_CHARS]
    except Exception:
        return None


def fetch_full_content(items: list) -> None:
    """Tải toàn văn cho từng bài, SỬA THẲNG vào items (in-place). Chạy song song
    (ThreadPoolExecutor) vì đây là I/O chờ mạng là chính — chạy tuần tự với ~380 bài,
    mỗi bài 1-3s sẽ mất cả chục phút, chạy song song 8 luồng rút xuống còn khoảng
    1-2 phút. Bài nào tải lỗi/timeout thì GIỮ NGUYÊN rss_summary làm content, không
    làm hỏng cả mẻ dữ liệu."""
    if not _HAS_TRAFILATURA:
        return

    print(f"\nĐang tải toàn văn cho {len(items)} bài ({FULL_TEXT_WORKERS} luồng song song)...")
    done = 0
    ok = 0
    with ThreadPoolExecutor(max_workers=FULL_TEXT_WORKERS) as pool:
        future_to_item = {pool.submit(_fetch_one_full_text, it["link"]): it for it in items if it["link"]}
        for future in as_completed(future_to_item):
            it = future_to_item[future]
            done += 1
            try:
                text = future.result(timeout=FULL_TEXT_TIMEOUT)
            except Exception:
                text = None
            if text and len(text) > len(it["rss_summary"]):
                it["content"] = text
                it["content_source"] = "full_text"
                ok += 1
            if done % 50 == 0 or done == len(future_to_item):
                print(f"  ...{done}/{len(future_to_item)} (tải toàn văn thành công: {ok})")
    print(f"Tải toàn văn thành công {ok}/{len(items)} bài — số còn lại giữ nguyên tóm tắt RSS.")


def dedupe(items: list) -> list:
    seen = set()
    unique = []
    for it in items:
        key = it["title"].lower()[:80]
        if key not in seen:
            seen.add(key)
            unique.append(it)
    return unique


def main():
    output_dir = Path(os.environ.get("NEWS_OUTPUT_DIR", DEFAULT_OUTPUT_DIR))

    print(f"Đang cào tin crypto quốc tế ({len(CRYPTO_FEEDS)} nguồn)...")
    all_items = fetch_group(CRYPTO_FEEDS, "crypto")
    print(f"Đang cào tin tài chính quốc tế ({len(INTL_FINANCE_FEEDS)} nguồn)...")
    all_items += fetch_group(INTL_FINANCE_FEEDS, "intl_finance")
    print(f"Đang cào tin tài chính trong nước ({len(VN_FEEDS)} nguồn)...")
    all_items += fetch_group(VN_FEEDS, "vn_stock")

    raw_total = len(all_items)
    all_items = dedupe(all_items)
    print(f"\nTổng số tin cào được: {raw_total} → sau khi lọc trùng: {len(all_items)}")

    if not all_items:
        print("Không cào được tin nào — kiểm tra lại kết nối mạng hoặc feed RSS có đổi URL không.")
        sys.exit(1)

    fetch_full_content(all_items)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Dựng sẵn NỘI DUNG trong bộ nhớ trước — tránh việc "mở file test rồi mở lại để
    # ghi thật" ở bản trước: giữa 2 lần mở, ổ ảo Drive có thể coi thư mục vừa biến
    # mất lần nữa (nó chập chờn giữa hiện/ẩn, không phải chỉ chậm một lần rồi ổn định).
    json_content = json.dumps(
        {
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "total": len(all_items),
            "sources": {
                "crypto": CRYPTO_FEEDS,
                "intl_finance": INTL_FINANCE_FEEDS,
                "vn_stock": VN_FEEDS,
            },
            "items": all_items,
        },
        ensure_ascii=False,
        indent=2,
    )

    csv_buf = io.StringIO()
    csv_fields = [
        "id", "group", "source", "title", "author", "categories", "tickers",
        "rss_summary", "content", "content_source", "link", "published", "scraped_at",
    ]
    writer = csv.DictWriter(csv_buf, fieldnames=csv_fields)
    writer.writeheader()
    for it in all_items:
        row = dict(it)
        # CSV không có kiểu list — nối bằng "|" cho dễ đọc/lọc trong Excel-Sheets.
        row["categories"] = " | ".join(it["categories"])
        row["tickers"] = " | ".join(it["tickers"])
        writer.writerow(row)
    csv_content = csv_buf.getvalue()

    def try_write(directory: Path) -> tuple[Path, Path] | None:
        """Thử mkdir + ghi CẢ HAI file trong một lần — trả về (json_path, csv_path)
        nếu thành công, None nếu thất bại. Không chia nhỏ thao tác ra nhiều bước để
        tránh khoảng hở giữa các lệnh, nơi ổ ảo Drive có thể đổi trạng thái."""
        try:
            directory.mkdir(parents=True, exist_ok=True)
            jp = directory / f"forecastai_news_{ts}.json"
            cp = directory / f"forecastai_news_{ts}.csv"
            with open(jp, "w", encoding="utf-8") as f:
                f.write(json_content)
            with open(cp, "w", encoding="utf-8", newline="") as f:
                f.write(csv_content)
            return jp, cp
        except OSError as e:
            print(f"[cảnh báo] ghi vào '{directory}' thất bại: {e}")
            return None

    used_fallback = False
    result = None
    for attempt, delay in enumerate([0, 1, 2, 4, 8], start=1):
        if delay:
            time.sleep(delay)
        result = try_write(output_dir)
        if result:
            break
        print(f"  (đã thử {attempt} lần)")

    if result is None:
        fallback = Path.home() / "Documents" / "ForecastAI_news_scraped"
        print(f"\nKhông ghi được vào '{output_dir}' sau {attempt} lần thử.")
        print(f"Chuyển sang lưu tạm ở '{fallback}' — bạn tự copy 2 file này vào Drive giúp tui.")
        result = try_write(fallback)
        used_fallback = True
        if result is None:
            print(f"Lưu dự phòng cũng thất bại — kiểm tra lại quyền ghi ở '{fallback}'.")
            sys.exit(1)

    json_path, csv_path = result

    if used_fallback:
        print(f"\nĐã lưu TẠM (chưa nằm trong Drive):")
        print(f"  {json_path}")
        print(f"  {csv_path}")
        print(f"\nBạn tự copy 2 file này vào '{DEFAULT_OUTPUT_DIR}' để chúng lên Drive nhé.")
    else:
        print(f"\nĐã lưu vào Google Drive:")
        print(f"  {json_path}")
        print(f"  {csv_path}")
        print("\nGoogle Drive Desktop sẽ tự đồng bộ 2 file này lên Drive trong ít phút "
              "(xem icon đám mây ở góc dưới bên phải màn hình).")


if __name__ == "__main__":
    main()
