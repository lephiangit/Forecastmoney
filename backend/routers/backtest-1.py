"""
routers/backtest.py – Kiểm thử chiến lược trên dữ liệu quá khứ.

╔══════════════════════════════════════════════════════════════════════════════╗
║  LỖI PHƯƠNG PHÁP ĐÃ SỬA: BACKTEST KHÔNG CHẠY CHIẾN LƯỢC CỦA HỆ THỐNG        ║
╚══════════════════════════════════════════════════════════════════════════════╝

Bản trước chấm điểm RSI/MACD/Bollinger bằng một bộ trọng số RIÊNG, không liên quan
gì tới thứ mà `cron_auto_trader.py` thực sự dùng để vào lệnh (dự báo TFT +
SentimentFusion). Nghĩa là con số "chiến lược này lãi bao nhiêu" đang đo một chiến
lược KHÁC với chiến lược của sản phẩm — và đó chính là con số sẽ nằm trong báo cáo.

Ngoài ra nó không tính phí giao dịch lẫn trượt giá, nên không trả lời được câu hỏi
duy nhất mà một backtest cần trả lời: **có lãi sau chi phí không.**

Bản này:

  - `signal_source="model"` (mặc định) chạy ĐÚNG tín hiệu của hệ thống: dự báo
    quantile 1 bước của TFT, gác theo ngưỡng lợi nhuận kỳ vọng và theo độ chắc chắn
    của dải quantile, kèm cắt lỗ / chốt lời như bot thật.
  - `signal_source="technical"` giữ nguyên bộ RSI/MACD cũ, nhưng nay được gọi đúng
    tên: một BASELINE để đối chứng, không phải chiến lược của hệ thống. Có đủ hai
    con số cạnh nhau là một phần đóng góp tốt cho báo cáo.
  - Phí và trượt giá áp cho cả hai chiều, và được báo cáo tách riêng.

────────────────────────────────────────────────────────────────────────────────
BA GIỚI HẠN PHẢI NÊU TRONG BÁO CÁO — không giấu được bằng code

1. KHÔNG CÓ TÂM LÝ THỊ TRƯỜNG TRONG QUÁ KHỨ.
   Bot thật gác lệnh bằng `confidence` lấy từ phân tích tin tức của Model 2. Bảng
   `research_reports` chỉ có dữ liệu từ lúc hệ thống bắt đầu chạy, nên với một
   backtest 1-2 năm thì tâm lý thị trường ở hầu hết các phiên KHÔNG TỒN TẠI.
   Không được bịa ra nó. Ở đây cổng tâm lý được thay bằng cổng dựa trên dải
   quantile của chính TFT (xem `_model_signals`), và điều đó phải được nói rõ:
   backtest này đo phần TFT của chiến lược, không đo toàn bộ chiến lược.

2. MÔ HÌNH ĐÃ THẤY MỘT PHẦN GIAI ĐOẠN NÀY LÚC HUẤN LUYỆN.
   `global_tft.keras` được train trên 70% đầu lịch sử của mỗi mã. Backtest 90 ngày
   gần nhất thì rơi vào vùng test (an toàn), nhưng backtest 5 năm thì phần lớn cửa
   sổ nằm trong vùng TRAIN — kết quả sẽ đẹp giả tạo. Endpoint cảnh báo khi điều này
   xảy ra (`warnings` trong summary), nhưng không thể tự sửa.

3. ĐÂY LÀ MÔ PHỎNG, KHÔNG PHẢI GIAO DỊCH THẬT.
   Không có khớp lệnh từng phần, không có thanh khoản hữu hạn, không có biên độ
   giá trần/sàn của sàn VN. Lệnh được giả định khớp trọn vẹn ở giá mở cửa phiên kế
   tiếp.
────────────────────────────────────────────────────────────────────────────────
"""

from typing import List, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


# ══════════════════════════════════════════════════════════════════════════════
#  CHI PHÍ GIAO DỊCH
# ══════════════════════════════════════════════════════════════════════════════
#
# Mặc định lấy theo mức phổ biến ở thị trường Việt Nam và sàn crypto:
#   - Phí môi giới VN khoảng 0,15-0,35% mỗi chiều; sàn crypto khoảng 0,1%.
#   - Trượt giá với mã thanh khoản tốt khoảng 0,03-0,1%.
#
# Con số mặc định ở đây là mức THẬN TRỌNG VỪA PHẢI. Báo cáo nên chạy thêm một lượt
# với phí cao hơn để cho thấy chiến lược có bền với chi phí không.
DEFAULT_FEE_PCT = 0.1        # % mỗi chiều
DEFAULT_SLIPPAGE_PCT = 0.05  # % mỗi chiều


