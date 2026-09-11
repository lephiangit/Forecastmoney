"""
feature_engineering.py – Tính chỉ báo kỹ thuật và dựng khung dữ liệu cho mô hình.

╔══════════════════════════════════════════════════════════════════════════════╗
║  LỖI PHƯƠNG PHÁP ĐÃ SỬA: ĐẶC TRƯNG ĐẦU VÀO PHỤ THUỘC MỨC GIÁ TUYỆT ĐỐI      ║
╚══════════════════════════════════════════════════════════════════════════════╝

Lần sửa trước đã đổi NHÃN (target) từ mức giá tuyệt đối sang % thay đổi giá, và
điều đó đúng. Nhưng ĐẦU VÀO thì vẫn còn nguyên vấn đề: 12 trong 22 đặc trưng cũ
mang đơn vị tiền tệ và trôi theo mức giá.

    Close, MACD, MACD_Signal, MACD_Hist, BB_Upper, BB_Lower,
    ATR, OBV, MA5, MA10, MA20, MA50

`Close` nghiêm trọng nhất: nó nằm ở cột 0 của ma trận đầu vào (`all_cols =
["Close"] + features`), nghĩa là mức giá thô được nạp thẳng vào mạng chứ không chỉ
dùng để tính nhãn.

Vì sao hỏng: scaler chỉ được khớp trên 70% dữ liệu đầu. Với mã tăng dài hạn, giá
ở giai đoạn test vượt xa giá lớn nhất từng thấy lúc train, nên giá trị sau chuẩn
hoá bắn ra ngoài phạm vi đã học và mạng buộc phải ngoại suy. MACD của một cổ
phiếu 400 USD lớn gấp trăm lần MACD của cổ phiếu 4 USD dù hình dạng tín hiệu
giống hệt nhau — mạng học mức giá thay vì học tín hiệu.

CÁCH SỬA: mỗi đặc trưng phi dừng được thay bằng một dạng KHÔNG CÓ ĐƠN VỊ, giá trị
nằm trong biên độ ổn định bất kể tài sản đắt hay rẻ:

    Close              → Return_1d        (% thay đổi phiên)
    MACD               → MACD_Pct         (MACD / Close · 100)
    MACD_Signal        → MACD_Signal_Pct
    MACD_Hist          → MACD_Hist_Pct
    BB_Upper, BB_Lower → BB_Position      (percent-B, chặn trong [0,1])
    ATR                → ATR_Pct          (ATR / Close · 100)
    OBV                → OBV_Osc          (lệch khỏi trung bình 20 phiên, chia
                                           cho khối lượng trung bình)
    MA5                → Close_to_MA5     (tỷ lệ)
    MA10               → Close_to_MA10    (tỷ lệ)
    MA20               → MA20_Slope       (% đổi của MA20 sau 5 phiên)
    MA50               → MA50_Slope       (% đổi của MA50 sau 10 phiên)

`Close_to_MA20` và `Close_to_MA50` vốn đã có sẵn nên MA20/MA50 chuyển sang dạng ĐỘ
DỐC để không mất thông tin xu hướng thay vì bị bỏ đi. Bollinger gộp hai cột thành
một, nên tổng đặc trưng đi từ 22 xuống 21.

QUAN TRỌNG: các cột THÔ (MACD, BB_Upper, MA20, ...) VẪN ĐƯỢC GIỮ trong DataFrame.
Chúng không còn là đầu vào của mạng, nhưng `routers/backtest.py` và biểu đồ ở
frontend (`forecaster._build_historical`) vẫn đọc chúng. Chỉ danh sách trả về bởi
`get_feature_columns()` là thay đổi.

────────────────────────────────────────────────────────────────────────────────
CHUẨN HOÁ: MinMaxScaler → StandardScaler + cắt ±5σ

Khi đặc trưng đã ở dạng %, phân phối có đuôi rất dài: một phiên DOGE-USD +355%
hay MS +87% là biến động THẬT và phải giữ lại, nhưng dưới MinMaxScaler một điểm
như thế kéo giãn phạm vi tới mức toàn bộ phần còn lại của cột bị nén về sát 0 —
mạng gần như không phân biệt được các phiên bình thường với nhau.

`FeatureScaler` ở dưới dùng StandardScaler rồi cắt ở ±5σ: ngoại lai vẫn được ghi
nhận là "rất lớn" nhưng không còn khống chế thang đo, và giá trị ở tập test vượt
ra ngoài phạm vi của tập train không còn là thảm hoạ vì z-score không bị chặn
cứng trong [0,1].
────────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

# Cột giá thô. Được giữ trong khung dữ liệu để tính nhãn % thay đổi giá, nhưng
# KHÔNG nằm trong ma trận đặc trưng đưa vào mạng.
TARGET_COLUMN = "Close"

# Ngưỡng cắt sau khi chuẩn hoá, tính theo độ lệch chuẩn.
CLIP_SIGMA = 5.0

# Đánh dấu phiên bản tập đặc trưng. `train_tft.py` ghi giá trị này vào tft_meta.json
# và so lại khi nạp checkpoint cũ — đổi tập đặc trưng mà tiếp tục huấn luyện từ
# trọng số cũ là trộn lẫn hai loại đầu vào khác nhau.
FEATURE_SET_VERSION = "stationary-v2"


# ══════════════════════════════════════════════════════════════════════════════
#  LÀM SẠCH DỮ LIỆU GIÁ
# ══════════════════════════════════════════════════════════════════════════════
#
# Hàm này trước đây nằm trong `train_tft.py`. Chuyển sang đây vì `forecaster.py`
# cũng phải làm sạch bằng ĐÚNG quy tắc đó trước khi dự báo — mà import
# `backend.train_tft` chỉ để lấy một hàm thì kéo theo cả TensorFlow vào tiến trình
# web. `train_tft.py` vẫn import lại từ đây nên mọi lời gọi cũ không đổi.

MAX_PLAUSIBLE_DAILY_RETURN = 1000.0


def clean_price_history(df: "pd.DataFrame") -> "pd.DataFrame":
    """
    Loại dữ liệu giá không hợp lệ TRƯỚC khi tính chỉ báo và dựng nhãn.

    VÌ SAO CẦN: lượt mở rộng lên 309 mã kéo theo vài file dữ liệu hỏng mà nhìn
    tổng quan không thấy được. Cụ thể đã gặp:

      - UNI-USD  : Yahoo ghép HAI tài sản khác nhau vào cùng một ký hiệu. Giá đứng
                   ở 0,000038 USD (volume 3) suốt nhiều tháng rồi nhảy thẳng lên
                   0,598 USD — tức 1.573.987% trong một phiên.
      - COMP-USD : 306 phiên giá bằng 0.
      - AAVE-USD : một dòng đầu rác (0,52 USD, volume 0) trước khi dữ liệu thật bắt
                   đầu ở 53 USD.

    Chỉ MỘT nhãn 1,5 triệu phần trăm cũng đủ khống chế hàm mất mát: lượt chạy thử
    cho loss tập train 9,43 trong khi tập validation chỉ 0,45 — chênh 20 lần theo
    chiều vô lý. Loại các mã hỏng đưa độ lệch chuẩn của nhãn từ 1330,95% xuống
    2,75%.

    Cách xử lý: bỏ dòng có giá không dương/không hữu hạn, rồi nếu vẫn còn bước nhảy
    bất khả thi thì GIỮ LẠI ĐOẠN LIÊN TỤC DÀI NHẤT không chứa bước nhảy nào — cách
    này xử được cả rác ở đầu file lẫn trường hợp file ghép hai tài sản ở giữa.
    """
    if "Close" not in df.columns:
        return df.iloc[0:0]

    close = pd.to_numeric(df["Close"], errors="coerce")
    df = df[np.isfinite(close) & (close > 0)]
    if len(df) < 2:
        return df

    close = pd.to_numeric(df["Close"], errors="coerce").values
    returns = np.abs((close[1:] - close[:-1]) / close[:-1] * 100.0)
    breaks = np.flatnonzero(returns > MAX_PLAUSIBLE_DAILY_RETURN)
    if len(breaks) == 0:
        return df

    # `breaks[k]` nghĩa là bước nhảy nằm giữa dòng breaks[k] và breaks[k]+1, nên các
    # đoạn liên tục là [0, b0], [b0+1, b1], ... [b_last+1, hết].
    bounds = [0] + [int(b) + 1 for b in breaks] + [len(df)]
    segments = [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]
    start, end = max(segments, key=lambda s: s[1] - s[0])
    return df.iloc[start:end]



def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Thêm chỉ báo kỹ thuật vào DataFrame OHLCV.
    Cần các cột: Open, High, Low, Close, Volume.
    Trả về một bản sao có thêm cột chỉ báo (cả dạng thô lẫn dạng đã khử đơn vị).
    """
    df = df.copy()

    close = df["Close"].astype(float)
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    volume = df["Volume"].astype(float) if "Volume" in df.columns else pd.Series(0.0, index=df.index)

    # Mẫu số dùng chung cho các tỷ lệ theo giá. Giá bằng 0 đã được
    # `train_tft.clean_price_history()` loại, nhưng các đường gọi khác
    # (backtest, biểu đồ) không đi qua đó nên vẫn phải phòng.
    close_nz = close.replace(0, np.nan)

    # ══════════════════════════════════════════════════════════════════════════
    #  CHỈ BÁO THÔ — giữ lại cho backtest và biểu đồ frontend
    # ══════════════════════════════════════════════════════════════════════════

    # ── RSI (Relative Strength Index) ────────────────────────────────────
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=13, adjust=False).mean()
    avg_loss = loss.ewm(com=13, adjust=False).mean()
    # Khi giá đứng yên hoàn toàn trong cả cửa sổ (hay gặp ở cổ phiếu VN thanh
    # khoản thấp và altcoin ít giao dịch), cả avg_gain lẫn avg_loss đều bằng 0 →
    # 0/0 = NaN, RSI thành NaN và những dòng đó bị dropna() loại bỏ âm thầm.
    # Mã có ít lịch sử vì thế có thể bị rơi khỏi báo cáo mà không ai biết lý do.
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))
    # avg_loss == 0: không có phiên giảm nào. Nếu cũng không có phiên tăng thì
    # coi như trung tính (50); nếu chỉ toàn tăng thì RSI đạt trần 100.
    df["RSI"] = df["RSI"].fillna(pd.Series(np.where(avg_gain > 0, 100.0, 50.0), index=df.index))

    # ── MACD ──────────────────────────────────────────────────────────────
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]

    # ── Bollinger Bands ──────────────────────────────────────────────────
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    df["BB_Upper"] = sma20 + (std20 * 2)
    df["BB_Lower"] = sma20 - (std20 * 2)
    df["BB_Width"] = (df["BB_Upper"] - df["BB_Lower"]) / sma20.replace(0, np.nan)

    # ── ATR (Average True Range) ──────────────────────────────────────────
    tr = pd.DataFrame({
        "hl": high - low,
        "hc": abs(high - close.shift(1)),
        "lc": abs(low - close.shift(1)),
    }).max(axis=1)
    df["ATR"] = tr.rolling(14).mean()

    # ── OBV (On-Balance Volume) ──────────────────────────────────────────
    obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()
    df["OBV"] = obv

    # ── Moving Averages ──────────────────────────────────────────────────
    for window in [5, 10, 20, 50]:
        df[f"MA{window}"] = close.rolling(window).mean()

    # ══════════════════════════════════════════════════════════════════════════
    #  ĐẶC TRƯNG DỪNG — đây mới là tập đầu vào của mô hình
    # ══════════════════════════════════════════════════════════════════════════

    # Thay cho `Close` thô. Biên độ ổn định ở mọi mức giá.
    df["Return_1d"] = close.pct_change() * 100

    # MACD quy về phần trăm giá: tách hình dạng tín hiệu khỏi mệnh giá tài sản.
    df["MACD_Pct"] = df["MACD"] / close_nz * 100
    df["MACD_Signal_Pct"] = df["MACD_Signal"] / close_nz * 100
    df["MACD_Hist_Pct"] = df["MACD_Hist"] / close_nz * 100

    # percent-B: vị trí của giá trong dải Bollinger. 0 = chạm dải dưới,
    # 1 = chạm dải trên. Thay thế cả BB_Upper lẫn BB_Lower; độ rộng dải đã được
    # BB_Width mang riêng nên không mất thông tin.
    bb_range = (df["BB_Upper"] - df["BB_Lower"]).replace(0, np.nan)
    df["BB_Position"] = (close - df["BB_Lower"]) / bb_range

    # Biến động thực tế tính theo phần trăm giá.
    df["ATR_Pct"] = df["ATR"] / close_nz * 100

    # OBV thô là tổng tích luỹ không có chặn trên — nó trôi vô hạn theo thời gian
    # và theo quy mô khối lượng của từng mã, nên là một trong những cột phi dừng
    # tệ nhất. Ở đây lấy phần lệch khỏi trung bình 20 phiên rồi chia cho khối lượng
    # trung bình (nhân √20 vì đây là tổng tích luỹ 20 phiên) → đại lượng không đơn vị.
    vol_ma20 = volume.rolling(20).mean().replace(0, np.nan)
    obv_osc = (obv - obv.rolling(20).mean()) / (vol_ma20 * np.sqrt(20))
    # Mã có khối lượng bằng 0 (một số mã .VN thanh khoản rất thấp) sẽ cho NaN ở
    # MỌI dòng, khiến dropna() xoá sạch mã đó khỏi tập huấn luyện mà không báo gì.
    # Trước đây OBV thô của các mã này là hằng số 0 nên chúng vẫn lọt qua. Gán 0
    # cho đúng trường hợp khối lượng không dùng được, giữ NaN cho các dòng đầu
    # chưa đủ cửa sổ (những dòng đó bị loại bởi MA50 rồi).
    df["OBV_Osc"] = obv_osc.where(vol_ma20.notna(), 0.0)

    # ── Tỷ lệ giá trên các đường trung bình ──────────────────────────────
    df["Close_to_MA5"] = close / df["MA5"].replace(0, np.nan)
    df["Close_to_MA10"] = close / df["MA10"].replace(0, np.nan)
    df["Close_to_MA20"] = close / sma20.replace(0, np.nan)
    df["Close_to_MA50"] = close / df["MA50"].replace(0, np.nan)

    # MA20/MA50 chuyển sang độ dốc thay vì mức: tỷ lệ giá/MA đã có ở trên, phần
    # thông tin còn lại của đường trung bình là hướng và tốc độ của nó.
    df["MA20_Slope"] = df["MA20"].pct_change(5) * 100
    df["MA50_Slope"] = df["MA50"].pct_change(10) * 100

    # ── Thống kê trượt ───────────────────────────────────────────────────
    df["Volatility_10d"] = close.pct_change().rolling(10).std() * 100
    df["Volatility_30d"] = close.pct_change().rolling(30).std() * 100
    df["Momentum_5d"] = close.pct_change(5) * 100
    df["Momentum_10d"] = close.pct_change(10) * 100

    # ── Đặc trưng thời gian ──────────────────────────────────────────────
    if hasattr(df.index, 'dayofweek'):
        df["DayOfWeek"] = df.index.dayofweek
        df["Month"] = df.index.month
        df["DayOfMonth"] = df.index.day
        df["IsMonthEnd"] = df.index.is_month_end.astype(int)
        df["IsQuarterEnd"] = df.index.is_quarter_end.astype(int)

    # Phép chia nào cũng có thể sinh ±inf khi mẫu số cực nhỏ. Đổi hết sang NaN để
    # dropna() ở `build_model_frame()` xử lý một lần, thay vì để inf chui vào
    # scaler và làm hỏng trung bình/độ lệch chuẩn của cả cột.
    df = df.replace([np.inf, -np.inf], np.nan)

    return df


