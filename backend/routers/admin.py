"""
routers/admin.py – Danh mục đầu tư, paper trading và quản trị hệ thống.

Thay đổi quan trọng so với bản trước:

1. **3 endpoint `trigger-*` không còn nhận secret qua query string.**
   Secret nay đi trong header `X-Cron-Secret` và dùng secret RIÊNG
   (`CRON_SECRET_KEY`), không dùng chung khoá ký JWT nữa. Trước đây nếu secret
   này lộ, kẻ tấn công có thể tự ký token admin — giờ thì không.

2. **`/system` trả số liệu THẬT.** Bản cũ dựng độ trễ, tỷ lệ lỗi, số kết nối DB
   bằng `random.uniform(...)`.

3. **Phép tính vị thế và tỷ lệ thắng dùng chung service** với bot auto-trade,
   nên hai nơi không còn ra kết quả lệch nhau.

4. **Chặn admin tự khoá mình** (tự hạ quyền / tự treo / tự xoá tài khoản).

Toàn bộ endpoint để `def` (không phải `async def`) để FastAPI chạy chúng trong
threadpool — các lời gọi Supabase và yfinance là blocking, nếu chạy trực tiếp
trên event loop sẽ làm đơ toàn bộ server.
"""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.database import (
    _get_client,
    get_admin_config,
    get_trades,
    save_trade,
    update_admin_config,
)
from backend.metrics import metrics
from backend.routers.auth import get_current_admin, get_current_user
from backend.security import log_and_raise, validate_ticker_format, verify_cron_secret
from backend.services.portfolio import (
    compute_position_for,
    compute_positions,
    compute_win_rate,
    sort_trades_ascending,
)

router = APIRouter()

MAX_WATCHLIST_SIZE = 50


# ══════════════════════════════════════════════════════════════════════════════
#  SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class TradeRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)
    action: str = Field(pattern="^(BUY|SELL)$")
    quantity: float = Field(gt=0, le=1_000_000_000)


class StartTradingRequest(BaseModel):
    amount: float = Field(gt=0, le=100_000_000)
    duration_hours: int = Field(ge=1, le=24 * 30)
    assets: List[str] = Field(default_factory=list, max_length=MAX_WATCHLIST_SIZE)
    strategy: str = Field(default="balanced", pattern="^(conservative|balanced|aggressive)$")
    stop_loss: float = Field(default=5.0, ge=0, le=100)
    take_profit: float = Field(default=15.0, ge=0, le=1000)
    min_confidence: float = Field(default=70.0, ge=0, le=100)


class BotConfigRequest(BaseModel):
    """Cấu hình bot, không kèm thời lượng chạy — dùng cho nút "Lưu cấu hình"."""

    amount: float = Field(gt=0, le=100_000_000)
    assets: List[str] = Field(default_factory=list, max_length=MAX_WATCHLIST_SIZE)
    strategy: str = Field(default="balanced", pattern="^(conservative|balanced|aggressive)$")
    stop_loss: float = Field(default=5.0, ge=0, le=100)
    take_profit: float = Field(default=15.0, ge=0, le=1000)
    min_confidence: float = Field(default=70.0, ge=0, le=100)


class BalanceRequest(BaseModel):
    amount: float = Field(ge=0, le=1_000_000_000)


# ══════════════════════════════════════════════════════════════════════════════
#  DANH MỤC & GIAO DỊCH
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/portfolio")
def get_portfolio(user=Depends(get_current_user)):
    """Trạng thái paper trading của người dùng hiện tại: số dư, vị thế, lãi/lỗ."""
    user_id = user["user_id"]
    config = get_admin_config(user_id)
    trades = get_trades(user_id, limit=500)

    positions = compute_positions(sort_trades_ascending(trades))

    win_trades = config.get("win_trades", 0) or 0
    loss_trades = config.get("loss_trades", 0) or 0

    return {
        "initial_balance": config.get("initial_balance", 0.0),
        "current_balance": config.get("current_balance", 0.0),
        "total_pnl": config.get("total_pnl", 0.0),
        "win_rate": compute_win_rate(win_trades, loss_trades),
        "win_trades": win_trades,
        "loss_trades": loss_trades,
        "closed_trades": win_trades + loss_trades,
        "total_trades": len(trades),
        "is_running": config.get("is_running", False),
        "positions": positions,
        "recent_trades": trades[:20],
        "sentiment_enhanced": True,
    }


