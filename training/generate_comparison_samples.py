"""
training/generate_comparison_samples.py – Sinh output SO SÁNH trước/sau fine-tune.

BỐI CẢNH
--------
finetune_qlora.py tự nhắc: "Đừng chỉ báo cáo loss. Hội đồng sẽ hỏi 'loss 0.8
nghĩa là gì' — hãy chuẩn bị sẵn vài ví dụ output trước và sau fine-tune để so
sánh trực quan." Script này làm đúng việc đó, tự động: lấy N câu hỏi thật từ
`test.jsonl` (tập KHÔNG được dùng để train/chọn checkpoint), sinh câu trả lời
hai lần — một lần bằng model GỐC (chưa fine-tune), một lần bằng model gốc +
adapter LoRA vừa train — rồi ghi cả hai cạnh nhau ra một file Markdown để đọc
và chấm tay.

CHẠY Ở ĐÂU: giống finetune_qlora.py, cần GPU — chạy trên Colab/Kaggle ngay
sau khi training xong, trong cùng session (adapter vẫn còn trong bộ nhớ/đĩa).

CÁCH DÙNG
---------
    python -m training.generate_comparison_samples --model qwen --n 8
    python -m training.generate_comparison_samples --model qwen --adapter /kaggle/working/ForecastAI/models/llm_adapter --dataset /kaggle/input/forecastai-llm-dataset --n 10
"""

from __future__ import annotations

import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Giữ đồng bộ với MODEL_CONFIGS trong finetune_qlora.py — không import trực
# tiếp để file này vẫn đọc được ở máy không có torch/transformers.
MODEL_IDS = {
    "qwen": "Qwen/Qwen2.5-7B-Instruct",
    "llama": "meta-llama/Llama-3.1-8B-Instruct",
}


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", choices=list(MODEL_IDS), default="qwen")
    p.add_argument("--adapter", type=str, default=os.path.join(PROJECT_ROOT, "models", "llm_adapter"))
    p.add_argument("--dataset", type=str, default=os.path.join(PROJECT_ROOT, "data", "llm_dataset"))
    p.add_argument("--n", type=int, default=8, help="Số mẫu test lấy ra so sánh")
    p.add_argument("--max-new-tokens", type=int, default=400)
    p.add_argument(
        "--output",
        type=str,
        default=os.path.join(PROJECT_ROOT, "models", "llm_adapter", "before_after_comparison.md"),
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    except ImportError as e:
        print(f"Thiếu thư viện: {e}")
        print("Cài đặt bằng: pip install transformers peft bitsandbytes accelerate")
        sys.exit(1)

    if not torch.cuda.is_available():
        print("Không phát hiện GPU. Chạy script này trên Colab/Kaggle với runtime GPU.")
        sys.exit(1)

    test_path = os.path.join(args.dataset, "test.jsonl")
    if not os.path.exists(test_path):
        print(f"Không tìm thấy {test_path}. Chạy `python -m training.build_llm_dataset` trước.")
        sys.exit(1)

    samples = []
    with open(test_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    samples = samples[: args.n]
    print(f"Lấy {len(samples)} mẫu từ tập test để so sánh.\n")

    model_id = MODEL_IDS[args.model]
    print(f"Đang tải model gốc: {model_id} (4-bit)...")

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
        bnb_4bit_use_double_quant=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"  # đúng chiều pad khi generate (khác lúc train)

    base_model = AutoModelForCausalLM.from_pretrained(
        model_id, quantization_config=bnb_config, device_map="auto", trust_remote_code=True
    )
    base_model.config.use_cache = True

    def generate(model, messages) -> str:
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            out = model.generate(
                **inputs,
                max_new_tokens=args.max_new_tokens,
                do_sample=False,
                temperature=None,
                top_p=None,
                pad_token_id=tokenizer.pad_token_id,
            )
        text = tokenizer.decode(out[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True)
        return text.strip()

    print("Sinh output với model GỐC (chưa fine-tune)...")
    before_outputs = []
    for i, sample in enumerate(samples, start=1):
        msgs = sample["messages"][:-1]  # bỏ câu trả lời thật, chỉ giữ system+user
        before_outputs.append(generate(base_model, msgs))
        print(f"  [{i}/{len(samples)}] xong")

    print(f"\nNạp adapter LoRA từ {args.adapter}...")
    if not os.path.isdir(args.adapter):
        print(f"Không tìm thấy thư mục adapter '{args.adapter}'. Chạy finetune_qlora.py trước.")
        sys.exit(1)

    tuned_model = PeftModel.from_pretrained(base_model, args.adapter)
    tuned_model.eval()

    print("Sinh output với model ĐÃ fine-tune...")
    after_outputs = []
    for i, sample in enumerate(samples, start=1):
        msgs = sample["messages"][:-1]
        after_outputs.append(generate(tuned_model, msgs))
        print(f"  [{i}/{len(samples)}] xong")

    # ── Ghi báo cáo Markdown ──
    lines = [
        "# So sánh output trước / sau fine-tune",
        "",
        f"Model gốc: `{model_id}` · Adapter: `{args.adapter}`",
        "",
        "Dùng bảng này để chấm tay: đúng định dạng? nhận định hợp lý so với tin tức "
        "đưa vào? có giữ disclaimer không? Đưa 3-5 ví dụ tiêu biểu vào báo cáo.",
        "",
    ]
    for i, sample in enumerate(samples):
        user_msg = next((m["content"] for m in sample["messages"] if m["role"] == "user"), "")
        reference = next((m["content"] for m in sample["messages"] if m["role"] == "assistant"), "")
        lines += [
            f"## Mẫu {i + 1}",
            "",
            "**Câu hỏi (input):**",
            "```",
            user_msg,
            "```",
            "",
            "**Nhãn tham chiếu (do Groq sinh — distillation, không phải con người gán):**",
            "```",
            reference,
            "```",
            "",
            "**Trước fine-tune (model gốc):**",
            "```",
            before_outputs[i],
            "```",
            "",
            "**Sau fine-tune:**",
            "```",
            after_outputs[i],
            "```",
            "",
            "---",
            "",
        ]

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\nXong. Đã ghi {len(samples)} cặp so sánh vào: {args.output}")
    print("Tải file này về và đọc thủ công trước khi đưa ví dụ vào báo cáo.")


if __name__ == "__main__":
    main()