def get_feature_columns() -> list:
    """
    Danh sách đặc trưng ĐẦU VÀO của mô hình — 21 cột, tất cả đều không có đơn vị.

    `Close` KHÔNG nằm trong danh sách này. Nó được `build_model_frame()` giữ riêng
    làm cột nhãn để tính % thay đổi giá.
    """
    return [
        # Động lượng và dao động
        "RSI", "Return_1d",
        # MACD dạng phần trăm giá
        "MACD_Pct", "MACD_Signal_Pct", "MACD_Hist_Pct",
        # Bollinger
        "BB_Position", "BB_Width",
        # Biến động và khối lượng
        "ATR_Pct", "OBV_Osc",
        # Quan hệ giá với đường trung bình
        "Close_to_MA5", "Close_to_MA10", "Close_to_MA20", "Close_to_MA50",
        "MA20_Slope", "MA50_Slope",
        # Thống kê trượt
        "Volatility_10d", "Volatility_30d",
        "Momentum_5d", "Momentum_10d",
        # Thời gian
        "DayOfWeek", "Month",
    ]


# Tập đặc trưng cũ, giữ lại để đối chiếu trong báo cáo và cho script kiểm chứng
# tính dừng. KHÔNG dùng để huấn luyện.
LEGACY_FEATURE_COLUMNS = [
    "RSI", "MACD", "MACD_Signal", "MACD_Hist",
    "BB_Upper", "BB_Lower", "BB_Width",
    "ATR", "OBV",
    "MA5", "MA10", "MA20", "MA50",
    "Volatility_10d", "Volatility_30d",
    "Momentum_5d", "Momentum_10d",
    "Close_to_MA20", "Close_to_MA50",
    "DayOfWeek", "Month",
]


