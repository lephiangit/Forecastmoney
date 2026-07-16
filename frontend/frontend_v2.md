# 🚀 FORECASTAI FRONTEND SPECIFICATION V3.1 (FULL SYSTEM)

---

# 🧠 PROJECT OVERVIEW

ForecastAI is an AI-powered financial intelligence and paper trading platform.

It provides:

- Real-time market monitoring (crypto + stocks + macro)
- AI-driven price forecasting (TFT model UI simulation)
- AI research reports (Gemini-style analysis)
- Portfolio tracking (paper trading)
- Auto-trading system (strategy-based)
- Signal-driven execution layer
- Institutional-grade analytics dashboard

This is NOT a simple dashboard. It is a **financial AI trading terminal**.

---

# 🎯 DESIGN GOALS

UI must feel like:

- Bloomberg Terminal
- Binance Pro
- TradingView
- BlackRock Aladdin

Priorities:

1. Institutional-grade density
2. AI-first experience
3. Real-time data feel
4. Fast navigation
5. Mobile + tablet support

---

# 🧱 TECH STACK

- **Language & Framework**: TypeScript, React 19, Next.js 16 (App Router)
- **Styling**: Tailwind CSS v4, Framer Motion
- **State Management**: Zustand (Auth & UI state)
- **Data Fetching**: TanStack Query (React Query)
- **Charts**: TradingView Lightweight Charts (primary), Recharts (secondary)
- **Icons**: Lucide React
- **Supabase**: SDK cho Google OAuth & xác thực người dùng

---

# 🔌 CONNECTION & SETUP

## Environment Variables ([frontend/.env.local](file:///c:/Users/ann28/Documents/DuAn/ForecastAI/frontend/.env.local))
Tạo file `.env.local` ở thư mục root của frontend:
```env
NEXT_PUBLIC_API_URL=https://forecastai-backend-w81j.onrender.com
NEXT_PUBLIC_SUPABASE_URL=https://xzvminpsnicxqwtnvsxp.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=sb_publishable_rFc46goq-BosUQgramtBPQ_TLxhHi3z
```

## API Connection ([frontend/src/lib/api.ts](file:///c:/Users/ann28/Documents/DuAn/ForecastAI/frontend/src/lib/api.ts))
- **Base URL**: Kết nối FastAPI Backend qua `NEXT_PUBLIC_API_URL`.
- **JWT Authorization**: Token được lưu tại `localStorage` với key `forecast_ai_token`, tự động gắn vào Header của mỗi API request:
  ```typescript
  Authorization: Bearer <token>
  ```
- **Session Expiry**: Trả về lỗi 401 từ backend sẽ tự động gọi hàm `logout()` từ Auth Store để xóa token, xóa session và redirect người dùng về `/login?reason=session_expired`.

## Supabase Client ([frontend/src/lib/supabase.ts](file:///c:/Users/ann28/Documents/DuAn/ForecastAI/frontend/src/lib/supabase.ts))
- Khởi tạo client bằng `NEXT_PUBLIC_SUPABASE_URL` và `NEXT_PUBLIC_SUPABASE_ANON_KEY`.
- Phục vụ chức năng đăng nhập bằng tài khoản Google (OAuth) thông qua hàm `signInWithGoogle`.
- Callback chuyển hướng về `/auth/callback` trước khi trích xuất JWT token để gửi tới backend.

## Local State & Authentication ([frontend/src/lib/store.ts](file:///c:/Users/ann28/Documents/DuAn/ForecastAI/frontend/src/lib/store.ts))
- **Zustand middleware persist**: Lưu trạng thái phiên làm việc (session state) xuống `localStorage` để duy trì đăng nhập qua reload trang.
- **`useAuthStore`**:
  - `user`: Thông tin người dùng (`id`, `name`, `email`, `role` là `"user" | "admin"`).
  - `login()`: Nhận profile từ backend/Supabase OAuth, lưu token vào `localStorage` và cập nhật thông tin user.
  - `logout()`: Xóa token JWT khỏi `localStorage` và reset user về `null`.

