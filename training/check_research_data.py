"""
check_research_data.py — Đếm xem bảng `research_reports` có đủ dữ liệu THẬT để
dựng lại dataset fine-tune cho Model 2 hay chưa.

VÌ SAO CẦN SCRIPT NÀY
─────────────────────
Bộ dataset hiện tại (`data/llm_dataset/`, sinh ngày 29/08) có 3000 mẫu thì
**cả 3000 đều do `generate_synthetic()` sinh ra bằng luật** — không có mẫu thật
nào. Trong các mẫu đó:

  - Nhãn ghi "Độ biến động 20 phiên ở mức {X}" trong khi input ghi
    "Biến động 10 phiên: {X}" → nhãn tự mâu thuẫn với chính input của nó.
  - Tin tức được sinh RA TỪ dấu biến động giá, rồi nhãn sentiment cũng suy từ
    chính dấu giá đó → trong dữ liệu, tin tức không mang thông tin nào cả.

Model fine-tune trên đó đã học đúng thứ có trong dữ liệu: nhìn dấu giá, chọn từ,
điền vào khuôn. Muốn nó thực sự đọc tin, dữ liệu huấn luyện phải có quan hệ
nhân quả tin tức → nhận định. Đó chính là các bản ghi `source='groq'` trong
bảng này: input là tin thật, nhãn là phân tích thật của model lớn.

LƯU Ý QUAN TRỌNG: chỉ bản ghi `source='groq'` mới dùng làm nhãn được.
Bản ghi `source='keyword'` là fallback đếm từ khoá (chấm điểm bằng luật) —
lấy nó làm nhãn là lặp lại đúng sai lầm của bộ dataset tổng hợp.

CÁCH CHẠY
─────────
    python -m training.check_research_data
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Ngưỡng tham khảo cho fine-tune QLoRA một model 7B trên tác vụ hẹp.
# Dưới 300 mẫu thì adapter gần như chỉ học được văn phong, không học được cách
# suy luận; 800-1000 mẫu thật thường đã cho kết quả dùng được.
MIN_VIABLE = 300
COMFORTABLE = 800


def _as_list(value):
    """headlines/key_factors có thể là list, hoặc chuỗi JSON tuỳ cách ghi vào DB."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return [value] if value.strip() else []
    return value if isinstance(value, list) else []


