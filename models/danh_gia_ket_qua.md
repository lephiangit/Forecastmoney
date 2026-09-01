# Đánh giá kết quả mô hình TFT: trước và sau khi khắc phục lỗi chuẩn hóa

*Cập nhật: 01/09/2026*

## 1. Tóm tắt

Bản đánh giá đầu tiên của mô hình TFT (28/08/2026) phát hiện MAPE tổng hợp cao bất thường (17.34%, gấp ~10 lần naive) và độ chính xác hướng dưới mức đoán ngẫu nhiên (48.9%). Phân tích sâu cho thấy nguyên nhân là một lỗi phương pháp luận cụ thể — không phải mô hình không học được — nằm ở khâu chuẩn hóa dữ liệu. Sau khi khắc phục (đổi biến mục tiêu từ giá tuyệt đối sang % thay đổi giá) và huấn luyện lại toàn bộ mô hình, kết quả cải thiện rõ rệt và đạt được các tính chất mong đợi của một mô hình dự báo giá tài chính hoạt động đúng.

| Chỉ số (trung bình 104 mã) | Trước khi sửa | Sau khi sửa | Kỳ vọng lý thuyết |
|---|---:|---:|---|
| MAPE TFT | 17.34% | 1.721% | ≈ Naive (giá tài chính gần bước ngẫu nhiên) |
| MAPE Naive | 1.72% | 1.720% | — |
| Độ chính xác hướng (DirAcc) | 48.9% | 51.7% | > 50% có ý nghĩa thống kê |
| Coverage dải tin cậy [p10, p90] | ~20–55%* | 78.8% | ≈ 80% (dải được hiệu chỉnh tốt) |

\*Coverage trước khi sửa dao động mạnh theo nhóm: chỉ ~20% ở các mã bị lệch scale nặng, ~55% ở các mã không bị ảnh hưởng.

## 2. Nguyên nhân gốc rễ: lệch phạm vi chuẩn hóa (scaler out-of-range)

Quy trình huấn luyện ban đầu fit `MinMaxScaler` một lần duy nhất trên 85% dữ liệu đầu (tập train theo thời gian), sau đó áp dụng cố định phạm vi này để chuẩn hóa cả tập kiểm tra (15% cuối) và dùng mô hình dự đoán trực tiếp **mức giá tuyệt đối đã chuẩn hóa**. Với các mã có xu hướng tăng giá dài hạn mạnh — đặc biệt cổ phiếu blue-chip Mỹ có lịch sử giao dịch hàng chục năm — phần lớn giai đoạn kiểm tra có mức giá vượt xa mức giá cao nhất mà mô hình từng quan sát lúc huấn luyện, buộc mô hình phải ngoại suy ra ngoài vùng dữ liệu đã học.

Kiểm chứng bằng chỉ số `out_of_range_pct` (% điểm kiểm tra có giá vượt max lúc train):

| Nhóm | Số mã | out_of_range_pct (TB) | MAPE TFT | Coverage | DirAcc |
|---|---|---|---|---|---|
| Lệch scale nặng (>50% điểm test vượt max train) | 42 | ~85% | 27.97% | 20.46% | 47.05% |
| Không lệch scale (≤5% điểm vượt) | 39 | ~1% | 10.55% | 55.46% | 51.03% |

Ví dụ điển hình: **AAPL** có khoảng giá lúc huấn luyện `[$0.04 – $55.2]`, trong khi giai đoạn kiểm tra nằm ở khoảng `[$54 – $340]` — 99.9% điểm kiểm tra vượt ngoài vùng huấn luyện, dẫn tới MAE lên tới 126 USD và Coverage chỉ 6.2%.

Đây là lỗi phổ biến, đã được ghi nhận trong tài liệu học thuật về dự báo chuỗi thời gian phi dừng (non-stationary time series): dùng một scaler cố định fit một lần cho một mô hình dùng chung (global model) trên tập hợp tài sản có biên độ và xu hướng tăng trưởng giá rất khác nhau.

## 3. Cách khắc phục

