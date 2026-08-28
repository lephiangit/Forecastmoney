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
            parts.append(f"- Biến động 10 phiên: {price_context['volatility']:.2f}%")
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
    """Dựng phần output mẫu từ một bản ghi phân tích đã lưu."""
    key_factors = record.get("key_factors") or []
    if isinstance(key_factors, str):
        try:
            key_factors = json.loads(key_factors)
        except json.JSONDecodeError:
            key_factors = [key_factors]

    confidence = float(record.get("confidence") or 0.5)
    if confidence > 1:
        confidence /= 100

    lines = [
        f"**Tâm lý thị trường:** {record.get('sentiment', 'NEUTRAL')}",
        f"**Độ tin cậy:** {confidence:.0%}",
        "",
        f"**Nhận định:** {record.get('summary', '')}",
        "",
        "**Các yếu tố chính:**",
    ]
    lines.extend(f"{i}. {f}" for i, f in enumerate(key_factors[:3], 1))
    lines.extend(
        [
            "",
            f"**Khuyến nghị:** {record.get('recommendation', 'Theo dõi thêm.')}",
            f"**Mức rủi ro:** {record.get('risk_level', 'MEDIUM')}",
            "",
            "*Đây là thông tin tham khảo phục vụ mục đích học thuật, không phải lời khuyên đầu tư.*",
        ]
    )
    return "\n".join(lines)


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
            # Chỉ dùng bản ghi do LLM sinh. Bản ghi "keyword" là kết quả đếm từ khoá —
            # huấn luyện trên đó chỉ dạy model bắt chước một heuristic thô.
            if record.get("source") != "groq":
                continue
            if not record.get("summary"):
                continue

            headlines_raw = record.get("headlines") or []
            if isinstance(headlines_raw, str):
                try:
                    headlines_raw = json.loads(headlines_raw)
                except json.JSONDecodeError:
                    headlines_raw = []

            headlines = [
                h.get("title", "") if isinstance(h, dict) else str(h)
                for h in headlines_raw
                if h
            ]
            if not headlines:
                continue

            user_prompt = build_user_prompt(record.get("ticker", "UNKNOWN"), headlines)
            yield to_chat_sample(user_prompt, build_target_response(record))
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

    csv_files = [f for f in os.listdir(data_dir) if f.endswith(".csv")]
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

        idx = random.randint(30, len(df) - 2)
        window = df["Close"].iloc[idx - 20 : idx + 1]
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

        price_context = {"current": round(current, 2), "change_pct": change_pct, "volatility": volatility}
        user_prompt = build_user_prompt(ticker, headlines, price_context)

        yield to_chat_sample(user_prompt, build_target_response(record))
        generated += 1

    print(f"Đã sinh {generated} mẫu tổng hợp.")


# ══════════════════════════════════════════════════════════════════════════════
#  XUẤT FILE
# ══════════════════════════════════════════════════════════════════════════════

def write_splits(samples: List[Dict], output_dir: str, review_sample: int = 0) -> None:
    """Chia train/validation/test theo tỷ lệ 80/10/10 và ghi ra JSONL."""
    if not samples:
        print("Không có mẫu nào để ghi. Kiểm tra lại nguồn dữ liệu.")
        return

    random.seed(42)
    random.shuffle(samples)

    n = len(samples)
    n_train = int(n * 0.8)
    n_val = int(n * 0.1)

    splits = {
        "train": samples[:n_train],
        "validation": samples[n_train : n_train + n_val],
        "test": samples[n_train + n_val :],
    }

    os.makedirs(output_dir, exist_ok=True)

    for name, rows in splits.items():
        path = os.path.join(output_dir, f"{name}.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
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
                f.write(f"## Mẫu {i}\n\n### Input\n```\n{row['messages'][1]['content']}\n```\n\n")
                f.write(f"### Output mẫu\n```\n{row['messages'][2]['content']}\n```\n\n")
                f.write("**Đánh giá:** [ ] ĐẠT  [ ] KHÔNG ĐẠT\n\n**Ghi chú:** \n\n---\n\n")
        print(f"  review       {len(review_rows):>6} mẫu → {review_path}")

    metadata = {
        "total_samples": n,
        "splits": {k: len(v) for k, v in splits.items()},
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

    write_splits(samples, args.output, args.review_sample)
    print(f"\nXong. Bước tiếp theo: mở training/finetune_qlora.py trên Colab hoặc Kaggle.")


if __name__ == "__main__":
    main()