def main() -> int:
    from backend.config import settings

    if not settings.supabase_url or not settings.supabase_key:
        print("Thiếu SUPABASE_URL / SUPABASE_KEY trong .env — không truy vấn được.")
        return 1

    try:
        from supabase import create_client
    except ImportError:
        print("Thiếu thư viện supabase: pip install supabase")
        return 1

    client = create_client(settings.supabase_url, settings.supabase_key)

    # Kéo theo trang, vì mặc định PostgREST giới hạn 1000 dòng/lần.
    rows = []
    page_size = 1000
    offset = 0
    while True:
        res = (
            client.table("research_reports")
            .select("source,sentiment,confidence,summary,key_factors,headlines,ticker,created_at")
            .order("created_at", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = res.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size

    if not rows:
        print("Bảng research_reports rỗng.")
        return 1

    print("=" * 74)
    print(f"TỔNG SỐ BẢN GHI research_reports: {len(rows)}")
    print("=" * 74)

    by_source = Counter(r.get("source") or "(trống)" for r in rows)
    print("\nPhân bố theo NGUỒN phân tích:")
    for src, n in by_source.most_common():
        note = ""
        if src == "groq":
            note = "  ← dùng làm nhãn được"
        elif src == "keyword":
            note = "  ← fallback đếm từ khoá, KHÔNG dùng làm nhãn"
        elif src == "no_data":
            note = "  ← không có tin tức, không dùng được"
        print(f"  {src:12s} {n:6d}  ({n / len(rows) * 100:5.1f}%){note}")

    # DÙNG CHUNG hàm với build_llm_dataset.
    #
    # LỖI ĐÃ SỬA: hai file định nghĩa "dùng được" khác nhau. `check` chỉ đòi có
    # summary + headlines, còn `build` còn ép headlines giải mã được thành list
    # KHÔNG RỖNG sau khi map title, và loại bản ghi thiếu key_factors. Nghĩa là cổng
    # go/no-go này có thể báo ĐỦ trong khi dataset dựng ra ít hơn hẳn — và không ai
    # biết vì sao. Cổng mà nói dối thì không còn là cổng.
    #
    # Đồng thời bộ lọc `== "groq"` bỏ sót provider `custom`/`local` — chính là chế
    # độ mà Model 2 sẽ chạy sau khi fine-tune xong.
    from training.build_llm_dataset import TRUSTED_LLM_SOURCES, is_usable_record

    groq_rows = [r for r in rows if (r.get("source") or "") in TRUSTED_LLM_SOURCES]
    usable = [r for r in groq_rows if is_usable_record(r)]

    print(f"\n{'─' * 74}")
    print(f"Bản ghi từ LLM thật (groq/custom/local)    : {len(groq_rows)}")
    print(f"  ├─ có summary (nhãn)                     : {sum(1 for r in groq_rows if (r.get('summary') or '').strip())}")
    print(f"  ├─ có headlines (input tin tức)          : {sum(1 for r in groq_rows if _as_list(r.get('headlines')))}")
    print(f"  ├─ có key_factors                        : {sum(1 for r in groq_rows if _as_list(r.get('key_factors')))}")
    print(f"  └─ DÙNG ĐƯỢC (đủ cả tin tức lẫn nhận định): {len(usable)}")
    print("─" * 74)

    if usable:
        sentiments = Counter(r.get("sentiment") for r in usable)
        tickers = Counter(r.get("ticker") for r in usable)
        dates = sorted((r.get("created_at") or "")[:10] for r in usable if r.get("created_at"))

        print(f"\nPhân bố nhãn tâm lý : {dict(sentiments)}")
        least = min(sentiments.values()) if sentiments else 0
        if least < len(usable) * 0.15:
            print(f"  ⚠ Lớp ít nhất chỉ chiếm {least / len(usable) * 100:.1f}% — mất cân bằng, "
                  f"cân nhắc bù thêm mẫu cho lớp đó.")
        print(f"Số mã khác nhau     : {len(tickers)}")
        print(f"Top mã              : {', '.join(f'{t}({n})' for t, n in tickers.most_common(5))}")
        if dates:
            print(f"Khoảng thời gian    : {dates[0]} → {dates[-1]}")

        avg_hl = sum(len(_as_list(r.get("headlines"))) for r in usable) / len(usable)
        print(f"Số tin/bản ghi (TB) : {avg_hl:.1f}")

    print(f"\n{'=' * 74}")
    n = len(usable)
    if n >= COMFORTABLE:
        print(f"KẾT LUẬN: {n} mẫu thật — ĐỦ để dựng lại dataset và fine-tune lại ngay.")
        print("Bước tiếp: sửa build_llm_dataset.py để chỉ dùng nguồn thật, rồi train lại.")
    elif n >= MIN_VIABLE:
        print(f"KẾT LUẬN: {n} mẫu thật — ĐỦ TỐI THIỂU, train được nhưng nên tích luỹ thêm.")
        print(f"Mỗi ngày cron_researcher chạy sẽ cộng thêm. Mốc thoải mái là ~{COMFORTABLE} mẫu.")
    else:
        print(f"KẾT LUẬN: chỉ {n} mẫu thật — CHƯA ĐỦ (cần tối thiểu ~{MIN_VIABLE}).")
        print("Cách tăng nhanh: chạy cron_researcher trên nhiều mã hơn, hoặc sinh phân tích")
        print("Groq cho tin tức lịch sử để lấp đầy — không dùng lại mẫu tổng hợp bằng luật.")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
