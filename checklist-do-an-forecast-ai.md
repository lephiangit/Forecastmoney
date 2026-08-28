# Checklist đồ án: Hệ thống Forecast Tài chính AI (TFT + LLM Research)

## Tổng quan hệ thống
- **Model 1 – Forecast:** Temporal Fusion Transformer (TFT) dự báo giá/chỉ số tài chính, horizon ngắn hạn
- **Model 2 – Research/Tổng hợp:** LLM fine-tune (LoRA/QLoRA) đọc tin tức + kết quả TFT → tổng hợp insight cho người dùng
- **Deploy:** Web (Render/Vercel free) + LLM inference (Hugging Face Spaces free)

---

## 🔎 Đánh giá thực tế so với checklist — 28/08/2026

Đã đọc toàn bộ code (`backend/`, `frontend/`, `data/`, `models/`, `supabase/schema.sql`, các tài liệu `logic.md`, `noibo.md`, `project_audit.md`) và đối chiếu với checklist gốc. Kết luận chung: dự án đã đi **xa hơn nhiều** so với checklist ở phần sản phẩm (có auth, portfolio, auto-trade bot, admin panel, websocket giá real-time, notifications, price alerts...) nhưng lại **lệch mục tiêu cốt lõi của đồ án** ở đúng phần được chấm điểm nhiều nhất — Model 2 (LLM fine-tune). Chi tiết theo từng tháng bên dưới, sau đó là phần nhược điểm/lỗi kỹ thuật cần sửa.

### Tháng 1 — Data pipeline + TFT baseline
- [x] Chọn mã tài sản mục tiêu — thực tế vượt phạm vi: `data/` có ~100 mã (cổ phiếu Mỹ, VN, crypto), không chỉ 1-3 mã như checklist đề xuất. Không sai, nhưng làm tăng độ phức tạp và thời gian train/maintain đáng kể so với dự tính ban đầu.
- [x] Lấy dữ liệu giá miễn phí (yfinance) — đã có, dung lượng `data/` ở mức vài chục MB, không vi phạm giới hạn.
- [x] Feature kỹ thuật (RSI, MACD, Bollinger, ATR, OBV, volatility, MA5/10/20/50...) — implement đầy đủ trong `backend/models/feature_engineering.py`, nhiều hơn yêu cầu gốc.
- [ ] Format theo `TimeSeriesDataSet` của `pytorch-forecasting` — **không dùng thư viện này**. Team tự viết một kiến trúc TFT rút gọn bằng TensorFlow/Keras (`backend/models/tft_model.py`: GRN + Variable Selection + Multi-Head Attention tự code tay). Đây là công sức kỹ thuật thật, nhưng nếu báo cáo đồ án nói "dùng `pytorch-forecasting`" thì cần sửa lại cho khớp với thực tế, hoặc ghi rõ lý do chuyển sang tự triển khai.
- [~] Train trên Colab GPU T4 — thực tế thấy thư mục `kaggle/train_kaggle_standalone.py`, tức train trên Kaggle chứ không phải Colab. Không sai về bản chất, chỉ cần khớp lại tài liệu.
- [ ] Đánh giá baseline MAE/RMSE/MAPE so với naive forecast/moving average — **không tìm thấy** script hay kết quả benchmark nào so sánh với naive forecast. Chỉ có `cron_accuracy_learner.py` log `error_pct` theo từng lần dự báo thực tế, không phải một bộ benchmark có hệ thống. Đây là phần bắt buộc phải bổ sung trước khi viết báo cáo, vì hội đồng chắc chắn sẽ hỏi "so với random walk thì mô hình tốt hơn bao nhiêu %".
- [x] Lưu checkpoint (`models/global_tft.keras`, `tft_meta.pkl`) — có, dùng `ModelCheckpoint` + `EarlyStopping`.

### Tháng 2 — Thu thập + tạo dataset fine-tune LLM
- [ ] **Chưa làm.** Không có bước thu thập/làm sạch tin tức thành dataset huấn luyện, không có cặp (input tin tức + số liệu) → (output insight mẫu), không có file dataset 2.000–10.000 cặp, không có train/val/test split cho LLM. Toàn bộ "research" hiện tại là gọi thẳng Groq API theo thời gian thực (`backend/agents/research_agent.py`) rồi lưu **kết quả** vào bảng `research_reports` — đây là logging kết quả suy luận, không phải dataset để fine-tune.