@router.get("/portfolio/history")
def get_portfolio_history_api(
    days: int = Query(default=90, ge=1, le=365), user=Depends(get_current_user)
):
    from backend.database import get_portfolio_history

    return {"history": get_portfolio_history(user["user_id"], days=days)}


@router.get("/portfolio/chart")
def get_portfolio_chart(user=Depends(get_current_user)):
    """Diễn biến số dư theo từng giao dịch, dùng để vẽ biểu đồ P&L."""
    user_id = user["user_id"]
    config = get_admin_config(user_id)

    trades = sort_trades_ascending(get_trades(user_id, limit=500))
    initial = float(config.get("initial_balance", 0.0) or 0.0)
    balance = initial

    start_date = config.get("started_at") or (
        trades[0]["trade_time"] if trades else datetime.now().isoformat()
    )
    history = [{"time": start_date, "balance": round(initial, 2), "pnl": 0.0}]

    for t in trades:
        value = float(t.get("total_value") or 0)
        balance += -value if t.get("action") == "BUY" else value
        history.append(
            {
                "time": t.get("trade_time"),
                "balance": round(balance, 2),
                "pnl": round(balance - initial, 2),
            }
        )

    return history


@router.get("/pnl")
def get_pnl_report(user=Depends(get_current_user)):
    user_id = user["user_id"]
    config = get_admin_config(user_id)
    trades = get_trades(user_id, limit=200)

    initial = float(config.get("initial_balance", 0.0) or 0.0)
    current = float(config.get("current_balance", 0.0) or 0.0)
    total_pnl = current - initial

    return {
        "initial_balance": initial,
        "current_balance": current,
        "total_pnl": total_pnl,
        "pnl_pct": round(total_pnl / initial * 100, 2) if initial > 0 else 0.0,
        "win_trades": config.get("win_trades", 0),
        "loss_trades": config.get("loss_trades", 0),
        "is_running": config.get("is_running", False),
        "started_at": config.get("started_at"),
        "trade_count": len(trades),
        "trades": trades[:50],
    }


