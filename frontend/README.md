# 🚀 ForecastAI Frontend - Hướng dẫn Phát triển & Kết nối

Đây là phần Frontend của dự án **ForecastAI** (Nền tảng AI-Powered Market Intelligence & Paper Trading). Ứng dụng cung cấp bảng điều khiển thời gian thực, biểu đồ dự báo giá bằng AI và công cụ giao dịch mô phỏng.

---

## 🛠️ Công nghệ & Ngôn ngữ sử dụng (Tech Stack)

Frontend được xây dựng bằng các công nghệ hiện đại sau:
*   **Ngôn ngữ chính**: **TypeScript** (đảm bảo an toàn kiểu dữ liệu) kết hợp **React 19** và **Next.js 16 (App Router)**.
*   **Styling (Giao diện)**: **Tailwind CSS v4** và **Framer Motion** cho các hiệu ứng chuyển động mượt mà.
*   **State Management (Quản lý trạng thái)**: **Zustand** (trạng thái toàn cục như Auth, Lang) và **TanStack Query (React Query)** để quản lý dữ liệu cache từ API.
*   **Thư viện Biểu đồ**:
    *   **TradingView Lightweight Charts** (biểu đồ chính hiển thị nến OHLCV + dự báo AI).
    *   **Recharts** (biểu đồ phụ hiển thị biến động PnL tài khoản).
*   **Database Client**: **Supabase JS SDK** hỗ trợ đăng nhập OAuth (Google).

---

## 🔌 Thiết lập kết nối Backend & Database

Kết nối giữa Frontend và hệ thống Backend / Supabase được cấu hình qua các biến môi trường trong file cấu hình cục bộ [.env.local](file:///c:/Users/ann28/Documents/DuAn/ForecastAI/frontend/.env.local).

### 1. File biến môi trường: `.env.local`
Tạo hoặc cập nhật file [.env.local](file:///c:/Users/ann28/Documents/DuAn/ForecastAI/frontend/.env.local) ở thư mục gốc của frontend với nội dung sau:
```env
NEXT_PUBLIC_API_URL=https://forecastai-backend-w81j.onrender.com
NEXT_PUBLIC_SUPABASE_URL=https://xzvminpsnicxqwtnvsxp.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=sb_publishable_rFc46goq-BosUQgramtBPQ_TLxhHi3z
```

### 2. Thiết lập kết nối API (FastAPI Backend)
Toàn bộ các yêu cầu HTTP gọi tới Backend được tập trung quản lý tại file [src/lib/api.ts](file:///c:/Users/ann28/Documents/DuAn/ForecastAI/frontend/src/lib/api.ts):
*   Sử dụng biến `NEXT_PUBLIC_API_URL` làm URL gốc (`BASE_URL`).
*   **Xác thực**: Token JWT tự động được lấy từ `localStorage` dưới khóa `forecast_ai_token` và gắn vào header của mỗi request:
    ```typescript
    const token = localStorage.getItem("forecast_ai_token");
    if (token) headers["Authorization"] = `Bearer ${token}`;
    ```
*   **Xử lý lỗi 401**: Nếu Backend trả về mã lỗi `401 Unauthorized` (Token hết hạn), ứng dụng sẽ tự động xóa token và chuyển hướng người dùng về trang `/login`.

### 3. Thiết lập kết nối Supabase (Google OAuth)
Kết nối trực tiếp đến Supabase phục vụ tính năng đăng nhập bằng Google được thiết lập tại file [src/lib/supabase.ts](file:///c:/Users/ann28/Documents/DuAn/ForecastAI/frontend/src/lib/supabase.ts):
*   Khởi tạo Supabase client sử dụng `NEXT_PUBLIC_SUPABASE_URL` và `NEXT_PUBLIC_SUPABASE_ANON_KEY`.
*   Sử dụng hàm `signInWithGoogle` để kích hoạt luồng OAuth:
    ```typescript
    export const supabase = createClient(supabaseUrl, supabaseAnonKey);
    ```

---

## 💻 Hướng dẫn chạy Locally (Local Development)

Đảm bảo bạn đã cài đặt Node.js phiên bản 20 trở lên.

1.  Di chuyển vào thư mục frontend:
    ```bash
    cd frontend
    ```
2.  Cài đặt các gói phụ thuộc (dependencies):
    ```bash
    npm install
    ```
3.  Chạy ứng dụng ở chế độ phát triển (Development mode):
    ```bash
    npm run dev
    ```
    Truy cập [http://localhost:3000](http://localhost:3000) trên trình duyệt để kiểm tra giao diện.

4.  Xây dựng dự án cho môi trường Production:
    ```bash
    npm run build
    ```

---

## 🚀 Triển khai (Deployment)

Dự án đã được cấu hình sẵn để triển khai tự động:
*   **Netlify**: Tự động build thông qua tệp cấu hình [netlify.toml](file:///c:/Users/ann28/Documents/DuAn/ForecastAI/netlify.toml) đặt ở thư mục gốc của dự án khi có thay đổi trên nhánh `main`.