### Tháng 3 — Fine-tune LoRA/QLoRA
- [ ] **Chưa làm — đây là lệch lớn nhất so với đề cương đồ án.** `backend/requirements.txt` không có `transformers`, `peft`, `bitsandbytes`. Không có script fine-tune, không có checkpoint Qwen2.5-7B hay Llama-3.1-8B nào, không có gì được upload lên Hugging Face Hub. Toàn bộ "Model 2" thực chất là **gọi API Groq đã host sẵn** (`llama-3.3-70b-versatile`) qua prompt engineering (system prompt tiếng Việt/Anh, ép trả JSON). Prompt engineering này làm khá tốt, có fallback bằng keyword-scoring khi Groq lỗi — nhưng về mặt học thuật, nó **không chứng minh được kỹ năng LoRA/QLoRA fine-tuning** mà checklist (và nhiều khả năng là yêu cầu chấm điểm của đồ án) đặt ra. Cần quyết định sớm: (a) thực sự dành thời gian fine-tune LoRA một model nhỏ (kể cả chỉ demo quy mô nhỏ) để có phần "của mình" trình bày, hoặc (b) chủ động ghi rõ trong báo cáo là đã đổi hướng sang "prompt engineering + RAG kết hợp API thương mại" kèm lý do (thời gian, tài nguyên GPU free tier hạn chế) — im lặng bỏ qua bước này là rủi ro cao nhất khi bảo vệ đồ án.

### Tháng 4 — Tích hợp TFT + Model Research
- [x] Có pipeline kết hợp: TFT → `SentimentFusion` điều chỉnh giá theo sentiment (`backend/models/sentiment_fusion.py`, `forecaster.py:run_combined_forecast`).
- [~] "SentimentFusion" có kiến trúc mạng neural đầy đủ (`build_sentiment_fusion_model`) nhưng **chưa từng được huấn luyện** — không tìm thấy file `sentiment_fusion_*d.keras` nào trong `models/`, nên lúc chạy luôn rơi vào nhánh `_rule_based_adjust()` (công thức tuyến tính đơn giản `price × (1 + sentiment_score × max_adj × time_factor)`). Nên ghi rõ trong báo cáo đây là "cơ chế fallback rule-based", không phải "mô hình fusion đã học" — nếu không sẽ bị hỏi khó khi demo.
- [x] Xử lý edge case thiếu tin tức — có, trả về NEUTRAL/confidence thấp khi không có headline.
- [~] Test end-to-end trên case thực tế — có làm (thấy trong `project_audit.md` cũ), nhưng là kiểm tra thủ công liên kết API, chưa phải test tự động.

### Tháng 5 — Xây web + Đánh giá
- [x] Frontend (Next.js, deploy Netlify) + backend (FastAPI, deploy Render free) — hoạt động, có kiến trúc rõ ràng.
- [ ] Deploy LLM fine-tune lên Hugging Face Spaces — không áp dụng, vì không có model tự fine-tune; đang dùng Groq API trực tiếp từ backend.
- [x] Dashboard trực quan: có biểu đồ nến, forecast band, portfolio P&L (Lightweight-Charts, Recharts).
- [ ] Feature importance / attention của TFT — **kiến trúc có** (`VariableSelectionNetwork` trả về trọng số biến), nhưng **không có endpoint hay UI nào hiển thị** trọng số này. Đây là điểm cộng học thuật dễ lấy nếu bổ sung (chỉ cần expose thêm output phụ).
- [ ] Đánh giá định lượng MAE/RMSE (TFT) một cách bài bản + BLEU/ROUGE hoặc human eval cho phần LLM — chưa có (phụ thuộc luôn vào việc có fine-tune LLM thật hay không ở Tháng 3).
- [x] Disclaimer — có ở footer: "Paper trading only. Not financial advice." (nên cân nhắc làm nổi bật hơn, ví dụ thêm banner ở các trang `/auto-trade`, `/forecast`).