Thay vì các giải pháp nhẹ hơn (giới hạn N năm dữ liệu gần nhất, rolling scaler...), nhóm chọn giải pháp triệt để nhất: **đổi biến mục tiêu của mô hình từ mức giá tuyệt đối đã chuẩn hóa sang % thay đổi giá (return) so với giá đóng cửa gần nhất trong cửa sổ đầu vào**.

```
pct_change = (giá_đóng_cửa_ngày_tiếp_theo − giá_đóng_cửa_cuối_cửa_sổ) / giá_đóng_cửa_cuối_cửa_sổ × 100
```

Return luôn dao động trong biên độ ổn định (thường trong khoảng ±5%) bất kể mức giá tuyệt đối của tài sản là 0.5 USD hay 95,000 USD, nên loại bỏ tận gốc vấn đề lệch scale — đây cũng là cách tiếp cận chuẩn trong tài chính định lượng. Đầu vào của mô hình (các đặc trưng kỹ thuật) vẫn được chuẩn hóa bằng MinMaxScaler như cũ; chỉ biến mục tiêu ở đầu ra thay đổi. Kiến trúc mạng và hàm mất mát pinball loss cho 3 phân vị (p10/p50/p90) giữ nguyên.

Để tránh trộn lẫn hai loại nhãn không tương thích khi tiếp tục huấn luyện từ checkpoint cũ, nhóm bổ sung cơ chế versioning: mỗi checkpoint lưu kèm `target_type` trong `tft_meta.json`; nếu phát hiện checkpoint cũ có `target_type` khác với phiên bản hiện tại, quy trình tự động chuyển sang huấn luyện lại từ đầu thay vì tiếp tục huấn luyện (fine-tune) trên nhãn không tương thích.

Mô hình được huấn luyện lại hoàn toàn (từ đầu) trên toàn bộ 104 mã sau khi áp dụng thay đổi.

## 4. Kết quả sau khi khắc phục

| Mô hình | MAPE (%) ↓ | Độ chính xác hướng (%) ↑ | Số mã |
|---|---:|---:|---:|
| **TFT (mô hình đề xuất)** | **1.721** | **51.7** | 104 |
| Naive (giá hôm nay) | 1.720 | 0.0 | 104 |
| Trung bình động 5 phiên | 2.620 | 50.7 | 104 |
| Trung bình động 20 phiên | 4.862 | 50.2 | 104 |
| Ngoại suy xu hướng | 1.934 | 49.1 | 104 |

### 4.1. Kiểm định thống kê

MAPE của TFT (1.721%) gần như bằng naive (1.720%) — đây **không phải** là dấu hiệu mô hình yếu, mà là hệ quả tự nhiên của giả thuyết thị trường hiệu quả dạng yếu (giá đóng cửa ngắn hạn của tài sản tài chính hành xử gần với bước ngẫu nhiên, nên baseline naive vốn đã rất khó vượt qua về MAE/MAPE tuyệt đối). Do đó, nhóm đánh giá mô hình chủ yếu qua hai tiêu chí có ý nghĩa hơn với bài toán dự báo tài chính: độ chính xác hướng và hiệu chỉnh dải tin cậy.

**a) TFT có thực sự tốt hơn naive không, hay chỉ là ngẫu nhiên?** Kiểm định dấu nhị thức (binomial sign test) trên MAE từng mã: TFT có MAE thấp hơn naive ở **65/104 mã (62.5%)**. Nếu TFT không có thông tin gì hơn naive, xác suất quan sát được kết quả lệch như vậy (hoặc lệch hơn) do ngẫu nhiên chỉ là **p = 0.0138** (< 0.05) — có ý nghĩa thống kê, cho thấy TFT nắm bắt được tín hiệu thực sự chứ không chỉ đang "sao chép" naive.

