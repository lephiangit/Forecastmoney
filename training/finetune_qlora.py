"""
finetune_qlora.py – Fine-tune Model 2 bằng QLoRA 4-bit.

════════════════════════════════════════════════════════════════════════════════
 CHẠY Ở ĐÂU

 Script này KHÔNG chạy trên Render hay trên máy cá nhân không có GPU.
 Nó dành cho Google Colab (GPU T4 miễn phí) hoặc Kaggle (T4 x2 / P100).

 Trên Colab, tạo một notebook và chạy:

     !git clone <repo-cua-ban> && cd ForecastAI
     !pip install -q transformers peft bitsandbytes accelerate trl datasets
     !python -m training.finetune_qlora --model qwen --epochs 3

 Kaggle cho 30 giờ GPU/tuần và session không bị ngắt sau 90 phút như Colab free —
 với công việc này Kaggle thường là lựa chọn tốt hơn.

════════════════════════════════════════════════════════════════════════════════
 VÌ SAO LÀ QLoRA

 Qwen2.5-7B ở độ chính xác đầy đủ cần khoảng 28GB VRAM chỉ để chứa trọng số —
 vượt xa 16GB của T4. QLoRA giải quyết bằng hai bước:

   1. Lượng tử hoá 4-bit: nén trọng số gốc xuống ~4GB, đóng băng không huấn luyện.
   2. LoRA adapter: chỉ huấn luyện các ma trận hạng thấp chèn thêm vào —
      khoảng 20-40 triệu tham số thay vì 7 tỷ.

 Kết quả: fine-tune được model 7B trên GPU 16GB, và file adapter xuất ra chỉ
 vài chục MB (upload lên Hugging Face Hub rất nhẹ).

════════════════════════════════════════════════════════════════════════════════
 SỐ LIỆU CẦN GHI LẠI CHO BÁO CÁO

 - train/eval loss theo từng epoch (script tự lưu vào training_log.json)
 - Số tham số huấn luyện so với tổng số tham số (script in ra lúc bắt đầu)
 - Thời gian huấn luyện và loại GPU
 - Một vài output mẫu sinh từ tập test, đọc và chấm bằng tay

 Đừng chỉ báo cáo loss. Hội đồng sẽ hỏi "loss 0.8 nghĩa là gì" — hãy chuẩn bị
 sẵn vài ví dụ output trước và sau fine-tune để so sánh trực quan.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# Hai lựa chọn model mà checklist đồ án yêu cầu so sánh.
MODEL_CONFIGS = {
    "qwen": {
        "model_id": "Qwen/Qwen2.5-7B-Instruct",
        "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        "note": "Hỗ trợ tiếng Việt tốt hơn — thường là lựa chọn phù hợp hơn cho đồ án này.",
    },
    "llama": {
        "model_id": "meta-llama/Llama-3.1-8B-Instruct",
        "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        "note": "Cần chấp nhận license trên Hugging Face và đăng nhập bằng token trước khi tải.",
    },
}


def parse_args():
    p = argparse.ArgumentParser(description="Fine-tune Model 2 bằng QLoRA")
    p.add_argument("--model", choices=list(MODEL_CONFIGS), default="qwen")
    p.add_argument("--dataset", type=str, default=os.path.join(PROJECT_ROOT, "data", "llm_dataset"))
    p.add_argument("--output", type=str, default=os.path.join(PROJECT_ROOT, "models", "llm_adapter"))
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--batch-size", type=int, default=1)
    p.add_argument("--grad-accum", type=int, default=8)
    p.add_argument("--lr", type=float, default=2e-4)
    p.add_argument("--lora-r", type=int, default=16, help="Hạng của LoRA; 8-64 là khoảng thường dùng")
    p.add_argument("--lora-alpha", type=int, default=32)
    p.add_argument("--max-seq-length", type=int, default=2048)
    p.add_argument("--push-to-hub", type=str, default=None, help="VD: ten-cua-ban/forecastai-research")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    # Import ở trong hàm: các thư viện này chỉ tồn tại trên môi trường có GPU,
    # nên file vẫn đọc/lint được ở máy local mà không cần cài chúng.
    try:
        import torch
        from datasets import load_dataset
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            BitsAndBytesConfig,
            TrainingArguments,
        )
        from trl import SFTTrainer
    except ImportError as e:
        print(f"Thiếu thư viện: {e}")
        print("\nCài đặt bằng lệnh:")
        print("  pip install transformers peft bitsandbytes accelerate trl datasets")
        sys.exit(1)

    if not torch.cuda.is_available():
        print("Không phát hiện GPU. QLoRA bắt buộc cần CUDA.")
        print("Hãy chạy script này trên Google Colab hoặc Kaggle với runtime GPU.")
        sys.exit(1)

    config = MODEL_CONFIGS[args.model]
    print("=" * 70)
    print(f"Fine-tune QLoRA: {config['model_id']}")
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"Ghi chú: {config['note']}")
    print("=" * 70)

    # ── Dataset ──
    data_files = {
        "train": os.path.join(args.dataset, "train.jsonl"),
        "validation": os.path.join(args.dataset, "validation.jsonl"),
    }
    for split, path in data_files.items():
        if not os.path.exists(path):
            print(f"Không tìm thấy {path}")
            print("Chạy `python -m training.build_llm_dataset` trước.")
            sys.exit(1)

    dataset = load_dataset("json", data_files=data_files)
    print(f"\nTrain: {len(dataset['train'])} mẫu | Validation: {len(dataset['validation'])} mẫu")

    # ── Tokenizer ──
    tokenizer = AutoTokenizer.from_pretrained(config["model_id"], trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    # Với causal LM, pad bên phải là đúng khi huấn luyện (pad trái dành cho generation).
    tokenizer.padding_side = "right"

    # ── Lượng tử hoá 4-bit ──
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        # NF4 là kiểu dữ liệu 4-bit được thiết kế riêng cho trọng số phân phối chuẩn,
        # giữ chất lượng tốt hơn đáng kể so với int4 thông thường.
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
        # Lượng tử hoá lồng: nén thêm cả các hằng số lượng tử hoá, tiết kiệm ~0.4 bit/tham số.
        bnb_4bit_use_double_quant=True,
    )

    print("\nĐang tải model (lần đầu sẽ mất vài phút để tải trọng số)...")
    model = AutoModelForCausalLM.from_pretrained(
        config["model_id"],
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model.config.use_cache = False  # Không tương thích với gradient checkpointing
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)

    # ── LoRA ──
    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=config["target_modules"],
    )
    model = get_peft_model(model, lora_config)

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(
        f"\nTham số huấn luyện: {trainable:,} / {total:,} ({trainable / total * 100:.4f}%)"
        "\n  ^ Con số này nên đưa vào báo cáo: nó cho thấy LoRA tiết kiệm tài nguyên tới mức nào."
    )

    # ── Huấn luyện ──
    os.makedirs(args.output, exist_ok=True)
    training_args = TrainingArguments(
        output_dir=args.output,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        logging_steps=10,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        bf16=torch.cuda.is_bf16_supported(),
        fp16=not torch.cuda.is_bf16_supported(),
        # Bộ tối ưu 8-bit tiết kiệm khoảng 2GB VRAM so với AdamW thường —
        # thường là khác biệt giữa "chạy được" và "hết bộ nhớ" trên T4.
        optim="paged_adamw_8bit",
        gradient_checkpointing=True,
        report_to="none",
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
    )

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"],
        processing_class=tokenizer,
    )

    print("\nBắt đầu huấn luyện...\n")
    started = datetime.now()
    result = trainer.train()
    duration = (datetime.now() - started).total_seconds()

    # ── Lưu adapter ──
    trainer.save_model(args.output)
    tokenizer.save_pretrained(args.output)

    log = {
        "base_model": config["model_id"],
        "gpu": torch.cuda.get_device_name(0),
        "trainable_params": trainable,
        "total_params": total,
        "trainable_pct": round(trainable / total * 100, 4),
        "lora_r": args.lora_r,
        "lora_alpha": args.lora_alpha,
        "epochs": args.epochs,
        "learning_rate": args.lr,
        "effective_batch_size": args.batch_size * args.grad_accum,
        "train_samples": len(dataset["train"]),
        "final_train_loss": result.training_loss,
        "duration_seconds": round(duration),
        "duration_human": f"{duration / 60:.1f} phút",
        "log_history": trainer.state.log_history,
        "trained_at": datetime.now().isoformat(),
    }
    with open(os.path.join(args.output, "training_log.json"), "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print("HOÀN TẤT")
    print(f"  Adapter:    {args.output}")
    print(f"  Train loss: {result.training_loss:.4f}")
    print(f"  Thời gian:  {duration / 60:.1f} phút")
    print("=" * 70)

    if args.push_to_hub:
        print(f"\nĐang đẩy lên Hugging Face Hub: {args.push_to_hub}")
        model.push_to_hub(args.push_to_hub)
        tokenizer.push_to_hub(args.push_to_hub)
        print("Xong. Nhớ ghi link Hub này vào báo cáo đồ án.")

    print("\nBước tiếp theo:")
    print("  1. Sinh output trên tập test và đọc thủ công vài mẫu")
    print("  2. Lặp lại với --model llama để có số liệu so sánh giữa hai model")
    print("  3. Deploy lên Hugging Face Spaces (Gradio + ZeroGPU)")


if __name__ == "__main__":
    main()
