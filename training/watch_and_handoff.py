"""
training/watch_and_handoff.py – Tự động chuyển từ train TFT sang chuẩn bị
dataset fine-tune LLM, không cần ngồi canh terminal.

CÁCH DÙNG
---------
Mở một cửa sổ terminal MỚI (không phải cửa sổ đang chạy train_tft.py — script
này KHÔNG điều khiển tiến trình đó, chỉ đứng ngoài quan sát), rồi:

    cd ForecastAI
    venv\\Scripts\\activate
    python training/watch_and_handoff.py

Mỗi 30 giây, script kiểm tra danh sách tiến trình xem có dòng lệnh nào chứa
"train_tft.py" không. Khi PHÁT HIỆN nó đã từng chạy rồi giờ biến mất (do
EarlyStopping tự dừng, bạn Ctrl+C, hoặc chạy hết 100 epoch), script tự động
chạy bước kế tiếp:

    python -m training.build_llm_dataset --source both --count 3000

rồi in hướng dẫn bước sau đó (fine-tune QLoRA — cần GPU nên KHÔNG tự chạy
được ở đây, phải làm thủ công trên Colab/Kaggle theo training/README.md).

Có thể chạy script này NGAY BÂY GIỜ, song song với training đang chạy dở —
không cần dừng hay khởi động lại gì cả. Nó chỉ quan sát, không đụng vào tiến
trình train.

Nếu có `psutil` (khuyến nghị, cài bằng `pip install psutil`), dùng nó để dò
tiến trình chính xác trên mọi hệ điều hành. Nếu không có, dùng `wmic` (có sẵn
trên Windows, dù đã bị deprecated ở một số bản Windows 11 mới — nếu lệnh này
báo lỗi/không hoạt động, cài psutil để chắc chắn hơn).
"""

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MARKER = PROJECT_ROOT / "training" / ".handoff_done"
POLL_SECONDS = 30
PROCESS_NEEDLE = "train_tft.py"

try:
    import psutil

    HAVE_PSUTIL = True
except ImportError:
    HAVE_PSUTIL = False


def _is_training_running() -> bool:
    if HAVE_PSUTIL:
        for p in psutil.process_iter(["cmdline"]):
            try:
                cmdline = " ".join(p.info["cmdline"] or [])
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            if PROCESS_NEEDLE in cmdline:
                return True
        return False

    try:
        out = subprocess.run(
            ["wmic", "process", "where", "name='python.exe'", "get", "CommandLine"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return PROCESS_NEEDLE in out.stdout
    except Exception:
        # Không xác định được trạng thái thật — coi như VẪN ĐANG CHẠY để
        # không lỡ tay kích hoạt bước tiếp theo khi train chưa xong.
        return True


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def _run_dataset_build() -> None:
    cmd = [sys.executable, "-m", "training.build_llm_dataset", "--source", "both", "--count", "3000"]
    _log(f"Chạy: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))

    if result.returncode != 0:
        _log(f"Lệnh dựng dataset thoát với mã lỗi {result.returncode} — kiểm tra log ở trên, chưa đánh dấu hoàn tất.")
        return

    MARKER.write_text(datetime.now().isoformat())
    _log("Xong bước dựng dataset LLM. Xem data/llm_dataset/dataset_info.json và review_sample.md.")
    _log("Bước tiếp theo (thủ công, cần GPU): mở training/finetune_qlora.py trên Colab/Kaggle theo training/README.md.")


def main() -> None:
    if MARKER.exists():
        _log(f"Đã chạy handoff trước đó lúc {MARKER.read_text().strip()}.")
        _log(f"Xoá file {MARKER} nếu muốn dựng lại dataset từ đầu.")
        return

    _log("Bắt đầu theo dõi tiến trình train_tft.py (Ctrl+C để dừng theo dõi — không ảnh hưởng training).")
    if not HAVE_PSUTIL:
        _log("Chưa có psutil, dùng wmic để dò tiến trình. Cài `pip install psutil` nếu muốn chắc chắn hơn.")

    seen_running = False
    try:
        while True:
            running = _is_training_running()
            if running:
                if not seen_running:
                    _log("Đã thấy train_tft.py đang chạy. Sẽ tự động chuyển bước khi nó dừng hẳn.")
                seen_running = True
            elif seen_running:
                _log("train_tft.py đã dừng. Bắt đầu dựng dataset fine-tune LLM...")
                break
            else:
                _log("Chưa thấy train_tft.py chạy — script vẫn đợi, không làm gì cho tới khi bạn khởi động training.")

            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        _log("Đã dừng theo dõi theo yêu cầu (Ctrl+C). Training, nếu đang chạy, không bị ảnh hưởng gì.")
        return

    _run_dataset_build()


if __name__ == "__main__":
    main()