class BacktestRequest(BaseModel):
    # `trade_amount` ÂM từng làm hỏng cả phiên mô phỏng mà không báo lỗi: điều kiện
    # `balance >= trade_amount` luôn đúng, `qty` thành số âm, `balance -= total` lại
    # LÀM TĂNG số dư, và `position_qty` âm vĩnh viễn nên hai chốt chặn
    # `position_qty == 0` / `> 0` đều không bao giờ đúng nữa — vị thế ma đó không
    # bao giờ được đóng và làm sai lệch đường vốn cho tới hết phiên. API vẫn trả về
    # một báo cáo trông rất hợp lý.
    ticker: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9][A-Za-z0-9.\-]{0,19}$")
    days_back: int = Field(default=90, ge=7, le=3650)
    strategy: str = Field(default="balanced", pattern="^(conservative|balanced|aggressive)$")
    initial_balance: float = Field(default=10000.0, gt=0, le=100_000_000)
    trade_amount: float = Field(default=500.0, gt=0, le=100_000_000)

    signal_source: str = Field(
        default="model",
        pattern="^(model|technical)$",
        description="model = dự báo TFT (chiến lược của hệ thống). "
                    "technical = RSI/MACD (baseline đối chứng).",
    )
    fee_pct: float = Field(default=DEFAULT_FEE_PCT, ge=0, le=5,
                           description="Phí giao dịch mỗi chiều, tính bằng %.")
    slippage_pct: float = Field(default=DEFAULT_SLIPPAGE_PCT, ge=0, le=5,
                                description="Trượt giá mỗi chiều, tính bằng %.")
    stop_loss_pct: float = Field(default=5.0, ge=0, le=100)
    take_profit_pct: float = Field(default=15.0, ge=0, le=1000)


class BacktestTrade(BaseModel):
    date: str
    action: str        # BUY | SELL
    price: float
    quantity: float
    total: float
    balance_after: float
    reason: str
    fee: float = 0.0


class BacktestSummary(BaseModel):
    ticker: str
    strategy: str
    days_back: int
    initial_balance: float
    final_balance: float
    total_pnl: float
    total_pnl_pct: float
    total_trades: int
    win_trades: int
    loss_trades: int
    win_rate: float
    max_drawdown: float
    sharpe_ratio: float

    # ── Bổ sung: những thứ khiến con số đọc được ──
    signal_source: str = "model"
    bars_simulated: int = 0
    total_fees: float = 0.0
    total_slippage_cost: float = 0.0
    pnl_before_costs: float = 0.0
    buy_and_hold_pnl_pct: float = 0.0
    warnings: List[str] = []


class BacktestResponse(BaseModel):
    summary: BacktestSummary
    trades: List[BacktestTrade]
    equity_curve: List[dict]  # [{date, balance}]


# ══════════════════════════════════════════════════════════════════════════════
#  NGƯỠNG CHIẾN LƯỢC
# ══════════════════════════════════════════════════════════════════════════════
#
# Nhánh `model` dùng ĐÚNG ngưỡng lợi nhuận kỳ vọng của `cron_auto_trader.py`, để
# backtest và bot thật nói cùng một ngôn ngữ.
#
# `require_lower_quantile_positive` thay cho cổng `min_confidence` của bot: bot gác
# bằng độ tin cậy từ tin tức, thứ không tồn tại trong quá khứ (xem giới hạn #1 ở
# đầu file). Thay vào đó dùng chính đầu ra của TFT: chỉ mua khi cả phân vị BI QUAN
# (p10) cũng dương — tức mô hình không chỉ đoán tăng mà còn ít nghi ngờ. Đây là
# cách dùng có cơ sở của đầu ra quantile, không phải một con số bịa ra.
MODEL_STRATEGY_PARAMS = {
    "conservative": {"min_expected_return": 3.0, "require_lower_quantile_positive": True,
                     "position_scale": 0.7},
    "balanced":     {"min_expected_return": 1.5, "require_lower_quantile_positive": True,
                     "position_scale": 1.0},
    "aggressive":   {"min_expected_return": 0.5, "require_lower_quantile_positive": False,
                     "position_scale": 1.3},
}