## Multi-Language & Currency system ([frontend/src/lib/store.ts](file:///c:/Users/ann28/Documents/DuAn/ForecastAI/frontend/src/lib/store.ts) & [i18n.ts](file:///c:/Users/ann28/Documents/DuAn/ForecastAI/frontend/src/lib/i18n.ts))
- **`useLangStore`**: Quản lý ngôn ngữ hiện tại (`"en" | "vi"`). Hàm `useT()` dịch tự động nhãn dựa trên từ điển trong `i18n.ts`.
- **`useCurrencyStore`**: Quản lý đơn vị hiển thị tiền tệ (`"USD" | "VND"`).
  - Exchange rate mặc định: `1 USD = 25,400 VND`.
  - Tích hợp hàm format tiền tệ tự động chuyển đổi tỷ giá khi người dùng toggle đơn vị tiền tệ trên UI.

## Charts Data Binding ([frontend/src/components/charts/](file:///c:/Users/ann28/Documents/DuAn/ForecastAI/frontend/src/components/charts/))
- **TradingView Chart (`chart-advanced.tsx`)**:
  - Gọi API `/forecast/[ticker]` để lấy dữ liệu lịch sử nến và chuỗi dự báo.
  - Ánh xạ mảng dữ liệu lịch sử nến (OHLCV) vào chart series dạng Candlestick.
  - Ánh xạ dải kỳ vọng (P10, P50, P90) thành các đường Line Series nét đứt và vùng Area Series bán trong suốt (Confidence Band).
- **Portfolio Chart (`chart-portfolio.tsx`)**:
  - Gọi API `/admin/portfolio/history` (hoặc `/portfolio/history` đối với user thường).
  - Ánh xạ mảng dữ liệu snapshot tài khoản qua Recharts AreaChart hiển thị tăng trưởng PnL theo thời gian.

---



# 🌈 GLOBAL DESIGN SYSTEM

## Background

- Primary: #0b0e11
- Secondary: #12161c

## Cards

- #1e2329

## Borders

- #2b3139

## Accent Colors

- Yellow: #fcd535
- Green: #0ecb81
- Red: #f6465d
- Blue: #3861fb

## Text

- Primary: #ffffff
- Secondary: #eaecef
- Muted: #707a8a

---

# 🌍 LANGUAGE SYSTEM

Supported:

- English
- Vietnamese

All UI labels must support i18n.

Examples:

- Dashboard ↔ Bảng điều khiển
- Research ↔ Nghiên cứu
- Forecast ↔ Dự báo
- Portfolio ↔ Danh mục
- Auto Trade ↔ Giao dịch tự động

---

# 🧠 AI TRANSLATION SYSTEM

Research reports are dual-language:

Fields:

- content_en
- content_vi
- translated_at

Behavior:

- If VI exists → render it
- Else → call translation API
- Cache translated result

---

# 👤 USER ROLES

## USER

- Dashboard
- Markets
- Research
- Forecast
- Portfolio
- Paper Trading
- Auto Trade
- Watchlist

## ADMIN

Everything above plus:

- User Management
- System Monitoring
- Model Accuracy
- Research Queue
- Admin Config

---

# 🧭 GLOBAL LAYOUT STRUCTURE

Navbar (fixed top)
↓
Market Ticker (sticky)
↓
Page Content
↓
Floating AI Copilot
↓
Footer

---

# 🔝 NAVBAR

Left:

- ForecastAI logo

Center:

- Dashboard
- Markets
- Research
- Forecast
- Portfolio
- Auto Trade
- Admin (role-based)

Right:

- Notifications
- Language switch
- User menu

IMPORTANT:

- Separate navigation vs account UI clearly
- Do NOT cluster login/register with navigation

---

# 📊 GLOBAL MARKET TICKER

