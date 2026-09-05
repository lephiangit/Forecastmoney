"""
routers/forecast.py – Dự báo giá thời gian thực.

Thay đổi:

1. **Không còn tạo `threading.Thread` thủ công** để ghi log dự báo. Mỗi request tạo
   một thread rời không ai quản lý; dưới tải cao chúng tích tụ và không có cách nào
   theo dõi. Nay dùng `BackgroundTasks` của FastAPI — chạy sau khi response đã gửi,
   trong vòng đời do framework quản lý.

2. **Mã tài sản được kiểm tra định dạng** trước khi đưa vào yfinance hay câu query.

3. **Khoá `research` luôn có mặt** trong phản hồi (do `run_combined_forecast` đảm bảo),
   nên phía gọi không cần phòng thủ bằng `.get()` lồng nhiều lớp.

Mọi endpoint để `def` (không phải `async def`) để FastAPI chạy trong threadpool:
yfinance và TensorFlow đều là blocking, chạy thẳng trên event loop sẽ làm đơ server.
"""

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from backend.models.forecaster import (
    fetch_ohlcv,
    get_live_quote,
    run_combined_forecast,
    run_tft_forecast,
)
from backend.security import validate_ticker_format

router = APIRouter()

MAX_FORECAST_DAYS = 30
# Vì sao chặn ở 30 chứ không phải 60 như trước: dự báo tự hồi quy dùng chính đầu ra
# của bước trước làm đầu vào bước sau, nên sai số tích luỹ theo cấp số nhân.
# Quá mốc này con số trả về trông vẫn "đẹp" nhưng không còn giá trị tham chiếu,
# và trình bày chúng như một dự báo nghiêm túc là điều không trung thực.


def _log_prediction(ticker: str, model_name: str, date: str, price: float) -> None:
    """Ghi lại dự báo T+1 để job đánh giá đối chiếu với giá thực tế sau này."""
    try:
        from backend.database import save_accuracy_prediction

        save_accuracy_prediction(ticker, model_name, date, price)
    except Exception as e:
        print(f"[forecast] Không ghi được dự báo để đánh giá: {type(e).__name__}")


@router.get("/combined/{ticker}")
def combined_forecast(
    ticker: str,
    background_tasks: BackgroundTasks,
    days: int = Query(default=7, ge=1, le=MAX_FORECAST_DAYS),
    refresh: bool = Query(default=False, description="Bỏ qua cache, tính lại từ đầu"),
):
    """
    Pipeline đầy đủ: tin tức → TFT → SentimentFusion.

    Kết quả được cache 6 tiếng vì cả hai đầu vào (giá theo ngày, tin tức RSS) đều
    không đổi nhanh hơn thế, trong khi mỗi lượt tính tốn một lượt gọi LLM và
    vài giây inference trên CPU của gói free.
    """
    from backend.database import get_forecast_cache, save_forecast_cache

    clean_ticker = validate_ticker_format(ticker)

    if not refresh:
        cached = get_forecast_cache(clean_ticker, days)
        if cached:
            cached["cached"] = True
            return cached

    from backend.agents.research_agent import analyze_market

    live = get_live_quote(clean_ticker)
    price_info = f"Giá: {live['price']:,.4f}" if live else ""

    research = analyze_market(clean_ticker, price_info)
    result = run_combined_forecast(clean_ticker, days, research)

    if result["current_price"] is None:
        raise HTTPException(404, f"Không lấy được dữ liệu cho mã '{clean_ticker}'.")

    result["live"] = live
    result["cached"] = False

    save_forecast_cache(clean_ticker, days, result)

    # Ghi lai dự báo T+1 của CẢ HAI mô hình. Bản cũ chỉ ghi "sentiment_fusion",
    # nên bảng "Độ chính xác mô hình" không bao giờ có dòng nào của TFT — trong khi
    # TFT mới là mô hình chính của đồ án. Ghi cả hai trên cùng một ngày dự báo cho
    # phép so sánh trực tiếp: sentiment fusion có thực sự cải thiện được TFT không.
    tft = result.get("tft") or {}
    if tft.get("median"):
        first = tft["median"][0]
        background_tasks.add_task(
            _log_prediction, clean_ticker, "tft", first["date"], first["price"]
        )

    sf = result.get("sentiment_fusion") or {}
    if sf.get("median"):
        first = sf["median"][0]
        background_tasks.add_task(
            _log_prediction, clean_ticker, "sentiment_fusion", first["date"], first["price"]
        )

    return result