# Baseline kỹ thuật — GIỮ NGUYÊN bộ trọng số cũ để số liệu cũ vẫn tái lập được.
TECHNICAL_STRATEGY_PARAMS = {
    "conservative": {"rsi_buy": 30, "rsi_sell": 70, "macd_weight": 0.8, "bb_weight": 0.7, "min_score": 2.5},
    "balanced":     {"rsi_buy": 35, "rsi_sell": 65, "macd_weight": 0.6, "bb_weight": 0.5, "min_score": 2.0},
    "aggressive":   {"rsi_buy": 40, "rsi_sell": 60, "macd_weight": 0.4, "bb_weight": 0.3, "min_score": 1.5},
}

# Giữ tên cũ để code/notebook cũ import không vỡ.
STRATEGY_PARAMS = TECHNICAL_STRATEGY_PARAMS


# ══════════════════════════════════════════════════════════════════════════════
#  TÍN HIỆU 1 — MÔ HÌNH (chiến lược thật của hệ thống)
# ══════════════════════════════════════════════════════════════════════════════

def _model_signals(
    df: pd.DataFrame,
    n_trading_bars: int,
    params: dict,
) -> pd.DataFrame:
    """
    Sinh tín hiệu từ dự báo quantile 1 bước của TFT.

    Trả về DataFrame chỉ gồm các phiên ĐƯỢC GIAO DỊCH, với các cột:
        signal (1/-1/0), reason, exp_return, q10, q90

    KHÔNG CÓ RÒ RỈ TƯƠNG LAI:
      - Scaler khớp CHỈ trên phần dữ liệu trước cửa sổ backtest.
      - Dự báo tại phiên t chỉ dùng cửa sổ [t-59, t]; quyết định ở phiên t được
        thực hiện ở giá MỞ CỬA phiên t+1 (xem vòng mô phỏng).
    """
    from backend.models.feature_engineering import (
        TARGET_COLUMN,
        FeatureScaler,
        build_model_frame,
        clean_price_history,
    )
    from backend.models.forecaster import LOOK_BACK, load_tft_model

    model = load_tft_model()
    if model is None:
        raise HTTPException(
            503,
            "Chưa có mô hình TFT (models/global_tft.keras). Huấn luyện bằng "
            "`python -m backend.train_tft --fresh`, hoặc chạy lại với "
            "signal_source=technical.",
        )

    cleaned = clean_price_history(df)
    frame, feature_cols = build_model_frame(cleaned)

    expected = getattr(model, "input_shape", (None, None, None))[-1]
    if expected is not None and expected != len(feature_cols):
        raise HTTPException(
            500,
            f"Checkpoint nhận {expected} đặc trưng nhưng tập đặc trưng hiện tại có "
            f"{len(feature_cols)}. Cần train lại: python -m backend.train_tft --fresh",
        )

    n_trading_bars = min(n_trading_bars, max(0, len(frame) - LOOK_BACK))
    if n_trading_bars < 5:
        raise HTTPException(
            400,
            f"Không đủ dữ liệu: sau khi tính chỉ báo còn {len(frame)} phiên, cần ít "
            f"nhất {LOOK_BACK + 5}. Chọn mã có lịch sử dài hơn hoặc giảm days_back.",
        )

    start = len(frame) - n_trading_bars   # vị trí phiên giao dịch đầu tiên

    # Scaler khớp trên phần TRƯỚC cửa sổ backtest — giống điều kiện lúc huấn luyện,
    # và quan trọng hơn: không để phân phối của giai đoạn sắp mô phỏng lọt vào
    # chuẩn hoá.
    fit_rows = frame[feature_cols].values[:start]
    if len(fit_rows) < LOOK_BACK:
        raise HTTPException(
            400,
            "Cửa sổ backtest chiếm gần hết lịch sử nên không còn dữ liệu để khớp "
            "scaler mà không rò rỉ. Giảm days_back.",
        )
    scaler = FeatureScaler()
    scaler.fit(fit_rows)
    scaled = scaler.transform(frame[feature_cols].values).astype(np.float32)

    # Dựng toàn bộ cửa sổ rồi predict MỘT LẦN theo lô — nhanh hơn hàng chục lần so
    # với gọi model.predict cho từng phiên.
    windows, positions = [], []
    for i in range(start, len(frame)):
        if i - LOOK_BACK + 1 < 0:
            continue
        windows.append(scaled[i - LOOK_BACK + 1 : i + 1])
        positions.append(i)

    if not windows:
        raise HTTPException(400, "Không dựng được cửa sổ dự báo nào.")

    preds = model.predict(np.asarray(windows, dtype=np.float32), verbose=0, batch_size=256)
    q = np.sort(preds[:, :3], axis=1)   # ràng buộc p10 <= p50 <= p90

    out = frame.iloc[positions][[TARGET_COLUMN]].copy()
    out["q10"] = q[:, 0]
    out["exp_return"] = q[:, 1]
    out["q90"] = q[:, 2]
    out["signal"] = 0
    out["reason"] = ""

    min_ret = params["min_expected_return"]
    need_q10 = params["require_lower_quantile_positive"]

    for pos in range(len(out)):
        r50 = float(out["exp_return"].iloc[pos])
        r10 = float(out["q10"].iloc[pos])
        r90 = float(out["q90"].iloc[pos])

        if r50 >= min_ret and (not need_q10 or r10 > 0):
            out.iloc[pos, out.columns.get_loc("signal")] = 1
            out.iloc[pos, out.columns.get_loc("reason")] = (
                f"TFT kỳ vọng {r50:+.2f}% (dải {r10:+.2f}%..{r90:+.2f}%)"
            )
        elif r50 <= -min_ret and (not need_q10 or r90 < 0):
            out.iloc[pos, out.columns.get_loc("signal")] = -1
            out.iloc[pos, out.columns.get_loc("reason")] = (
                f"TFT kỳ vọng {r50:+.2f}% (dải {r10:+.2f}%..{r90:+.2f}%)"
            )

    return out


