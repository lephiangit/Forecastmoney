# Train TFT Model on Kaggle

Vì quá trình train mô hình TFT trên máy cá nhân có thể mất nhiều thời gian, thư mục này chứa công cụ giúp bạn đưa toàn bộ quá trình training lên **Kaggle** để tận dụng GPU miễn phí.

## Cách thực hiện:

### Bước 1: Tạo Dataset trên Kaggle
1. Đăng nhập vào [Kaggle](https://www.kaggle.com/).
2. Nhấn vào mục **Datasets** -> **New Dataset**.
3. Đặt tên Dataset là `forecastai-data`.
4. Upload toàn bộ các file `.csv` trong thư mục `data/` của dự án lên đây và nhấn Create.

### Bước 2: Tạo Notebook train
1. Nhấn **Create** -> **New Notebook** trên Kaggle.
2. Ở cột bên phải (Notebook options):
   - Bật thẻ **ACCELERATOR** thành **GPU P100** hoặc **GPU T4x2**.
   - Mục **INPUT**, nhấn **Add Data** -> tìm dataset `forecastai-data` bạn vừa tạo và add vào.
3. Tạo một block code (Code cell) mới, mở file `train_kaggle_standalone.py` trong thư mục này, copy toàn bộ nội dung và dán vào cell đó.
4. Bấm Run (nút Play). Mô hình sẽ tự động train và lưu kết quả vào `/kaggle/working/models/`.

### Bước 3: Tải Model về
1. Khi train xong (chạy hết 100 epochs), nhìn vào cột bên phải mục **OUTPUT** -> `/kaggle/working/models/`.
2. Tải toàn bộ các file trong đó về (`global_tft.keras`, `tft_meta.pkl` và các file `scaler_*.pkl`).
3. Bỏ tất cả các file vừa tải về vào thư mục `models/` trên máy của bạn (thư mục gốc của project).
4. Khởi động lại server backend, hệ thống sẽ tự động nhận diện model.
