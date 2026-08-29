# Chạy demo ForecastAI trên máy cá nhân

File này dành riêng cho việc **chạy thử và demo đồ án**.
Nếu bạn muốn deploy lên Render/Netlify thì đọc [`MIGRATION.md`](./MIGRATION.md) — nặng hơn nhiều.

**Tin tốt:** file `backend/.env` hiện tại của bạn chạy được ngay, không cần sửa dòng nào.
Ở chế độ `development`, các secret đều có giá trị mặc định và cổng chặn cấu hình
production không kích hoạt. Mật khẩu cũ vẫn đăng nhập bình thường.

---

## Chạy trong 3 lệnh

Mở **hai** cửa sổ terminal.

### Terminal 1 — Backend

```bash
cd C:\Users\ann28\Documents\DuAn\ForecastAI
venv\Scripts\activate
uvicorn backend.main:app --reload --port 8000
```

> **Đừng chạy `pip install -r backend/requirements.txt` lúc này.**
> Bản cập nhật không thêm thư viện nào, chỉ **gỡ bớt** (`ccxt`, `finnhub-python`,
> `google-generativeai`) và đổi `tensorflow` thành `tensorflow-cpu`. Nếu cài đè lên
> venv đang có `tensorflow`, hai gói này xung đột với nhau và bạn sẽ mất thời gian gỡ rối
> ngay trước buổi demo. Venv hiện tại đã đủ mọi thứ để chạy.
>
> Chỉ chạy `pip install` khi dựng môi trường mới từ đầu — và khi đó nhớ
> `pip uninstall tensorflow` trước.

Dấu hiệu chạy đúng:

```
ForecastAI API khởi động (environment=development)...
[tft] Đã nạp mô hình vào bộ nhớ.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Kiểm tra nhanh: mở http://localhost:8000/health — phải thấy `"db_connected": true`
và `"tft_loaded": true`.

### Terminal 2 — Frontend

```bash
cd C:\Users\ann28\Documents\DuAn\ForecastAI\frontend
npm run dev
```

Mở http://localhost:3000

> `frontend/.env.local` hiện đang trỏ `NEXT_PUBLIC_API_URL` tới backend trên Render.
> Nếu muốn demo với backend chạy ở máy, sửa dòng đó thành `http://localhost:8000`.
> Để nguyên cũng được — lúc đó bạn đang demo bản đã deploy.

---

## Kịch bản demo (khoảng 8 phút)

Thứ tự này dựng câu chuyện từ dữ liệu → mô hình → sản phẩm, và chèn sẵn
các điểm bạn chủ động nêu hạn chế trước khi hội đồng phải hỏi.

### 1. Đánh giá mô hình — làm TRƯỚC khi mở web (2 phút)

Đây là phần học thuật nhất, và cũng là phần dễ bị hỏi nhất. Chuẩn bị sẵn:

```bash
python -m backend.evaluate_tft --tickers BTC-USD,AAPL,NVDA,FPT.VN --limit 4
```

Mở `models/evaluation_report.md` và chiếu lên. Nói theo mạch:

- "Em so sánh TFT với bốn baseline, trong đó **naive forecast** là baseline khó vượt nhất."
- "Dữ liệu được chia **theo thời gian**, không trộn ngẫu nhiên, nên không có rò rỉ."
- Nếu TFT thua naive: **nói thẳng ra**. "Kết quả này phù hợp với giả thuyết thị trường
  hiệu quả dạng yếu — giá đóng cửa ngắn hạn hành xử gần với bước ngẫu nhiên. Vì vậy em
  chuyển trọng tâm sang **độ chính xác về hướng**, chỉ số liên quan trực tiếp tới tín hiệu
  giao dịch." Trung thực về một kết quả không đẹp gây ấn tượng tốt hơn nhiều so với việc
  giấu nó đi rồi bị phát hiện.
- Chỉ vào dòng **Coverage**: "Dải tin cậy p10–p90 bao phủ X% quan sát thực tế,
  lý tưởng là 80%."

### 2. Dashboard và thị trường (1 phút)

Mở http://localhost:3000 — cho thấy giá real-time qua WebSocket, dải giá chạy ngang.

Nếu muốn khoe phần xử lý lỗi: **tắt terminal backend đi**. Sau khoảng 15 giây, dải
cảnh báo vàng *"Đang hiển thị dữ liệu mẫu"* hiện lên. Nói: "Hệ thống không sập khi
mất backend, nhưng cũng không giả vờ số liệu là thật." Bật backend lại, cảnh báo tự biến mất.

