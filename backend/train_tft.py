"""
train_tft.py – Huấn luyện Temporal Fusion Transformer toàn cục.

╔══════════════════════════════════════════════════════════════════════════════╗
║  LỖI PHƯƠNG PHÁP ĐÃ SỬA: RÒ RỈ DỮ LIỆU KHI CHIA TẬP VALIDATION              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Bản trước làm thế này:

    np.random.shuffle(indices)          # trộn toàn bộ mẫu của mọi mã
    model.fit(X, Y, validation_split=0.1)

Keras cắt 10% CUỐI của mảng làm tập validation. Vì mảng đã bị trộn ngẫu nhiên
trước đó, tập validation chứa các cửa sổ thời gian nằm xen kẽ với tập train —
ví dụ train có cửa sổ ngày 100-160 và ngày 102-162, còn validation có ngày 101-161.
Ba cửa sổ này chồng lấn gần như hoàn toàn.

Hệ quả: val_loss trông rất đẹp, nhưng nó đo khả năng nội suy giữa những ngày mô hình
ĐÃ THẤY, chứ không đo khả năng dự báo tương lai. Với một đồ án, đây là loại lỗi mà
hội đồng sẽ hỏi ngay khi nhìn đường loss quá mượt — và mọi con số MAE/RMSE báo cáo
dựa trên nó đều không dùng được.

Bản này chia theo THỜI GIAN cho từng mã: 85% đầu tiên của lịch sử mỗi mã dùng để
huấn luyện, 15% cuối dùng để validate. Ngoài ra bỏ hẳn `VALIDATION_GAP` cửa sổ ở
ranh giới để cửa sổ cuối của tập train không chạm sang vùng validation.

Chỉ tập train mới được trộn; tập validation giữ nguyên thứ tự thời gian.

────────────────────────────────────────────────────────────────────────────────
GHI CHÚ VỀ QUANTILE LOSS

`Y_quantile = np.column_stack([Y, Y, Y])` là ĐÚNG, không phải lỗi. Trong hồi quy
quantile, mỗi quantile τ được học từ chính giá trị thực tế quan sát được, thông qua
hàm mất mát bất đối xứng (pinball loss). Việc ba cột giống nhau là bình thường —
sự khác biệt giữa p10/p50/p90 sinh ra từ trọng số bất đối xứng của loss, không phải
từ nhãn khác nhau.

Điều CẦN kiểm chứng là dải tin cậy có được hiệu chỉnh đúng hay không: khoảng
[p10, p90] lẽ ra phải bao phủ khoảng 80% số quan sát thực tế. Phép đo đó nằm ở
`backend/evaluate_tft.py`.
────────────────────────────────────────────────────────────────────────────────
LỖI PHƯƠNG PHÁP ĐÃ SỬA (lần 2): DỰ ĐOÁN MỨC GIÁ TUYỆT ĐỐI THAY VÌ % THAY ĐỔI

Bản trước huấn luyện model dự đoán GIÁ ĐÃ CHUẨN HOÁ (Close sau MinMaxScaler) của
phiên kế tiếp. `MinMaxScaler` chỉ được fit MỘT LẦN trên 85% dữ liệu đầu (train).
Với các mã có xu hướng tăng giá dài hạn mạnh — đặc biệt cổ phiếu Mỹ có lịch sử
giá nhiều thập kỷ, đã qua nhiều lần tách cổ phiếu — phần lớn giai đoạn validation/
test có giá VƯỢT quá giá lớn nhất model từng thấy lúc train. Giá trị sau chuẩn hoá
khi đó vượt ngưỡng [0,1], buộc model phải ngoại suy ra ngoài vùng đã học.

Đo thực nghiệm trên 104 mã (xem `models/danh_gia_ket_qua.md`): 42/104 mã có >50%
điểm test vượt giá max lúc train, nhóm này có MAPE gấp 23 lần naive forecast và
Coverage dải tin cậy chỉ ~20% (đáng lẽ phải ~80%). Vấn đề tập trung nặng nhất ở
cổ phiếu Mỹ (US Stock/ETF): trung bình 58% điểm test bị lệch phạm vi.

Bản này đổi biến mục tiêu (target) sang TỶ LỆ % THAY ĐỔI GIÁ (return) so với phiên
cuối cùng trong cửa sổ đầu vào, thay vì mức giá tuyệt đối:

    return[i] = (Close[i+look_back] - Close[i+look_back-1]) / Close[i+look_back-1] * 100

Return luôn dao động trong biên độ ổn định (thường vài % mỗi phiên) bất kể mức giá
tuyệt đối của tài sản là bao nhiêu — loại bỏ tận gốc vấn đề lệch scale ở trên. Đầu
ra của model giờ là quantile của % thay đổi giá, không phải quantile của giá.

QUAN TRỌNG: đây là thay đổi về Ý NGHĨA của target, không phải kiến trúc mạng hay
số chiều đầu vào — nên `train_tft()` KHÔNG tự phát hiện được qua so sánh
`num_features` như với thay đổi tập đặc trưng. Nếu tiếp tục huấn luyện từ
checkpoint cũ (vốn học để dự đoán giá tuyệt đối đã chuẩn hoá), model sẽ bị trộn
lẫn hai loại nhãn hoàn toàn khác nhau. Vì vậy hàm `train_tft()` kiểm tra field
`target_type` trong `tft_meta.json` của checkpoint cũ và TỰ ĐỘNG ép `fresh=True`
nếu không khớp — không cần nhớ truyền `--fresh` bằng tay, nhưng vẫn nên truyền để
rõ ràng.
────────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import os
import pickle
import sys
from datetime import datetime

import math

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

# Khi stdout được redirect ra file (vd: `python -m ... *> log.txt` trong PowerShell),
# Python KHÔNG dùng UTF-8 nữa mà rơi về bảng mã mặc định của hệ thống (cp1258 trên
# Windows tiếng Việt) — bảng mã này thiếu một số ký tự có dấu, khiến script crash
# ngay dòng print() đầu tiên có tiếng Việt. Ép UTF-8 tường minh để in ra màn hình
# lẫn ghi ra file đều hoạt động như nhau.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import tensorflow as tf

# Seed dùng chung cho numpy và TensorFlow để kết quả huấn luyện tái lập được.
RANDOM_SEED = 42

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.models.feature_engineering import add_technical_indicators, get_feature_columns
from backend.models.tft_model import build_tft_model, compile_tft_model, get_tft_callbacks

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")

LOOK_BACK = 60
EPOCHS = 100
BATCH_SIZE = 64

# ══════════════════════════════════════════════════════════════════════════════
#  CHIA TẬP BA PHẦN (train / validation / test) — SỬA LỖI RÒ RỈ Ở KHÂU ĐÁNH GIÁ
# ══════════════════════════════════════════════════════════════════════════════
#
# LỖI CỦA BẢN CŨ: chỉ chia HAI phần (85% train / 15% validation). Tập 15% đó vừa
# được dùng để `EarlyStopping` chọn epoch dừng và `ModelCheckpoint` chọn bộ trọng số
# tốt nhất (`monitor="val_loss"`, `restore_best_weights=True`), LẠI VỪA được
# `evaluate_tft.py` dùng làm "tập kiểm thử" để báo cáo MAPE/DirAcc/Coverage —
# `evaluate_tft.py` import thẳng `TRAIN_RATIO`/`VALIDATION_GAP` từ file này và tính
# ra đúng cùng một lát cắt.
#
# Nghĩa là bộ trọng số được chọn CHÍNH VÌ nó đạt loss thấp nhất trên đúng những dòng
# sau đó được đem đi đo. Đây là rò rỉ ở khâu chọn mô hình (model-selection leakage):
# mọi con số "ngoài mẫu" trong báo cáo đều lạc quan hơn thực tế, và câu ghi chú
# "nằm ngoài tầm nhìn của mô hình" trong evaluate_tft.py là sai.
#
# CÁCH SỬA: ba tập tách rời theo thời gian, có khoảng trống giữa các tập.
#   - train (70%)      : dùng để cập nhật trọng số.
#   - validation (15%) : CHỈ dùng cho EarlyStopping/ModelCheckpoint.
#   - test (15% cuối)  : KHÔNG hề được chạm tới trong lúc huấn luyện; chỉ
#                        `evaluate_tft.py` dùng, đúng một lần, để báo cáo.
TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
# Phần còn lại (~15%) là tập test.

# Số phiên bỏ trống ở MỖI ranh giới giữa hai tập. Cửa sổ cuối của tập trước kết thúc
# ngay sát điểm cắt; không có khoảng trống này thì mẫu đầu tiên của tập sau vẫn dùng
# chung phần lớn dữ liệu với nó.
SPLIT_GAP = LOOK_BACK

# Giữ tên cũ để code/notebook cũ import không bị vỡ.
VALIDATION_GAP = SPLIT_GAP


def _min_rows_for_split() -> int:
    """
    Số phiên tối thiểu để cả ba tập đều dùng được.

    Không ước lượng bằng công thức tay: hai khoảng trống `SPLIT_GAP` bị TRỪ THẲNG vào
    tập test (tập cuối), nên tập test nhỏ hơn tỷ lệ danh nghĩa rất nhiều ở các mã
    lịch sử ngắn — với 500 phiên thì test thậm chí RỖNG. Ở đây dò thẳng bằng chính
    `split_indices()` để con số luôn khớp với cách cắt thật, kể cả sau này có đổi tỷ lệ.
    """
    need = LOOK_BACK + 5
    n = LOOK_BACK * 3
    while n < 100_000:
        train_end, val_start, val_end, test_start = split_indices(n)
        if (
            train_end >= LOOK_BACK + 10
            and (val_end - val_start) >= need
            and (n - test_start) >= need
        ):
            return n
        n += 1
    raise RuntimeError("Không tìm được số phiên tối thiểu — kiểm tra lại tỷ lệ chia tập.")


def split_indices(n_rows: int) -> tuple[int, int, int, int]:
    """
    Ranh giới ba tập cho một mã có `n_rows` phiên sạch.

    Trả về (train_end, val_start, val_end, test_start) — dùng như sau:
        train = df.iloc[:train_end]
        val   = df.iloc[val_start:val_end]
        test  = df.iloc[test_start:]

    `evaluate_tft.py` BẮT BUỘC gọi chính hàm này thay vì tự tính lại, để hai file
    không thể lệch nhau — chính việc mỗi bên tự tính là gốc rễ của lỗi cũ.
    """
    train_end = int(n_rows * TRAIN_RATIO)
    val_start = train_end + SPLIT_GAP
    val_end = val_start + int(n_rows * VAL_RATIO)
    test_start = val_end + SPLIT_GAP
    return train_end, val_start, val_end, test_start

# Số phiên tối thiểu một mã phải có để chia được ba tập dùng được.
MIN_ROWS_FOR_SPLIT = _min_rows_for_split()

# Các file dữ liệu tổng hợp / trùng lặp — bỏ qua khi build dataset.
SKIP_FILES = {"merged_data", "bitcoin_data", "bitcoin_data_global"}

# Đánh dấu phiên bản ý nghĩa của target — dùng để tự động phát hiện checkpoint cũ
# (huấn luyện với target khác) và ép train mới thay vì tiếp tục huấn luyện nhầm.
TARGET_TYPE = "return_pct_1step"


# ══════════════════════════════════════════════════════════════════════════════
#  DỰNG DATASET
# ══════════════════════════════════════════════════════════════════════════════

def _build_sequences(scaled: np.ndarray, raw_close: np.ndarray, look_back: int):
    """
    Cắt chuỗi đã chuẩn hoá thành các cặp (cửa sổ đầu vào, % thay đổi giá kế tiếp).

    Đầu vào X vẫn dùng dữ liệu đã qua MinMaxScaler như trước (ổn định cho việc học
    của mạng). Nhãn Y giờ là % THAY ĐỔI GIÁ tính từ giá THẬT (raw_close, chưa
    chuẩn hoá) — không đi qua scaler — để tránh việc nhãn bị bó buộc vào phạm vi
    [0,1] của giai đoạn train, vốn là nguyên nhân gây lệch scale nghiêm trọng khi
    giá tương lai vượt ngưỡng đã học (xem ghi chú ở đầu file).
    """
    X, Y = [], []
    for i in range(len(scaled) - look_back):
        last_close = raw_close[i + look_back - 1]
        next_close = raw_close[i + look_back]
        pct_change = (next_close - last_close) / last_close * 100.0
        X.append(scaled[i : i + look_back])
        Y.append(pct_change)
    return X, Y


def _build_targets(raw_close: np.ndarray, look_back: int) -> np.ndarray:
    """
    Chỉ tính vector nhãn, không dựng cửa sổ đầu vào.

    `targets[i]` là % thay đổi giá của cửa sổ bắt đầu tại vị trí `i`: từ phiên cuối
    cửa sổ (i + look_back - 1) sang phiên kế tiếp (i + look_back). Công thức GIỐNG
    HỆT `_build_sequences` ở trên — hai hàm phải luôn cho ra cùng một nhãn, chỉ khác
    ở chỗ hàm này không nhân bản dữ liệu đầu vào ra thành từng cửa sổ riêng.
    """
    closes = np.asarray(raw_close, dtype=np.float64)
    if len(closes) <= look_back:
        return np.empty(0, dtype=np.float32)
    last = closes[look_back - 1 : -1]
    nxt = closes[look_back:]
    return ((nxt - last) / last * 100.0).astype(np.float32)


# ══════════════════════════════════════════════════════════════════════════════
#  DATASET CẮT CỬA SỔ KHI CẦN (thay vì dựng sẵn toàn bộ trong RAM)
# ══════════════════════════════════════════════════════════════════════════════
#
# Bản cũ dựng SẴN mọi cửa sổ 60 phiên thành từng bản riêng rồi gộp vào một mảng
# numpy khổng lồ. Hai cửa sổ liên tiếp trùng nhau 59/60 phiên, nên cùng một dữ liệu
# bị nhân lên khoảng 60 lần: với 104 mã đã tốn ~2,7 GB chỉ riêng X_train, và nếu mở
# rộng danh sách mã thì con số này vượt 6 GB — tràn RAM của một laptop bình thường.
#
# Ở đây chỉ giữ ma trận đã chuẩn hoá của mỗi mã ĐÚNG MỘT LẦN (~0,15 GB cho toàn bộ
# dữ liệu) và cắt cửa sổ ngay lúc tạo batch. Giảm khoảng 40 lần bộ nhớ, đổi lại một
# chút chi phí CPU khi ghép batch — không đáng kể so với thời gian tính của mạng.

try:  # Keras 3 đổi tên Sequence thành PyDataset.
    _DatasetBase = tf.keras.utils.PyDataset
except AttributeError:  # pragma: no cover
    _DatasetBase = tf.keras.utils.Sequence


class WindowDataset(_DatasetBase):
    """
    Sinh batch (X, Y) bằng cách cắt cửa sổ từ ma trận gốc của từng mã.

    `blocks`: danh sách (scaled, targets) cho mỗi mã —
        scaled  : ma trận (n, F) đã chuẩn hoá theo scaler riêng của mã đó
        targets : vector (n - look_back,), targets[i] là % thay đổi giá từ phiên
                  cuối cửa sổ bắt đầu tại i sang phiên kế tiếp
    """

    def __init__(self, blocks, look_back, batch_size, shuffle, seed=42, **kwargs):
        try:
            super().__init__(**kwargs)
        except TypeError:  # Sequence cũ không nhận kwargs
            super().__init__()
        self.blocks = blocks
        self.look_back = look_back
        self.batch_size = batch_size
        self.shuffle = shuffle
        self._rng = np.random.default_rng(seed)

        pairs = [
            (b, i)
            for b, (_, targets) in enumerate(blocks)
            for i in range(len(targets))
        ]
        self.index = np.array(pairs, dtype=np.int32)
        if shuffle:
            self._rng.shuffle(self.index)

        self.num_features = blocks[0][0].shape[1] if blocks else 0

    def __len__(self):
        return math.ceil(len(self.index) / self.batch_size)

    def __getitem__(self, k):
        sel = self.index[k * self.batch_size : (k + 1) * self.batch_size]
        X = np.empty((len(sel), self.look_back, self.num_features), dtype=np.float32)
        # Pinball loss cần y_true có cùng số cột với y_pred (3 quantile).
        Y = np.empty((len(sel), 3), dtype=np.float32)
        for j in range(len(sel)):
            b, i = int(sel[j, 0]), int(sel[j, 1])
            scaled, targets = self.blocks[b]
            X[j] = scaled[i : i + self.look_back]
            Y[j, :] = targets[i]
        return X, Y

    def on_epoch_end(self):
        # Chỉ trộn tập train; tập validation giữ nguyên thứ tự thời gian.
        if self.shuffle:
            self._rng.shuffle(self.index)


def create_tft_dataset(verbose: bool = True, max_tickers: int | None = None):
    """
    Dựng dataset toàn cục từ mọi file CSV trong data/.

    Trả về (train_ds, val_ds, num_features, report) — hai dataset cắt cửa sổ khi cần
    (xem WindowDataset), KHÔNG phải mảng numpy dựng sẵn.

    Việc chuẩn hoá được thực hiện RIÊNG cho từng mã. Đây là lựa chọn có chủ ý:
    BTC giá hàng chục nghìn USD còn FPT.VN vài chục nghìn VND — đưa chung vào một
    thang đo sẽ khiến mô hình chỉ học được đặc điểm của mã có biên độ lớn nhất.

    Scaler KHÔNG được lưu ra file. Lúc inference, `forecaster.py` khớp scaler mới
    trên chính dữ liệu lịch sử của mã đang dự báo — nhờ vậy hệ thống chạy được với
    bất kỳ mã nào, kể cả mã chưa từng xuất hiện lúc huấn luyện.
    """
    train_blocks, val_blocks = [], []
    report = {"tickers_used": [], "tickers_skipped": [], "feature_columns": []}

    if not os.path.isdir(DATA_DIR):
        print(f"Không tìm thấy thư mục dữ liệu: {DATA_DIR}")
        return None, None, None, None, 0, report

    csv_files = sorted(f for f in os.listdir(DATA_DIR) if f.endswith(".csv"))
    if max_tickers:
        # Dùng cho lượt chạy thử nhanh: lấy mẫu ĐỀU khắp danh sách thay vì cắt phần
        # đầu, để tập con vẫn có đủ cổ phiếu Mỹ / ETF / crypto / mã .VN.
        step = max(1, len(csv_files) // max_tickers)
        csv_files = csv_files[::step][:max_tickers]
    if verbose:
        print(f"Tìm thấy {len(csv_files)} file CSV trong data/")

    feature_cols_reference = None

    for filename in csv_files:
        ticker = filename[:-4]
        if ticker in SKIP_FILES:
            continue

        try:
            df = pd.read_csv(os.path.join(DATA_DIR, filename), index_col="Date", parse_dates=True)
        except Exception as e:
            report["tickers_skipped"].append({"ticker": ticker, "reason": f"đọc lỗi: {e}"})
            continue

        if df.empty or "Close" not in df.columns:
            report["tickers_skipped"].append({"ticker": ticker, "reason": "thiếu cột Close"})
            continue

        df = df.sort_index()
        df = add_technical_indicators(df)

        available = [c for c in get_feature_columns() if c in df.columns]
        all_cols = ["Close"] + available

        df_clean = df[all_cols].dropna()

        min_rows = MIN_ROWS_FOR_SPLIT
        if len(df_clean) < min_rows:
            report["tickers_skipped"].append(
                {"ticker": ticker, "reason": f"chỉ có {len(df_clean)} phiên, cần {min_rows}"}
            )
            continue

        # Số chiều đặc trưng phải giống nhau ở mọi mã — mô hình có input shape cố định.
        if feature_cols_reference is None:
            feature_cols_reference = all_cols
        elif all_cols != feature_cols_reference:
            report["tickers_skipped"].append({"ticker": ticker, "reason": "tập đặc trưng không khớp"})
            continue

        # ── Cắt theo thời gian TRƯỚC khi chuẩn hoá ──
        # Tập TEST (phần sau `test_start`) được cắt ra ở đây rồi BỎ HẲN, không đưa
        # vào mảng train/val dưới bất kỳ hình thức nào. Chỉ `evaluate_tft.py` chạm
        # tới nó, sau khi huấn luyện xong.
        train_end, val_start, val_end, test_start = split_indices(len(df_clean))
        train_slice = df_clean.iloc[:train_end]
        val_slice = df_clean.iloc[val_start:val_end]
        test_len = len(df_clean) - test_start

        if (
            len(train_slice) < LOOK_BACK + 10
            or len(val_slice) < LOOK_BACK + 5
            or test_len < LOOK_BACK + 5
        ):
            report["tickers_skipped"].append({"ticker": ticker, "reason": "không đủ dữ liệu sau khi cắt 3 tập"})
            continue

        # Scaler khớp CHỈ trên phần train. Khớp trên toàn bộ dữ liệu sẽ để lộ
        # giá trị min/max của tương lai vào quá trình huấn luyện — cũng là một
        # dạng rò rỉ, tinh vi hơn nhưng vẫn làm kết quả đẹp giả tạo.
        scaler = MinMaxScaler(feature_range=(0, 1))
        scaler.fit(train_slice.values)

        # Chỉ lưu ma trận đã chuẩn hoá + vector nhãn; cửa sổ được cắt lúc tạo batch.
        tr_scaled = scaler.transform(train_slice.values).astype(np.float32)
        va_scaled = scaler.transform(val_slice.values).astype(np.float32)
        tr_targets = _build_targets(train_slice["Close"].values, LOOK_BACK)
        va_targets = _build_targets(val_slice["Close"].values, LOOK_BACK)

        if len(tr_targets) == 0 or len(va_targets) == 0:
            report["tickers_skipped"].append({"ticker": ticker, "reason": "không đủ cửa sổ"})
            continue

        train_blocks.append((tr_scaled, tr_targets))
        val_blocks.append((va_scaled, va_targets))

        report["tickers_used"].append(
            {"ticker": ticker, "train_samples": len(tr_targets), "val_samples": len(va_targets)}
        )
        if verbose:
            print(f"  {ticker}: {len(tr_targets)} mẫu train, {len(va_targets)} mẫu validation")

    if not train_blocks:
        return None, None, 0, report

    train_ds = WindowDataset(train_blocks, LOOK_BACK, BATCH_SIZE, shuffle=True, seed=RANDOM_SEED)
    val_ds = WindowDataset(val_blocks, LOOK_BACK, BATCH_SIZE, shuffle=False, seed=RANDOM_SEED)

    report["feature_columns"] = feature_cols_reference or []
    num_features = train_ds.num_features

    if verbose:
        mem_mb = sum(s.nbytes + t.nbytes for s, t in train_blocks + val_blocks) / 1e6
        print(
            f"\nDataset: {len(train_ds.index):,} mẫu train, {len(val_ds.index):,} mẫu validation"
            f" — giữ trong RAM {mem_mb:,.0f} MB"
        )
        print(f"Số mã dùng được: {len(report['tickers_used'])}, bỏ qua: {len(report['tickers_skipped'])}")

    return train_ds, val_ds, num_features, report


# ══════════════════════════════════════════════════════════════════════════════
#  HUẤN LUYỆN
# ══════════════════════════════════════════════════════════════════════════════

def plot_loss(history, filename: str = "loss_tft.png") -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")  # Không cần màn hình — quan trọng khi chạy trên Colab/Kaggle
        import matplotlib.pyplot as plt

        plt.figure(figsize=(10, 5))
        plt.plot(history.history["loss"], label="Train loss", color="#f0b90b")
        if "val_loss" in history.history:
            plt.plot(history.history["val_loss"], label="Validation loss", color="#3861fb")
        plt.title("TFT Training Loss (chia tập theo thời gian)")
        plt.xlabel("Epoch")
        plt.ylabel("Quantile (pinball) loss")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(os.path.join(MODELS_DIR, filename), dpi=150)
        plt.close()
        print(f"Đã lưu đồ thị loss: {filename}")
    except Exception as e:
        print(f"Bỏ qua vẽ đồ thị loss: {e}")


def train_tft(fresh: bool = False, max_tickers: int | None = None, epochs: int | None = None) -> None:
    """
    Huấn luyện mô hình.

    `fresh=True` bỏ qua checkpoint cũ và khởi tạo lại từ đầu — nên dùng khi
    tập đặc trưng, cách chia dữ liệu, hoặc Ý NGHĨA của target thay đổi, vì lúc đó
    tiếp tục huấn luyện từ trọng số cũ sẽ trộn lẫn hai chế độ dữ liệu khác nhau.
    Hàm này cũng tự động phát hiện trường hợp target_type đổi (xem bên dưới) và
    tự ép fresh=True, nhưng truyền cờ `--fresh` bằng tay vẫn là thói quen tốt.
    """
    # Cố định seed cho TensorFlow/Keras. Trước đây chỉ numpy được seed, còn khởi tạo
    # trọng số của các lớp Dense/GRN và mặt nạ Dropout lấy từ RNG toàn cục CHƯA seed
    # của TF — nghĩa là chạy lại đúng script trên đúng dữ liệu vẫn ra bộ trọng số
    # khác, và do đó ra MAPE/DirAcc/Coverage khác. Số liệu trong báo cáo vì thế
    # không tái lập được, một điểm rất dễ bị hỏi khi bảo vệ.
    tf.keras.utils.set_random_seed(RANDOM_SEED)

    os.makedirs(MODELS_DIR, exist_ok=True)

    print("=" * 70)
    print("HUẤN LUYỆN TEMPORAL FUSION TRANSFORMER")
    print("=" * 70)

    train_ds, val_ds, num_features, report = create_tft_dataset(max_tickers=max_tickers)
    if train_ds is None:
        print("Không dựng được dataset. Kiểm tra lại thư mục data/.")
        return

    model_path = os.path.join(MODELS_DIR, "global_tft.keras")
    meta_path = os.path.join(MODELS_DIR, "tft_meta.json")

    # Checkpoint cũ có thể được huấn luyện với Ý NGHĨA target khác (giá tuyệt đối
    # thay vì % thay đổi) — điều này không thể phát hiện qua num_features vì kiến
    # trúc/số chiều đầu vào không đổi. Đọc meta cũ để kiểm tra, ép fresh nếu lệch.
    if os.path.exists(meta_path):
        try:
            with open(meta_path, encoding="utf-8") as f:
                old_meta = json.load(f)
            old_target_type = old_meta.get("target_type", "close_price_scaled")
        except Exception:
            old_target_type = None
        if not fresh and old_target_type != TARGET_TYPE:
            print(
                f"Checkpoint cũ có target_type='{old_target_type}', khác với target hiện "
                f"tại ('{TARGET_TYPE}'). Tự động chuyển sang huấn luyện MỚI để tránh trộn "
                "lẫn hai loại nhãn khác nhau."
            )
            fresh = True

    if os.path.exists(model_path) and not fresh:
        print("Nạp lại checkpoint đã có để huấn luyện tiếp...")
        from backend.models.tft_model import quantile_loss

        model = tf.keras.models.load_model(
            model_path, custom_objects={"loss_fn": quantile_loss([0.1, 0.5, 0.9])}
        )
        # Kiến trúc cũ có thể không khớp số đặc trưng hiện tại.
        if model.input_shape[-1] != num_features:
            print(
                f"Số đặc trưng đã thay đổi ({model.input_shape[-1]} -> {num_features}). "
                "Khởi tạo mô hình mới."
            )
            model = compile_tft_model(
                build_tft_model(input_shape=(LOOK_BACK, num_features)), learning_rate=0.001
            )
    else:
        print(f"Khởi tạo mô hình mới: input=({LOOK_BACK}, {num_features})")
        model = compile_tft_model(
            build_tft_model(
                input_shape=(LOOK_BACK, num_features),
                hidden_size=64,
                num_heads=4,
                num_blocks=2,
                dropout_rate=0.2,
                num_quantiles=3,
            ),
            learning_rate=0.001,
        )

    model.summary()

    print("\nBắt đầu huấn luyện...")
    # `train_ds`/`val_ds` tự cắt cửa sổ và tự trộn (chỉ tập train) ở mỗi epoch, nên
    # không truyền batch_size/shuffle ở đây nữa — chúng đã nằm trong dataset.
    history = model.fit(
        train_ds,
        validation_data=val_ds,  # Tập validation tách theo thời gian, không dùng validation_split
        epochs=epochs or EPOCHS,
        callbacks=get_tft_callbacks(model_path, patience=15),
        verbose=1,
    )

    plot_loss(history)

    # Lưu metadata để các script khác (đánh giá, fine-tune) biết mô hình được
    # huấn luyện với cấu hình nào.
    meta = {
        "num_features": int(num_features),
        "look_back": LOOK_BACK,
        "feature_columns": report["feature_columns"],
        "train_ratio": TRAIN_RATIO,
        "val_ratio": VAL_RATIO,
        "test_ratio": round(1.0 - TRAIN_RATIO - VAL_RATIO, 4),
        "split_gap": SPLIT_GAP,
        "split_scheme": "3-way chronological (train / val cho EarlyStopping / test giữ riêng)",
        "validation_gap": VALIDATION_GAP,
        "split_strategy": "chronological-per-ticker",
        "target_type": TARGET_TYPE,
        "batch_size": BATCH_SIZE,
        "train_samples": int(len(train_ds.index)),
        "val_samples": int(len(val_ds.index)),
        "tickers_used": [t["ticker"] for t in report["tickers_used"]],
        "trained_at": datetime.now().isoformat(),
        "best_val_loss": float(min(history.history.get("val_loss", [float("nan")]))),
    }

    with open(os.path.join(MODELS_DIR, "tft_meta.pkl"), "wb") as f:
        pickle.dump(meta, f)
    # Lưu thêm bản JSON để đọc được bằng mắt và trích thẳng vào báo cáo.
    with open(os.path.join(MODELS_DIR, "tft_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print("HOÀN TẤT HUẤN LUYỆN")
    print(f"  Mô hình:      {model_path}")
    print(f"  Val loss tốt nhất: {meta['best_val_loss']:.6f}")
    print(f"  Số mã:        {len(meta['tickers_used'])}")
    print(f"  Mẫu train:    {meta['train_samples']:,}")
    print(f"  Mẫu val:      {meta['val_samples']:,}")
    print("=" * 70)
    print("\nBước tiếp theo: chạy `python -m backend.evaluate_tft` để so sánh với")
    print("baseline (naive forecast, moving average) và lấy số liệu cho báo cáo.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Huấn luyện mô hình TFT toàn cục.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ:
  # Chạy thử nhanh trước khi train thật (khoảng 10-15 phút) — kiểm tra pipeline
  # chạy trơn và ước lượng thời gian mỗi epoch:
  python -m backend.train_tft --fresh --max-tickers 20 --epochs 3

  # Train thật, dùng toàn bộ dữ liệu:
  python -m backend.train_tft --fresh
""",
    )
    parser.add_argument(
        "--fresh", action="store_true",
        help="Huấn luyện lại từ đầu thay vì tiếp tục từ checkpoint cũ. "
             "BẮT BUỘC dùng khi đã đổi cách chia tập hoặc mở rộng dữ liệu.",
    )
    parser.add_argument(
        "--max-tickers", type=int, default=None,
        help="Chỉ dùng N mã (lấy mẫu đều khắp danh sách). Dành cho chạy thử.",
    )
    parser.add_argument(
        "--epochs", type=int, default=None,
        help=f"Số epoch tối đa (mặc định {EPOCHS}; EarlyStopping thường dừng sớm hơn).",
    )
    args = parser.parse_args()
    train_tft(fresh=args.fresh, max_tickers=args.max_tickers, epochs=args.epochs)
