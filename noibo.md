# Tài liệu Nội bộ: Cấu trúc & Chức năng hệ thống ForecastAI

Tài liệu này giải thích chi tiết mục đích và chức năng của từng file/folder trong dự án ForecastAI. Phục vụ cho việc bàn giao, bảo trì và phát triển tính năng mới. **KHÔNG PUSH LÊN GITHUB**.

---

## 1. Cấu trúc tổng quan

Dự án được chia thành 2 phần chính:
- **`frontend/`**: Ứng dụng web viết bằng Next.js (React), giao diện người dùng trực quan.
- **`backend/`**: Máy chủ API viết bằng FastAPI (Python), chứa toàn bộ logic AI, quét tin tức, dự báo giá và auto-trade.

Ngoài ra còn có các folder phụ trợ:
- **`data/`**: Chứa dữ liệu lịch sử tải về, phục vụ cho AI huấn luyện.
- **`models/`**: Nơi lưu trữ các file mô hình Machine Learning sau khi đã huấn luyện (`.pt`, `.pkl`).
- **`kaggle/`**: Notebook hoặc script chạy trên môi trường Kaggle để train mô hình nặng.

---

## 2. Thư mục `backend/` (Khối Logic & AI)

Đây là "bộ não" của hệ thống, thực hiện các thuật toán học máy, chạy ngầm (cron), thao tác Database Supabase.

### Root của Backend
- **`main.py`**: File khởi chạy server FastAPI. Khai báo các API routes (`/api/...`) và đặc biệt là bộ lên lịch (scheduler) để chạy ngầm các file `cron_*.py` một cách liên tục.
- **`config.py`**: Lưu các cấu hình hệ thống, biến môi trường (như Supabase key, Groq key), và danh sách danh mục Ticker mặc định.
- **`database.py`**: Chứa logic tương tác trực tiếp với Supabase. Toàn bộ các thao tác `select`, `insert`, `update` (VD: lưu báo cáo, lưu PnL, lưu thông tin user) đều nằm ở đây.
- **`cron_researcher.py`**: Script chạy ngầm định kỳ (VD: mỗi 6 tiếng). Nó sẽ duyệt qua tất cả các mã coin/cổ phiếu đang được user quan tâm, tự động thu thập tin tức, phân tích bằng Groq (AI Sentiment), và lưu trữ lại kết quả vào Database.
- **`cron_auto_trader.py`**: Bot Auto-Trade. Script chạy ngầm mỗi 15 phút. Quét tất cả user đang bật bot, lấy dự báo từ AI (tăng hay giảm so với giá hiện tại) rồi thực hiện đặt lệnh MUA hoặc BÁN. Cập nhật lại số dư và PnL.
- **`cron_accuracy_learner.py`**: Script "Fine-Tuning Evaluator". Chạy ngầm định kỳ để lấy giá thực tế so sánh với dự đoán trước đó, tính toán phần trăm sai số, lưu lại làm dữ liệu đánh giá và tự rút kinh nghiệm.
- **`train_tft.py`**: Script dùng để huấn luyện thủ công (train) mô hình AI dự đoán chuỗi thời gian (TFT - Temporal Fusion Transformer).

### `backend/routers/` (API Endpoints)
Khai báo các đường dẫn API cung cấp dữ liệu cho Frontend.
- **`forecast.py`**: Xử lý API `/api/forecast/...`. Gọi mô hình dự báo AI (TFT + SentimentFusion) để tính toán mức giá kỳ vọng T+1 đến T+30.
- **`market.py`**: Xử lý API `/api/market/...`. Kết nối lấy dữ liệu giá Real-time từ các nguồn (như Yahoo Finance), xử lý format OHLCV (nến) và các chỉ số kỹ thuật (RSI, MACD) trả về biểu đồ.
- **`research.py`**: Xử lý API `/api/research/...`. Trả về báo cáo tin tức và chỉ số tâm lý thị trường (Sentiment) đã được lưu trong DB bởi `cron_researcher`. Cung cấp kho lưu trữ (Archive) và tìm kiếm AI.
- **`system.py`**: Cung cấp API quản trị (Admin). Quản lý cấu hình, người dùng, cập nhật trạng thái bật/tắt Auto-Trade. Cung cấp API lịch sử giao dịch và điểm đánh giá sai số mô hình (Fine-Tuning Accuracy).
- **`auth.py`**: API cho việc đăng nhập/đăng ký user.

### `backend/models/` (AI & Data Science)
Chứa nhân (core) của thuật toán học máy.
- **`forecaster.py`**: File trung tâm của model AI. Cung cấp hàm `run_combined_forecast()` để hợp nhất kết quả từ phân tích kỹ thuật (TFT) và tâm lý thị trường (SentimentFusion).
- **`feature_engineering.py`**: Tập hợp các hàm xử lý dữ liệu đầu vào. Biến đổi dữ liệu thô thành các chỉ số (Technical Indicators) như RSI, MACD, Bollinger Bands để đút vào cho mô hình AI học.
- **`tft_model.py`**: Định nghĩa cấu trúc Neural Network cho mô hình Temporal Fusion Transformer (mô hình dự báo chuỗi thời gian chuyên sâu).
- **`sentiment_fusion.py`**: Mô hình nhỏ thứ hai. Nhận vào kết quả dự báo thô của TFT, và nhúng (fuse) thêm chỉ số rủi ro/lạc quan từ tin tức vào, làm mượt lại con số dự báo cuối cùng.