### Tháng 6 — Bảo mật, hoàn thiện, viết báo cáo
- [ ] Rate limiting cho API — **chưa có**, không thấy middleware/thư viện rate-limit nào (`slowapi`, v.v.) trong `requirements.txt` hay `main.py`. Toàn bộ endpoint kể cả `/auth/login`, `/auth/register` không giới hạn số lần thử.
- [~] Secrets management — có `.gitignore` cho `.env`, `apikey.txt`, `account.txt` (tốt), nhưng **nhiều secret thật đang nằm dạng plaintext** trong các file này trên máy và **bị dùng lại/đặt giá trị yếu ở nhiều nơi** — xem mục Bảo mật bên dưới, đây là việc cần xử lý **ngay**, không chỉ để cuối tháng 6.
- [ ] Input validation / chống prompt injection — request tới Groq nhét thẳng `req.message` của user vào prompt mà không giới hạn độ dài hay lọc nội dung (`routers/chat.py`); tin tức RSS cũng được đưa thẳng vào prompt không qua bước làm sạch. Rủi ro prompt injection/leak system prompt qua chat còn mở.
- [~] CORS — có cấu hình qua `ALLOWED_ORIGINS`, nhưng giá trị mặc định trong `config.py` và `.env.example` là `"*"`, kết hợp với `allow_credentials=True` — cấu hình này về nguyên tắc CORS là kết hợp không hợp lệ/không an toàn (`*` + credentials). Cần xác nhận biến môi trường thật trên Render đã được set origin cụ thể chưa; nếu chưa set thì đang chạy với origin mở.
- [ ] Không lộ chi tiết lỗi ra frontend — **chưa đạt**. Rất nhiều endpoint (`auth.py`, `notifications.py`, …) trả thẳng `str(e)` từ exception (bao gồm cả lỗi driver DB) vào response JSON cho client.
- [x] HTTPS — mặc định có sẵn trên Render/Netlify, không cần làm gì thêm.
- [~] Sửa lỗi/tối ưu UI-UX — đã có một vòng audit trước (`project_audit.md`, các mục 1-12 phần lớn đã "Đã Fix"), nhưng vẫn còn các bug mới phát hiện ở lượt audit này (xem bên dưới).
- [ ] Slide + báo cáo với phần "future work" — chưa thấy tài liệu này trong repo (`README.md`, `README_INTERNAL.md` mới dừng ở mô tả kỹ thuật).
- [ ] Buffer thời gian dự phòng — mang tính kế hoạch, không đánh giá qua code được.

---

## 🐞 Lỗi kỹ thuật đã xác minh trong code (ưu tiên xử lý)

**1. Auto-trade bot không bao giờ tự vào lệnh mới (chỉ SL/TP hoạt động).** `cron_auto_trader.py` đọc `confidence` từ `fc.get("research", {}).get("confidence")`, nhưng hàm `run_combined_forecast()` trong `backend/models/forecaster.py` (được gọi trực tiếp từ cron, không qua endpoint `/forecast/combined`) **không có key `"research"` trong dict trả về** — key này chỉ được thêm ở `routers/forecast.py` khi gọi qua HTTP. Kết quả: `confidence` luôn rơi về mặc định `50`, trong khi cả 3 chiến lược (Conservative/Balanced/Aggressive) yêu cầu tối thiểu 60-80% → điều kiện vào lệnh theo dự báo **không bao giờ được thoả**, bot chỉ còn hoạt động ở phần Stop-Loss/Take-Profit khi đã có vị thế sẵn. Đây là tính năng "flagship" của sản phẩm nhưng đang bị hỏng ở một điểm rất nhỏ, dễ fix (tự tính `research_analysis` trong cron trước khi gọi forecast, giống cách `forecast.py` đang làm).

**2. ĐÍNH CHÍNH — nhận định trước của tôi về quantile loss là SAI, nhưng có một lỗi nghiêm trọng hơn ở ngay cạnh.** Ở lượt audit đầu tôi có nói `Y_quantile = np.column_stack([Y, Y, Y])` là lỗi. Không phải. Trong hồi quy quantile, mỗi quantile được học từ chính giá trị thực tế quan sát được thông qua pinball loss bất đối xứng — ba cột giống nhau là hoàn toàn đúng chuẩn. Tôi đã nhầm, và xin đính chính rõ ở đây.

