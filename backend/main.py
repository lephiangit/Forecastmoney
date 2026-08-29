"""
main.py – FastAPI application entry point.

Thay đổi so với bản trước:
  - Chặn khởi động ở production nếu secret/CORS chưa được cấu hình an toàn
  - Tắt /docs và /redoc ở production
  - Rate limiting toàn cục theo IP
  - Global exception handler: không để lọt stack trace ra client
  - Các chu kỳ job nền được đặt tên hằng số ở một chỗ, dễ tinh chỉnh
"""

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime

# Đảm bảo thư mục gốc dự án nằm trong sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.config import settings
from backend.metrics import metrics
from backend.routers import admin, auth, backtest, chat, forecast, market, notifications, research
from backend.security import get_client_ip, rate_limiter

# ── Chu kỳ các job nền (giây) ─────────────────────────────────────────────────
# Đặt tập trung ở đây để tinh chỉnh mà không phải lục trong lifespan.
# Lưu ý: yfinance không có SLA cho việc gọi dày đặc — hạ các số này xuống quá thấp
# sẽ khiến IP của Render bị chặn tạm thời.
AUTO_TRADE_INTERVAL = 60
SNAPSHOT_INTERVAL = 3600
MODEL_EVAL_INTERVAL = 3600
PRICE_ALERT_INTERVAL = 60
WS_BROADCAST_INTERVAL = 10


# ══════════════════════════════════════════════════════════════════════════════
#  WEBSOCKET MANAGER
# ══════════════════════════════════════════════════════════════════════════════

class PriceWSManager:
    """Quản lý các kết nối WebSocket cho luồng giá real-time."""

    # Chặn client đăng ký quá nhiều mã để một kết nối không kéo cả server đi fetch.
    MAX_SUBSCRIPTIONS_PER_CLIENT = 25
    MAX_CONNECTIONS = 200

    def __init__(self):
        self.connections: list[WebSocket] = []
        self.subscriptions: dict[WebSocket, set[str]] = {}

    async def connect(self, ws: WebSocket) -> bool:
        if len(self.connections) >= self.MAX_CONNECTIONS:
            await ws.close(code=1013)  # try again later
            return False
        await ws.accept()
        self.connections.append(ws)
        self.subscriptions[ws] = set()
        return True

    def disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)
        self.subscriptions.pop(ws, None)

    def subscribe(self, ws: WebSocket, tickers: list[str]):
        if ws not in self.subscriptions:
            return
        clean = {
            str(t).upper()[:20]
            for t in tickers[: self.MAX_SUBSCRIPTIONS_PER_CLIENT]
            if isinstance(t, str) and t.strip()
        }
        self.subscriptions[ws] = clean

    async def broadcast(self, prices: dict):
        dead = []
        for ws in self.connections:
            try:
                subs = self.subscriptions.get(ws, set())
                filtered = {k: v for k, v in prices.items() if k in subs} if subs else prices
                if filtered:
                    await ws.send_json({"type": "prices", "data": filtered})
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


ws_manager = PriceWSManager()


# ══════════════════════════════════════════════════════════════════════════════
#  BACKGROUND JOBS
# ══════════════════════════════════════════════════════════════════════════════

def _take_portfolio_snapshots():
    """Lưu snapshot số dư hằng ngày cho mọi user."""
    from backend.database import _get_client, save_portfolio_snapshot

    c = _get_client()
    if not c:
        return
    try:
        res = c.table("admin_config").select("user_id, current_balance, total_pnl").execute()
        for row in res.data or []:
            save_portfolio_snapshot(
                user_id=row["user_id"],
                balance=row.get("current_balance", 0),
                total_pnl=row.get("total_pnl", 0),
            )
        print(f"[snapshot] Đã lưu snapshot cho {len(res.data or [])} user.")
    except Exception as e:
        print(f"[snapshot] Lỗi: {e}")


