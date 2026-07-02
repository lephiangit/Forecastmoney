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

- Next.js App Router
- TypeScript
- React
- Tailwind CSS
- Framer Motion
- Zustand (state)
- React Query (data fetching)
- TradingView Lightweight Charts (primary)
- Recharts (secondary)
- Lucide React (icons)

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