Tuy nhiên, khi rà lại kỹ `train_tft.py` tôi phát hiện một lỗi phương pháp **nghiêm trọng hơn nhiều**: rò rỉ dữ liệu khi chia tập validation. Code cũ trộn ngẫu nhiên toàn bộ mẫu (`np.random.shuffle`) rồi mới gọi `model.fit(..., validation_split=0.1)`. Keras cắt 10% cuối của mảng đã trộn làm tập validation, nên tập này chứa các cửa sổ thời gian **xen kẽ và chồng lấn** với tập train — ví dụ train có cửa sổ ngày 100-160 và 102-162, validation có ngày 101-161. Hệ quả: `val_loss` trông rất đẹp nhưng nó đo khả năng nội suy giữa những ngày mô hình đã thấy, không đo khả năng dự báo tương lai. **Mọi con số MAE/RMSE báo cáo dựa trên checkpoint cũ đều không dùng được.** Đã sửa bằng cách chia theo thời gian cho từng mã (85% đầu để train, 15% cuối để validate, cách nhau 60 phiên), scaler cũng chỉ khớp trên phần train. Cần huấn luyện lại từ đầu (`--fresh`).

**3. Dự báo nhiều ngày (autoregressive) dùng chỉ báo kỹ thuật "đông cứng".** Trong `run_tft_forecast()`, khi lặp dự báo T+2, T+3, ..., chỉ cột `Close` được cập nhật bằng giá dự báo của bước trước; toàn bộ các cột RSI/MACD/Bollinger/ATR... vẫn giữ nguyên giá trị của ngày cuối cùng có dữ liệu thật. Với horizon dài (checklist cho phép tới 30-60 ngày), sai số sẽ tích luỹ nhanh vì mô hình "nhìn" chỉ báo kỹ thuật cũ trong khi giá đã trôi đi nhiều ngày. Cần tính lại chỉ báo theo từng bước lặp, hoặc giới hạn horizon thực tế xuống mức mà sai số này còn chấp nhận được.

**4. "Online learning" không có tác dụng cho tới khi restart server.** `cron_accuracy_learner.online_learning()` load một instance model **riêng** (`tf.keras.models.load_model`), fine-tune 3 epoch rồi ghi đè `models/global_tft.keras`, nhưng model đang phục vụ request thực tế nằm trong biến cache `_model_cache["tft"]` ở `forecaster.py` — biến này **không được refresh** sau khi online learning chạy xong. Vì Render free-tier web service hiếm khi tự restart, tính năng "tự học" gần như không phản ánh vào sản phẩm đang chạy cho tới lần deploy/restart kế tiếp. Ngoài ra online learning không có bước validate trước khi ghi đè model production — nếu batch dữ liệu mới lệch (ví dụ thị trường biến động bất thường), model có thể bị "hỏng" mà không có cách rollback.

**5. `/reports` (trang Research) chỉ hard-code đúng 5 mã** (`BTC-USD, ETH-USD, NVDA, FPT.VN, VCB.VN`) bất kể `cron_researcher.py` đã phân tích bao nhiêu mã khác trong watchlist người dùng — nên trang Research sẽ trông "cụt" so với phần còn lại của sản phẩm hỗ trợ mọi ticker.

**6. Thiếu kiểm tra quyền sở hữu khi đánh dấu đã đọc thông báo.** `POST /notifications/{id}/read` chỉ kiểm tra thông báo có tồn tại, không kiểm tra `user_id` như endpoint `delete` đã làm bên cạnh — một user đăng nhập có thể đánh dấu đã đọc thông báo của người khác (mức độ rủi ro thấp, nhưng là lỗi kiểm soát truy cập (IDOR) nên sửa cho nhất quán).

---

## 🔐 Vấn đề bảo mật cần xử lý ngay (mức độ cao → thấp)