### 3. Dự báo (2 phút)

Vào `/forecast` → chọn một mã → `/forecast/BTC-USD`.

- Chỉ vào disclaimer ở đầu trang: "Trang nào có nội dung dự báo đều có cảnh báo này."
- Biểu đồ nến + dải dự báo p10/p50/p90.
- Nêu chủ động: "TFT dự báo tự hồi quy, sai số tích luỹ theo từng bước, nên em giới hạn
  horizon ở 30 phiên thay vì 60."

### 4. Nghiên cứu tin tức (1,5 phút)

Vào `/research` → chọn một mã.

- Cho thấy sentiment, độ tin cậy, các yếu tố chính, link bài báo gốc.
- Nêu rõ trường `source`: `groq` là do LLM phân tích, `keyword` là cơ chế dự phòng khi
  API quá hạn mức. "Hệ thống không im lặng giả vờ vẫn dùng AI khi thực ra đang đếm từ khoá."

### 5. Bot giao dịch tự động (1,5 phút)

Vào `/auto-trade`.

- Disclaimer ở đây **không đóng được** — cố ý, vì trang này có nút đặt lệnh.
- Giải thích ba tầng chiến lược và ngưỡng độ tin cậy.
- Bật bot, để terminal backend hiện ra bên cạnh: hội đồng thấy log bot quét từng mã
  và giải thích vì sao vào lệnh hoặc bỏ qua.

### 6. Trang quản trị (1 phút)

Vào `/admin` → tab "System monitoring".

Đây là chỗ đáng nói: "Các số liệu này được đo từ chính tiến trình đang chạy —
độ trễ p50/p95, tỷ lệ lỗi, uptime. Bản trước của em sinh chúng bằng `random.uniform()`,
em đã thay bằng đo thật."

---

## Trước buổi demo — kiểm tra 5 phút

- [ ] Backend chạy, `/health` trả `db_connected: true` và `tft_loaded: true`
- [ ] Đăng nhập được (mật khẩu cũ vẫn dùng bình thường)
- [ ] `models/evaluation_report.md` đã sinh và đã đọc qua
- [ ] `frontend/.env.local` trỏ đúng backend bạn định demo
- [ ] Đã thử tắt/bật backend một lần để chắc dải cảnh báo hoạt động
- [ ] Nếu demo bản trên Render: **gọi API trước 2 phút** để đánh thức service
      (gói free ngủ sau 15 phút không truy cập, lần gọi đầu mất 30–60 giây)

---

## Xử lý sự cố

| Hiện tượng | Nguyên nhân và cách xử lý |
|---|---|
| `RuntimeError: Cấu hình production không an toàn` | Biến `ENVIRONMENT` đang là `production`. Xoá dòng đó khỏi `.env` hoặc đổi thành `development` |
| `/health` trả `db_connected: false` | Sai `SUPABASE_URL` / `SUPABASE_KEY`, hoặc dùng nhầm anon key thay vì service_role |
| `tft_loaded: false` | Thiếu `models/global_tft.keras`. Chạy `python -m backend.train_tft` |
| Frontend luôn hiện "Đang hiển thị dữ liệu mẫu" | `NEXT_PUBLIC_API_URL` sai, hoặc backend chưa chạy. Đổi env xong phải **khởi động lại** `npm run dev` |
| Lỗi CORS trên console trình duyệt | Frontend không chạy ở `localhost:3000`. Thêm cổng thật vào `ALLOWED_ORIGINS` |
| Bot không vào lệnh nào | Đúng như thiết kế khi chưa có báo cáo tin tức: độ tin cậy mặc định 50% thấp hơn mọi ngưỡng chiến lược. Chạy `python -m backend.cron_researcher` trước để sinh báo cáo |
| Lỗi khi bấm "đã đọc" một thông báo chung | Bảng `notification_reads` chưa tồn tại. Chạy `supabase/schema.sql` (thông báo cá nhân vẫn hoạt động bình thường) |
| yfinance trả lỗi hoặc rỗng | Bị chặn tạm thời do gọi quá dày. Đợi vài phút; hệ thống đã có cache TTL để hạn chế |

---

## Demo khi không có mạng hoặc database

Vẫn demo được phần giao diện: chỉ chạy frontend (`npm run dev`), không chạy backend.
Ứng dụng sẽ hiển thị dữ liệu mẫu kèm dải cảnh báo vàng — và chính điều đó lại là
một điểm đáng khoe: hệ thống suy giảm chức năng một cách trung thực thay vì sập,
và cũng không lừa người dùng rằng số liệu là thật.