**b) Độ chính xác hướng 51.7% có ý nghĩa thống kê không, hay chỉ nhỉnh hơn 50% do may rủi?** Kiểm định t một mẫu (so với giá trị kỳ vọng 50%) trên DirAcc của 104 mã: trung bình 51.667% (độ lệch chuẩn 2.905%), t = 5.853, **p ≈ 4.8 × 10⁻⁹** — có ý nghĩa thống kê rất mạnh. Mô hình dự đoán đúng chiều tăng/giảm nhiều hơn mức ngẫu nhiên một cách nhất quán trên phần lớn các mã, dù biên độ vượt trội (1.7 điểm phần trăm) là khiêm tốn — điều này cần được nêu rõ và trung thực trong báo cáo, tránh diễn giải quá mức.

**c) Dải tin cậy [p10, p90] có được hiệu chỉnh đúng không?** Coverage trung bình đạt **78.8%** (median 79.5%), rất gần giá trị lý tưởng 80% theo định nghĩa phân vị p10–p90. 97/104 mã (93%) có coverage nằm trong khoảng chấp nhận được [70%, 90%]. So với coverage chỉ ~20% ở các mã bị lệch scale trước khi sửa, đây là cải thiện rõ rệt nhất, cho thấy mô hình giờ đây tạo ra dải bất định (uncertainty) có ý nghĩa thực tế, có thể dùng để đánh giá rủi ro dự báo — điều mà phiên bản trước hoàn toàn không đạt được.

### 4.2. Nhận xét theo nhóm tài sản

Không còn hiện tượng phân hóa mạnh theo nhóm tài sản như trước khi sửa (khi đó US Stock/ETF có MAPE 20.86% do lệch scale nặng nhất). Sau khi sửa, các mã có biến động thấp (ETF chỉ số như DIA, VTI, VOO, các cổ phiếu phòng thủ như KO, JNJ, PG) có MAPE thấp nhất (0.6–0.9%) và DirAcc cao nhất (52–56%), trong khi các tài sản biến động mạnh (cổ phiếu tăng trưởng mới niêm yết như COIN, HOOD, PLTR, hoặc altcoin) có MAPE cao hơn (3–3.8%) — đúng như kỳ vọng, vì tài sản biến động cao vốn khó dự báo hơn về bản chất, không phải do lỗi kỹ thuật.

## 5. Kết luận

Việc MAPE tổng hợp của TFT xấp xỉ bằng naive không phản ánh mô hình thất bại, mà phản ánh đúng bản chất khó dự báo của giá tài chính ngắn hạn — một baseline "giá hôm nay = giá ngày mai" vốn đã rất mạnh. Giá trị thực sự của mô hình TFT trong đồ án này nằm ở (1) độ chính xác hướng cao hơn mức ngẫu nhiên một cách có ý nghĩa thống kê (p ≈ 4.8×10⁻⁹), và (2) dải tin cậy được hiệu chỉnh tốt (coverage ≈ 80%), cho phép định lượng độ bất định của dự báo — hai tính chất mà mô hình phiên bản lỗi trước đó hoàn toàn không đạt được.

## 6. Hạn chế còn lại và hướng phát triển

1. Biên độ vượt trội của DirAcc so với 50% còn khiêm tốn (~1.7 điểm phần trăm) — phù hợp với đặc tính thị trường hiệu quả, nhưng cần nêu rõ trong báo cáo, không phóng đại khả năng "đánh bại thị trường".
2. TFT hiện chỉ dự báo dựa trên dữ liệu giá/kỹ thuật lịch sử, không phản ứng được với sự kiện/tin tức đột biến trong giai đoạn dự báo. Đây là lý do đồ án bổ sung **SentimentFusionEngine** — một mô hình phụ trợ kết hợp tín hiệu sentiment/tin tức (qua LLM Research Agent) để điều chỉnh dự báo của TFT trong biên độ giới hạn (±5%). Xem phần đánh giá riêng của SentimentFusionEngine để biết chi tiết huấn luyện và kiểm thử.
3. Có thể cải thiện thêm bằng bộ chuẩn hóa thích nghi (rolling/expanding-window scaler) cho các đặc trưng đầu vào, hoặc log-return thay vì % return tuyến tính, nhưng nằm ngoài phạm vi thời gian của đồ án hiện tại.