def _evaluate_model_predictions():
    """
    Đối chiếu dự báo cũ với giá thực tế.

    Lưu ý: dùng giá đóng cửa của ĐÚNG ngày được dự báo (fetch lịch sử), không dùng
    giá live hiện tại — vì một dự báo cho T+1 được đánh giá vài ngày sau đó mà lấy
    giá hôm nay thì sai số đo được sẽ vô nghĩa.
    """
    import pandas as pd

    from backend.database import get_pending_evaluations, update_accuracy_evaluation
    from backend.models.forecaster import fetch_ohlcv

    pending = get_pending_evaluations()
    if not pending:
        return

    print(f"[accuracy] Đang đánh giá {len(pending)} dự báo...")

    # Gom theo ticker để mỗi mã chỉ fetch lịch sử một lần.
    by_ticker: dict = {}
    for record in pending:
        by_ticker.setdefault(record["ticker"], []).append(record)

    for ticker, records in by_ticker.items():
        df = fetch_ohlcv(ticker, period="3mo")
        if df is None or df.empty:
            continue
        df.index = df.index.normalize()

        for record in records:
            try:
                target_date = pd.to_datetime(record["forecast_date"]).normalize()
                if target_date not in df.index:
                    continue  # Phiên đó chưa có dữ liệu (ngày nghỉ, hoặc chưa tới)
                actual = float(df.loc[target_date, "Close"])
                predicted = float(record["predicted_price"])
                if actual <= 0:
                    continue
                error_pct = abs(actual - predicted) / actual * 100
                update_accuracy_evaluation(record["id"], actual, error_pct)
                print(
                    f"[accuracy] {ticker} {record['forecast_date']}: "
                    f"dự báo={predicted:.2f} thực tế={actual:.2f} sai số={error_pct:.2f}%"
                )
            except Exception as e:
                print(f"[accuracy] Lỗi khi đánh giá {ticker}: {e}")


def _check_price_alerts():
    """Kiểm tra các cảnh báo giá đang bật và tạo notification khi chạm ngưỡng."""
    from backend.database import _get_client
    from backend.models.forecaster import get_live_quote

    c = _get_client()
    if not c:
        return

    try:
        res = c.table("price_alerts").select("*").eq("is_triggered", False).execute()
        alerts = res.data or []
        if not alerts:
            return

        price_cache: dict = {}
        triggered_count = 0

        for alert in alerts:
            ticker = alert["ticker"]
            if ticker not in price_cache:
                live = get_live_quote(ticker)
                if not live:
                    continue
                price_cache[ticker] = live["price"]

            current_price = price_cache[ticker]
            target_price = float(alert["target_price"])
            condition = alert["condition"]

            triggered = (condition == "above" and current_price >= target_price) or (
                condition == "below" and current_price <= target_price
            )
            if not triggered:
                continue

            c.table("price_alerts").update(
                {"is_triggered": True, "triggered_at": datetime.now().isoformat()}
            ).eq("id", alert["id"]).execute()

            direction = "vượt lên trên" if condition == "above" else "giảm xuống dưới"
            c.table("notifications").insert(
                {
                    "user_id": alert["user_id"],
                    "title": f"Cảnh báo giá: {ticker}",
                    "message": (
                        f"{ticker} đã {direction} ${target_price:,.2f}. "
                        f"Giá hiện tại: ${current_price:,.2f}"
                    ),
                    "is_read": False,
                }
            ).execute()
            triggered_count += 1

        if triggered_count:
            print(f"[alerts] {triggered_count} cảnh báo giá đã được kích hoạt.")
    except Exception as e:
        print(f"[alerts] Lỗi: {e}")


# Danh sách mã luôn được stream sẵn cho client chưa subscribe gì.
WS_DEFAULT_TICKERS = [
    "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "ADA-USD",
    "XRP-USD", "DOGE-USD", "AVAX-USD", "AAPL", "NVDA", "TSLA",
]


def _fetch_live_prices_for_ws() -> dict:
    """
    Lấy giá cho các mã đang được stream.

    `get_live_quote` có cache TTL nội bộ (xem forecaster.py) nên vòng lặp này
    không tạo ra một lượt gọi yfinance cho mỗi chu kỳ broadcast.
    """
    from concurrent.futures import ThreadPoolExecutor

    from backend.models.forecaster import get_live_quote

    all_subs: set = set()
    for subs in ws_manager.subscriptions.values():
        all_subs.update(subs)

    tickers_to_fetch = list(set(WS_DEFAULT_TICKERS) | all_subs)[:25]

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(get_live_quote, tickers_to_fetch))

    prices = {}
    for ticker, q in zip(tickers_to_fetch, results):
        if q:
            prices[ticker] = {
                "price": q["price"],
                "change": q.get("change", 0),
                "change_pct": q.get("change_pct", 0),
                "volume": q.get("volume", 0),
            }
    return prices


# ══════════════════════════════════════════════════════════════════════════════
#  LIFESPAN
# ══════════════════════════════════════════════════════════════════════════════

