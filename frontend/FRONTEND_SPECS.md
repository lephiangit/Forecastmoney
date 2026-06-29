# FORECASTAI FRONTEND SPECIFICATION V3.0

## PROJECT OVERVIEW

ForecastAI là nền tảng AI-Powered Market Intelligence & Paper Trading Platform.

Hệ thống cho phép người dùng:

- Theo dõi thị trường tài chính theo thời gian thực.
- Xem dự báo giá được tạo bởi mô hình AI TFT.
- Đọc báo cáo phân tích do Gemini AI tổng hợp.
- Quản lý danh mục đầu tư mô phỏng.
- Giao dịch thủ công bằng tiền ảo.
- Bật Auto-Trading để AI tự giao dịch.
- Theo dõi hiệu suất mô hình AI.
- Nhận tín hiệu đầu tư được sinh bởi hệ thống AI.

Frontend phải phản ánh đầy đủ sức mạnh của hệ thống backend hiện có thay vì chỉ tập trung vào biểu đồ dự báo.

---

# DESIGN GOALS

UI phải mang cảm giác:

- Bloomberg Terminal
- Binance
- TradingView
- BlackRock Aladdin

Các ưu tiên:

1. Financial Professional
2. AI First
3. Data Rich
4. Fast Navigation
5. Mobile Friendly

---

# TECHNOLOGY STACK

Framework

- Next.js App Router
- TypeScript
- React

Styling

- Tailwind CSS
- Framer Motion

State Management

- Zustand
- React Query

Charts

Primary Chart

- TradingView Lightweight Charts

Secondary Charts

- Recharts

Icons

- Lucide React

---

# GLOBAL COLOR SYSTEM

Background

Primary

#0b0e11

Secondary

#12161c

Cards

#1e2329

Borders

#2b3139

Primary Accent

#fcd535

Positive

#0ecb81

Negative

#f6465d

Information

#3861fb

Text Primary

#ffffff

Text Secondary

#eaecef

Text Muted

#707a8a

---

# LANGUAGE SYSTEM

Supported Languages

- English
- Vietnamese

Global Language Toggle

Navbar Right Side

Behavior

Every label must support i18n.

Examples

Dashboard ↔ Bảng điều khiển

Research ↔ Nghiên cứu

Forecast ↔ Dự báo

Portfolio ↔ Danh mục

Auto Trade ↔ Giao dịch tự động

Admin ↔ Quản trị

---

# AI TRANSLATION SYSTEM

Research Reports support dual language.

Research Viewer

English | Tiếng Việt

Behavior

If Vietnamese version exists:

Show content_vi

If not:

Call translation endpoint

Cache result

Store translated report

Research Table Suggested Fields

content_en

content_vi

translated_at

---

# USER ROLES

USER

Permissions

- Dashboard
- Markets
- Research
- Forecast
- Portfolio
- Paper Trading
- Auto Trade
- Watchlist

ADMIN

Permissions

Everything above plus:

- User Management
- System Monitoring
- Model Accuracy
- Research Queue
- Admin Configuration

---

# GLOBAL LAYOUT

Navbar

↓

Market Ticker

↓

Page Content

↓

Floating AI Copilot

↓

Footer

---

# NAVBAR

Left Section

ForecastAI Logo

Center Section

Dashboard

Markets

Research

Forecast

Portfolio

Auto Trade

Admin (Admin Only)

Right Section

Notification Bell

Language Switch

User Menu

Important

Navigation items and Account items must be visually separated by large spacing.

Do not cluster Login/Register beside navigation links.

---

# GLOBAL MARKET TICKER

Position

Sticky below Navbar

Assets

BTC

ETH

SP500

NASDAQ

DOW

GOLD

OIL

Display Format

[Ticker]

[Price]

[Arrow]

[% Change]

Green if positive

Red if negative

Auto Refresh

30 Seconds

Infinite Scroll

Enabled

---

# FLOATING AI COPILOT

Visible on all pages.

Position

Bottom Right

Capabilities

Forecast BTC

Analyze AAPL

Compare NVDA vs TSLA

Show best signal today

Behavior

Enter

↓

Navigate to related page

↓

Execute AI query

---

# ROUTING STRUCTURE

/

Dashboard

/markets

Market Explorer

/research

Research Center

/research/[ticker]

Research Detail

/forecast

Forecast Explorer

/forecast/[ticker]

Forecast Detail

/portfolio

Portfolio Management

/auto-trade

Auto Trading

/settings

Profile Settings

/admin

Admin Dashboard

/admin/users

User Management

/admin/accuracy

Model Accuracy

/admin/research

Research Queue

/login

/register

---

# DASHBOARD PHILOSOPHY

Dashboard answers:

“How is my account doing today?”

Markets answers:

“What is happening in the market?”

Forecast answers:

“What does AI think will happen?”

Research answers:

“Why does AI think that?”

Portfolio answers:

“What do I currently own?”

Auto Trade answers:

“What is AI trading for me?”

Admin answers:

“How is the system performing?”

---

# GLOBAL UX REQUIREMENTS

All numeric values use count-up animation.

All cards use hover animation.

All charts animate on first render.

All pages support skeleton loading.

All API failures must show dedicated error cards.

All tables must support mobile horizontal scrolling.

All pages must be responsive.

Minimum Desktop Width

1440px optimized

Tablet Support

Required

Mobile Support

Required
