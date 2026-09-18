"""
build_llm_dataset.py – Dựng dataset instruction-tuning cho Model 2 (LLM Research).

════════════════════════════════════════════════════════════════════════════════
 BỐI CẢNH

 Checklist đồ án đặt ra Model 2 là một LLM được fine-tune bằng LoRA/QLoRA, đọc
 tin tức + kết quả TFT rồi tổng hợp thành insight. Hệ thống hiện tại thay thế
 bước đó bằng cách gọi API Groq với prompt engineering — chạy tốt, nhưng không
 chứng minh được kỹ năng fine-tune mà đề cương yêu cầu.

 Script này dựng cầu nối: nó biến chính dữ liệu hệ thống đã tích luỹ
 (bảng `research_reports` + dữ liệu giá) thành các cặp huấn luyện đúng định dạng
 để fine-tune. Nói cách khác, mọi lượt gọi Groq từ trước tới nay đều đã âm thầm
 tạo ra dữ liệu huấn luyện — chỉ cần trích ra và đóng gói lại.

════════════════════════════════════════════════════════════════════════════════
 CÁCH DÙNG

     # Xuất từ Supabase (dữ liệu thật hệ thống đã thu thập)
     python -m training.build_llm_dataset --source supabase --output data/llm_dataset

     # Xuất từ file CSV giá (sinh mẫu tổng hợp khi DB còn ít dữ liệu)
     python -m training.build_llm_dataset --source synthetic --count 2000

 Kết quả: ba file JSONL (train/validation/test) theo định dạng messages của
 OpenAI/HuggingFace — dùng trực tiếp được với `trl.SFTTrainer`.

════════════════════════════════════════════════════════════════════════════════
 GHI CHÚ VỀ CHẤT LƯỢNG DỮ LIỆU

 Các cặp sinh từ output của Groq là "distillation" — model nhỏ học bắt chước
 model lớn. Đây là kỹ thuật hợp lệ và phổ biến, NHƯNG phải nêu rõ trong báo cáo:
 model của bạn học từ nhãn do một LLM khác sinh ra, không phải nhãn do con người
 gán. Kèm theo đó là trần chất lượng — model học được sẽ khó vượt qua model thầy.

 Checklist yêu cầu "review thủ công một phần" chính là để xử lý điểm này. Script
 có cờ `--review-sample` xuất ra một tệp riêng để bạn đọc và chấm tay; con số
 "đã review N/M mẫu" là thứ nên đưa vào báo cáo.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from datetime import datetime
from typing import Dict, Iterator, List, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.agents.research_agent import build_analysis_prompt  # noqa: E402

SYSTEM_PROMPT = (
    "Bạn là chuyên gia phân tích tài chính. Dựa trên tin tức và số liệu dự báo kỹ thuật "
    "được cung cấp, hãy đưa ra nhận định thị trường ngắn gọn, có cấu trúc và trung thực "
    "về mức độ không chắc chắn. Luôn nêu rõ đây là thông tin tham khảo, không phải "
    "lời khuyên đầu tư."
)


# ══════════════════════════════════════════════════════════════════════════════
#  ĐỊNH DẠNG MẪU HUẤN LUYỆN
# ══════════════════════════════════════════════════════════════════════════════

def build_user_prompt(
    ticker: str,
    headlines: List[str],
    price_context: Optional[Dict] = None,
    forecast_context: Optional[Dict] = None,
) -> str:
    """
    Dựng phần input của một mẫu huấn luyện.

    Cấu trúc này phải KHỚP CHÍNH XÁC với prompt mà hệ thống sẽ dùng lúc chạy thật.
    Sai lệch giữa lúc huấn luyện và lúc suy luận (train/serve skew) là nguyên nhân
    phổ biến nhất khiến một model fine-tune chạy tốt trên tập test nhưng tệ khi
    tích hợp vào sản phẩm.
    """
    parts = [f"Mã tài sản: {ticker}", ""]

    if price_context:
        parts.append("Số liệu giá:")
        parts.append(f"- Giá hiện tại: {price_context.get('current', 'N/A')}")
        if price_context.get("change_pct") is not None:
            parts.append(f"- Biến động phiên gần nhất: {price_context['change_pct']:+.2f}%")
        if price_context.get("rsi") is not None:
            parts.append(f"- RSI(14): {price_context['rsi']:.1f}")
        if price_context.get("volatility") is not None:
            parts.append(f"- Biến động 20 phiên: {price_context['volatility']:.2f}%")
        parts.append("")

    if forecast_context:
        parts.append("Dự báo từ mô hình TFT:")
        parts.append(f"- Giá dự báo (p50): {forecast_context.get('median', 'N/A')}")
        if forecast_context.get("lower") is not None and forecast_context.get("upper") is not None:
            parts.append(
                f"- Khoảng tin cậy 80%: [{forecast_context['lower']}, {forecast_context['upper']}]"
            )
        if forecast_context.get("expected_return") is not None:
            parts.append(f"- Lợi nhuận kỳ vọng: {forecast_context['expected_return']:+.2f}%")
        parts.append("")

    if headlines:
        parts.append("Tin tức gần đây:")
        parts.extend(f"- {h}" for h in headlines[:15])
        parts.append("")

    parts.append(
        "Hãy tổng hợp thành nhận định thị trường gồm: tâm lý (BULLISH/BEARISH/NEUTRAL), "
        "độ tin cậy, tóm tắt, 3 yếu tố chính, khuyến nghị và mức rủi ro."
    )
    return "\n".join(parts)


def build_target_response(record: Dict) -> str:
    """
    Dựng phần output mẫu — JSON ĐÚNG SCHEMA mà hệ thống parse lúc chạy thật.

    LỖI ĐÃ SỬA — TRAIN/SERVE SKEW TOÀN PHẦN.

    Bản cũ dạy model trả lời bằng Markdown:

        **Tâm lý thị trường:** BULLISH
        **Độ tin cậy:** 72%
        ...

    Nhưng lúc suy luận, `research_agent._llm_analysis()` yêu cầu "Trả về DUY NHẤT
    một JSON hợp lệ" rồi gọi `_parse_json()`. Model fine-tune sẽ trả Markdown đúng
    như được dạy → `_parse_json` trả None → `_normalize_analysis` không chạy →
    `analyze_market` rơi xuống nhánh `_keyword_sentiment`.

    Nghĩa là: adapter LoRA tốn hàng giờ GPU để train, cắm vào hệ thống, và sản phẩm
    LUÔN dùng kết quả đếm từ khoá. Trang Admin báo source='keyword' 100%. Không có
    lỗi nào được ném ra — triệu chứng duy nhất là "fine-tune xong mà chẳng khác gì".

    Nay đầu ra là đúng JSON schema của `_llm_analysis`, gồm cả `price_target_bias`
    vốn bị bản Markdown bỏ quên hoàn toàn.
    """
    key_factors = record.get("key_factors") or []
    if isinstance(key_factors, str):
        try:
            key_factors = json.loads(key_factors)
        except json.JSONDecodeError:
            key_factors = [key_factors]
    if not isinstance(key_factors, list):
        key_factors = []

    confidence = float(record.get("confidence") or 0.5)
    if confidence > 1:
        confidence /= 100

    bias = str(record.get("price_target_bias") or "").strip().upper()
    if bias not in {"UP", "DOWN", "SIDEWAYS"}:
        sentiment_now = str(record.get("sentiment", "NEUTRAL")).upper()
        bias = {"BULLISH": "UP", "BEARISH": "DOWN"}.get(sentiment_now, "SIDEWAYS")

    payload = {
        "sentiment": str(record.get("sentiment", "NEUTRAL")).upper(),
        "confidence": round(confidence, 3),
        "summary": str(record.get("summary", ""))[:1000],
        "key_factors": [str(f)[:200] for f in key_factors[:3]],
        "recommendation": str(record.get("recommendation") or "Theo dõi thêm."),
        "risk_level": str(record.get("risk_level", "MEDIUM")).upper(),
        "price_target_bias": bias,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


# Nhà cung cấp LLM THẬT. Bản ghi "keyword"/"no_data" là heuristic, không phải nhãn.
#
# LỖI ĐÃ SỬA: bản cũ lọc `source != "groq"`. Sau khi thêm lớp trừu tượng provider
# (06/09), `analyze_market` ghi `source = _resolve_llm_provider()`, tức "custom" hoặc
# "local" khi chạy bằng vLLM/Ollama/model tự host — chính là mục tiêu của Model 2.
# Bộ lọc cũ vì thế vứt sạch dữ liệu thật và in ra "Đã đọc 0 mẫu từ Supabase" mà không
# báo lỗi gì, rồi pipeline lặng lẽ rơi về dữ liệu tổng hợp.
TRUSTED_LLM_SOURCES = {"groq", "custom", "local"}


def normalize_headlines(raw) -> List[Dict]:
    """
    Đưa cột `headlines` của một bản ghi về đúng dạng mà prompt suy luận cần:
    list các dict có `title`, `summary`, `source`.
    """
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []

    out: List[Dict] = []
    for h in raw:
        if isinstance(h, dict):
            title = str(h.get("title") or "").strip()
            if not title:
                continue
            out.append({
                "title": title,
                # Bản ghi cũ (trước 11/09) không lưu summary — prompt sẽ có phần đuôi
                # rỗng. Không cứu được, chỉ có thể backfill lại.
                "summary": str(h.get("summary") or ""),
                "source": str(h.get("source") or "RSS"),
            })
        elif h:
            out.append({"title": str(h), "summary": "", "source": "RSS"})
    return out


def is_usable_record(record: Dict) -> bool:
    """
    Một bản ghi `research_reports` có dùng làm mẫu huấn luyện được không.

    HÀM DÙNG CHUNG với `training/check_research_data.py`. Trước đây hai file định
    nghĩa "dùng được" khác nhau — `check` chỉ đòi có `summary` + `headlines`, còn
    `build` còn ép `headlines` giải mã được thành list KHÔNG RỖNG sau khi map title.
    Nghĩa là cổng go/no-go có thể báo ĐỦ trong khi dataset dựng ra ít hơn hẳn, và
    không ai biết vì sao.
    """
    if record.get("source") not in TRUSTED_LLM_SOURCES:
        return False
    if not str(record.get("summary") or "").strip():
        return False
    if not normalize_headlines(record.get("headlines")):
        return False
    # key_factors rỗng dạy model xuất một mục trống — loại luôn.
    kf = record.get("key_factors")
    if isinstance(kf, str):
        try:
            kf = json.loads(kf)
        except json.JSONDecodeError:
            kf = None
    if not kf:
        return False
    return True


def dedup_key(ticker: str, headlines: List[Dict]) -> str:
    """
    Khoá khử trùng lặp: mã + tập tiêu đề.

    VÌ SAO CẦN: `cron_researcher` chạy lại cùng danh sách mã mỗi ngày trên cùng hai
    feed RSS không lọc theo mã, nên bản ghi của VCB.VN và MBB.VN trong cùng một ngày
    có tập tiêu đề gần như trùng khít, và cùng một mã ở hai ngày liên tiếp cũng vậy.
    Không khử trùng lặp thì bản sao gần-trùng nằm ở cả train lẫn test.
    """
    import hashlib

    joined = "|".join(sorted(h["title"] for h in headlines))
    return hashlib.sha256(f"{ticker}::{joined}".encode("utf-8")).hexdigest()


def to_chat_sample(user_prompt: str, assistant_response: str) -> Dict:
    """Định dạng messages — chuẩn dùng chung của trl.SFTTrainer và các API chat."""
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": assistant_response},
        ]
    }


# ══════════════════════════════════════════════════════════════════════════════
#  NGUỒN 1: SUPABASE (dữ liệu thật)
# ══════════════════════════════════════════════════════════════════════════════

def load_from_supabase(limit: int = 10000) -> Iterator[Dict]:
    """Đọc toàn bộ research_reports đã tích luỹ và chuyển thành mẫu huấn luyện."""
    from backend.database import _get_client

    client = _get_client()
    if client is None:
        print("Không kết nối được Supabase. Kiểm tra SUPABASE_URL / SUPABASE_KEY trong .env")
        return

    page_size = 1000
    offset = 0
    total = 0

    while offset < limit:
        res = (
            client.table("research_reports")
            .select("*")
            .order("created_at", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            break

        for record in rows:
            if not is_usable_record(record):
                continue

            headlines = normalize_headlines(record.get("headlines"))
            ticker = record.get("ticker", "UNKNOWN")

            # PROMPT DÙNG CHUNG với lúc suy luận — không tự dựng lại.
            #
            # Bản cũ gọi `build_user_prompt(ticker, [title, ...])`, tức một khung
            # HOÀN TOÀN KHÁC prompt mà `research_agent._llm_analysis` gửi đi lúc
            # chạy thật, và còn bỏ luôn price_context. Model học một dạng input rồi
            # gặp một dạng khác khi vào sản phẩm.
            #
            # `price_info` để rỗng vì bảng `research_reports` không lưu giá tại thời
            # điểm phân tích — trùng khớp với trường hợp `get_live_quote` trả None
            # lúc chạy thật (prompt in ra "Thông tin giá: không có"). Muốn có khối
            # giá trong dữ liệu huấn luyện thì phải bổ sung cột giá vào bảng TRƯỚC
            # khi backfill; xem kế hoạch nâng cấp.
            user_prompt = build_analysis_prompt(ticker, headlines, "")
            yield {
                "sample": to_chat_sample(user_prompt, build_target_response(record)),
                "ticker": ticker,
                "created_at": str(record.get("created_at") or ""),
                "dedup_key": dedup_key(ticker, headlines),
                "origin": "supabase",
            }
            total += 1

        offset += page_size

    print(f"Đã đọc {total} mẫu từ Supabase.")


# ══════════════════════════════════════════════════════════════════════════════
#  NGUỒN 2: SINH TỔNG HỢP TỪ DỮ LIỆU GIÁ
# ══════════════════════════════════════════════════════════════════════════════

_HEADLINE_TEMPLATES = {
    "bullish": [
        "{ticker} bứt phá lên mức cao nhất trong {n} phiên",
        "Dòng tiền tổ chức đổ mạnh vào {ticker}",
        "{ticker} vượt kháng cự quan trọng, thanh khoản tăng vọt",
        "Giới phân tích nâng dự báo với {ticker}",
    ],
    "bearish": [
        "{ticker} giảm sâu phiên thứ {n} liên tiếp",
        "Áp lực bán tháo gia tăng trên {ticker}",
        "{ticker} thủng ngưỡng hỗ trợ, nhà đầu tư thận trọng",
        "Lo ngại vĩ mô đè nặng lên {ticker}",
    ],
    "neutral": [
        "{ticker} đi ngang trong biên độ hẹp",
        "Thị trường chờ đợi tín hiệu rõ ràng hơn từ {ticker}",
        "{ticker} giằng co quanh mốc tham chiếu",
    ],
}


def generate_synthetic(count: int, data_dir: str) -> Iterator[Dict]:
    """
    Sinh mẫu huấn luyện từ dữ liệu giá lịch sử.

    ⚠️  QUAN TRỌNG: các mẫu này KHÔNG phải dữ liệu thật. Chúng dùng để kiểm thử
    pipeline fine-tune (đảm bảo script chạy được, định dạng đúng, đo được loss)
    khi database chưa tích luỹ đủ bản ghi. Một model huấn luyện CHỦ YẾU trên
    dữ liệu tổng hợp này chỉ học được các mẫu câu do chính script sinh ra —
    tuyệt đối không trình bày kết quả đó như năng lực phân tích thật trong báo cáo.
    """
    import pandas as pd

    # Cùng danh sách SKIP_FILES với backend/train_tft.py: đây là 3 file CSV rác
    # còn sót lại từ một lần gộp dữ liệu lỗi trước đây (xem training/collect_tft_data.py).
    # Chúng có dòng header kép kiểu yfinance cũ (dòng thứ 2 là "BTC-USD,BTC-USD,..."
    # thay vì dữ liệu số), khiến pandas đọc cả cột "Close" thành chuỗi và crash ở
    # phép chia bên dưới. train_tft.py đã biết né 3 file này; hàm sinh mẫu tổng hợp
    # thì trước đây lại chọn ngẫu nhiên từ TOÀN BỘ *.csv nên vẫn dính phải.
    SKIP_FILES = {"merged_data", "bitcoin_data", "bitcoin_data_global"}

    csv_files = [
        f for f in os.listdir(data_dir) if f.endswith(".csv") and f[:-4] not in SKIP_FILES
    ]
    if not csv_files:
        print(f"Không có file CSV nào trong {data_dir}")
        return

    random.seed(42)
    generated = 0

    while generated < count and csv_files:
        filename = random.choice(csv_files)
        ticker = filename[:-4]

        try:
            df = pd.read_csv(os.path.join(data_dir, filename), index_col="Date", parse_dates=True)
        except Exception:
            csv_files.remove(filename)
            continue

        if len(df) < 60 or "Close" not in df.columns:
            csv_files.remove(filename)
            continue

        close_numeric = pd.to_numeric(df["Close"], errors="coerce").dropna()
        if len(close_numeric) < 60:
            csv_files.remove(filename)
            continue

        idx = random.randint(30, len(close_numeric) - 2)
        window = close_numeric.iloc[idx - 20 : idx + 1]
        current = float(window.iloc[-1])
        change_pct = float((window.iloc[-1] / window.iloc[-2] - 1) * 100)
        volatility = float(window.pct_change().std() * 100)

        if change_pct > 1.5:
            tone = "bullish"
        elif change_pct < -1.5:
            tone = "bearish"
        else:
            tone = "neutral"

        n = random.randint(2, 8)
        headlines = [
            t.format(ticker=ticker, n=n) for t in random.sample(_HEADLINE_TEMPLATES[tone], k=2)
        ]

        confidence = round(min(0.85, 0.5 + abs(change_pct) / 20), 2)
        sentiment = {"bullish": "BULLISH", "bearish": "BEARISH", "neutral": "NEUTRAL"}[tone]

        record = {
            "ticker": ticker,
            "sentiment": sentiment,
            "confidence": confidence,
            "summary": (
                f"{ticker} biến động {change_pct:+.2f}% ở phiên gần nhất với mức biến động "
                f"{volatility:.2f}%. Diễn biến giá cho thấy tâm lý {sentiment.lower()} "
                "trong ngắn hạn."
            ),
            "key_factors": [
                f"Biến động giá {change_pct:+.2f}% phiên gần nhất",
                # LỖI ĐÃ SỬA: dòng này ghi "20 phiên" trong khi phần input của
                # CHÍNH mẫu đó ghi "Biến động 10 phiên" — cùng một con số, hai cái
                # tên. Cửa sổ thật là `close_numeric.iloc[idx-20 : idx+1]`, tức 20
                # return, nên nhãn đúng là 20 phiên và input mới là chỗ sai. Cả
                # 3000/3000 mẫu của bộ 29/08 đều dính, dạy model quy tắc vô nghĩa
                # "chép số ở dòng 10 phiên sang dòng 20 phiên".
                f"Độ biến động 20 phiên ở mức {volatility:.2f}%",
                f"Tin tức thị trường nghiêng về hướng {sentiment.lower()}",
            ],
            "recommendation": {
                "BULLISH": "Có thể cân nhắc giải ngân từng phần nếu giá điều chỉnh.",
                "BEARISH": "Ưu tiên quản trị rủi ro và bảo toàn vốn.",
                "NEUTRAL": "Theo dõi thêm, chờ tín hiệu rõ ràng hơn.",
            }[sentiment],
            "risk_level": "HIGH" if volatility > 3 else "MEDIUM" if volatility > 1.5 else "LOW",
        }

        # Dùng CHUNG prompt với lúc suy luận, để mẫu tổng hợp không có hình dạng
        # khác mẫu thật (chạy `--source both` trước đây cho ra dataset hai dạng
        # prompt lẫn lộn).
        headline_dicts = [{"title": h, "summary": "", "source": "synthetic"} for h in headlines]
        # NHÃN PHẢI CÓ CĂN CỨ TRONG INPUT.
        # Bản cũ chỉ đưa giá vào prompt, trong khi nhãn đích lại chứa hai con số
        # CHÍNH XÁC (`change_pct`, `volatility`) mà prompt hoàn toàn không nhắc
        # tới. Đó là dạy model bịa số — và số bịa đó sau này được ghi thẳng vào
        # `research_reports` rồi hiện ra giao diện như phân tích thật.
        price_info = (
            f"Giá: {current:,.4f} | Biến động phiên gần nhất: {change_pct:+.2f}% "
            f"| Độ biến động 20 phiên: {volatility:.2f}%"
        )
        user_prompt = build_analysis_prompt(ticker, headline_dicts, price_info)

        yield {
            "sample": to_chat_sample(user_prompt, build_target_response(record)),
            "ticker": ticker,
            # Mẫu tổng hợp không có mốc thời gian thật; để rỗng nên chúng luôn bị
            # xếp vào phần TRAIN khi chia theo thời gian (xem write_splits).
            "created_at": "",
            "dedup_key": dedup_key(ticker, headline_dicts),
            "origin": "synthetic",
        }
        generated += 1

    print(f"Đã sinh {generated} mẫu tổng hợp.")


# ══════════════════════════════════════════════════════════════════════════════
#  XUẤT FILE
# ══════════════════════════════════════════════════════════════════════════════

def write_splits(samples: List[Dict], output_dir: str, review_sample: int = 0,
                 force: bool = False) -> None:
    """
    Khử trùng lặp, chia train/validation/test THEO THỜI GIAN 80/10/10, ghi JSONL.

    LỖI ĐÃ SỬA 1 — CHIA NGẪU NHIÊN.
    Bản cũ `random.shuffle(samples)` rồi cắt 80/10/10. Với dữ liệu thật do
    `cron_researcher` sinh, các bản ghi gần-trùng nhau (cùng ngày khác mã, hoặc cùng
    mã hai ngày liên tiếp — vì hai feed RSS không lọc theo mã) sẽ nằm cả ở train lẫn
    test. Eval loss trên test khi đó đo khả năng GHI NHỚ, không phải khái quát hoá.
    Trên bộ 29/08, 93/93 ticker của test đã xuất hiện trong train.

    LỖI ĐÃ SỬA 2 — KHÔNG KHỬ TRÙNG LẶP. Không có bước nào loại bản sao.

    LỖI ĐÃ SỬA 3 — GHI ĐÈ KHÔNG HỎI.
    `--output` mặc định là `data/llm_dataset`. Nếu backfill mới cho ra 40 bản ghi,
    hàm này vẫn ghi đè `train.jsonl` (3,8 MB) bằng 32 dòng. Cảnh báo "<500 mẫu" chỉ
    được IN RA chứ không chặn, và không có backup nào của thư mục này.
    """
    if not samples:
        print("Không có mẫu nào để ghi. Kiểm tra lại nguồn dữ liệu.")
        return

    # ── Khử trùng lặp ──
    seen = set()
    deduped = []
    for item in samples:
        key = item.get("dedup_key")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        deduped.append(item)
    if len(deduped) < len(samples):
        print(f"Đã loại {len(samples) - len(deduped)} mẫu trùng lặp (còn {len(deduped)}).")
    samples = deduped

    # ── Chặn ghi đè ──
    train_path = os.path.join(output_dir, "train.jsonl")
    if os.path.exists(train_path) and not force:
        try:
            with open(train_path, encoding="utf-8") as f:
                existing = sum(1 for _ in f)
        except OSError:
            existing = 0
        if existing > len(samples):
            print(
                f"\nTỪ CHỐI GHI ĐÈ: {train_path} đang có {existing} mẫu, bộ mới chỉ có "
                f"{len(samples)}.\nGhi đè sẽ mất bộ dữ liệu lớn hơn. Nếu chắc chắn, "
                "chạy lại với --force, hoặc đổi --output sang thư mục khác."
            )
            return

    # ── Chia THEO NGUỒN, rồi THEO THỜI GIAN ──
    #
    # LỖI ĐÃ SỬA: bản cũ chỉ sort theo `created_at` rồi cắt 80/10/10. Mẫu tổng hợp
    # có `created_at` rỗng nên dồn về đầu, nhưng với `--source both` (mặc định)
    # chúng chiếm phần lớn dataset — nên tập VALIDATION hoàn toàn có thể gồm 100%
    # mẫu tổng hợp. Mà validation chính là tập dùng để CHỌN CHECKPOINT tốt nhất:
    # chọn bằng dữ liệu tự sinh nghĩa là chọn ra model giỏi bắt chước quy tắc sinh
    # dữ liệu, không phải model giỏi phân tích tin tức thật.
    #
    # Nay: `validation` và `test` CHỈ lấy từ mẫu thật (`supabase`), chia theo thời
    # gian; mẫu `synthetic` chỉ được vào `train`.
    n = len(samples)
    synthetic = [it for it in samples if it.get("origin") == "synthetic"]
    real = [it for it in samples if it.get("origin") != "synthetic"]
    real.sort(key=lambda it: it.get("created_at") or "")

    n_real = len(real)
    n_val = int(n_real * 0.1)
    n_test = int(n_real * 0.1)
    n_real_train = n_real - n_val - n_test

    splits = {
        "train": synthetic + real[:n_real_train],
        "validation": real[n_real_train : n_real_train + n_val],
        "test": real[n_real_train + n_val :],
    }

    # Mẫu thật quá ít thì validation/test gần như rỗng — vẫn ghi, nhưng phải nói to.
    if n_real < 30:
        print(
            "\n" + "=" * 70 + "\n"
            f"CẢNH BÁO LỚN: chỉ có {n_real} mẫu THẬT (supabase) trong toàn bộ dataset.\n"
            f"Tập validation ({len(splits['validation'])} mẫu) và test "
            f"({len(splits['test'])} mẫu) quá nhỏ để đo được bất cứ điều gì.\n"
            "Việc chọn checkpoint sẽ gần như ngẫu nhiên, và mọi con số đo trên tập\n"
            "test KHÔNG được đưa vào báo cáo. Hãy thu thập thêm dữ liệu thật trước.\n"
            + "=" * 70
        )

    # Cảnh báo ĐỐI XỨNG cho cả validation lẫn test: cả hai đều mất giá trị nếu
    # lẫn mẫu tổng hợp (tin tức sinh ra từ dấu biến động giá, nhãn cũng suy từ
    # chính dấu giá đó).
    for split_name, label in (("validation", "VALIDATION"), ("test", "TEST")):
        rows = splits[split_name]
        synth_count = sum(1 for it in rows if it.get("origin") == "synthetic")
        if synth_count:
            print(
                f"\nCẢNH BÁO: {synth_count}/{len(rows)} mẫu trong tập {label} là dữ "
                "liệu TỔNG HỢP.\nMọi chỉ số đo trên tập này không có giá trị khoa học "
                "— đừng đưa vào báo cáo.\nDùng --source supabase khi đã đủ dữ liệu thật."
            )
        elif not rows:
            print(
                f"\nCẢNH BÁO: tập {label} RỖNG (không có mẫu thật nào để chia). "
                + (
                    "Không thể chọn checkpoint theo dữ liệu thật."
                    if split_name == "validation"
                    else "Không thể báo cáo bất kỳ chỉ số đánh giá nào."
                )
            )

    os.makedirs(output_dir, exist_ok=True)

    for name, rows in splits.items():
        path = os.path.join(output_dir, f"{name}.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for row in rows:
                # Chỉ ghi phần `messages`; metadata (ticker/created_at/dedup) chỉ
                # phục vụ việc chia tập và không được lọt vào file huấn luyện.
                f.write(json.dumps(row["sample"], ensure_ascii=False) + "\n")
        print(f"  {name:<12} {len(rows):>6} mẫu → {path}")

    # Tệp để review thủ công — con số "đã review N mẫu" nên đưa vào báo cáo.
    if review_sample > 0:
        review_rows = random.sample(samples, min(review_sample, len(samples)))
        review_path = os.path.join(output_dir, "review_sample.md")
        with open(review_path, "w", encoding="utf-8") as f:
            f.write("# Mẫu dữ liệu để review thủ công\n\n")
            f.write(
                f"Chọn ngẫu nhiên {len(review_rows)} mẫu trong tổng số {n}.\n"
                "Với mỗi mẫu, đánh dấu ĐẠT / KHÔNG ĐẠT và ghi lý do.\n\n---\n\n"
            )
            for i, row in enumerate(review_rows, 1):
                msgs = row["sample"]["messages"]
                f.write(f"## Mẫu {i} — {row.get('ticker', '?')} ({row.get('origin', '?')})\n\n")
                f.write(f"### Input\n```\n{msgs[1]['content']}\n```\n\n")
                f.write(f"### Output mẫu\n```json\n{msgs[2]['content']}\n```\n\n")
                f.write("**Đánh giá:** [ ] ĐẠT  [ ] KHÔNG ĐẠT\n\n**Ghi chú:** \n\n---\n\n")
        print(f"  review       {len(review_rows):>6} mẫu → {review_path}")

    metadata = {
        "total_samples": n,
        "splits": {k: len(v) for k, v in splits.items()},
        "origin_counts": {
            name: {
                "supabase": sum(1 for it in rows if it.get("origin") == "supabase"),
                "synthetic": sum(1 for it in rows if it.get("origin") == "synthetic"),
            }
            for name, rows in splits.items()
        },
        "split_strategy": "chronological by created_at (80/10/10), deduplicated by ticker+headlines",
        "target_format": "json matching research_agent._llm_analysis schema",
        "prompt_builder": "backend.agents.research_agent.build_analysis_prompt",
        "system_prompt": SYSTEM_PROMPT,
        "generated_at": datetime.now().isoformat(),
        "format": "chat messages (system/user/assistant)",
    }
    with open(os.path.join(output_dir, "dataset_info.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Dựng dataset fine-tune cho Model 2")
    parser.add_argument("--source", choices=["supabase", "synthetic", "both"], default="both")
    parser.add_argument("--count", type=int, default=2000, help="Số mẫu tổng hợp cần sinh")
    parser.add_argument("--limit", type=int, default=10000, help="Số bản ghi tối đa đọc từ Supabase")
    parser.add_argument("--output", type=str, default=os.path.join(PROJECT_ROOT, "data", "llm_dataset"))
    parser.add_argument("--review-sample", type=int, default=50, help="Số mẫu xuất ra để review tay")
    parser.add_argument(
        "--force", action="store_true",
        help="Cho phép ghi đè dataset hiện có kể cả khi bộ mới nhỏ hơn.",
    )
    args = parser.parse_args()

    samples: List[Dict] = []

    if args.source in ("supabase", "both"):
        print("Đang đọc dữ liệu thật từ Supabase...")
        samples.extend(load_from_supabase(args.limit))

    if args.source in ("synthetic", "both"):
        data_dir = os.path.join(PROJECT_ROOT, "data")
        if os.path.isdir(data_dir):
            needed = max(0, args.count - len(samples)) if args.source == "both" else args.count
            if needed:
                print(f"Đang sinh {needed} mẫu tổng hợp từ dữ liệu giá...")
                samples.extend(generate_synthetic(needed, data_dir))

    print(f"\nTổng cộng {len(samples)} mẫu.")
    if len(samples) < 500:
        print(
            "\nCẢNH BÁO: dưới 500 mẫu thường không đủ để LoRA học được gì có ý nghĩa.\n"
            "Checklist đồ án đặt mục tiêu 2.000-10.000 cặp chất lượng. Hãy để job nghiên cứu\n"
            "chạy thêm một thời gian để tích luỹ dữ liệu thật, hoặc tăng --count."
        )

    write_splits(samples, args.output, args.review_sample, force=args.force)
    print(f"\nXong. Bước tiếp theo: mở training/finetune_qlora.py trên Colab hoặc Kaggle.")


if __name__ == "__main__":
    main()
