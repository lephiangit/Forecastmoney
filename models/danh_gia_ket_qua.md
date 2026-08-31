# Đánh giá kết quả mô hình TFT và phân tích nguyên nhân

## 1. Kết quả tổng hợp

| Mô hình | MAPE (%) | Độ chính xác hướng (%) |
|---|---|---|
| TFT (mô hình đề xuất) | 17.34 | 48.9 |
| Naive (giá hôm nay) | 1.72 | — (không xác định do định nghĩa) |
| Trung bình động 5 phiên | 2.62 | 50.7 |
| Trung bình động 20 phiên | 4.86 | 50.2 |
| Ngoại suy xu hướng | 1.93 | 49.1 |

Xét trên toàn bộ MAPE tổng hợp, mô hình TFT không vượt qua được các baseline đơn giản. Tuy nhiên, phân tích sâu hơn theo từng mã cho thấy đây không phải là một thất bại đồng đều, mà bắt nguồn từ một nguyên nhân kỹ thuật cụ thể, có thể định vị và lý giải rõ ràng.

## 2. Phân tích nguyên nhân: lệch phạm vi chuẩn hóa (scaler out-of-range)

Quy trình huấn luyện fit `MinMaxScaler` một lần duy nhất trên 85% dữ liệu đầu (tập train theo thời gian), sau đó áp dụng cố định phạm vi này để chuẩn hóa cả tập kiểm tra (15% cuối). Với các mã có xu hướng tăng giá dài hạn mạnh — đặc biệt là cổ phiếu blue-chip Mỹ có lịch sử giao dịch hàng chục năm — phần lớn giai đoạn kiểm tra có mức giá **vượt xa** mức giá cao nhất mà mô hình từng quan sát lúc huấn luyện. Khi đó, giá trị sau chuẩn hóa bị đẩy ra ngoài khoảng `[0, 1]`, buộc mô hình phải ngoại suy (extrapolate) ra ngoài vùng dữ liệu đã học — điều mà kiến trúc mạng nơ-ron nói chung xử lý rất kém.

Để kiểm chứng giả thuyết này, nhóm tiến hành đo tỷ lệ phần trăm số điểm trong tập kiểm tra có giá vượt quá giá lớn nhất từng thấy lúc huấn luyện (`out_of_range_pct`), rồi đối chiếu với chất lượng dự báo:

| Nhóm | Số mã | out_of_range_pct (TB) | MAPE TFT | MAPE Naive | Coverage p10–p90 | DirAcc |
|---|---|---|---|---|---|---|
| Lệch scale nặng (>50% điểm test vượt max train) | 42 | ~85% | 27.97% | 1.22% | 20.46% | 47.05% |
| Không lệch scale (≤5% điểm vượt) | 39 | ~1% | 10.55% | 2.26% | 55.46% | 51.03% |

Kết quả cho thấy tương quan rõ ràng: nhóm bị lệch scale nặng có MAPE gấp gần 23 lần naive và Coverage của dải tin cậy [p10, p90] chỉ đạt 20% (đáng lẽ phải xấp xỉ 80% nếu mô hình được hiệu chỉnh tốt) — nghĩa là dải dự báo gần như vô nghĩa. Nhóm không bị lệch scale có kết quả tốt hơn đáng kể (Coverage 55%, DirAcc nhỉnh hơn mức đoán ngẫu nhiên 50%), dù vẫn chưa vượt qua naive về MAPE tuyệt đối — điều này phù hợp với đặc tính giá tài chính gần với bước ngẫu nhiên (random walk), một hiện tượng đã được ghi nhận rộng rãi trong tài liệu tài chính định lượng.

Phân theo nhóm tài sản, vấn đề tập trung rõ rệt nhất ở nhóm cổ phiếu Mỹ (US Stock/ETF) — nhóm có lịch sử giá dài nhất và đã qua nhiều lần tách cổ phiếu:

| Nhóm tài sản | Số mã | out_of_range_pct (TB) | MAPE TFT | Coverage | DirAcc |
|---|---|---|---|---|---|
| US Stock/ETF | 59 | 58.2% | 20.86% | 36.6% | 47.7% |
| VN Stock | 25 | 25.3% | 10.06% | 56.4% | 50.4% |
| Crypto | 20 | 4.9% | 16.07% | 51.3% | 50.4% |

Ví dụ điển hình: **AAPL** có khoảng giá lúc huấn luyện `[$0.04 – $55.2]`, trong khi giai đoạn kiểm tra nằm ở khoảng `[$54 – $340]` — gần như toàn bộ (99.9%) điểm kiểm tra vượt ngoài vùng huấn luyện, dẫn đến MAE lên tới 126 USD và Coverage chỉ 6.2%.

## 3. Kết luận

Kết quả MAPE tổng hợp thấp hơn kỳ vọng không phản ánh việc mô hình TFT "không học được gì", mà bắt nguồn từ một hạn chế phương pháp luận cụ thể trong khâu chuẩn hóa dữ liệu: sử dụng bộ chuẩn hóa (scaler) cố định, fit một lần trên dữ liệu quá khứ, cho một mô hình dùng chung (global model) dự đoán **mức giá tuyệt đối** trên tập hợp các tài sản có biên độ và xu hướng tăng trưởng giá rất khác nhau. Đây là một lỗi phổ biến, đã được ghi nhận trong tài liệu học thuật về dự báo chuỗi thời gian phi dừng (non-stationary time series).

## 4. Hướng khắc phục và phát triển

1. **Đổi biến mục tiêu sang tỷ lệ thay đổi giá (return) thay vì mức giá tuyệt đối.** Return luôn dao động trong biên độ ổn định bất kể mức giá tuyệt đối của tài sản, loại bỏ tận gốc vấn đề lệch scale. Đây là cách tiếp cận chuẩn trong tài chính định lượng.
2. **Sử dụng log-price thay vì giá tuyệt đối** làm đầu vào/đầu ra, giúp nén biên độ tăng trưởng theo cấp số nhân về gần tuyến tính.
3. **Áp dụng bộ chuẩn hóa thích nghi (rolling/expanding-window scaler)**, cập nhật định kỳ theo thời gian thay vì fit cố định một lần.
4. **Giới hạn dữ liệu huấn luyện trong N năm gần nhất** đối với các mã có lịch sử giá quá dài, tránh việc mức giá cổ phiếu từ nhiều thập kỷ trước (đã qua nhiều lần tách cổ phiếu) làm sai lệch phạm vi chuẩn hóa.

Những hướng cải tiến này được xác định là công việc tiếp theo của đồ án, nằm ngoài phạm vi thời gian thực hiện hiện tại.