async def _run_periodically(fn, interval: int, label: str):
    """Chạy một hàm đồng bộ theo chu kỳ trong threadpool, không chặn event loop."""
    while True:
        try:
            await asyncio.to_thread(fn)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[{label}] Lỗi vòng lặp: {e}")
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"ForecastAI API khởi động (environment={settings.environment})...")
    print(f"CORS cho phép các origin: {', '.join(settings.origin_list)}")

    # Các vấn đề không chặn khởi động nhưng làm hỏng chức năng. In rõ ở đây để
    # không phải mò trong lúc demo — triệu chứng của chúng thường rất dễ gây hiểu lầm.
    for warning in settings.startup_warnings():
        print(f"  [CẢNH BÁO] {warning}")

    # Nạp sẵn TFT vào RAM để request đầu tiên không phải chờ load model.
    try:
        from backend.models.forecaster import load_tft_model

        load_tft_model()
    except Exception as e:
        print(f"[startup] Bỏ qua preload TFT: {e}")

    async def ws_broadcast_loop():
        while True:
            try:
                if ws_manager.connections:
                    prices = await asyncio.to_thread(_fetch_live_prices_for_ws)
                    if prices:
                        await ws_manager.broadcast(prices)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"[ws] Lỗi broadcast: {e}")
            await asyncio.sleep(WS_BROADCAST_INTERVAL)

    from backend.cron_auto_trader import run_auto_trade

    tasks = [
        asyncio.create_task(_run_periodically(run_auto_trade, AUTO_TRADE_INTERVAL, "auto-trade")),
        asyncio.create_task(_run_periodically(_take_portfolio_snapshots, SNAPSHOT_INTERVAL, "snapshot")),
        asyncio.create_task(_run_periodically(_evaluate_model_predictions, MODEL_EVAL_INTERVAL, "accuracy")),
        asyncio.create_task(_run_periodically(_check_price_alerts, PRICE_ALERT_INTERVAL, "alerts")),
        asyncio.create_task(ws_broadcast_loop()),
    ]

    yield

    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    print("ForecastAI API đã dừng.")


# ══════════════════════════════════════════════════════════════════════════════
#  APP
# ══════════════════════════════════════════════════════════════════════════════

# Chặn khởi động nếu cấu hình production không an toàn.
# Thà app không lên còn hơn lên với secret mặc định và CORS mở toang.
_config_problems = settings.validate_for_production()
if _config_problems:
    print("\n" + "=" * 70)
    print("KHỞI ĐỘNG BỊ CHẶN — cấu hình production chưa an toàn:")
    for p in _config_problems:
        print(f"  - {p}")
    print("=" * 70 + "\n")
    raise RuntimeError("Cấu hình production không an toàn. Xem chi tiết ở log phía trên.")

app = FastAPI(
    title="ForecastAI API",
    description="Market research + AI-powered crypto/stock forecasting",
    version="2.0.0",
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
    lifespan=lifespan,
)

# ── Rate limiting toàn cục ────────────────────────────────────────────────────

# Các nhóm endpoint có chi phí khác nhau nên có hạn mức khác nhau.
_EXPENSIVE_PREFIXES = ("/forecast", "/research", "/backtest", "/chat")
_AUTH_PREFIXES = ("/auth/login", "/auth/register", "/auth/forgot-password", "/auth/reset-password")


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path

    # Health check và preflight không tính vào hạn mức.
    if request.method == "OPTIONS" or path in ("/", "/health"):
        return await call_next(request)

    if path.startswith(_AUTH_PREFIXES):
        bucket, limit = "auth", settings.rate_limit_auth
    elif path.startswith(_EXPENSIVE_PREFIXES):
        bucket, limit = "expensive", settings.rate_limit_expensive
    else:
        bucket, limit = "default", settings.rate_limit_default

    retry_after = rate_limiter.check(get_client_ip(request), bucket, limit)
    if retry_after is not None:
        return JSONResponse(
            status_code=429,
            content={"detail": "Bạn đang thao tác quá nhanh. Vui lòng thử lại sau ít giây."},
            headers={"Retry-After": str(retry_after)},
        )

    return await call_next(request)


# ── Security headers + đo số liệu vận hành ────────────────────────────────────

@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    """
    Gắn security header và đo độ trễ thật của từng request.

    Số liệu đo ở đây là nguồn dữ liệu cho trang Admin — thay cho các giá trị
    `random.uniform(...)` ở bản trước.
    """
    import time as _time

    start = _time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        metrics.record_request((_time.perf_counter() - start) * 1000, 500)
        raise

    duration_ms = (_time.perf_counter() - start) * 1000
    if request.url.path not in ("/health", "/"):
        metrics.record_request(duration_ms, response.status_code)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Response-Time-Ms"] = f"{duration_ms:.1f}"
    return response