def build_model_frame(df: pd.DataFrame, already_featured: bool = False):
    """
    Dựng khung dữ liệu chuẩn cho mô hình — MỘT nguồn sự thật duy nhất.

    Trước đây đoạn `all_cols = ["Close"] + feature_cols` được chép tay ở NĂM chỗ
    (train_tft, evaluate_tft, forecaster ×2, cron_accuracy_learner). Năm bản sao
    của cùng một quy ước chính là kiểu lỗi mà `split_indices()` đã được gom lại để
    tránh: chỉ cần một chỗ quên cập nhật là ma trận đầu vào lệch số cột so với lúc
    huấn luyện, và mô hình sẽ nhận sai đặc trưng mà không báo lỗi gì.

    Trả về `(frame, feature_cols)`:
        frame[TARGET_COLUMN]  giá thô — CHỈ để tính nhãn % thay đổi, không vào mạng
        frame[feature_cols]   ma trận đặc trưng dừng — đây mới là đầu vào của mạng

    Thứ tự cột trong `feature_cols` là cố định và phải khớp với thứ tự lúc huấn
    luyện, vì mạng chỉ nhận một mảng số không tên.
    """
    featured = df if already_featured else add_technical_indicators(df)

    feature_cols = [c for c in get_feature_columns() if c in featured.columns]
    if TARGET_COLUMN not in featured.columns:
        raise ValueError(f"Thiếu cột {TARGET_COLUMN!r} — không tính được nhãn.")

    cols = [TARGET_COLUMN] + feature_cols
    frame = featured[cols].replace([np.inf, -np.inf], np.nan).dropna()
    return frame, feature_cols