Assets:
BTC, ETH, SP500, NASDAQ, DOW, GOLD, OIL

Each item shows:

- Price
- % change
- Arrow direction

Rules:

- Green if positive
- Red if negative
- Auto refresh every 30s
- Infinite scroll horizontal

---

# 🤖 FLOATING AI COPILOT

Always visible bottom-right.

Capabilities:

- forecast BTC
- analyze AAPL
- compare NVDA vs TSLA
- best signal today

Behavior:

- input command
- navigate or open modal
- trigger AI query response

---

# 🧱 ROUTING STRUCTURE

/
Dashboard

/markets
Market Explorer

/research
/research/[ticker]
Research detail

/forecast
/forecast/[ticker]
Forecast detail

/portfolio
Portfolio management

/auto-trade
Auto trading strategies

/settings
/admin
/admin/users
/admin/accuracy
/admin/research
/login
/register

---

# 📊 DASHBOARD PHILOSOPHY

Dashboard answers:
“How is my account doing today?”

Markets:
“What is happening now?”

Forecast:
“What does AI predict?”

Research:
“Why is AI predicting this?”

Portfolio:
“What do I own?”

Auto Trade:
“What is AI trading?”

Admin:
“How is system performing?”

---

# 📈 DASHBOARD LAYOUT

## LEFT

- Market heatmap
- Sector performance
- Macro indicators

## CENTER

- Portfolio PnL
- AI summary
- Risk exposure

## RIGHT

- AI signals feed
- Alerts
- News impact

---

# 📉 FORECAST PAGE

Main chart:

- TradingView Lightweight Chart

Overlays:

- AI forecast curve (dashed)
- Confidence band
- Buy/sell markers
- Support/resistance zones

Side panel:

- Prediction range
- AI reasoning
- Risk score
- Signal strength

---

# 📚 RESEARCH PAGE

Sections:

1. AI Summary (TLDR)
2. Market Impact Score
3. Bull vs Bear case
4. Data charts
5. Dual language toggle (EN/VI)

---

# 💼 PORTFOLIO PAGE

Features:

- Holdings table
- PnL tracking
- Risk heatmap
- Asset allocation chart
- AI sentiment per asset

---

# 🤖 AUTO TRADE PAGE

Strategy cards:

- Momentum
- Mean Reversion
- AI Forecast Strategy
- Volatility Breakout

Each card:

- Win rate
- Sharpe ratio
- Drawdown
- ON/OFF toggle

---

# ⚡ GLOBAL UI RULES

- All numbers animate (count-up)
- Cards have hover lift effect
- Charts animate on load
- Skeleton loading everywhere
- Mobile horizontal scroll tables
- No layout shift allowed

---

# 🎨 COMPONENT SYSTEM

## AI SYSTEM

- AICopilot
- AICommandPanel
- AISignalCard
- AIReasoningPanel

## MARKET SYSTEM

- MarketTicker
- MarketHeatmap
- MarketCard
- TradingViewChart

## PORTFOLIO SYSTEM

- HoldingsTable
- PortfolioSummary
- RiskHeatmap

## FORECAST SYSTEM

- ForecastOverlay
- ConfidenceBand
- SignalMarkers

## UI SYSTEM

- GlassPanel
- AnimatedCard
- CountUpNumber
- LoadingSkeleton

---

# 📱 RESPONSIVE RULES

- Desktop: 1440px optimized
- Tablet: full adaptive layout
- Mobile:
  - stacked panels
  - bottom sheets
  - full-screen charts

---

# 🧠 SYSTEM ARCHITECTURE IDEA

This is not a dashboard.

It is:

> A multi-layer AI financial intelligence terminal

Layers:

1. Market Data Layer
2. AI Intelligence Layer
3. Execution Layer
4. Research Layer

---

# 🚀 FINAL OUTPUT GOAL

A production-grade AI trading terminal UI ready for:

- real-time market APIs
- AI forecasting models
- paper trading engine
- institutional analytics system
