# ForecastAI V1.2.1 🤖📈

> **AI-powered market research & price forecasting platform**
> Real-time data · TFT + SentimentFusion models · Gemini Research Agent · Paper trading

[![Next.js](https://img.shields.io/badge/Frontend-Next.js_15-black?logo=nextdotjs)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Supabase](https://img.shields.io/badge/Database-Supabase-3ECF8E?logo=supabase)](https://supabase.com)
[![Netlify](https://img.shields.io/badge/Deploy-Netlify-00C7B7?logo=netlify)](https://netlify.com)

---

## Tổng quan

ForecastAI là nền tảng phân tích thị trường tài chính và giao dịch tự động giả lập (Paper Trading) kết hợp:

- 📰 **Research Agent** (Gemini Flash) — phân tích tin tức, đưa ra sentiment score và khuyến nghị.
- 🧠 **TFT** (Temporal Fusion Transformer) — dự báo giá từ 60 ngày OHLCV + 20 technical indicators.
- 🔀 **SentimentFusion** — kết hợp TFT output với signals từ research để tinh chỉnh dự báo.
- 📊 **Paper Trading & Auto-Trade Bot** — Đầu tư ảo thời gian thực, có bot tự động chạy ngầm liên tục 24/7 thực hiện giao dịch dựa trên dự báo AI.

**Triết lý thiết kế:** Dữ liệu giá và forecast **KHÔNG bao giờ lưu vào database** — tất cả đều fetch và tính toán live theo mỗi request, tránh phình to dữ liệu và hỗ trợ bất kỳ mã giao dịch nào. 

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

> ⚠️ **Disclaimer:** ForecastAI chỉ mang tính chất học thuật và tham khảo. Không phải lời khuyên đầu tư tài chính.