class FeatureScaler:
    """
    Chuẩn hoá đặc trưng: StandardScaler rồi cắt ở ±CLIP_SIGMA.

    Vì sao không dùng MinMaxScaler nữa: xem ghi chú ở đầu file. Tóm tắt là đặc
    trưng dạng % có đuôi dài, và MinMax để một ngoại lai duy nhất quyết định thang
    đo của cả cột.

    Vì sao vẫn cắt: z-score của một phiên +355% là khoảng 100σ. Không cắt thì giá
    trị đó vẫn khống chế gradient dù đã chuẩn hoá. Cắt ở 5σ giữ lại thông tin
    "phiên này rất bất thường" mà không để nó nuốt mất phần còn lại.

    Dùng chung ở cả huấn luyện, đánh giá và inference để ba nơi không thể lệch nhau.
    """

    def __init__(self, clip_sigma: float = CLIP_SIGMA):
        self.clip_sigma = clip_sigma
        self._scaler = StandardScaler()

    def fit(self, X) -> "FeatureScaler":
        self._scaler.fit(np.asarray(X, dtype=np.float64))
        return self

    def transform(self, X) -> np.ndarray:
        out = self._scaler.transform(np.asarray(X, dtype=np.float64))
        return np.clip(out, -self.clip_sigma, self.clip_sigma)

    def fit_transform(self, X) -> np.ndarray:
        return self.fit(X).transform(X)