@router.post("/trade")
def execute_trade(req: TradeRequest, user=Depends(get_current_user)):
    """Đặt một lệnh paper trading thủ công."""
    from backend.models.forecaster import get_live_quote

    user_id = user["user_id"]
    ticker = validate_ticker_format(req.ticker)

    live = get_live_quote(ticker)
    if not live:
        raise HTTPException(503, f"Không lấy được giá hiện tại của {ticker}.")

    price = live["price"]
    total = price * req.quantity
    config = get_admin_config(user_id)
    balance = float(config.get("current_balance", 0.0) or 0.0)

    if req.action == "BUY":
        if total > balance:
            raise HTTPException(
                400, f"Số dư không đủ: cần {total:,.2f}, hiện có {balance:,.2f}."
            )
        new_balance = balance - total
    else:
        # Không cho bán khống — chỉ bán được phần đang thực sự nắm giữ.
        position = compute_position_for(sort_trades_ascending(get_trades(user_id, limit=500)), ticker)
        if position["qty"] < req.quantity:
            raise HTTPException(
                400,
                f"Bạn chỉ đang nắm giữ {position['qty']:.6f} {ticker}, không đủ để bán.",
            )
        new_balance = balance + total

    # Ghi số dư theo kiểu so-sánh-rồi-ghi: chỉ thành công nếu số dư dưới DB vẫn
    # đúng bằng giá trị ta vừa đọc. Nếu có request khác chen vào giữa lúc kiểm tra
    # và lúc ghi, phép ghi này thất bại và ta báo lỗi thay vì đè lên thay đổi của
    # họ — nếu không, hai lệnh mua đồng thời đều qua được cửa kiểm tra số dư và
    # người dùng nhận nhiều cổ phiếu hơn số tiền thực bị trừ.
    from backend.database import update_balance_cas

    if not update_balance_cas(user_id, balance, new_balance):
        raise HTTPException(
            409,
            "Số dư vừa thay đổi bởi một giao dịch khác. Vui lòng tải lại và thử lại.",
        )

    # Sổ lệnh phải ghi được, nếu không số dư đã trừ mà vị thế không tồn tại —
    # vị thế được tính từ chính bảng paper_trades này.
    if not save_trade(
        user_id=user_id,
        ticker=ticker,
        action=req.action,
        quantity=req.quantity,
        price=price,
        total_value=total,
        model_signal="MANUAL",
    ):
        # Hoàn lại số dư về đúng giá trị trước giao dịch.
        update_balance_cas(user_id, new_balance, balance)
        raise HTTPException(503, "Không ghi được giao dịch. Số dư đã được hoàn lại.")

    return {
        "success": True,
        "ticker": ticker,
        "action": req.action,
        "quantity": req.quantity,
        "price": price,
        "total": total,
        "new_balance": new_balance,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  BOT AUTO-TRADE
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/trading/start")
def start_auto_trading(
    req: StartTradingRequest,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
):
    """
    Bật bot auto-trade cho người dùng hiện tại.

    LỖI BẢO MẬT ĐÃ SỬA — leo thang đặc quyền qua cấu hình bot
    ---------------------------------------------------------
    Bản cũ ghi thẳng `req.amount` vào `initial_balance` và `current_balance`:

        update_admin_config(user_id, {..., "initial_balance": req.amount,
                                           "current_balance": req.amount, ...})

    `req.amount` là "Số tiền mỗi lệnh giao dịch" do CHÍNH NGƯỜI DÙNG nhập trên
    giao diện, và endpoint này chỉ yêu cầu `get_current_user` (user thường).
    Trong khi đó, việc đặt số dư là đặc quyền riêng của quản trị viên, nằm sau
    `PUT /users/{user_id}/balance` với `Depends(get_current_admin)`.

    Hệ quả: bất kỳ user nào cũng có thể tự nạp tiền cho mình tới mức trần
    validate (100 triệu) chỉ bằng cách bật bot — vô hiệu hoá hoàn toàn cổng
    kiểm soát của admin. Chiều ngược lại cũng sai: user nhập 500 để đặt cỡ lệnh
    thì bị XOÁ TRẮNG số dư thật admin đã cấp, kèm toàn bộ lịch sử giao dịch.

    Nay: `amount` chỉ còn đúng một nghĩa là cỡ lệnh (khớp với nhãn trên UI).
    Số dư là tài sản do admin cấp — bật bot KHÔNG được tạo, sửa hay xoá nó.

    Vì số dư nay được giữ nguyên, lịch sử giao dịch cũng KHÔNG bị xoá nữa: số dư
    hiện tại là kết quả của chính các lệnh trong lịch sử đó. Xoá lệnh mà giữ số
    dư sẽ làm vị thế (tính từ `paper_trades`) lệch khỏi số dư — user hiện ra như
    không nắm giữ gì dù tiền đã bị trừ để mua.
    """
    from backend.database import save_bot_config

    user_id = user["user_id"]
    assets = [validate_ticker_format(a) for a in req.assets]

    config = get_admin_config(user_id)  # Đảm bảo bản ghi cấu hình đã tồn tại
    balance = float(config.get("current_balance", 0.0) or 0.0)

    if balance <= 0:
        raise HTTPException(
            400,
            "Tài khoản chưa có số dư để giao dịch. Vui lòng liên hệ quản trị viên "
            "để được cấp vốn trước khi bật bot.",
        )
    if req.amount > balance:
        raise HTTPException(
            400,
            f"Số tiền mỗi lệnh ({req.amount:,.2f}) vượt quá số dư hiện có "
            f"({balance:,.2f}). Hãy giảm cỡ lệnh xuống.",
        )

    end_time = (datetime.now() + timedelta(hours=req.duration_hours)).isoformat()

    save_bot_config(
        user_id,
        {
            "amount": req.amount,
            "end_time": end_time,
            "assets": assets,
            "strategy": req.strategy,
            "stop_loss": req.stop_loss,
            "take_profit": req.take_profit,
            "min_confidence": req.min_confidence,
        },
    )

    # Chỉ bật cờ chạy. Không đụng tới initial_balance / current_balance / total_pnl /
    # win_trades / loss_trades — đó là sổ sách kế toán của tài khoản, không phải
    # trạng thái của bot.
    update_admin_config(
        user_id,
        {
            "is_running": True,
            "started_at": datetime.now().isoformat(),
        },
    )

    from backend.cron_auto_trader import run_auto_trade

    background_tasks.add_task(run_auto_trade)

    return {
        "message": "Đã bật bot auto-trade",
        "is_running": True,
        "end_time": end_time,
        "current_balance": balance,
        "amount_per_trade": req.amount,
    }


@router.post("/trading/stop")
def stop_auto_trading(user=Depends(get_current_user)):
    user_id = user["user_id"]
    update_admin_config(user_id, {"is_running": False})
    config = get_admin_config(user_id)
    return {
        "message": "Đã dừng bot auto-trade",
        "is_running": False,
        "final_balance": config.get("current_balance"),
        "total_pnl": config.get("total_pnl"),
    }


@router.get("/trading/config")
def get_auto_trading_config(user=Depends(get_current_user)):
    from backend.database import get_bot_config

    return get_bot_config(user["user_id"]) or {"amount": 0, "end_time": None}


@router.put("/trading/config")
def save_auto_trading_config(req: BotConfigRequest, user=Depends(get_current_user)):
    """
    Lưu cấu hình bot mà KHÔNG bật bot.

    Trước đây không có endpoint này: nút "Lưu cấu hình" trên giao diện chỉ đổi một
    biến state cục bộ rồi hiện dòng "Configuration saved" — không hề gửi gì lên
    máy chủ. Người dùng chỉnh chiến lược, cắt lỗ, chốt lời, thấy báo đã lưu, tải
    lại trang là mất sạch, quay về giá trị mặc định. Cấu hình chỉ thực sự được ghi
    khi bấm "Start Bot", nên hai nút cạnh nhau có hành vi hoàn toàn khác nhau mà
    giao diện không hề nói ra.

    Endpoint này KHÔNG đụng tới số dư, không bật/tắt bot, và giữ nguyên thời hạn
    chạy hiện có (nếu bot đang chạy thì cấu hình mới áp dụng cho các lượt kế tiếp).
    """
    from backend.database import get_bot_config, save_bot_config

    user_id = user["user_id"]
    assets = [validate_ticker_format(a) for a in req.assets]
    existing = get_bot_config(user_id) or {}

    ok = save_bot_config(
        user_id,
        {
            "amount": req.amount,
            "end_time": existing.get("end_time"),
            "assets": assets,
            "strategy": req.strategy,
            "stop_loss": req.stop_loss,
            "take_profit": req.take_profit,
            "min_confidence": req.min_confidence,
        },
    )
    if not ok:
        raise HTTPException(503, "Không lưu được cấu hình. Vui lòng thử lại.")

    return {"success": True, "message": "Đã lưu cấu hình bot."}


# ══════════════════════════════════════════════════════════════════════════════
#  WATCHLIST
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/watchlist")
def get_watchlist_api(user=Depends(get_current_user)):
    from backend.database import get_watchlist

    return get_watchlist(user["user_id"])


@router.post("/watchlist")
def add_to_watchlist_api(
    ticker: str = Query(..., min_length=1, max_length=20), user=Depends(get_current_user)
):
    from backend.database import get_watchlist

    user_id = user["user_id"]
    clean_ticker = validate_ticker_format(ticker)

    current = get_watchlist(user_id)
    if clean_ticker in current:
        return {"success": True, "message": "Mã đã có trong danh sách theo dõi."}
    if len(current) >= MAX_WATCHLIST_SIZE:
        raise HTTPException(
            400, f"Danh sách theo dõi tối đa {MAX_WATCHLIST_SIZE} mã. Hãy xoá bớt trước khi thêm."
        )

    c = _get_client()
    if c is None:
        raise HTTPException(503, "Không kết nối được cơ sở dữ liệu.")

    try:
        c.table("user_watchlists").insert({"user_id": user_id, "ticker": clean_ticker}).execute()
    except Exception as e:
        if "duplicate key" in str(e).lower():
            return {"success": True, "message": "Mã đã có trong danh sách theo dõi."}
        log_and_raise("add_watchlist", e, 500, "Không thêm được mã vào danh sách theo dõi.")

    return {"success": True}


@router.delete("/watchlist/{ticker}")
def remove_from_watchlist_api(ticker: str, user=Depends(get_current_user)):
    clean_ticker = validate_ticker_format(ticker)
    c = _get_client()
    if c is None:
        raise HTTPException(503, "Không kết nối được cơ sở dữ liệu.")
    c.table("user_watchlists").delete().eq("user_id", user["user_id"]).eq(
        "ticker", clean_ticker
    ).execute()
    return {"success": True}


# ══════════════════════════════════════════════════════════════════════════════
#  LEADERBOARD
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/leaderboard")
def get_leaderboard():
    """Top 10 tài khoản theo lãi/lỗ. Tên đăng nhập được che bớt để giữ riêng tư."""
    c = _get_client()
    if c is None:
        return []

    try:
        res = (
            c.table("admin_config")
            .select("id, total_pnl, win_trades, loss_trades, users!inner(username)")
            .order("total_pnl", desc=True)
            .limit(10)
            .execute()
        )
    except Exception as e:
        print(f"[admin] Lỗi lấy leaderboard: {e}")
        return []

    leaderboard = []
    for idx, row in enumerate(res.data or []):
        raw_username = (row.get("users") or {}).get("username", "unknown")
        # Che phần định danh: giữ 4 ký tự đầu, ẩn phần còn lại kể cả domain email.
        masked = (raw_username[:4] if len(raw_username) > 4 else raw_username) + "***"

        win = row.get("win_trades", 0) or 0
        loss = row.get("loss_trades", 0) or 0
        leaderboard.append(
            {
                "id": str(row.get("id") or idx),
                "rank": idx + 1,
                "username": masked,
                "total_pnl": row.get("total_pnl", 0),
                "win_trades": win,
                "loss_trades": loss,
                "win_rate": compute_win_rate(win, loss),
            }
        )
    return leaderboard


# ══════════════════════════════════════════════════════════════════════════════
#  QUẢN LÝ NGƯỜI DÙNG (CHỈ ADMIN)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/users")
def get_all_users(admin=Depends(get_current_admin)):
    c = _get_client()
    if c is None:
        return []

    try:
        res = c.table("users").select(
            "id, username, role, status, created_at, last_active, admin_config(current_balance)"
        ).execute()
    except Exception as e:
        print(f"[admin] Lỗi lấy danh sách user: {e}")
        return []

    mapped = []
    for u in res.data or []:
        configs = u.get("admin_config") or []
        if isinstance(configs, list):
            balance = configs[0].get("current_balance", 0) if configs else 0
        elif isinstance(configs, dict):
            balance = configs.get("current_balance", 0)
        else:
            balance = 0

        mapped.append(
            {
                "id": str(u["id"]),
                "name": u["username"].split("@")[0],
                "email": u["username"],
                "role": u.get("role", "user"),
                "status": u.get("status", "active"),
                "portfolioValue": balance,
                "joinedAt": u.get("created_at"),
                "lastActive": u.get("last_active"),
            }
        )
    return mapped


def _guard_not_self(admin: dict, target_user_id: int, action: str) -> None:
    """
    Chặn admin tự tác động lên chính mình.

    Không có bước này, một cú nhấp nhầm vào nút "Hạ quyền" trên chính dòng của mình
    sẽ khoá vĩnh viễn quyền quản trị, và không còn đường nào lấy lại ngoài việc
    sửa tay trong Supabase.
    """
    if int(admin.get("user_id", -1)) == int(target_user_id):
        raise HTTPException(400, f"Bạn không thể tự {action} tài khoản của chính mình.")


@router.put("/users/{user_id}/balance")
def update_user_balance(user_id: int, req: BalanceRequest, admin=Depends(get_current_admin)):
    c = _get_client()
    if c is None:
        raise HTTPException(503, "Không kết nối được cơ sở dữ liệu.")

    get_admin_config(user_id)  # Đảm bảo bản ghi tồn tại trước khi update

    # Đây là thao tác ĐẶT LẠI VỐN, không phải nạp thêm: nó ghi đè cả
    # `initial_balance` và đưa `total_pnl` về 0. Vì vậy sổ lệnh cũ BẮT BUỘC phải
    # được dọn cùng lúc.
    #
    # Nếu không: vị thế đang mở được tính từ bảng `paper_trades` và hoàn toàn
    # không biết gì về việc đặt lại số dư. Người dùng mua 10 cổ phiếu hết sạch
    # 10.000$ (số dư còn 0, vị thế còn 10 cổ). Quản trị viên đặt lại số dư về 0
    # để phạt. Người dùng bán 10 cổ đó — hệ thống thấy vị thế vẫn còn nên cộng
    # thẳng tiền bán vào số dư. Khoản phạt biến thành tiền mặt cho không, đúng
    # bằng giá trị thị trường của số cổ phiếu họ đã mua trước khi bị đặt lại.
    from backend.database import clear_trading_history

    clear_trading_history(user_id)
    c.table("admin_config").update(
        {
            "current_balance": req.amount,
            "initial_balance": req.amount,
            "total_pnl": 0.0,
            "win_trades": 0,
            "loss_trades": 0,
        }
    ).eq("user_id", user_id).execute()

    return {
        "success": True,
        "new_balance": req.amount,
        "message": "Đã đặt lại vốn và dọn sổ lệnh mô phỏng của tài khoản này.",
    }


@router.put("/users/{user_id}/status")
def update_user_status(user_id: int, admin=Depends(get_current_admin)):
    _guard_not_self(admin, user_id, "khoá")
    c = _get_client()
    if c is None:
        raise HTTPException(503, "Không kết nối được cơ sở dữ liệu.")

    res = c.table("users").select("status").eq("id", user_id).execute()
    if not res.data:
        raise HTTPException(404, "Không tìm thấy người dùng.")

    new_status = "suspended" if res.data[0].get("status", "active") == "active" else "active"
    c.table("users").update({"status": new_status}).eq("id", user_id).execute()
    return {"success": True, "new_status": new_status}


@router.put("/users/{user_id}/role")
def update_user_role(user_id: int, admin=Depends(get_current_admin)):
    _guard_not_self(admin, user_id, "đổi quyền")
    c = _get_client()
    if c is None:
        raise HTTPException(503, "Không kết nối được cơ sở dữ liệu.")

    res = c.table("users").select("role").eq("id", user_id).execute()
    if not res.data:
        raise HTTPException(404, "Không tìm thấy người dùng.")

    current_role = res.data[0].get("role", "user")
    new_role = "user" if current_role == "admin" else "admin"

    # Không cho hạ quyền admin cuối cùng — hệ thống phải luôn còn ít nhất một quản trị viên.
    if current_role == "admin":
        admins = c.table("users").select("id", count="exact").eq("role", "admin").execute()
        if (admins.count or 0) <= 1:
            raise HTTPException(400, "Không thể hạ quyền quản trị viên cuối cùng của hệ thống.")

    c.table("users").update({"role": new_role}).eq("id", user_id).execute()
    return {"success": True, "new_role": new_role}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, admin=Depends(get_current_admin)):
    _guard_not_self(admin, user_id, "xoá")
    c = _get_client()
    if c is None:
        raise HTTPException(503, "Không kết nối được cơ sở dữ liệu.")

    res = c.table("users").select("role").eq("id", user_id).execute()
    if not res.data:
        raise HTTPException(404, "Không tìm thấy người dùng.")

    if res.data[0].get("role") == "admin":
        admins = c.table("users").select("id", count="exact").eq("role", "admin").execute()
        if (admins.count or 0) <= 1:
            raise HTTPException(400, "Không thể xoá quản trị viên cuối cùng của hệ thống.")

    c.table("users").delete().eq("id", user_id).execute()
    return {"success": True}