**1. `ADMIN_SECRET_KEY` bị dùng lại cho hai việc khác nhau — rủi ro chiếm quyền admin.** Secret này vừa là khoá ký JWT (`SECRET_KEY` trong `auth.py`, dùng HMAC-SHA256 để ký token đăng nhập), vừa là "mật khẩu" cho 3 endpoint không cần đăng nhập `GET /admin/trigger-learner|trigger-autotrade|trigger-research?secret=...`. Ba endpoint này công khai trong Swagger UI tại `/docs` (không bị tắt ở production) dù comment ghi "Hidden endpoint". Nếu secret này lộ qua log truy cập, lịch sử trình duyệt, hay bất kỳ kênh nào (nó được truyền qua query string!), kẻ tấn công không chỉ trigger được các job nền mà còn **tự ký được JWT giả danh admin** bằng đúng thuật toán trong `auth.py`, dẫn tới toàn quyền trên hệ thống (xoá user, đổi số dư, đổi role...). Nên: tách hai secret ra làm hai biến riêng biệt, đổi cơ chế xác thực cron sang header thay vì query param, và đổi `ADMIN_SECRET_KEY` sang một giá trị ngẫu nhiên mạnh (secrets.token_urlsafe) — giá trị mặc định hiện tại là một chuỗi đoán được để trong code.

**2. Supabase: tắt hoàn toàn RLS và cấp quyền ALL cho `anon`.** `supabase/schema.sql` có `GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres, anon, authenticated, service_role` và không bật Row Level Security trên bảng nào. Vì `SUPABASE_ANON_KEY` (khoá publishable) đang được đưa thẳng vào `frontend/.env.local` để chạy client-side, **bất kỳ ai cũng có thể gọi thẳng Supabase REST API bằng khoá anon này để đọc/sửa/xoá toàn bộ dữ liệu** (bảng `users`, `paper_trades`, `admin_config`...), bỏ qua hoàn toàn backend FastAPI và lớp xác thực JWT tự viết. Đây là lỗ hổng nghiêm trọng nhất trong toàn bộ hệ thống — cần bật RLS + viết policy theo `user_id` cho từng bảng trước khi nộp/đưa lên production thật.

**3. Secret thật đang nằm dạng plaintext ở nhiều nơi và cần luân chuyển (rotate) ngay** vì đã hiển thị qua nhiều kênh (file, chat này): khoá Supabase (cả bản `sb_publishable_...` lẫn `sb_secret_...`), Gemini API key, Groq API key, Finnhub API key, `ADMIN_PASSWORD` và `ADMIN_SECRET_KEY`. Đề xuất: vào Supabase/Groq/Google AI Studio/Finnhub, thu hồi và tạo khoá mới, cập nhật lại trong biến môi trường trên Render/Netlify (không phải trong file trong repo), rồi xoá nội dung nhạy cảm khỏi `apikey.txt`/`account.txt` (hoặc ít nhất đảm bảo chúng chưa từng được `git add` — có thể kiểm tra bằng `git log --all --full-history -- apikey.txt account.txt`).

**4. CORS `*` + `allow_credentials=True`.** Cấu hình mặc định trong `config.py`/`.env.example` không an toàn cho production; cần xác nhận biến `ALLOWED_ORIGINS` trên Render đã trỏ đúng domain Netlify, không phải `*`.

**5. Không có rate limiting** trên `/auth/login`, `/auth/register` — mở đường cho brute-force hoặc tạo tài khoản hàng loạt (spam), đặc biệt khi `/register` không yêu cầu xác minh email.

**6. Lỗi backend bị trả nguyên văn (`str(e)`) cho client** ở nhiều endpoint — nên đổi thành thông điệp lỗi chung chung, log chi tiết ở server.

---

## Ghi chú quan trọng
- **Không cào 500GB-1TB dữ liệu** — rủi ro pháp lý (ToS), không khả thi trên Colab, và không cần thiết cho chất lượng model
- TFT nhẹ → chạy tốt trên Render/Vercel free CPU; LLM nặng → phải tách sang Hugging Face Spaces (hiện đang thay bằng Groq API — cần quyết định rõ hướng đi trước khi viết báo cáo)
- Đây là bản demo/PoC cho đồ án — real-time toàn cầu thật + hạ tầng production để dành cho giai đoạn xin vốn sau này

## ✅ ĐÃ SỬA — đợt cập nhật 28/08/2026

Toàn bộ các hạng mục dưới đây đã được viết lại và ghi thẳng vào thư mục dự án.
Xem `MIGRATION.md` để biết các bước bạn cần tự làm trước khi hệ thống chạy được trở lại.

### Bảo mật