# ── CORS ──────────────────────────────────────────────────────────────────────
# QUAN TRỌNG: middleware này phải được add_middleware() SAU CÙNG (không phải đầu
# tiên như trực giác thông thường).
#
# Starlette dựng middleware stack theo thứ tự NGƯỢC với thứ tự add_middleware():
# middleware add SAU sẽ bọc NGOÀI middleware add TRƯỚC. Nếu CORSMiddleware được
# add trước rate_limit_middleware/observability_middleware (như bản cũ), nó sẽ
# nằm ở lớp TRONG CÙNG — khi rate_limit_middleware trả thẳng response 429 mà
# không gọi call_next(), response đó không bao giờ đi qua CORSMiddleware, nên
# thiếu hẳn header Access-Control-Allow-Origin.
#
# Hậu quả nhìn thấy trên trình duyệt: Chrome báo "CORS request blocked / missing
# header" — nhìn giống lỗi cấu hình CORS, nhưng bản chất là request bị rate-limit
# (429) và mất header vì thứ tự middleware sai. Đặt CORSMiddleware add_middleware()
# ở đây (sau hai middleware kia) để nó luôn là lớp NGOÀI CÙNG, đảm bảo mọi response
# — kể cả 429 từ rate limiter, kể cả 500 từ exception handler — đều được gắn đúng
# header CORS trước khi trả về trình duyệt.
_origins = settings.origin_list
_allow_credentials = "*" not in _origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Cron-Secret"],
    max_age=86400,
)


# ── Exception handlers ────────────────────────────────────────────────────────

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """HTTPException do code chủ động raise — thông điệp đã được kiểm soát, trả nguyên."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Lỗi validate input — chỉ trả tên trường bị sai, không trả toàn bộ payload."""
    fields = []
    for err in exc.errors():
        loc = [str(p) for p in err.get("loc", []) if p not in ("body", "query", "path")]
        if loc:
            fields.append(".".join(loc))
    detail = "Dữ liệu gửi lên không hợp lệ."
    if fields:
        detail += f" Kiểm tra lại: {', '.join(fields[:5])}"
    return JSONResponse(status_code=422, content={"detail": detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Lưới an toàn cuối cùng: mọi exception chưa được xử lý đều dừng ở đây.
    Chi tiết ghi vào log server; client chỉ nhận thông điệp chung chung.
    """
    print(f"[UNHANDLED] {request.method} {request.url.path}: {type(exc).__name__}: {exc}")
    if not settings.is_production:
        import traceback

        traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": "Đã có lỗi xảy ra phía máy chủ. Vui lòng thử lại sau."},
    )


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(market.router, prefix="/market", tags=["Market"])
app.include_router(research.router, prefix="/research", tags=["Research"])
app.include_router(forecast.router, prefix="/forecast", tags=["Forecast"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(backtest.router, prefix="/backtest", tags=["Backtest"])
app.include_router(chat.router, prefix="/chat", tags=["Chat"])

# Notifications router tự khai báo đường dẫn đầy đủ bên trong (bao gồm cả
# /admin/notifications) nên KHÔNG được gắn prefix ở đây.
app.include_router(notifications.router, tags=["Notifications"])


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws/prices")
async def ws_prices(ws: WebSocket):
    """Stream giá real-time. Client gửi {"type":"subscribe","tickers":[...]} để lọc."""
    if not await ws_manager.connect(ws):
        return
    try:
        while True:
            data = await ws.receive_text()
            if len(data) > 4096:  # Chặn payload rác
                continue
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue
            if msg.get("type") == "subscribe" and isinstance(msg.get("tickers"), list):
                ws_manager.subscribe(ws, msg["tickers"])
                await ws.send_json({"type": "subscribed", "tickers": sorted(ws_manager.subscriptions[ws])})
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
    except Exception:
        ws_manager.disconnect(ws)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
@app.head("/", tags=["Health"])
async def root():
    return {"name": "ForecastAI API", "version": "2.0.0", "status": "running"}


@app.get("/health", tags=["Health"])
@app.head("/health", tags=["Health"])
async def health():
    from backend.database import is_available
    from backend.models.forecaster import is_tft_loaded

    return {
        "status": "ok",
        "environment": settings.environment,
        "db_connected": is_available(),
        "llm_configured": bool(settings.groq_api_key),
        "tft_loaded": is_tft_loaded(),
        "ws_clients": len(ws_manager.connections),
    }


# ── Dev runner ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
