"""
services/portfolio.py – Logic tính vị thế & lãi/lỗ dùng chung.

Trước đây phép tính vị thế bị viết lặp ở hai nơi với hai cách xử lý khác nhau:
  - `routers/admin.py::get_portfolio` — không giảm giá vốn khi bán
  - `cron_auto_trader.py::_calculate_position` — có giảm giá vốn theo tỷ lệ

Hệ quả là số liệu trên trang Portfolio và số liệu bot dùng để quyết định
cắt lỗ/chốt lời có thể lệch nhau. Gom về một chỗ để hai bên luôn đồng nhất.
"""

from __future__ import annotations

from typing import Dict, Iterable, List


def compute_positions(trades: Iterable[dict]) -> Dict[str, dict]:
    """
    Dựng vị thế hiện tại từ lịch sử giao dịch.

    `trades` phải theo thứ tự thời gian TĂNG DẦN (cũ → mới), vì giá vốn trung bình
    phụ thuộc vào thứ tự khớp lệnh.

    Trả về: {ticker: {"qty", "avg_cost", "total_cost", "realized_pnl"}}
    Các mã đã bán hết (qty <= 0) được loại khỏi kết quả.
    """
    positions: Dict[str, dict] = {}

    for t in trades:
        ticker = t.get("ticker")
        if not ticker:
            continue

        pos = positions.setdefault(
            ticker, {"qty": 0.0, "avg_cost": 0.0, "total_cost": 0.0, "realized_pnl": 0.0}
        )

        action = t.get("action")
        qty = float(t.get("quantity") or 0)
        value = float(t.get("total_value") or 0)

        if qty <= 0:
            continue

        if action == "BUY":
            pos["qty"] += qty
            pos["total_cost"] += value
            pos["avg_cost"] = pos["total_cost"] / pos["qty"] if pos["qty"] > 0 else 0.0

        elif action == "SELL":
            # Chỉ khớp được phần đang thực sự nắm giữ.
            sell_qty = min(qty, pos["qty"])
            if sell_qty <= 0:
                continue

            cost_basis = pos["avg_cost"] * sell_qty
            proceeds = value * (sell_qty / qty) if qty else 0.0
            pos["realized_pnl"] += proceeds - cost_basis

            pos["qty"] -= sell_qty
            pos["total_cost"] = max(0.0, pos["total_cost"] - cost_basis)
            if pos["qty"] <= 1e-12:
                # Đã đóng hết vị thế — dọn về 0 để tránh sai số dấu phẩy động tích luỹ.
                pos["qty"] = 0.0
                pos["total_cost"] = 0.0
                pos["avg_cost"] = 0.0

    return {k: v for k, v in positions.items() if v["qty"] > 0}


def compute_position_for(trades: Iterable[dict], ticker: str) -> dict:
    """Vị thế của đúng một mã. Trả về dict rỗng (qty=0) nếu không nắm giữ."""
    positions = compute_positions(t for t in trades if t.get("ticker") == ticker)
    return positions.get(ticker, {"qty": 0.0, "avg_cost": 0.0, "total_cost": 0.0, "realized_pnl": 0.0})


def compute_win_rate(win_trades: int, loss_trades: int) -> float:
    """
    Tỷ lệ thắng = số lệnh thắng / số lệnh ĐÃ ĐÓNG.

    Bản cũ chia cho tổng số giao dịch (gồm cả lệnh MUA đang mở), khiến tỷ lệ thắng
    luôn bị kéo xuống một cách vô nghĩa — mua vào không phải là một lệnh thua.
    """
    closed = win_trades + loss_trades
    if closed <= 0:
        return 0.0
    return round(win_trades / closed * 100, 1)


def sort_trades_ascending(trades: List[dict]) -> List[dict]:
    """Chuẩn hoá thứ tự giao dịch về tăng dần theo thời gian."""
    return sorted(trades, key=lambda t: t.get("trade_time") or "")


def compute_live_equity(user_id, cash: float, initial: float) -> Dict[str, float]:
    """
    Vốn chủ sở hữu và lãi/lỗ tổng của một tài khoản, tính NGAY theo giá hiện tại.

        vốn chủ sở hữu = tiền mặt + giá trị thị trường các vị thế đang mở
        lãi/lỗ tổng    = vốn chủ sở hữu − vốn ban đầu

    Định nghĩa DUY NHẤT, dùng chung cho `/trading/stop`, bảng xếp hạng và job
    snapshot hằng giờ — trước đây mỗi nơi chép lại một bản, và bảng xếp hạng thì
    đọc cột `admin_config.total_pnl` (chỉ được làm mới mỗi giờ).

    Không lấy được giá của mã nào thì tạm dùng giá vốn của mã đó, để vốn chủ sở hữu
    không hụt hẳn một vị thế (thà lệch một chút còn hơn báo lỗ giả). `get_live_quote`
    có cache TTL dùng chung nên nhiều tài khoản giữ cùng một mã chỉ tốn một lượt gọi.
    """
    from backend.database import get_all_trades
    from backend.models.forecaster import get_live_quote

    cash = float(cash or 0.0)
    initial = float(initial or 0.0)
    holdings_value = 0.0
    priced_at_cost: List[str] = []
    for ticker, pos in compute_positions(sort_trades_ascending(get_all_trades(user_id))).items():
        qty = float(pos.get("qty") or 0.0)
        if qty <= 0:
            continue
        try:
            quote = get_live_quote(ticker)
        except Exception:
            quote = None
        price = float(quote["price"]) if quote and quote.get("price") else None
        if price:
            holdings_value += qty * price
        else:
            holdings_value += float(pos.get("total_cost") or 0.0)
            priced_at_cost.append(ticker)

    equity = cash + holdings_value
    return {
        "cash": cash,
        "holdings_value": round(holdings_value, 2),
        "equity": round(equity, 2),
        "total_pnl": round(equity - initial, 2),
        "priced_at_cost": priced_at_cost,
    }