# ══════════════════════════════════════════════════════════════════════════════
#  SỨC KHOẺ HỆ THỐNG
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/system/accuracy")
def get_system_accuracy(
    limit: int = Query(default=20, ge=1, le=100), admin=Depends(get_current_admin)
):
    """Các bản ghi đánh giá sai số mô hình gần nhất (đã có giá thực tế để đối chiếu)."""
    c = _get_client()
    if c is None:
        return {"success": False, "records": [], "summary": None}

    try:
        res = (
            c.table("model_accuracy")
            .select("*")
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

        return {"success": True, "records": records, "summary": summary}
    except Exception as e:
        print(f"[admin] Lỗi lấy số liệu accuracy: {e}")
        return {"success": False, "records": [], "summary": None}


@router.get("/system")
def get_system_metrics(admin=Depends(get_current_admin)):
    """
    Số liệu vận hành THẬT, đo từ chính tiến trình đang chạy.

    Các giá trị này reset mỗi lần service khởi động lại — điều đáng lưu ý trên
    Render free tier, nơi service ngủ sau 15 phút không có traffic.
    """
    snap = metrics.snapshot()

    c = _get_client()
    db_healthy = c is not None

    pending_evaluations = 0
    research_reports = 0
    if db_healthy:
        try:
            pending = (
                c.table("model_accuracy")
                .select("id", count="exact")
                .is_("actual_price", "null")
                .execute()
            )
            pending_evaluations = pending.count or 0
            reports = c.table("research_reports").select("id", count="exact").execute()
            research_reports = reports.count or 0
        except Exception as e:
            print(f"[admin] Lỗi đếm số liệu hệ thống: {e}")

    def status_for(value: float, warn: float, critical: float) -> str:
        if value >= critical:
            return "critical"
        if value >= warn:
            return "warning"
        return "healthy"

    return [
        {
            "label": "Độ trễ API (p50)",
            "value": snap["api_latency_p50_ms"],
            "unit": "ms",
            "status": status_for(snap["api_latency_p50_ms"], 500, 2000),
            "hint": f"p95: {snap['api_latency_p95_ms']} ms trên {snap['total_requests']} request",
        },
        {
            "label": "Thời gian inference (p50)",
            "value": snap["inference_p50_ms"],
            "unit": "ms",
            "status": status_for(snap["inference_p50_ms"], 3000, 10000),
            "hint": (
                f"{snap['inference_samples']} lượt dự báo đã đo"
                if snap["inference_samples"]
                else "Chưa có lượt dự báo nào kể từ khi khởi động"
            ),
        },
        {
            "label": "Kết nối cơ sở dữ liệu",
            "value": 1 if db_healthy else 0,
            "unit": "",
            "status": "healthy" if db_healthy else "critical",
            "hint": "Supabase phản hồi bình thường" if db_healthy else "Không kết nối được Supabase",
        },
        {
            "label": "Dự báo chờ đánh giá",
            "value": pending_evaluations,
            "unit": "bản ghi",
            "status": status_for(pending_evaluations, 100, 500),
            "hint": "Sẽ được đối chiếu tự động khi phiên giao dịch tương ứng có dữ liệu",
        },
        {
            "label": "Tỷ lệ lỗi (5xx)",
            "value": snap["error_rate_pct"],
            "unit": "%",
            "status": status_for(snap["error_rate_pct"], 1, 5),
            "hint": f"{snap['error_requests']}/{snap['total_requests']} request lỗi",
        },
        {
            # `value` luôn phải là số: type SystemMetric ở frontend khai báo
            # value: number, và giao diện gọi các hàm định dạng số lên nó.
            # Chuỗi thân thiện với người đọc được đưa vào `hint`.
            "label": "Thời gian hoạt động",
            "value": round(snap["uptime_seconds"] / 3600, 1),
            "unit": "giờ",
            "status": "healthy",
            "hint": (
                f"{snap['uptime_human']} · {research_reports} báo cáo nghiên cứu đã lưu"
            ),
        },
    ]


@router.get("/research-queue")
def get_research_queue(
    limit: int = Query(default=20, ge=1, le=50), admin=Depends(get_current_admin)
):
    """Các báo cáo nghiên cứu gần nhất do job nền tạo ra."""
    c = _get_client()
    if c is None:
        return []

    try:
        res = (
            c.table("research_reports")
            .select("id, ticker, source, created_at")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [
            {
                "id": str(r.get("id", "")),
                "ticker": r.get("ticker", "UNKNOWN"),
                "status": "completed",
                "requestedBy": r.get("source", "system"),
                "progress": 100,
                "createdAt": r.get("created_at", ""),
            }
            for r in res.data or []
        ]
    except Exception as e:
        print(f"[admin] Lỗi lấy hàng đợi research: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
#  ĐIỂM KÍCH HOẠT JOB NỀN (dành cho cron-job.org, GitHub Actions, ...)
# ══════════════════════════════════════════════════════════════════════════════
#
# Cách gọi:
#   curl -X POST https://<api>/admin/trigger-research -H "X-Cron-Secret: <CRON_SECRET_KEY>"
#
# Các endpoint này dùng POST (không phải GET) vì chúng thay đổi trạng thái hệ thống,
# và secret đi trong header thay vì query string để không bị ghi vào access log.


def _run_in_background(background_tasks: BackgroundTasks, fn, label: str) -> dict:
    def task():
        try:
            fn()
        except Exception as e:
            print(f"[cron:{label}] Lỗi: {e}")

    background_tasks.add_task(task)
    return {"success": True, "message": f"Đã khởi chạy job '{label}' ở chế độ nền."}


@router.post("/trigger-learner", dependencies=[Depends(verify_cron_secret)])
def trigger_learner(background_tasks: BackgroundTasks):
    """Đánh giá sai số dự báo cũ rồi fine-tune nhẹ mô hình trên dữ liệu mới."""

    def job():
        import backend.cron_accuracy_learner as learner

        tickers = learner.run_evaluations()
        learner.online_learning(tickers)

    return _run_in_background(background_tasks, job, "accuracy-learner")


@router.post("/trigger-autotrade", dependencies=[Depends(verify_cron_secret)])
def trigger_autotrade(background_tasks: BackgroundTasks):
    from backend.cron_auto_trader import run_auto_trade

    return _run_in_background(background_tasks, run_auto_trade, "auto-trade")


@router.post("/trigger-research", dependencies=[Depends(verify_cron_secret)])
def trigger_research(background_tasks: BackgroundTasks):
    from backend.cron_researcher import run_research

    return _run_in_background(background_tasks, run_research, "researcher")