| Vấn đề | Cách xử lý |
|---|---|
| Supabase mở toang cho `anon` | `supabase/schema.sql` viết lại: thu hồi toàn bộ quyền của `anon`/`authenticated`, bật RLS trên 13 bảng. Hai lớp phòng thủ độc lập. |
| `ADMIN_SECRET_KEY` dùng chung cho ký JWT và xác thực cron | Tách thành `ADMIN_SECRET_KEY` và `CRON_SECRET_KEY` riêng biệt |
| Secret cron đi qua query string | Chuyển sang header `X-Cron-Secret`, so sánh bằng `hmac.compare_digest`, đổi `GET` → `POST` |
| Không có rate limiting | Middleware sliding-window theo IP, ba mức hạn mức: auth 10/phút, endpoint tốn tài nguyên 20/phút, còn lại 120/phút |
| CORS `*` + credentials | Mặc định là `localhost:3000`; app **từ chối khởi động** ở production nếu còn `*` |
| Stack trace lọt ra client | Ba exception handler toàn cục; chi tiết chỉ ghi vào log server |
| `/docs` phơi toàn bộ API ở production | Tự động tắt khi `ENVIRONMENT=production` |
| Salt mật khẩu suy ra từ khoá JWT | Salt ngẫu nhiên riêng từng user; hash cũ tự nâng cấp sau lần đăng nhập đầu — **đổi khoá JWT không còn khoá tài khoản người dùng** |
| Không giới hạn độ dài / lọc prompt injection | `sanitize_user_text()` áp dụng cho cả tin nhắn người dùng lẫn tiêu đề RSS |
| **Open redirect qua trường `href` của LLM** (lỗi mới phát hiện) | Server chỉ chấp nhận đường dẫn khớp `^/(forecast\|research)/<mã hợp lệ>$` |
| IDOR khi đánh dấu đã đọc thông báo | Kiểm tra quyền sở hữu; thông báo chung có bảng `notification_reads` riêng theo từng người |
| Admin có thể tự khoá mình khỏi hệ thống | Chặn tự hạ quyền/tự treo/tự xoá, và chặn xoá quản trị viên cuối cùng |
| Tài khoản admin seed sẵn với mật khẩu trong repo | Gỡ khỏi schema, thay bằng hướng dẫn tạo tài khoản an toàn |

### Lỗi logic

| Lỗi | Ảnh hưởng thực tế |
|---|---|
| Bot auto-trade không bao giờ vào lệnh | `confidence` luôn = 50 vì `run_combined_forecast()` không trả khoá `research` khi gọi trực tiếp. Đã sửa; bot nay tự chạy phân tích tin tức trước khi dự báo |
| Tín hiệu tâm lý bị bỏ qua hoàn toàn | Bot truyền `{"sentiment_score": ...}` còn hàm nhận lại đọc `sentiment` + `confidence`. Hai bên không khớp nên sentiment chưa từng có tác dụng |
| `cron_researcher` không đọc được mã của bot | Truy vấn cột `config` không tồn tại (bảng dùng cột `assets`), lỗi bị `except: pass` nuốt mất |
| "Online learning" vô tác dụng | Ghi đè file mô hình nhưng không làm mới cache trong RAM. Nay gọi `reload_tft_model()`, có validate trên tập giữ lại + sao lưu trước khi ghi đè |
| Bộ đếm thắng/thua bị ghi đè | Nhiều lệnh trong cùng lượt chạy dùng chung snapshot cũ. Nay gom vào `_UserSession`, ghi DB một lần |
| Chỉ báo kỹ thuật "đông cứng" khi dự báo dài ngày | Chỉ cột Close được cập nhật, RSI/MACD/BB giữ nguyên của ngày cuối. Nay tính lại toàn bộ chỉ báo ở từng bước |
| Ngày dự báo rơi vào cuối tuần | Cổ phiếu nay dùng ngày làm việc; crypto vẫn chạy đủ 7 ngày |
| Tỷ lệ thắng tính sai | Chia cho tổng số giao dịch (gồm cả lệnh mua đang mở) thay vì số lệnh đã đóng |
| Hai công thức tính vị thế khác nhau | Gộp về `services/portfolio.py`, dùng chung giữa router và bot |
| Trang Admin hiển thị số liệu bịa | `random.uniform()` thay bằng `backend/metrics.py` đo độ trễ, tỷ lệ lỗi, uptime thật |
| `/reports` hard-code 5 mã | Lấy động từ dữ liệu thật |
| yfinance bị gọi dồn dập | Cache TTL dùng chung (giá 30s, OHLCV 15 phút) — trước đó WebSocket gọi 20 mã mỗi 5 giây |