### `backend/agents/` (AI Agents)
- **`research_agent.py`**: Đặc vụ AI (Sử dụng LLM - Groq). Lấy tin tức -> Prompt đưa cho Groq -> Trả về JSON chứa Sentiment (BULLISH/BEARISH/NEUTRAL), độ tự tin và tóm tắt ngắn.

### `backend/services/` (Tích hợp nguồn dữ liệu)
- **`news.py`**: Module quét và cào dữ liệu RSS tin tức từ các báo đài (CoinTelegraph, VNExpress) để cung cấp cho `research_agent`.

---

## 3. Thư mục `frontend/` (Giao diện Web)

Thư mục này chạy dự án Next.js (React) kết hợp Tailwind CSS.

### `frontend/src/app/` (Hệ thống Trang - Routing)
Mỗi folder trong này tương ứng với 1 URL trên web.
- **`page.tsx`**: Trang Dashboard tổng quan. Hiện biểu đồ PnL, danh sách Watchlist, tóm tắt lệnh Auto-trade.
- **`markets/page.tsx`**: Trang Khám phá Thị trường. Liệt kê các danh mục tiền mã hóa, cổ phiếu, cho phép thêm vào yêu thích.
- **`forecast/page.tsx`**: Trang Dự báo AI tổng quan.
- **`forecast/[ticker]/page.tsx`**: Chi tiết dự báo của 1 mã cụ thể. Hiển thị biểu đồ nến có dải Band dự báo, chỉ số RSI/MACD.
- **`research/page.tsx`**: Trang Trung tâm Nghiên cứu. Hiện danh sách các tin tức được phân tích tâm lý bởi Groq.
- **`research/history/page.tsx`**: Trang Archive để lục tìm các phân tích quá khứ theo bộ lọc (Ticker, Sentiment).
- **`auto-trade/page.tsx`**: Trang cấu hình Bot Giao dịch tự động. Cài đặt vốn, mức Stop-Loss, Take-Profit, và bật tắt Bot.
- **`admin/system/page.tsx`**: Trang dành riêng cho Admin để xem tổng thể hệ thống, logs lỗi, danh sách user, quản lý Auto-Trade và Đánh giá sai số Model (Model Accuracy).
- **`settings/page.tsx`**: Cài đặt cá nhân user (Đổi ngôn ngữ Tiếng Anh/Tiếng Việt, Theme Sáng/Tối).
- **`auth/page.tsx`**: Giao diện đăng nhập/đăng ký.

### `frontend/src/components/` (UI Components dùng chung)
- **`layout/`**: `sidebar.tsx` (Menu trái), `header.tsx` (Thanh trên cùng), `market-ticker.tsx` (Thanh giá chạy ngang màn hình).
- **`ui/`**: Các component nhỏ bé, tái sử dụng cao. Ví dụ `stat-card.tsx` (Hiển thị số tiền to), `sparkline.tsx` (Biểu đồ mini), `tags.tsx` (Các badge màu xanh đỏ).
- **`charts/`**: Các biểu đồ phức tạp.
  - `chart-advanced.tsx`: Biểu đồ nến kết hợp (OHLCV + Dự báo). Sử dụng thư viện Lightweight-Charts.
  - `chart-portfolio.tsx`: Biểu đồ PnL (Lợi nhuận) của tài khoản.

### `frontend/src/lib/` (Công cụ, State, Kết nối Backend)
- **`api.ts`**: Cực kỳ quan trọng. Gom toàn bộ hàm dùng để gọi lên Backend (vd `api.getMarkets()`, `api.startBot()`). Nó giúp code trong trang gọn gàng hơn vì chỉ việc gọi hàm từ `api.ts`.
- **`store.ts`**: Hệ thống quản lý State toàn cầu (sử dụng Zustand). Lưu trạng thái Đăng nhập (`useAuthStore`), ngôn ngữ (`useLangStore`), cài đặt giao diện.
- **`i18n.ts`**: Từ điển dịch thuật (Vietnamese / English).
- **`types.ts`**: Định nghĩa khuôn mẫu dữ liệu (Interfaces/Types) cho TypeScript. Đảm bảo Frontend luôn truyền và nhận đúng kiểu biến từ Backend (VD: `MarketAsset`, `Forecast`).
- **`format.ts`**: Hàm format tiền tệ (thêm dấu phẩy, ký hiệu $ hoặc VNĐ), format % tỷ lệ, format ngày tháng.

---

## 4. Các file Root quan trọng khác
- **`fetch_100_tickers.py`**: Script tải dữ liệu hàng loạt từ Yahoo Finance về thư mục `data/` để làm data huấn luyện cho mô hình TFT.
- **`run_learner.bat`**: File batch chạy trên Windows giúp kích hoạt quá trình huấn luyện nhanh.
- **`render.yaml`**: Cấu hình tự động triển khai (CI/CD) cho nền tảng Render.com (cung cấp info về Web Service, Background Worker, môi trường Python/Nodejs).
- **`netlify.toml`**: Cấu hình tự động triển khai (CI/CD) cho nền tảng Netlify (chuyên cho Frontend Next.js).

---
*Tài liệu được tạo tự động bởi AI Copilot. Lưu ý cập nhật tài liệu nếu có thay đổi cấu trúc lớn trong tương lai.*