@router.get("/tft/{ticker}")
def tft_only_forecast(
    ticker: str,
    background_tasks: BackgroundTasks,
    days: int = Query(default=7, ge=1, le=MAX_FORECAST_DAYS),
):
    """Chỉ chạy TFT — nhanh hơn vì bỏ qua bước lấy tin tức và gọi LLM."""
    clean_ticker = validate_ticker_format(ticker)

    df = fetch_ohlcv(clean_ticker, period="2y")
    if df is None:
        raise HTTPException(404, f"Không lấy được dữ liệu cho mã '{clean_ticker}'.")

    median, lower, upper = run_tft_forecast(clean_ticker, days, df)
    if median is None:
        raise HTTPException(
            503,
            "Mô hình TFT chưa sẵn sàng. Chạy backend/train_tft.py để huấn luyện trước.",
        )

    def to_list(series):
        return (
            None
            if series is None
            else [{"date": str(d.date()), "price": round(float(v), 6)} for d, v in series.items()]
        )

    live = get_live_quote(clean_ticker)
    forecast = {
        "median": to_list(median),
        "lower_q10": to_list(lower),
        "upper_q90": to_list(upper),
    }

    if forecast["median"]:
        first = forecast["median"][0]
        background_tasks.add_task(_log_prediction, clean_ticker, "tft", first["date"], first["price"])

    from datetime import datetime

    return {
        "ticker": clean_ticker,
        "model": "TFT",
        "days": days,
        "current_price": live["price"] if live else float(df["Close"].iloc[-1]),
        "forecast": forecast,
        "generated_at": datetime.now().isoformat(),
    }


@router.get("/accuracy/{ticker}")
def forecast_accuracy(
    ticker: str,
    model: str = Query(default="tft", pattern="^(tft|sentiment_fusion)$"),
    limit: int = Query(default=30, ge=1, le=100),
):
    """
    Lịch sử sai số dự báo của một mã.

    Đây là chỉ số duy nhất được lưu lâu dài — chính là số liệu dùng để chứng minh
    chất lượng mô hình trong báo cáo đồ án.
    """
    from backend.database import _get_client

    clean_ticker = validate_ticker_format(ticker)
    c = _get_client()
    if c is None:
        return {"ticker": clean_ticker, "model": model, "records": [], "summary": None, "db_available": False}

    try:
        res = (
            c.table("model_accuracy")
            .select("*")
            .eq("ticker", clean_ticker)
            .eq("model_name", model)
            .not_.is_("actual_price", "null")
            .order("forecast_date", desc=True)
            .limit(limit)
            .execute()
        )
        records = res.data or []

        errors = [float(r["error_pct"]) for r in records if r.get("error_pct") is not None]
        summary = None
        if errors:
            summary = {
                "count": len(errors),
                "mape": round(sum(errors) / len(errors), 2),
                "best": round(min(errors), 2),
                "worst": round(max(errors), 2),
            }

        return {
            "ticker": clean_ticker,
            "model": model,
            "records": records,
            "summary": summary,
            "db_available": True,
        }
    except Exception as e:
        print(f"[forecast] Lỗi lấy lịch sử sai số: {type(e).__name__}")
        return {"ticker": clean_ticker, "model": model, "records": [], "summary": None, "db_available": True}


@router.get("/feature-importance/{ticker}")
def feature_importance(ticker: str):
    """
    Permutation importance cho dự báo T+1 của mã này.

    ĐÍNH CHÍNH: đây KHÔNG phải trọng số của lớp VariableSelectionNetwork —
    lớp đó tồn tại trong backend/models/tft_model.py nhưng build_tft_model()
    không hề gọi tới nó, nên nó chưa từng ảnh hưởng dự báo nào. Xem docstring
    của compute_feature_importance() trong forecaster.py để biết chi tiết
    phương pháp thực tế đang dùng (permutation importance).
    """
    from backend.models.forecaster import compute_feature_importance

    clean_ticker = validate_ticker_format(ticker)
    result = compute_feature_importance(clean_ticker)
    if result is None:
        raise HTTPException(
            404,
            f"Không tính được feature importance cho '{clean_ticker}' "
            "(thiếu dữ liệu lịch sử hoặc model TFT chưa được nạp).",
        )
    return {
        "ticker": clean_ticker,
        "method": "permutation_importance_next_day",
        "note": "Đo mức ảnh hưởng thực nghiệm, không phải trọng số Variable Selection Network.",
        "features": result,
    }
