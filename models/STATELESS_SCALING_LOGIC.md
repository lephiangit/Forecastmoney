# Cơ Chế Stateless Scaling & Global Model

Tài liệu này giải thích cách mô hình **TFT (Temporal Fusion Transformer)** trong ForecastAI V2 có thể dự báo được cho **bất kỳ mã chứng khoán/crypto nào**, kể cả những mã chưa từng xuất hiện trong tập dữ liệu training.

---

## 1. Vấn đề của mô hình dự báo truyền thống
Nếu đưa trực tiếp giá trị thật của Bitcoin (60,000$) và Cardano (0.4$) vào cùng một mạng Neural để train, model sẽ bị "loạn" vì trọng số (weights) không thể tương thích với các biên độ giá lệch nhau quá lớn.

Các mô hình truyền thống (như ForecastAI V1) thường giải quyết bằng cách:
- Train **riêng biệt** mỗi mã 1 model (nhược điểm: tốn tài nguyên, không có tính tổng quát).
- Dùng Scaler ép về `[0, 1]`, sau đó lưu file `scaler_BTC.pkl`, `scaler_ADA.pkl`. (nhược điểm: Khi hệ thống có 1000 mã, bạn phải lưu 1000 file `.pkl` và load lên RAM cực kỳ nặng nề).

---

## 2. Giải pháp trong V2: "Stateless Scaling"
Để biến TFT thành một **Global Model** (Một model dự báo mọi thứ) và **Stateless** (Không phụ thuộc vào file `.pkl` ở backend), chúng ta áp dụng cơ chế sau:

### A. Quá trình Training (Dạy AI hiểu "Mô thức")
Trong file `backend/train_tft.py` (hoặc `kaggle/train_kaggle_standalone.py`):
```python
# Scale per-ticker (important: each asset has different price range)
scaler = MinMaxScaler(feature_range=(0, 1))
scaled_data = scaler.fit_transform(df_clean[all_cols].values)
```
- Khi đọc file `BTC.csv`, hệ thống dùng `MinMaxScaler` ép giá BTC (50k-70k) về khoảng `0-1`.
- Khi đọc file `ADA.csv`, hệ thống dùng một `MinMaxScaler` khác ép giá ADA (0.3-1.0) về khoảng `0-1`.
- Tất cả ma trận `[0-1]` này được đổ chung vào một "Nồi lẩu" `global_tft.keras`.
=> **Kết quả:** AI hoàn toàn **không biết** giá trị thực của tài sản. Nó chỉ học các **mô thức hình học** (Pattern): *"Khi giá giảm từ 0.8 xuống 0.2, kết hợp RSI dưới 30, nến tiếp theo thường nảy lên 0.25"*.

### B. Quá trình Dự báo (Stateless Inference trên mã lạ)
Khi người dùng gõ một mã mới toanh chưa từng train (vd: `TSLA`) trên web, file `backend/models/forecaster.py` sẽ làm như sau:

1. **Fetch Live:** Kéo 60 ngày giá lịch sử của `TSLA` từ Yahoo Finance về.
2. **Fit On-The-Fly:** (Dòng code quan trọng)
   ```python
   def _fit_scaler_on_the_fly(data: np.ndarray):
       scaler = MinMaxScaler(feature_range=(0, 1))
       scaler.fit(data)
       return scaler
   ```
   Backend tự động tạo một cái thước đo (`MinMaxScaler`) mới tinh ngay tại thời điểm đó, tính toán min/max của TSLA trong 60 ngày đó, và ép về `[0, 1]`.
3. **Inference:** Ném mảng `[0, 1]` này vào model `global_tft.keras`. Model nhận ra pattern quen thuộc, trả về dự báo `0.25` cho ngày mai.
4. **Inverse Transform:** Backend dùng lại cái thước đo vừa tạo ở bước 2 để dịch ngược `0.25` về giá trị đô-la thật của Tesla. Sau đó hủy thước đo đó khỏi RAM.

---

## 3. Tinh chỉnh trong tương lai (Dành cho Developer)
Nếu sau này bạn muốn tối ưu thêm độ chính xác của logic này, có thể thử các hướng sau:

1. **Đổi sang `StandardScaler`:** Thay vì dùng `MinMaxScaler` (0-1), có thể dùng `StandardScaler` để ép giá về trung bình `0` và độ lệch chuẩn `1`. Xử lý nhiễu (outliers) tốt hơn.
2. **Dự báo Log Return:** Thay vì cho AI dự báo giá trị tuyệt đối, hãy tính chênh lệch % giữa các ngày (Daily Return hoặc Log Return). Sau đó cho AI dự báo Return, rồi cộng ngược lại vào giá hiện tại. Cách này giúp dự báo giá dài hạn (30-60 ngày) không bị Flatline (đường thẳng).
3. **Cập nhật hàm:** Logic Scaling hiện đang nằm ở 2 hàm:
   - `create_tft_dataset()` trong `train_tft.py`
   - `_fit_scaler_on_the_fly()` và `inverse_close()` trong `backend/models/forecaster.py`
   Hãy đảm bảo nếu sửa ở train thì phải sửa đồng bộ ở forecaster.
