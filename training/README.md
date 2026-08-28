# Model 2 — Hạ tầng fine-tune LLM

Thư mục này chứa phần còn thiếu giữa **hệ thống đang chạy** và **yêu cầu của đề cương đồ án**.

## Vấn đề cần giải quyết

Checklist đồ án (Tháng 2–3) yêu cầu:

- Thu thập và tạo dataset 2.000–10.000 cặp huấn luyện
- Fine-tune Qwen2.5-7B và Llama-3.1-8B bằng QLoRA để so sánh
- Upload model lên Hugging Face Hub

Hệ thống hiện tại **không làm bước nào trong số đó**. "Model 2" thực chất là các lời gọi
API Groq (`llama-3.3-70b-versatile`) kèm prompt engineering. Cách này chạy tốt và có
cơ chế dự phòng đàng hoàng, nhưng nó không chứng minh được kỹ năng fine-tune —
và đó thường là phần chiếm điểm nặng nhất khi chấm.

## Hai lựa chọn, chọn sớm

**Lựa chọn A — Thực sự fine-tune (dùng thư mục này).**
Bạn có được thứ đề cương yêu cầu. Chi phí: khoảng 2–3 buổi làm việc, cộng thời gian GPU
trên Colab/Kaggle. Sản phẩm là một adapter thật trên Hugging Face Hub, kèm số liệu để
đưa vào báo cáo.

**Lựa chọn B — Giữ Groq, ghi rõ đã đổi hướng.**
Hoàn toàn hợp lệ về mặt học thuật, *với điều kiện* báo cáo nêu rõ lý do (giới hạn tài nguyên
GPU miễn phí, ưu tiên tính ổn định của sản phẩm demo) và trình bày phần prompt engineering
+ cơ chế fallback như một đóng góp kỹ thuật có chủ ý.

**Rủi ro lớn nhất là im lặng**: trình bày hệ thống như thể có fine-tune trong khi không có.
Chỉ cần một câu hỏi "cho xem file adapter" là lộ. Chọn A hoặc B, đừng để lửng lơ.

---

## Quy trình cho Lựa chọn A

### Bước 1 — Dựng dataset

```bash
# Dùng dữ liệu thật mà hệ thống đã tích luỹ trong bảng research_reports
python -m training.build_llm_dataset --source supabase

# Nếu database chưa đủ bản ghi, bổ sung mẫu tổng hợp từ dữ liệu giá
python -m training.build_llm_dataset --source both --count 3000
```

Kết quả trong `data/llm_dataset/`:

| File | Nội dung |
|---|---|
| `train.jsonl` | 80% dữ liệu, định dạng chat messages |
| `validation.jsonl` | 10%, dùng để chọn checkpoint tốt nhất |
| `test.jsonl` | 10%, chỉ chạm vào ở bước đánh giá cuối |
| `review_sample.md` | 50 mẫu để bạn đọc và chấm bằng tay |
| `dataset_info.json` | Metadata để trích vào báo cáo |

**Đừng bỏ qua bước review thủ công.** Checklist yêu cầu nó, và con số
"đã review 50/3000 mẫu, 46 đạt" là một dòng cụ thể đưa được vào báo cáo.

### Bước 2 — Fine-tune trên Colab hoặc Kaggle

```python
!git clone <repo-cua-ban>
%cd ForecastAI
!pip install -q transformers peft bitsandbytes accelerate trl datasets

# Qwen2.5-7B — hỗ trợ tiếng Việt tốt hơn, không cần xin quyền truy cập
!python -m training.finetune_qlora --model qwen --epochs 3

# Llama-3.1-8B — cần chấp nhận license và đăng nhập HF trước
!huggingface-cli login
!python -m training.finetune_qlora --model llama --epochs 3
```

Ước lượng thời gian trên T4 với 3.000 mẫu, 3 epoch: khoảng 2–4 giờ mỗi model.
Kaggle phù hợp hơn Colab free vì session không bị ngắt sau 90 phút.

### Bước 3 — Đánh giá và so sánh

Ghi lại cho từng model:

- `eval_loss` cuối cùng (có trong `training_log.json`)
- Tỷ lệ tham số huấn luyện (script in ra lúc bắt đầu)
- Thời gian huấn luyện và loại GPU
- 5–10 output sinh trên tập `test.jsonl`, đọc và chấm tay theo các tiêu chí:
  đúng định dạng, nhận định hợp lý, có nêu disclaimer

Bảng so sánh hai model là thứ hội đồng muốn thấy, không phải một con số loss đơn lẻ.

### Bước 4 — Đưa lên Hugging Face Hub

```bash
python -m training.finetune_qlora --model qwen --push-to-hub ten-cua-ban/forecastai-research
```

File adapter chỉ vài chục MB, upload rất nhanh. Ghi link Hub vào báo cáo.

### Bước 5 — Deploy lên Hugging Face Spaces

Tạo một Space dùng Gradio, load base model + adapter, mở một REST endpoint.
Backend gọi Space đó thay cho Groq. Nếu Space free bị hết quota, xin ZeroGPU.

---

## Cần lưu ý về chất lượng dữ liệu

Các cặp huấn luyện lấy từ output của Groq là **distillation** — model nhỏ học bắt chước
model lớn. Đây là kỹ thuật hợp lệ và phổ biến, nhưng phải nêu rõ trong báo cáo:

- Nhãn do một LLM khác sinh ra, không phải do con người gán
- Chất lượng model học được bị chặn trên bởi chất lượng của model thầy
- Bước review thủ công là biện pháp kiểm soát chất lượng duy nhất trong quy trình này

Các mẫu **tổng hợp** (`--source synthetic`) còn hạn chế hơn: chúng chỉ dùng để kiểm thử
pipeline chạy được. Một model huấn luyện chủ yếu trên đó chỉ học được các mẫu câu do
chính script sinh ra. Đừng trình bày kết quả đó như năng lực phân tích thật.
