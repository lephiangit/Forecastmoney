# ForecastAI V1.2.5b 🤖📈

**Mới trong bản cập nhật 1.2.5 & 1.2.5b:**
- Nâng cấp **AI Copilot**: Kết nối trực tiếp với LLM Groq ở Backend, hỗ trợ nhận diện và phản hồi tự nhiên bằng Tiếng Việt 100%, có hiệu ứng typing.
- Nâng cấp **AI Research**: Phân tích từ 30 bài báo (thay vì 12 bài) và thêm Biểu đồ Tâm lý AI (Sentiment Gauge) sinh động bằng Recharts.
- Thêm tính năng **Quy đổi tiền tệ toàn cầu (USD/VND)** dựa trên tỷ giá trực tiếp từ Open Exchange Rates API.
- Cập nhật Ticker Tape Navbar để tự động thay đổi định dạng theo thiết lập tiền tệ của người dùng.
- Trả về nội dung Markdown chi tiết cho trung tâm Nghiên cứu AI.


> **AI-powered market research & price forecasting platform**
> Real-time data · TFT + SentimentFusion models · Gemini Research Agent · Paper trading

[![Next.js](https://img.shields.io/badge/Frontend-Next.js_16-black?logo=nextdotjs)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Supabase](https://img.shields.io/badge/Database-Supabase-3ECF8E?logo=supabase)](https://supabase.com)
[![Render](https://img.shields.io/badge/Backend_Deploy-Render-46E3B7?logo=render)](https://render.com)
[![Vercel](https://img.shields.io/badge/Frontend_Deploy-Vercel-000000?logo=vercel)](https://vercel.com)

---

## Tổng quan

ForecastAI là nền tảng phân tích thị trường tài chính và giao dịch tự động giả lập (Paper Trading) kết hợp:

- 📰 **Research Agent** (Gemini Flash) — phân tích tin tức, đưa ra sentiment score và khuyến nghị.
- 🧠 **TFT** (Temporal Fusion Transformer) — dự báo giá từ 60 ngày OHLCV + 20 technical indicators.
- 🔀 **SentimentFusion** — kết hợp TFT output với signals từ research để tinh chỉnh dự báo.
- 📊 **Paper Trading & Auto-Trade Bot** — Đầu tư ảo thời gian thực, có bot tự động chạy ngầm liên tục 24/7 thực hiện giao dịch dựa trên dự báo AI.

**Triết lý thiết kế:** Dữ liệu giá và forecast **KHÔNG bao giờ lưu vào database** — tất cả đều fetch và tính toán live theo mỗi request, tránh phình to dữ liệu và hỗ trợ bất kỳ mã giao dịch nào. 

---

## Kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────────┐
│  Frontend (Next.js 16 / Vercel)                         │
│  ├─ Login (Email/Password)  ──┐                         │
│  ├─ Login (Google OAuth)   ───┤── POST /auth/login      │
│  │     └─ Supabase OAuth      │   POST /auth/google     │
│  │     └─ /auth/callback      │                         │
│  └─ All API calls ───────────→│ Bearer: Custom JWT      │
├─────────────────────────────────────────────────────────┤
│  Backend (FastAPI / Render)                              │
│  ├─ Auth: Custom JWT (HMAC-SHA256, 7-day expiry)        │
│  ├─ Models: TFT, SentimentFusion                        │
│  ├─ Cron: Auto-Trade Bot, Portfolio Snapshots            │
│  └─ Database: Supabase (PostgreSQL)                     │
└─────────────────────────────────────────────────────────┘
```

---

## Xác thực (Authentication)

Hệ thống sử dụng **1 loại token duy nhất** (Custom JWT) cho mọi phương thức đăng nhập:

| Phương thức | Flow |
|---|---|
| **Email/Password** | Frontend gọi `POST /auth/login` → Backend trả Custom JWT |
| **Google OAuth** | Frontend redirect → Supabase OAuth → Callback nhận Supabase token → Frontend gọi `POST /auth/google` → Backend xác minh 1 lần, tạo user nếu chưa có, trả Custom JWT |
| **Đăng ký** | Frontend gọi `POST /auth/register` → Backend tạo user + trả Custom JWT |

Token được lưu trong `localStorage` với key `forecast_ai_token` và tự động gắn vào mọi API request qua header `Authorization: Bearer <token>`.

---

## AI Models

### Model 1: TFT (Temporal Fusion Transformer)
- **Input:** 60 ngày OHLCV + 20 technical indicators (RSI, MACD, Bollinger Bands, ATR, MA...)
- **Output:** Dự báo giá + khoảng tin cậy [P10, P50, P90]
- **Đặc điểm:** Quantile regression, hỗ trợ bất kỳ ticker nào, scaler fit on-the-fly

### Model 2: SentimentFusion
- **Input:** TFT forecast sequence + 5 market signals từ Research Agent
- **Signals:** sentiment_score, confidence, RSI, MACD, BB_position
- **Output:** Giá dự báo được tinh chỉnh theo sentiment tin tức

### Research Agent (Gemini Flash)
- Fetch RSS/Google News cho bất kỳ ticker
- Phân tích sentiment: BULLISH / BEARISH / NEUTRAL + confidence score
- Output: key_factors, recommendation, risk_level, headline list
- Cache: 30 phút trong memory (raw news không lưu DB)

---

## Quickstart

### Yêu cầu
- Python 3.11+
- Node.js 20+

### Backend Setup
```bash
cd backend

# Cài dependencies
pip install -r requirements.txt

# Cấu hình môi trường (Cần GEMINI_API_KEY và thông tin Supabase DB)
cp .env.example .env

# Chạy API server (Tự động kích hoạt luồng bot auto-trade ngầm)
uvicorn backend.main:app --reload --port 8000
```

### Frontend Setup
```bash
cd frontend

npm install

# Setup env URL
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
echo "NEXT_PUBLIC_SUPABASE_URL=<your-supabase-url>" >> .env.local
echo "NEXT_PUBLIC_SUPABASE_ANON_KEY=<your-supabase-anon-key>" >> .env.local

npm run dev
# App chạy tại: http://localhost:3000
```

---

## Tài sản hỗ trợ

**Bất kỳ ticker nào** mà Yahoo Finance hỗ trợ. Mặc định watchlist:

| Crypto | VN Stocks |
|--------|-----------|
| BTC-USD, ETH-USD, BNB-USD, SOL-USD | FPT.VN, VCB.VN, HPG.VN, VIC.VN |
| ADA-USD, XRP-USD, DOGE-USD, AVAX-USD | MWG.VN, SSI.VN, TCB.VN, VHM.VN |

Người dùng có thể thêm bất kỳ mã nào (crypto, cổ phiếu US, VN, ETF...) qua nút **"Thêm tài sản"** trên dashboard.

---

## Deploy

| Service | Platform | Auto-deploy |
|---------|----------|-------------|
| Backend API | Render (Free) | ✅ On `git push` to `main` |
| Frontend | Vercel | ✅ On `git push` to `main` |
| Database | Supabase (Free) | N/A |

---

> ⚠️ **Disclaimer:** ForecastAI chỉ mang tính chất học thuật và tham khảo. Không phải lời khuyên đầu tư tài chính.
