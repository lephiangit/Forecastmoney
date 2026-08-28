# ForecastAI 2.0

> Nền tảng phân tích thị trường và giao dịch mô phỏng, kết hợp mô hình chuỗi thời gian
> với mô hình ngôn ngữ lớn. **Đồ án học thuật — không phải công cụ đầu tư.**

[![Next.js](https://img.shields.io/badge/Frontend-Next.js_16-black?logo=nextdotjs)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Supabase](https://img.shields.io/badge/Database-Supabase-3ECF8E?logo=supabase)](https://supabase.com)
[![Render](https://img.shields.io/badge/Backend-Render-46E3B7?logo=render)](https://render.com)
[![Netlify](https://img.shields.io/badge/Frontend-Netlify-00C7B7?logo=netlify)](https://netlify.com)

---

## ⚠️ Đọc trước nếu bạn đang nâng cấp từ bản 1.x

Bản 2.0 thay đổi cách cấu hình secret và siết quyền truy cập database.
**Hệ thống sẽ không khởi động được** cho tới khi bạn làm theo [`MIGRATION.md`](./MIGRATION.md).

Đó là chủ ý: app được thiết kế để từ chối chạy khi cấu hình production còn kẽ hở,
thay vì âm thầm chạy với secret mặc định như bản trước.

---

## Tổng quan

Hệ thống gồm hai mô hình nối tiếp nhau:

**Model 1 — Dự báo giá.** Temporal Fusion Transformer tự triển khai bằng TensorFlow
(Gated Residual Network + Multi-Head Attention + đầu ra quantile). Đầu vào là 60 phiên
OHLCV cùng 21 chỉ báo kỹ thuật; đầu ra là ba mức p10/p50/p90 cho từng phiên dự báo.

**Model 2 — Tổng hợp tin tức.** Đọc RSS tài chính, phân tích tâm lý thị trường và
sinh nhận định. Hiện dùng Groq API (`llama-3.3-70b-versatile`) qua prompt engineering,
có cơ chế dự phòng bằng chấm điểm từ khoá khi API lỗi hoặc quá hạn mức.

> **Lưu ý về Model 2 dành cho báo cáo đồ án:** đề cương ban đầu yêu cầu fine-tune
> Qwen2.5-7B / Llama-3.1-8B bằng LoRA. Hiện tại **chưa có fine-tune** — đây là gọi API.
> Hạ tầng để thực sự fine-tune đã sẵn sàng trong [`training/`](./training/README.md).
> Bạn cần chọn một trong hai: làm thật, hoặc ghi rõ trong báo cáo là đã đổi hướng
> và giải thích lý do. Đừng để lửng lơ.

Kết quả hai mô hình được hợp nhất qua `SentimentFusion`: dự báo kỹ thuật của TFT được
dịch chuyển theo điểm tâm lý từ tin tức, với mức ảnh hưởng giảm dần theo thời gian.

**Triết lý dữ liệu:** giá và kết quả dự báo **không bao giờ lưu xuống database**.
Mọi thứ được lấy và tính lại theo từng request, có cache TTL ngắn trong bộ nhớ.
Nhờ vậy hệ thống chạy được với bất kỳ mã nào yfinance hỗ trợ, kể cả mã chưa từng
xuất hiện lúc huấn luyện.

---

## Kiến trúc

```
┌──────────────────────────────────────────────────────────────┐
│  Frontend — Next.js 16 (Netlify)                             │
│    Đăng nhập email/mật khẩu  ─┐                              │
│    Đăng nhập Google           ├─→ Bearer token (HMAC-SHA256)  │
│    Thăm dò /health ───────────┘   → dải cảnh báo "dữ liệu mẫu"│
└───────────────────────────┬──────────────────────────────────┘
                            │  CORS: chỉ domain được liệt kê
┌───────────────────────────┴──────────────────────────────────┐
│  Backend — FastAPI (Render)                                   │
│                                                               │
│   security.py    rate limit theo IP · lọc prompt injection    │
│   metrics.py     đo độ trễ / tỷ lệ lỗi / uptime THẬT          │
│   models/        TFT · SentimentFusion · feature engineering  │
│   agents/        Research Agent (Groq + dự phòng từ khoá)     │
│   services/      logic vị thế & lãi lỗ dùng chung             │
│   cron_*.py      auto-trade · nghiên cứu · đánh giá sai số    │
└───────────────────────────┬──────────────────────────────────┘
                            │  service_role key (bỏ qua RLS)
┌───────────────────────────┴──────────────────────────────────┐
│  Supabase PostgreSQL — RLS BẬT trên toàn bộ 13 bảng           │
│  anon/authenticated bị thu hồi toàn bộ quyền trên bảng        │
└───────────────────────────────────────────────────────────────┘
```

---

## Cấu trúc thư mục

| Đường dẫn | Nội dung |
|---|---|
| `backend/main.py` | Điểm vào FastAPI, middleware, job nền, WebSocket giá |
| `backend/config.py` | Cấu hình tập trung + cổng chặn cấu hình production không an toàn |
| `backend/security.py` | Rate limiter, làm sạch input, xác thực cron, ẩn lỗi |
| `backend/metrics.py` | Đo số liệu vận hành thật (thay cho giá trị ngẫu nhiên ở bản cũ) |
| `backend/models/` | TFT, SentimentFusion, feature engineering, forecast engine |
| `backend/agents/` | Research Agent — lấy tin, phân tích tâm lý bằng LLM |
| `backend/services/` | Logic nghiệp vụ dùng chung giữa router và job nền |
| `backend/routers/` | Các endpoint API |
| `backend/train_tft.py` | Huấn luyện TFT (chia tập theo thời gian) |
| `backend/evaluate_tft.py` | **So sánh TFT với baseline — số liệu cho báo cáo** |
| `training/` | Hạ tầng fine-tune LoRA cho Model 2 |
| `supabase/schema.sql` | Schema + RLS. An toàn để chạy trên DB đang có dữ liệu |
| `frontend/src/` | Ứng dụng Next.js |

---

## Cài đặt

**Yêu cầu:** Python 3.11+, Node.js 20+

### Backend

```bash
cp backend/.env.example backend/.env
# Điền các giá trị vào backend/.env — xem phần "Biến môi trường" bên dưới

pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

Kiểm tra: `curl http://localhost:8000/health`

### Frontend

```bash
cd frontend
npm install

cat > .env.local <<EOF
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key>
EOF

npm run dev
```

### Database

Mở Supabase → SQL Editor → chạy toàn bộ `supabase/schema.sql`.
File này dùng `CREATE TABLE IF NOT EXISTS` nên an toàn với dữ liệu đang có.

---

## Biến môi trường

| Biến | Bắt buộc | Ghi chú |
|---|---|---|
| `ENVIRONMENT` | ✓ | `development` hoặc `production` |
| `SUPABASE_URL` | ✓ | |
| `SUPABASE_KEY` | ✓ | **service_role** key, không phải anon key |
| `GROQ_API_KEY` | ✓ | Thiếu thì hệ thống rơi về chấm điểm từ khoá |
| `ADMIN_SECRET_KEY` | ✓ | Ký token đăng nhập. Tối thiểu 32 ký tự |
| `CRON_SECRET_KEY` | ✓ | Xác thực job nền. **Phải khác** `ADMIN_SECRET_KEY` |
| `ALLOWED_ORIGINS` | ✓ | Danh sách domain, phân tách bằng dấu phẩy. Không dùng `*` |
| `RATE_LIMIT_*` | | Có giá trị mặc định hợp lý |

Sinh secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Ở `ENVIRONMENT=production`, app **từ chối khởi động** nếu secret còn để mặc định,
hai secret trùng nhau, hoặc `ALLOWED_ORIGINS` vẫn là `*`.

---

## Huấn luyện và đánh giá mô hình

```bash
# Huấn luyện (nên chạy trên Colab/Kaggle với GPU)
python -m backend.train_tft --fresh

# Đánh giá — đây là bước sinh số liệu cho báo cáo đồ án
python -m backend.evaluate_tft
```

`evaluate_tft.py` so sánh TFT với bốn baseline (naive, MA5, MA20, ngoại suy xu hướng)
trên MAE, RMSE, MAPE, **độ chính xác về hướng** và **độ phủ của dải tin cậy p10–p90**.
Kết quả ghi ra `models/evaluation_report.md`, dán thẳng vào báo cáo được.

> **Cách chia dữ liệu:** tách theo thời gian cho từng mã (85% đầu để huấn luyện,
> 15% cuối để kiểm thử, cách nhau 60 phiên). Bản trước trộn ngẫu nhiên rồi dùng
> `validation_split`, khiến tập validation chồng lấn với tập train — mọi chỉ số
> đo được từ checkpoint cũ đều không dùng cho báo cáo được.

> **Chuẩn bị tinh thần:** TFT có thể **không** đánh bại được naive forecast.
> Đó là kết quả rất thường gặp với chuỗi giá tài chính, phù hợp với giả thuyết
> thị trường hiệu quả dạng yếu, và hoàn toàn có thể trình bày trong báo cáo —
> miễn là bạn giải thích được và chuyển trọng tâm sang độ chính xác về hướng.

---

## Xác thực

Một loại token duy nhất cho mọi cách đăng nhập: HMAC-SHA256 tự ký, hạn 7 ngày,
lưu ở `localStorage` dưới key `forecast_ai_token`.

Mật khẩu băm bằng PBKDF2-SHA256, 200.000 vòng, **salt ngẫu nhiên riêng từng người dùng**.
Hash theo định dạng cũ vẫn đăng nhập được và tự động nâng cấp sau lần đăng nhập
thành công đầu tiên — nên đổi `ADMIN_SECRET_KEY` không còn khoá tài khoản của ai
như ở bản 1.x.

---

## Job nền

Ba job chạy theo chu kỳ ngay trong tiến trình web, và cũng có thể kích hoạt từ bên ngoài:

```bash
curl -X POST https://<api>/admin/trigger-research \
     -H "X-Cron-Secret: <CRON_SECRET_KEY>"
```

| Job | Chu kỳ | Việc làm |
|---|---|---|
| `cron_auto_trader` | 60 giây | Cắt lỗ/chốt lời, rồi vào lệnh mới theo chiến lược |
| `cron_researcher` | thủ công / cron ngoài | Lấy tin, phân tích tâm lý, lưu báo cáo |
| `cron_accuracy_learner` | thủ công / cron ngoài | Đối chiếu dự báo cũ với giá thật, fine-tune nhẹ |

Job fine-tune có cổng kiểm chứng: mô hình mới phải không tệ hơn quá 5% trên tập
giữ lại thì mới được ghi đè, và bản cũ luôn được sao lưu trước.

---

## Bảo mật

| Lớp bảo vệ | Cách triển khai |
|---|---|
| Truy cập database | RLS bật trên toàn bộ bảng; `anon` bị thu hồi mọi quyền |
| Rate limiting | Sliding window theo IP: auth 10/phút, endpoint nặng 20/phút, còn lại 120/phút |
| Quản lý secret | `ADMIN_SECRET_KEY` và `CRON_SECRET_KEY` tách biệt; chặn khởi động nếu chưa cấu hình |
| Xác thực cron | Header `X-Cron-Secret`, so sánh chống timing attack |
| CORS | Danh sách domain cụ thể; `*` bị chặn ở production |
| Prompt injection | Làm sạch cả input người dùng lẫn tiêu đề tin RSS |
| Open redirect | Trường `href` do LLM trả về được kiểm tra theo mẫu cho phép |
| Rò rỉ lỗi | Ba exception handler toàn cục; stack trace chỉ vào log server |
| Bề mặt API | `/docs` tự tắt ở production |

---

## Tài sản hỗ trợ

Bất kỳ mã nào Yahoo Finance hỗ trợ — crypto, cổ phiếu Mỹ, cổ phiếu Việt Nam (`.VN`),
ETF, chỉ số (`^GSPC`), hàng hoá (`GC=F`). Watchlist mặc định gồm các mã crypto phổ biến
và một số mã VN30.

---

## Giới hạn đã biết

Nêu rõ ở đây để không phải phát hiện chúng giữa buổi bảo vệ:

- **Gói free của Render ngủ sau 15 phút không có truy cập.** Request đầu tiên mất
  30–60 giây. Giao diện có báo trước điều này, nhưng khi demo nên gọi thử API sớm.
- **Số liệu vận hành reset mỗi lần khởi động lại.** Chúng nằm trong RAM tiến trình.
- **Rate limiter là in-memory.** Đủ cho một web service đơn lẻ; scale nhiều instance
  thì cần Redis.
- **Dự báo nhiều bước dùng phiên giả lập.** Với phiên chưa xảy ra, hệ thống dùng
  chính giá dự báo cho cả Open/High/Low, nên các chỉ báo dựa trên biên độ (ATR,
  Bollinger) bị phẳng dần ở các bước xa. Horizon giới hạn ở 30 phiên vì lý do này.
- **`SentimentFusion` chưa được huấn luyện.** Kiến trúc mạng đã có nhưng không có
  checkpoint, nên thực tế luôn chạy nhánh điều chỉnh theo quy tắc. Cần nói rõ điều
  này trong báo cáo thay vì gọi nó là "mô hình fusion đã học".
- **Lịch giao dịch là xấp xỉ.** Đã bỏ cuối tuần cho cổ phiếu, nhưng chưa loại ngày
  nghỉ lễ của từng sàn.

---

## Tài liệu liên quan

- [`MIGRATION.md`](./MIGRATION.md) — các bước bắt buộc khi nâng cấp lên 2.0
- [`training/README.md`](./training/README.md) — hạ tầng fine-tune Model 2
- [`checklist-do-an-forecast-ai.md`](./checklist-do-an-forecast-ai.md) — tiến độ đồ án

---

> **Miễn trừ trách nhiệm:** ForecastAI là đồ án học thuật. Mọi dự báo do mô hình AI
> sinh ra và có thể sai. Toàn bộ giao dịch là mô phỏng, không dùng tiền thật.
> Nội dung trong hệ thống không phải lời khuyên đầu tư, tài chính hay pháp lý.