# ══════════════════════════════════════════════════════════════════════════════
#  TÍN HIỆU 2 — BASELINE KỸ THUẬT (để đối chứng)
# ══════════════════════════════════════════════════════════════════════════════

def _generate_signals(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """
    Sinh tín hiệu MUA/BÁN từ chỉ báo kỹ thuật.

    ĐÂY LÀ BASELINE, KHÔNG PHẢI CHIẾN LƯỢC CỦA HỆ THỐNG. Bot thật vào lệnh theo dự
    báo TFT + SentimentFusion (xem `_model_signals`). Giữ lại vì có một baseline
    kỹ thuật để đặt cạnh là điều báo cáo cần.
    """
    df = df.copy()
    df["signal"] = 0  # 0 = hold, 1 = buy, -1 = sell
    df["reason"] = ""
    df["score"] = 0.0

    for i in range(1, len(df)):
        score = 0.0
        reasons = []

        rsi = df["RSI"].iloc[i] if pd.notna(df["RSI"].iloc[i]) else 50
        macd = df["MACD"].iloc[i] if pd.notna(df["MACD"].iloc[i]) else 0
        macd_signal = df["MACD_Signal"].iloc[i] if pd.notna(df["MACD_Signal"].iloc[i]) else 0
        close = df["Close"].iloc[i]
        bb_lower = df["BB_Lower"].iloc[i] if pd.notna(df["BB_Lower"].iloc[i]) else close
        bb_upper = df["BB_Upper"].iloc[i] if pd.notna(df["BB_Upper"].iloc[i]) else close
        ma20 = df["MA20"].iloc[i] if "MA20" in df.columns and pd.notna(df["MA20"].iloc[i]) else close
        ma50 = df["MA50"].iloc[i] if "MA50" in df.columns and pd.notna(df["MA50"].iloc[i]) else close

        # RSI signal
        if rsi < params["rsi_buy"]:
            score += 1.0
            reasons.append(f"RSI oversold ({rsi:.0f})")
        elif rsi > params["rsi_sell"]:
            score -= 1.0
            reasons.append(f"RSI overbought ({rsi:.0f})")

        # MACD: TÍNH THEO TRẠNG THÁI (macd so với đường tín hiệu ở ngày hiện tại),
        # KHÔNG chỉ tính đúng ngày xảy ra crossover.
        #
        # Bản cũ chỉ cộng/trừ điểm đúng ngày macd cắt qua signal — đó là một sự
        # kiện xảy ra đúng 1 ngày trong cả một xu hướng kéo dài nhiều tuần. Kết
        # hợp với việc RSI quá mua/quá bán và giá chạm dải Bollinger thường rơi
        # vào GIAI ĐOẠN KHÁC của chu kỳ giá (không phải đúng ngày cắt), nên 3
        # điều kiện gần như không bao giờ trùng ngày — dẫn tới 0 giao dịch suốt
        # nhiều tháng dù dữ liệu và code đều chạy đúng, không có lỗi nào cả.
        #
        # Sửa: cộng điểm mỗi ngày xu hướng MACD còn đang tăng/giảm (trạng thái),
        # cộng thêm điểm thưởng đúng ngày vừa cắt (giữ lại ý nghĩa "tín hiệu mới").
        prev_macd = df["MACD"].iloc[i-1] if pd.notna(df["MACD"].iloc[i-1]) else 0
        prev_signal = df["MACD_Signal"].iloc[i-1] if pd.notna(df["MACD_Signal"].iloc[i-1]) else 0
        if macd > macd_signal:
            score += params["macd_weight"]
            if prev_macd <= prev_signal:
                score += 0.2
                reasons.append("MACD bullish crossover")
            else:
                reasons.append("MACD > signal (xu hướng tăng)")
        elif macd < macd_signal:
            score -= params["macd_weight"]
            if prev_macd >= prev_signal:
                score -= 0.2
                reasons.append("MACD bearish crossover")
            else:
                reasons.append("MACD < signal (xu hướng giảm)")

        # Bollinger Band signal
        if close <= bb_lower:
            score += params["bb_weight"]
            reasons.append("Price at BB lower")
        elif close >= bb_upper:
            score -= params["bb_weight"]
            reasons.append("Price at BB upper")

        # MA crossover
        if ma20 > ma50:
            score += 0.3
            reasons.append("MA20 > MA50")
        elif ma20 < ma50:
            score -= 0.3
            reasons.append("MA20 < MA50")

        df.iloc[i, df.columns.get_loc("score")] = score

        if score >= params["min_score"]:
            df.iloc[i, df.columns.get_loc("signal")] = 1
            df.iloc[i, df.columns.get_loc("reason")] = " | ".join(reasons)
        elif score <= -params["min_score"]:
            df.iloc[i, df.columns.get_loc("signal")] = -1
            df.iloc[i, df.columns.get_loc("reason")] = " | ".join(reasons)

    return df


# ══════════════════════════════════════════════════════════════════════════════
#  ENDPOINT
# ══════════════════════════════════════════════════════════════════════════════

def _period_for(days_back: int) -> str:
    """
    LỖI ĐÃ SỬA — BẢNG TRA CỨU CHỈ KHỚP 5 GIÁ TRỊ.

    `days_back` được validate ge=7, le=3650, nhưng bảng cũ chỉ có {30,60,90,180,365}
    và mọi giá trị khác âm thầm rơi về "3mo". Gửi days_back=3650 → tải về ~63 phiên,
    điều kiện `len(df) > req.days_back` sai nên không cắt gì, rồi summary vẫn trả
    đúng 3650. Người đọc nhận một báo cáo "backtest 10 năm" với Sharpe và Max
    Drawdown tính trên 3 tháng dữ liệu.

    Nay ánh xạ theo NGƯỠNG, và cộng thêm phần đệm cho cửa sổ 60 phiên của mô hình
    cùng cửa sổ khởi động của các chỉ báo (MA50).
    """
    needed = days_back + 200  # đệm: LOOK_BACK 60 + MA50 + dư cho scaler
    if needed <= 30:
        return "1mo"
    if needed <= 90:
        return "3mo"
    if needed <= 180:
        return "6mo"
    if needed <= 365:
        return "1y"
    if needed <= 730:
        return "2y"
    if needed <= 1825:
        return "5y"
    return "max"


@router.post("/run", response_model=BacktestResponse)
def run_backtest(req: BacktestRequest):
    """Chạy mô phỏng chiến lược trên dữ liệu quá khứ."""
    from backend.models.feature_engineering import add_technical_indicators
    from backend.models.forecaster import fetch_ohlcv

    ticker = req.ticker.upper()
    warnings: List[str] = []

    df_raw = fetch_ohlcv(ticker, period=_period_for(req.days_back))
    if df_raw is None or df_raw.empty:
        raise HTTPException(404, f"Không lấy được dữ liệu lịch sử cho '{ticker}'.")

    fee_rate = req.fee_pct / 100.0
    slip_rate = req.slippage_pct / 100.0

    # ── Sinh tín hiệu ────────────────────────────────────────────────────────
    if req.signal_source == "model":
        params = MODEL_STRATEGY_PARAMS.get(req.strategy, MODEL_STRATEGY_PARAMS["balanced"])
        sig = _model_signals(df_raw, req.days_back, params)
        position_scale = params["position_scale"]

        _warn_if_in_training_window(ticker, sig, warnings)
        warnings.append(
            "Cổng tâm lý thị trường của bot thật KHÔNG có trong backtest này — "
            "research_reports không có dữ liệu quá khứ. Đã thay bằng cổng dải "
            "quantile của TFT. Backtest đo phần TFT của chiến lược, không đo toàn bộ."
        )
    else:
        params = TECHNICAL_STRATEGY_PARAMS.get(req.strategy, TECHNICAL_STRATEGY_PARAMS["balanced"])
        position_scale = 1.0
        try:
            featured = add_technical_indicators(df_raw)
        except Exception as e:
            raise HTTPException(500, f"Không tính được chỉ báo: {e}")
        featured = featured.dropna(subset=["RSI", "MACD", "MACD_Signal", "BB_Lower", "BB_Upper"])
        if len(featured) > req.days_back:
            featured = featured.iloc[-req.days_back:]
        sig = _generate_signals(featured, params)
        warnings.append(
            "signal_source=technical là BASELINE RSI/MACD để đối chứng, KHÔNG phải "
            "chiến lược mà bot thật đang chạy."
        )

    if sig.empty:
        raise HTTPException(400, "Không sinh được tín hiệu nào.")

    # ── Mô phỏng ─────────────────────────────────────────────────────────────
    trade_amount = req.trade_amount * position_scale
    balance = req.initial_balance
    position_qty = 0.0
    position_avg_cost = 0.0
    trades: List[BacktestTrade] = []
    equity_curve: List[dict] = []
    win_trades = loss_trades = 0
    total_fees = 0.0
    total_slippage = 0.0

    dates = list(sig.index)
    closes_raw = df_raw["Close"]
    opens_raw = df_raw["Open"] if "Open" in df_raw.columns else closes_raw

    def _exec_price(next_date, side: str):
        """
        Giá khớp lệnh: giá MỞ CỬA phiên kế tiếp, cộng/trừ trượt giá.

        Quyết định ở phiên t chỉ dùng thông tin tới hết phiên t, và lệnh khớp ở
        phiên t+1 — nên không có chuyện "giao dịch ở đúng cây nến vừa dùng để ra
        quyết định", một dạng lookahead rất dễ lọt.
        """
        try:
            base = float(opens_raw.loc[next_date])
            if not np.isfinite(base) or base <= 0:
                base = float(closes_raw.loc[next_date])
        except (KeyError, TypeError, ValueError):
            return None
        if not np.isfinite(base) or base <= 0:
            return None
        return base * (1 + slip_rate) if side == "BUY" else base * (1 - slip_rate)

    for k, date in enumerate(dates):
        close = float(sig["Close"].iloc[k]) if "Close" in sig.columns else float(closes_raw.loc[date])
        date_str = str(date.date()) if hasattr(date, "date") else str(date)
        signal = int(sig["signal"].iloc[k])
        reason = str(sig["reason"].iloc[k] or "")

        # Phiên cuối không có phiên kế tiếp để khớp lệnh.
        next_date = dates[k + 1] if k + 1 < len(dates) else None

        # ── Cắt lỗ / chốt lời, kiểm tra TRƯỚC tín hiệu mới ──
        if position_qty > 0 and position_avg_cost > 0 and next_date is not None:
            change_pct = (close - position_avg_cost) / position_avg_cost * 100
            exit_reason = None
            if req.stop_loss_pct > 0 and change_pct <= -req.stop_loss_pct:
                exit_reason = f"Cắt lỗ ({change_pct:.1f}%)"
            elif req.take_profit_pct > 0 and change_pct >= req.take_profit_pct:
                exit_reason = f"Chốt lời (+{change_pct:.1f}%)"

            if exit_reason:
                px = _exec_price(next_date, "SELL")
                if px:
                    gross = px * position_qty
                    fee = gross * fee_rate
                    balance += gross - fee
                    total_fees += fee
                    total_slippage += px * position_qty * slip_rate / (1 - slip_rate)
                    if px >= position_avg_cost:
                        win_trades += 1
                    else:
                        loss_trades += 1
                    trades.append(BacktestTrade(
                        date=str(next_date.date()) if hasattr(next_date, "date") else str(next_date),
                        action="SELL", price=round(px, 4), quantity=position_qty,
                        total=round(gross, 2), balance_after=round(balance, 2),
                        reason=exit_reason, fee=round(fee, 4),
                    ))
                    position_qty = 0.0
                    position_avg_cost = 0.0

        # ── Tín hiệu ──
        if signal == 1 and position_qty == 0 and next_date is not None:
            px = _exec_price(next_date, "BUY")
            if px:
                qty = trade_amount / px
                gross = px * qty
                fee = gross * fee_rate
                if qty > 0 and balance >= gross + fee:
                    balance -= gross + fee
                    total_fees += fee
                    total_slippage += gross * slip_rate / (1 + slip_rate)
                    position_qty = qty
                    position_avg_cost = px
                    trades.append(BacktestTrade(
                        date=str(next_date.date()) if hasattr(next_date, "date") else str(next_date),
                        action="BUY", price=round(px, 4), quantity=qty,
                        total=round(gross, 2), balance_after=round(balance, 2),
                        reason=reason, fee=round(fee, 4),
                    ))

        elif signal == -1 and position_qty > 0 and next_date is not None:
            px = _exec_price(next_date, "SELL")
            if px:
                gross = px * position_qty
                fee = gross * fee_rate
                balance += gross - fee
                total_fees += fee
                total_slippage += gross * slip_rate / (1 - slip_rate)
                if px >= position_avg_cost:
                    win_trades += 1
                else:
                    loss_trades += 1
                trades.append(BacktestTrade(
                    date=str(next_date.date()) if hasattr(next_date, "date") else str(next_date),
                    action="SELL", price=round(px, 4), quantity=position_qty,
                    total=round(gross, 2), balance_after=round(balance, 2),
                    reason=reason, fee=round(fee, 4),
                ))
                position_qty = 0.0
                position_avg_cost = 0.0

        equity_curve.append({"date": date_str, "balance": round(balance + position_qty * close, 2)})

    # ── Đóng vị thế còn lại ở giá cuối ──
    if position_qty > 0:
        last_close = float(closes_raw.loc[dates[-1]])
        px = last_close * (1 - slip_rate)
        gross = px * position_qty
        fee = gross * fee_rate
        balance += gross - fee
        total_fees += fee
        if px >= position_avg_cost:
            win_trades += 1
        else:
            loss_trades += 1
        trades.append(BacktestTrade(
            date=str(dates[-1].date()) if hasattr(dates[-1], "date") else str(dates[-1]),
            action="SELL", price=round(px, 4), quantity=position_qty,
            total=round(gross, 2), balance_after=round(balance, 2),
            reason="Kết thúc backtest — đóng vị thế bắt buộc", fee=round(fee, 4),
        ))
        position_qty = 0.0
        if equity_curve:
            equity_curve[-1]["balance"] = round(balance, 2)

    # ── Chỉ số ───────────────────────────────────────────────────────────────
    total_trades = win_trades + loss_trades
    win_rate = (win_trades / total_trades * 100) if total_trades else 0.0
    total_pnl = balance - req.initial_balance
    total_pnl_pct = (total_pnl / req.initial_balance * 100) if req.initial_balance > 0 else 0.0
    total_costs = total_fees + total_slippage

    equities = np.array([e["balance"] for e in equity_curve], dtype=float) if equity_curve else np.array([])
    max_dd = 0.0
    if equities.size:
        peak = equities[0]
        for eq in equities:
            peak = max(peak, eq)
            if peak > 0:
                max_dd = max(max_dd, (peak - eq) / peak * 100)

    sharpe = 0.0
    if equities.size > 1:
        prev = equities[:-1]
        safe = np.where(prev == 0, np.nan, prev)
        daily = np.diff(equities) / safe
        daily = daily[np.isfinite(daily)]
        if daily.size > 1 and daily.std() > 0:
            sharpe = float(daily.mean() / daily.std() * np.sqrt(252))

    # Mua-và-giữ trên cùng cửa sổ: mốc so sánh tối thiểu mà mọi chiến lược phải
    # vượt qua thì mới đáng gọi là chiến lược.
    buy_hold_pct = 0.0
    try:
        first_px = float(closes_raw.loc[dates[0]])
        last_px = float(closes_raw.loc[dates[-1]])
        if first_px > 0:
            buy_hold_pct = (last_px - first_px) / first_px * 100
    except (KeyError, IndexError, TypeError, ValueError):
        pass

    if total_trades == 0:
        warnings.append(
            "Không có giao dịch nào khớp trong cửa sổ này — ngưỡng chiến lược có thể "
            "quá chặt so với biên độ của mã. Thử strategy=aggressive hoặc kéo dài days_back."
        )
    if total_pnl_pct < buy_hold_pct:
        warnings.append(
            f"Chiến lược ({total_pnl_pct:+.2f}%) THUA mua-và-giữ ({buy_hold_pct:+.2f}%) "
            "trên cùng giai đoạn. Đây là con số phải nêu trung thực trong báo cáo."
        )

    summary = BacktestSummary(
        ticker=ticker,
        strategy=req.strategy,
        days_back=req.days_back,
        initial_balance=req.initial_balance,
        final_balance=round(balance, 2),
        total_pnl=round(total_pnl, 2),
        total_pnl_pct=round(total_pnl_pct, 2),
        total_trades=total_trades,
        win_trades=win_trades,
        loss_trades=loss_trades,
        win_rate=round(win_rate, 1),
        max_drawdown=round(max_dd, 2),
        sharpe_ratio=round(float(sharpe), 2),
        signal_source=req.signal_source,
        # Số phiên THỰC SỰ mô phỏng, không phải con số người dùng gửi lên — bản cũ
        # trả lại đúng `days_back` kể cả khi chỉ chạy trên 63 phiên.
        bars_simulated=len(dates),
        total_fees=round(total_fees, 2),
        total_slippage_cost=round(total_slippage, 2),
        pnl_before_costs=round(total_pnl + total_costs, 2),
        buy_and_hold_pnl_pct=round(buy_hold_pct, 2),
        warnings=warnings,
    )

    return BacktestResponse(summary=summary, trades=trades, equity_curve=equity_curve)


def _warn_if_in_training_window(ticker: str, sig: pd.DataFrame, warnings: List[str]) -> None:
    """
    Cảnh báo khi cửa sổ backtest lấn vào vùng TRAIN của mô hình.

    `global_tft.keras` học trên 70% đầu lịch sử mỗi mã. Backtest vài tháng gần nhất
    thì nằm gọn trong vùng test (an toàn); backtest nhiều năm thì phần lớn cửa sổ
    nằm trong vùng mô hình ĐÃ HỌC, và kết quả sẽ đẹp một cách vô nghĩa.
    """
    try:
        import json
        import os

        from backend.train_tft import MODELS_DIR, TRAIN_RATIO

        meta_path = os.path.join(MODELS_DIR, "tft_meta.json")
        if not os.path.exists(meta_path):
            return
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)

        if ticker not in set(meta.get("tickers_used") or []):
            warnings.append(
                f"{ticker} KHÔNG nằm trong tập huấn luyện của mô hình — đây là đánh "
                "giá zero-shot. Ghi rõ điều này khi so sánh với các mã đã huấn luyện."
            )
            return

        from backend.models.feature_engineering import build_model_frame, clean_price_history
        from backend.models.forecaster import fetch_ohlcv

        full = fetch_ohlcv(ticker, period="max")
        if full is None or full.empty:
            return
        frame, _ = build_model_frame(clean_price_history(full))
        train_end_date = frame.index[int(len(frame) * TRAIN_RATIO) - 1]

        overlap = sum(1 for d in sig.index if d <= train_end_date)
        if overlap:
            pct = overlap / len(sig) * 100
            warnings.append(
                f"{pct:.0f}% số phiên trong cửa sổ backtest nằm trong vùng mô hình ĐÃ "
                f"HỌC (tới {train_end_date.date()}). Kết quả bị thổi phồng — giảm "
                "days_back để cửa sổ nằm gọn sau mốc đó."
            )
    except Exception:
        # Cảnh báo là thứ có thì tốt; không được để nó làm hỏng cả endpoint.
        pass
