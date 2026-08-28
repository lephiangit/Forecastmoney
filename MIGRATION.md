# Hướng dẫn nâng cấp lên ForecastAI 2.0

Đợt cập nhật này thay đổi cách cấu hình secret và siết quyền truy cập database.
**Hệ thống sẽ không chạy được nếu bỏ qua các bước dưới đây** — đó là chủ ý:
app được thiết kế để từ chối khởi động khi cấu hình production còn kẽ hở, thay vì
âm thầm chạy với secret mặc định như trước.

Làm theo đúng thứ tự. Toàn bộ quy trình mất khoảng 30 phút.

---

## Bước 0 — Thu hồi các khoá đã lộ (làm ngay, trước mọi thứ khác)

Các khoá sau đang nằm dạng văn bản thuần trong `.env`, `apikey.txt`, `account.txt`
và đã hiển thị qua nhiều kênh. Phải coi chúng là **đã bị lộ** và thay mới toàn bộ:

| Dịch vụ | Nơi thu hồi và tạo khoá mới |
|---|---|
| Supabase | Dashboard → Project Settings → API → Reset cả `anon` và `service_role` |
| Groq | console.groq.com → API Keys → xoá khoá cũ, tạo khoá mới |
| Google Gemini | aistudio.google.com → API Keys (khoá này không còn được dùng, chỉ cần xoá) |
| Finnhub | finnhub.io/dashboard → xoá khoá (không còn được dùng) |

Sau đó kiểm tra xem chúng đã từng bị đẩy lên GitHub chưa:

```bash
git log --all --full-history -- .env apikey.txt account.txt backend/.env
```

Nếu lệnh trên trả về bất kỳ commit nào, khoá đã nằm trong lịch sử Git vĩnh viễn —
việc xoá file ở commit mới **không** gỡ chúng ra. Lúc đó bắt buộc phải thu hồi khoá
(bước trên) và cân nhắc dùng `git filter-repo` để dọn lịch sử.

---

## Bước 1 — Sinh secret mới

```bash
python -c "import secrets; print('ADMIN_SECRET_KEY=' + secrets.token_urlsafe(48))"
python -c "import secrets; print('CRON_SECRET_KEY='  + secrets.token_urlsafe(48))"
```

Hai giá trị này **phải khác nhau**. App sẽ từ chối khởi động nếu chúng trùng.

> **Người dùng có phải đặt lại mật khẩu không?** Không.
> Đổi `ADMIN_SECRET_KEY` sẽ khiến mọi phiên đăng nhập hiện tại hết hiệu lực
> (người dùng phải đăng nhập lại), nhưng **mật khẩu vẫn dùng được bình thường**.
> Ở bản 2.0, salt mật khẩu đã tách khỏi khoá ký token và các hash cũ được
> tự động nâng cấp ngay sau lần đăng nhập thành công đầu tiên.
> Ở bản cũ thì không như vậy — đổi khoá đồng nghĩa khoá luôn tài khoản của mọi người.

---

## Bước 2 — Cập nhật biến môi trường

### Máy cá nhân (`backend/.env`)

```env
ENVIRONMENT=development
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_KEY=<service_role key MỚI>
GROQ_API_KEY=<khoá Groq MỚI>
ADMIN_SECRET_KEY=<giá trị sinh ở bước 1>
CRON_SECRET_KEY=<giá trị sinh ở bước 1, KHÁC cái trên>
ALLOWED_ORIGINS=http://localhost:3000
```

### Render (Dashboard → service → Environment)

Đặt đúng các biến sau. **Không** đưa chúng vào repo:

```
ENVIRONMENT      = production
SUPABASE_URL     = https://<project>.supabase.co
SUPABASE_KEY     = <service_role key MỚI>
GROQ_API_KEY     = <khoá Groq MỚI>
ADMIN_SECRET_KEY = <secret mới>
CRON_SECRET_KEY  = <secret mới, khác>
ALLOWED_ORIGINS  = https://<tên-site>.netlify.app
```

`ALLOWED_ORIGINS` phải là domain cụ thể. Để `*` ở production sẽ khiến app
không khởi động — và đó là hành vi đúng, vì API bật `allow_credentials`.

### Netlify (frontend)

```
NEXT_PUBLIC_API_URL           = https://<backend>.onrender.com
NEXT_PUBLIC_SUPABASE_URL      = https://<project>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY = <anon key MỚI>
```

> ⚠️ Chỉ dùng **anon key** ở frontend. Khoá `service_role` tuyệt đối không được
> xuất hiện trong bất kỳ biến `NEXT_PUBLIC_*` nào — chúng được nhúng thẳng vào
> JavaScript gửi tới trình duyệt của mọi người dùng.

---

## Bước 3 — Chạy schema Supabase

Mở Supabase → SQL Editor → dán toàn bộ nội dung `supabase/schema.sql` → Run.

Script này an toàn với dữ liệu đang có: dùng `CREATE TABLE IF NOT EXISTS`, không
xoá bảng nào. Nó sẽ:

