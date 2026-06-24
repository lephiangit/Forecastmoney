# FORECAST DETAIL PAGE (UPDATED UX SPECIFICATION)

## Route

/forecast/[ticker]

Ví dụ:

/forecast/BTC

/forecast/AAPL

/forecast/NVDA

---

# 1. HEADER SECTION

Hiển thị thông tin tài sản hiện tại.

Layout:

Ticker Symbol

Asset Name

Current Price

24H Change

Market Cap

Volume

Ví dụ:

BTC

Bitcoin

$107,542

+2.43%

Market Cap: $2.1T

Volume: $48.3B

---

# 2. FORECAST HORIZON SELECTOR

## Previous Design (Deprecated)

❌ Buttons:

3 Days

7 Days

14 Days

30 Days

Lý do:

- Không mở rộng được
- Không hỗ trợ 60 ngày
- Giao diện rối khi thêm nhiều lựa chọn

---

## New Design

✅ Slider Component

Range:

1 → 60 Days

Default:

14 Days

Step:

1 Day

UI Example:

Forecast Horizon

[========●-----------]

14 Days

Behavior:

- Kéo thanh trượt để thay đổi số ngày dự báo
- Hiển thị giá trị hiện tại ngay phía trên slider
- Tự động gọi API mới khi thay đổi

Advantages:

- Không nhập sai dữ liệu
- Không thể nhập chữ
- UX trực quan hơn
- Dễ mở rộng lên 90 hoặc 180 ngày trong tương lai

---

# 3. KPI FORECAST CARDS

Hiển thị ngay dưới Header.

Grid 4 Columns

Card 1

Expected Return

+7.2%

Card 2

Target Price

$118,450

Card 3

Confidence

81%

Card 4

Risk Level

Medium

Color Rules:

Confidence > 80%

Green

Confidence 60-80%

Yellow

Confidence < 60%

Red

---

# 4. CHART 1 — MAIN PRICE & FORECAST CHART

Priority:

Highest

Position:

FIRST chart on page

Purpose:

Hiển thị xu hướng giá lịch sử và dự báo trong cùng một biểu đồ liên tục.

Chart Type:

Line Chart

NOT Candlestick

Reason:

- Dễ đọc hơn cho người dùng phổ thông
- Forecast nối liền tự nhiên với lịch sử
- Trực quan hơn khi AI dự báo tương lai

---

Historical Data

Line:

White

Stroke Width:

2px

Data:

Historical Close Price

---

Forecast Data

Line:

Yellow (#fcd535)

Stroke Width:

3px

Data:

TFT Median Forecast

---

Sentiment Forecast

Optional

Line:

Blue (#3861fb)

Dashed

Data:

Sentiment Fusion Forecast

---

Confidence Band

Area Chart

Upper Bound:

upper_q90

Lower Bound:

lower_q10

Color:

#fcd535

Opacity:

0.1

---

Forecast Separator

Vertical Dashed Line

Label:

Forecast

or

AI Forecast Begins

---

Tooltip

Hover hiển thị:

Date

Historical Price

Forecast Price

Expected Change

Confidence Range

---

Zoom & Pan

Supported

Mouse Wheel

Drag

Reset Zoom Button

---

# 5. CHART 2 — FORECAST CANDLESTICK CHART

Position:

Immediately below Main Chart

Purpose:

Hiển thị chi tiết từng phiên dự báo tăng giảm.

Chart Type:

Forecast Candlestick

---

Historical Candles

Green:

Close >= Open

Color:

#0ecb81

Red:

Close < Open

Color:

#f6465d

---

Forecast Candles

Generated From:

Predicted Open

Predicted High

Predicted Low

Predicted Close

Green:

Forecast Close > Forecast Open

Red:

Forecast Close < Forecast Open

---

Forecast Style

Opacity:

0.6

Border:

Dashed

Purpose:

Người dùng biết đây là dữ liệu AI, không phải dữ liệu thực tế.

---

Tooltip

Date

Predicted Open

Predicted High

Predicted Low

Predicted Close

Forecast Change %

---

# 6. AI RESEARCH SECTION

Position:

Below Charts

Components:

1. Executive Summary

2. Bullish Factors

3. Bearish Factors

4. News Sentiment

5. Recommendation

---

# 7. AI RECOMMENDATION CARD

Recommendation:

BUY

HOLD

SELL

Target Price

Confidence

Time Horizon

Generated Time

---

# 8. RESPONSIVE BEHAVIOR

Desktop:

Charts Full Width

Stack Vertically

Mobile:

Charts Height Reduced

Research Cards Collapse

Slider Full Width

All KPI Cards Become 2x2 Grid
