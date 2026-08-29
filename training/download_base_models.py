"""
training/download_base_models.py – Tải trước (và cache) model gốc từ Hugging
Face Hub, tách riêng khỏi bước fine-tune.

VÌ SAO CẦN FILE NÀY
--------------------
`finetune_qlora.py` đã tự tải model gốc (Qwen2.5-7B hoặc Llama-3.1-8B) từ
Hugging Face Hub ngay trong lúc chạy — không cần tải thủ công, và KHÔNG nên
tải về máy cá nhân hay đẩy lên GitHub (model ~15GB, vượt xa giới hạn file
của GitHub, với lại máy không GPU thì tải về cũng không dùng để làm gì).

Nhưng gộp chung bước tải (phụ thuộc mạng, có thể chậm/đứt) với bước train
(tốn 2-4 tiếng GPU) nghĩa là nếu tải lỗi giữa chừng, bạn mất luôn thời gian
GPU đã dùng cho tới lúc đó. Script này tách riêng: chạy nó TRƯỚC, xác nhận
tải xong xuôi (model được cache lại), rồi mới chạy finetune_qlora.py — lúc
đó model đã có sẵn trong cache nên tải lại tức thì, không tốn thời gian GPU
chờ mạng.

CHẠY Ở ĐÂU: trên Colab/Kaggle (cùng môi trường sẽ chạy finetune_qlora.py),
không chạy được ở máy local vì cần các thư viện transformers/huggingface_hub
mà local venv chưa chắc có (và tải ~15GB cũng không cần thiết ở đó).

CÁCH DÙNG
---------
    pip install -q transformers accelerate huggingface_hub
    python -m training.download_base_models --model qwen
    python -m training.download_base_models --model llama   # cần đã login HF trước
    python -m training.download_base_models --model both
"""

from __future__ import annotations

import argparse
import sys

MODEL_IDS = {
    "qwen": "Qwen/Qwen2.5-7B-Instruct",
    "llama": "meta-llama/Llama-3.1-8B-Instruct",
}


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", choices=["qwen", "llama", "both"], default="qwen")
    return p.parse_args()


def _download(model_id: str) -> None:
    from huggingface_hub import snapshot_download

    print(f"Đang tải {model_id} về cache Hugging Face (lần đầu mất vài phút, ~15GB)...")
    path = snapshot_download(
        repo_id=model_id,
        # Chỉ cần trọng số safetensors + tokenizer — bỏ qua bin/pt cũ (pytorch_model*.bin),
        # ONNX, GGUF... nếu repo có kèm, đỡ tải dư dữ liệu không dùng tới.
        ignore_patterns=["*.bin", "*.pt", "*.onnx", "*.gguf", "*.msgpack", "*.h5"],
    )
    print(f"  Đã cache tại: {path}")


def main() -> None:
    args = parse_args()

    try:
        from huggingface_hub import snapshot_download  # noqa: F401
    except ImportError:
        print("Thiếu huggingface_hub. Cài bằng: pip install huggingface_hub")
        sys.exit(1)

    targets = list(MODEL_IDS) if args.model == "both" else [args.model]

    for key in targets:
        try:
            _download(MODEL_IDS[key])
        except Exception as e:
            print(f"Lỗi khi tải {MODEL_IDS[key]}: {type(e).__name__}: {e}")
            if key == "llama":
                print(
                    "Llama-3.1-8B cần: (1) đã accept license tại "
                    "https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct, và "
                    "(2) đã đăng nhập bằng token — `huggingface-cli login` hoặc "
                    "`huggingface_hub.login(token=...)` trước khi chạy script này."
                )
            sys.exit(1)

    print("\nXong. Model đã cache — chạy training.finetune_qlora bây giờ sẽ tải model gần như tức thì.")


if __name__ == "__main__":
    main()