- Tạo 4 bảng còn thiếu mà code đang dùng: `bot_configs`, `user_profiles`,
  `price_alerts`, `notification_reads`
- Thêm các index còn thiếu
- **Thu hồi toàn bộ quyền của `anon` và `authenticated` trên mọi bảng**
- **Bật Row Level Security trên tất cả các bảng**

### Kiểm chứng sau khi chạy

```sql
-- Mọi dòng phải có rls_enabled = true
SELECT tablename, rowsecurity AS rls_enabled
FROM pg_tables WHERE schemaname = 'public'
ORDER BY rowsecurity, tablename;

-- Truy vấn này phải trả về 0 dòng
SELECT grantee, table_name, privilege_type
FROM information_schema.role_table_grants
WHERE table_schema = 'public' AND grantee IN ('anon', 'authenticated');
```

Nếu còn dòng nào ở truy vấn thứ hai, database vẫn đang phơi ra Internet.

---

## Bước 4 — Cập nhật các job cron bên ngoài

Ba endpoint job nền đã đổi từ `GET ...?secret=...` sang `POST` + header.
Nếu bạn đang dùng cron-job.org hoặc dịch vụ tương tự, phải sửa lại cấu hình:

| | Cũ | Mới |
|---|---|---|
| Method | `GET` | `POST` |
| Secret | query param `?secret=` | header `X-Cron-Secret` |
| Dùng secret nào | `ADMIN_SECRET_KEY` | `CRON_SECRET_KEY` |

```bash
curl -X POST https://<backend>.onrender.com/admin/trigger-research \
     -H "X-Cron-Secret: <CRON_SECRET_KEY>"
```

Lý do đổi: query string bị ghi vào access log của Render, vào lịch sử trình duyệt,
và vào header `Referer` khi điều hướng — nghĩa là secret rò rỉ dần theo thời gian.

---

## Bước 5 — Xoá thủ công các file không còn dùng

Tôi không có quyền xoá file trên máy bạn, nên phần này cần bạn tự làm:

```
backend/services/market_data.py      ← code chết: dùng ccxt + finnhub, không nơi nào gọi
apikey.txt                           ← chứa khoá đã lộ, đã có trong .gitignore
account.txt                          ← chứa thông tin đăng nhập, đã có trong .gitignore
models/scaler_*.pkl                  ← scaler cũ, hệ thống nay khớp scaler tại chỗ
backend/routers/__pycache__/superadmin.cpython-311.pyc   ← còn sót từ file đã xoá
```

Ba gói `ccxt`, `finnhub-python`, `google-generativeai` đã được gỡ khỏi
`requirements.txt`. Riêng `ccxt` nặng khoảng 50MB — bỏ nó rút ngắn đáng kể
thời gian build trên Render.

---

## Bước 6 — Huấn luyện lại mô hình TFT

Cách chia tập validation đã thay đổi (từ trộn ngẫu nhiên sang tách theo thời gian).
Checkpoint cũ được huấn luyện dưới điều kiện có rò rỉ dữ liệu, nên **mọi chỉ số
đo từ nó đều không dùng được cho báo cáo**.

```bash
python -m backend.train_tft --fresh
python -m backend.evaluate_tft
```

Bước thứ hai sinh ra `models/evaluation_report.md` — bảng so sánh TFT với
naive forecast và moving average, dán thẳng được vào báo cáo đồ án.

Hãy chuẩn bị tinh thần cho khả năng TFT **không** đánh bại được naive forecast.
Đó là kết quả rất thường gặp với dữ liệu giá tài chính và hoàn toàn có thể
trình bày — miễn là bạn giải thích được vì sao (giả thuyết thị trường hiệu quả
dạng yếu) và chuyển trọng tâm sang độ chính xác về hướng.

---

## Bước 7 — Chạy thử

```bash
# Backend
cd <thư mục dự án>
uvicorn backend.main:app --reload

# Kiểm tra sức khoẻ
curl http://localhost:8000/health

# Frontend
cd frontend && npm run dev
```

### Danh sách kiểm tra

- [ ] `/health` trả về `db_connected: true`
- [ ] Đăng nhập được bằng tài khoản cũ (mật khẩu không đổi)
- [ ] Trang Admin hiển thị số liệu hệ thống **thật** (không còn giá trị nhảy ngẫu nhiên)
- [ ] Tắt backend → giao diện hiện dải cảnh báo vàng "Đang hiển thị dữ liệu mẫu"
- [ ] Bot auto-trade thực sự vào lệnh khi có báo cáo tin tức đủ độ tin cậy
- [ ] `/docs` **không** truy cập được khi `ENVIRONMENT=production`
- [ ] Gọi Supabase REST bằng anon key từ trình duyệt bị từ chối

Kiểm tra cuối cùng — đây là lỗ hổng nghiêm trọng nhất đã được vá:

```bash
# Phải trả về lỗi permission denied, KHÔNG được trả về dữ liệu người dùng
curl "https://<project>.supabase.co/rest/v1/users?select=*" \
     -H "apikey: <anon key>"
```