def prepare_multivariate_data(df: pd.DataFrame, look_back: int = 60,
                              split_ratio: float = 0.8):
    """
    Dựng dataset đa biến cho việc thử nghiệm nhanh.

    LƯU Ý: nhãn ở đây là % THAY ĐỔI GIÁ của phiên kế tiếp, cùng ngữ nghĩa với
    `train_tft.TARGET_TYPE`. Bản cũ của hàm này trả về giá đã chuẩn hoá — dùng
    nhầm sẽ huấn luyện ra mô hình có ý nghĩa đầu ra khác hẳn phần còn lại của hệ
    thống. Đường huấn luyện chính thức vẫn là `backend/train_tft.py`.
    """
    frame, feature_cols = build_model_frame(df)

    if len(frame) < look_back + 10:
        raise ValueError(f"Dữ liệu quá ít sau khi tính chỉ báo: {len(frame)} dòng")

    # Scaler khớp CHỈ trên phần train.
    #
    # LỖI ĐÃ SỬA: bản cũ gọi `fit_transform` trên TOÀN BỘ khung rồi mới cắt 80/20,
    # nên trung bình/độ lệch chuẩn của 20% cuối tham gia vào chuẩn hoá của 80% đầu
    # — rò rỉ dữ liệu kinh điển, trong một hàm public không có cảnh báo nào. Bất kỳ
    # notebook thử nghiệm nào gọi hàm này đều cho ra con số đẹp hơn thực tế, và con
    # số đó rất dễ lọt vào chương "thử nghiệm" của báo cáo.
    n_rows = len(frame)
    split_row = int(n_rows * split_ratio)
    if split_row < look_back + 5 or n_rows - split_row < look_back + 5:
        raise ValueError(
            f"Không đủ dữ liệu để chia train/test: {n_rows} dòng, look_back={look_back}"
        )

    scaler = FeatureScaler()
    scaler.fit(frame[feature_cols].values[:split_row])
    scaled = scaler.transform(frame[feature_cols].values)
    closes = frame[TARGET_COLUMN].values.astype(np.float64)

    def _windows(lo: int, hi: int):
        xs, ys = [], []
        for i in range(lo, hi - look_back):
            last_close = closes[i + look_back - 1]
            next_close = closes[i + look_back]
            if last_close <= 0:
                continue
            xs.append(scaled[i : i + look_back])
            ys.append((next_close - last_close) / last_close * 100.0)
        return np.array(xs, dtype=np.float32), np.array(ys, dtype=np.float32)

    # Khoảng trống `look_back` ở ranh giới để cửa sổ cuối của train không chạm sang
    # vùng test — cùng nguyên tắc với SPLIT_GAP trong train_tft.py.
    X_train, Y_train = _windows(0, split_row)
    X_test, Y_test = _windows(split_row + look_back, n_rows)
    return X_train, Y_train, X_test, Y_test, scaler, feature_cols