### Đánh giá mô hình

- `backend/evaluate_tft.py` — so sánh TFT với naive forecast, MA5, MA20 và ngoại suy xu hướng. Đo MAE, RMSE, MAPE, **độ chính xác về hướng** và **độ phủ của dải tin cậy p10-p90** (lý tưởng 80%). Xuất ra `models/evaluation_report.md` dán thẳng vào báo cáo được.
- Script tự viết phần nhận xét theo đúng con số đo được — kể cả khi TFT thua naive forecast, kèm cách diễn giải trung thực cho báo cáo.

### Model 2 (LLM)

- `training/build_llm_dataset.py` — dựng dataset instruction-tuning từ chính bảng `research_reports` đã tích luỹ, chia train/val/test, xuất kèm file review thủ công.
- `training/finetune_qlora.py` — script QLoRA 4-bit cho Qwen2.5-7B và Llama-3.1-8B, chạy trên Colab/Kaggle.
- `training/README.md` — nêu rõ hai lựa chọn (làm thật LoRA, hoặc ghi rõ đã đổi hướng) và cảnh báo về giới hạn của dữ liệu distillation.

### Giao diện

- Design tokens nâng cấp: độ tương phản chữ phụ đạt WCAG AA, thêm focus-visible (trước đây không có — người dùng bàn phím không biết mình đang ở đâu), chữ số dạng bảng cho dữ liệu tài chính, tôn trọng `prefers-reduced-motion`.
- **Dải cảnh báo "Đang hiển thị dữ liệu mẫu"** — giải quyết vấn đề nghiêm trọng nhất về UX: trước đây người dùng không có cách nào phân biệt số liệu thật với dữ liệu mẫu khi backend ngủ.
- Disclaimer chuyển từ một dòng chữ nhỏ ở footer thành khối cảnh báo có viền, cộng thêm component đặt được ngay cạnh nội dung dự báo.
- Bộ trạng thái loading/empty/error đầy đủ, có ARIA, kèm ghi chú "lần gọi đầu mất 30-60 giây" cho gói free của Render.
- Bỏ qua điều hướng (skip link) cho người dùng bàn phím.

### Kiểm chứng

- 60 kiểm tra tự động trên các phần logic thuần: rate limiter, lọc prompt injection, chặn open redirect, tính vị thế/giá vốn, chuẩn hoá output LLM, băm mật khẩu và tương thích ngược, token. Tất cả đều đạt.
- Hai lỗi được chính bộ test này phát hiện và đã sửa: mã chỉ số `^GSPC` bị từ chối nhầm, và cách xử lý giá trị confidence vô lý từ LLM.
- Kiểm tra 53 đường dẫn API đăng ký đúng, thứ tự route tĩnh/động chính xác, WebSocket hoạt động, và cổng chặn cấu hình production thực sự chặn.

---

## ⚠️ Việc bạn cần tự làm (xem MIGRATION.md để biết chi tiết)

1. **Thu hồi và tạo mới toàn bộ API key đã lộ** — Supabase, Groq, Gemini, Finnhub. Đây là việc gấp nhất và tôi không làm thay được.
2. **Chạy `supabase/schema.sql`** trên Supabase SQL Editor để bật RLS.
3. **Đặt biến môi trường mới** trên Render và Netlify (`CRON_SECRET_KEY` là biến mới).
4. **Cập nhật job cron bên ngoài** sang `POST` + header `X-Cron-Secret`.
5. **Xoá thủ công** `backend/services/market_data.py`, `apikey.txt`, `account.txt`, `models/scaler_*.pkl` (tôi không có quyền xoá file trên máy bạn).
6. **Huấn luyện lại TFT** bằng `python -m backend.train_tft --fresh` rồi chạy `python -m backend.evaluate_tft` — checkpoint cũ được huấn luyện với dữ liệu bị rò rỉ nên số liệu từ nó không dùng cho báo cáo được.
7. **Quyết định hướng đi cho Model 2** — đây vẫn là rủi ro lớn nhất khi bảo vệ đồ án.
