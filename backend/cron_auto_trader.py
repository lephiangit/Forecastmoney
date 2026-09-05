"""
cron_auto_trader.py – Bot giao dịch mô phỏng theo chiến lược, có quản trị rủi ro.

Đây là bản sửa ba lỗi khiến bot gần như không hoạt động ở phiên bản trước:

1. **`confidence` luôn bằng 50 nên bot không bao giờ vào lệnh.**
   Bot đọc `fc["research"]["confidence"]`, nhưng `run_combined_forecast()` khi được
   gọi trực tiếp (không qua HTTP) lại không hề có khoá `research` — khoá đó chỉ được
   router thêm vào. Kết quả: confidence rơi về mặc định 50, trong khi cả ba chiến lược
   đều yêu cầu tối thiểu 60-80%. Điều kiện vào lệnh vì thế KHÔNG BAO GIỜ thoả,
   bot chỉ còn chạy phần cắt lỗ/chốt lời. Nay bot tự chạy phân tích tin tức trước
   rồi truyền vào forecast, và `run_combined_forecast` luôn trả về khoá `research`.

2. **Tín hiệu tâm lý không hề được áp dụng.**
   Bot truyền `{"sentiment_score": 0.8}`, nhưng `extract_market_signals()` lại đọc
   hai khoá `sentiment` và `confidence`. Hai bên không khớp nhau nên tín hiệu tâm lý
   bị bỏ qua hoàn toàn, dù log vẫn hiển thị "sentiment_enhanced".

3. **Bộ đếm thắng/thua bị ghi đè.**
   `config` được đọc một lần đầu vòng lặp rồi dùng lại cho mọi lệnh trong lượt chạy.
   Khi hai mã cùng chốt lời trong một lượt, lệnh sau ghi đè bộ đếm của lệnh trước.
   Nay số dư và bộ đếm được giữ trong biến cục bộ và chỉ ghi xuống DB một lần ở cuối.

Chiến lược:
  - Conservative: confidence >= 80%, kỳ vọng >= 3.0%, quy mô lệnh 70%
  - Balanced:     confidence >= 70%, kỳ vọng >= 1.5%, quy mô lệnh 100%
  - Aggressive:   confidence >= 60%, kỳ vọng >= 0.5%, quy mô lệnh 130%
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from backend.database import (
    _get_client,
    get_bot_config,
    get_recent_research,
    get_trades,
    get_watchlist,
    save_trade,
    update_admin_config,
)
from backend.models.forecaster import get_live_quote, run_combined_forecast
from backend.services.portfolio import compute_position_for, sort_trades_ascending

STRATEGY_PARAMS = {
    "conservative": {"min_confidence": 80, "min_expected_return": 3.0, "position_scale": 0.7},
    "balanced": {"min_confidence": 70, "min_expected_return": 1.5, "position_scale": 1.0},
    "aggressive": {"min_confidence": 60, "min_expected_return": 0.5, "position_scale": 1.3},
}

# Báo cáo tin tức cũ hơn ngưỡng này bị coi là hết giá trị tham chiếu.
RESEARCH_MAX_AGE_HOURS = 12

# Số mã tối đa bot xử lý cho mỗi user trong một lượt chạy — chặn trường hợp
# watchlist 50 mã làm một lượt chạy kéo dài hàng phút và nghẽn cả job nền.
MAX_TICKERS_PER_USER = 12


# ══════════════════════════════════════════════════════════════════════════════
#  HELPER
# ══════════════════════════════════════════════════════════════════════════════

def _get_strategy_params(bot_cfg: dict) -> dict:
    strategy = bot_cfg.get("strategy", "balanced")
    params = STRATEGY_PARAMS.get(strategy, STRATEGY_PARAMS["balanced"]).copy()
    # Người dùng có thể siết chặt hơn ngưỡng của chiến lược từ giao diện.
    if bot_cfg.get("min_confidence"):
        params["min_confidence"] = float(bot_cfg["min_confidence"])
    return params


def _load_research_context(ticker: str) -> Optional[Dict]:
    """
    Lấy báo cáo tin tức gần nhất và chuyển về đúng định dạng mà
    `extract_market_signals()` mong đợi: hai khoá `sentiment` và `confidence`.

    Trả về None nếu chưa có báo cáo hoặc báo cáo đã quá cũ — khi đó bot
    chạy thuần phân tích kỹ thuật thay vì dùng tin tức lỗi thời.
    """
    records = get_recent_research(ticker, limit=1)
    if not records:
        return None

    record = records[0]

    created_at = record.get("created_at")
    if created_at:
        try:
            from datetime import timezone

            created = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - created).total_seconds() / 3600
            if age_hours > RESEARCH_MAX_AGE_HOURS:
                return None
        except (ValueError, TypeError):
            pass

    return {
        "sentiment": str(record.get("sentiment", "NEUTRAL")).upper(),
        "confidence": float(record.get("confidence") or 0.5),
        "sentiment_score": float(record.get("sentiment_score") or 0.0),
        "summary": record.get("summary", ""),
        "source": record.get("source", "db"),
    }


def _build_forecast(ticker: str) -> Optional[Dict]:
    """
    Chạy dự báo cho một mã và rút ra (giá dự báo T+1, độ tin cậy %).

    Độ tin cậy lấy từ báo cáo tin tức. Khi không có tin tức, ta KHÔNG bịa ra một
    con số cao để bot vẫn vào lệnh — trả về 50% là mức trung tính, và mọi chiến lược
    đều yêu cầu cao hơn mức đó, nghĩa là bot sẽ đứng ngoài. Đó là hành vi đúng:
    không có cơ sở thì không giao dịch.
    """
    research = _load_research_context(ticker)

    try:
        fc = run_combined_forecast(ticker, days=1, research_analysis=research)
    except Exception as e:
        print(f"     [!] Lỗi dự báo {ticker}: {type(e).__name__}: {e}")
        return None

    if not fc:
        return None

    predicted_price = None
    model_used = None

    sf = fc.get("sentiment_fusion") or {}
    tft = fc.get("tft") or {}

    if sf.get("median"):
        predicted_price = sf["median"][0]["price"]
        model_used = "sentiment_fusion"
    elif tft.get("median"):
        predicted_price = tft["median"][0]["price"]
        model_used = "tft"

    if predicted_price is None:
        return None

    research_block = fc.get("research") or {}
    raw_confidence = research_block.get("confidence")

    if raw_confidence is None:
        confidence_pct = 50.0
    else:
        # Báo cáo lưu confidence ở thang 0..1; giao diện và ngưỡng chiến lược dùng thang %.
        confidence = float(raw_confidence)
        confidence_pct = confidence * 100 if confidence <= 1.0 else confidence

    return {
        "price": float(predicted_price),
        "confidence": confidence_pct,
        "model": model_used,
        "has_research": research is not None,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  QUẢN TRỊ RỦI RO
# ══════════════════════════════════════════════════════════════════════════════

class _UserSession:
    """
    Giữ trạng thái ví của một user trong suốt một lượt chạy bot.

    Mọi thay đổi số dư và bộ đếm thắng/thua được cộng dồn ở đây rồi ghi xuống DB
    một lần duy nhất ở cuối — tránh việc các lệnh trong cùng một lượt ghi đè lẫn nhau.
    """

    def __init__(self, config: dict):
        self.user_id = config["user_id"]
        self.initial_balance = float(config.get("initial_balance") or 0.0)
        self.balance = float(config.get("current_balance") or 0.0)
        # Số dư đọc được lúc bắt đầu lượt chạy — dùng làm mốc so sánh khi ghi xuống
        # DB ở flush(), để phát hiện có lượt chạy khác ghi chen vào hay không.
        self.balance_at_start = self.balance
        self.win_trades = int(config.get("win_trades") or 0)
        self.loss_trades = int(config.get("loss_trades") or 0)
        self.dirty = False

    def record_buy(self, value: float) -> None:
        self.balance -= value
        self.dirty = True

    def record_sell(self, value: float, profitable: bool) -> None:
        self.balance += value
        if profitable:
            self.win_trades += 1
        else:
            self.loss_trades += 1
        self.dirty = True

    def flush(self) -> bool:
        """
        Ghi số dư và bộ đếm thắng/thua xuống DB.

        LỖI ĐÃ SỬA — mất cập nhật do hai lượt chạy chồng nhau.
        `run_auto_trade()` được kích hoạt theo HAI đường và chúng có thể chạy đè lên
        nhau: bộ đếm giờ 60 giây trong main.py, và endpoint /admin/trigger-autotrade.
        Mỗi lượt chụp số dư MỘT LẦN lúc bắt đầu, cộng dồn toàn bộ mua bán trong bộ
        nhớ, rồi cuối lượt ghi đè VÔ ĐIỀU KIỆN.

        Số dư 1.000$: lượt A mua 400$ (còn 600) và ghi lúc t=45s; lượt B vốn cũng đọc
        thấy 1.000$ mua tiếp 700$ (còn 300) rồi ghi lúc t=50s. Thực chi 1.100$ trên
        số dư 1.000$, và lượt ghi sau còn xoá luôn bộ đếm thắng/thua của lượt trước.
        Đây đúng là lỗi đã được sửa cho lệnh tay ở /trade bằng update_balance_cas,
        nhưng bot thì chưa được cập nhật theo.

        Nay chỉ ghi khi số dư dưới DB vẫn đúng bằng giá trị đọc lúc bắt đầu lượt.
        Trả False nếu bị từ chối — lượt chạy đó coi như bỏ, lượt sau sẽ tính lại trên
        số dư mới nhất.
        """
        if not self.dirty:
            return True

        from backend.database import update_balance_cas

        ok = update_balance_cas(
            self.user_id,
            expected_balance=self.balance_at_start,
            new_balance=self.balance,
            extra={
                "total_pnl": self.balance - self.initial_balance,
                "win_trades": self.win_trades,
                "loss_trades": self.loss_trades,
            },
        )
        if not ok:
            print(
                f"  [!] User {self.user_id}: số dư đã bị một lượt chạy khác thay đổi "
                "giữa chừng — bỏ qua ghi để không đè mất cập nhật của lượt đó."
            )
        return ok


def _check_risk_exit(
    session: _UserSession,
    ticker: str,
    current_price: float,
    position: dict,
    stop_loss_pct: float,
    take_profit_pct: float,
) -> bool:
    """
    Kiểm tra và thực hiện cắt lỗ / chốt lời. Trả về True nếu đã bán.

    Cắt lỗ được kiểm tra TRƯỚC chốt lời: nếu vì lý do nào đó cả hai cùng thoả
    (dữ liệu giá nhảy bậc), ưu tiên bảo toàn vốn.
    """
    qty = position["qty"]
    avg_cost = position["avg_cost"]
    if qty <= 0 or avg_cost <= 0:
        return False

    price_change_pct = (current_price - avg_cost) / avg_cost * 100
    sell_value = current_price * qty

    if stop_loss_pct > 0 and price_change_pct <= -stop_loss_pct:
        save_trade(session.user_id, ticker, "SELL", qty, current_price, sell_value, "AUTO_SL")
        session.record_sell(sell_value, profitable=False)
        print(
            f"     [SL] User {session.user_id}: bán {qty:.4f} {ticker} @ {current_price:.2f} "
            f"({price_change_pct:.1f}%)"
        )
        return True

    if take_profit_pct > 0 and price_change_pct >= take_profit_pct:
        save_trade(session.user_id, ticker, "SELL", qty, current_price, sell_value, "AUTO_TP")
        session.record_sell(sell_value, profitable=True)
        print(
            f"     [TP] User {session.user_id}: bán {qty:.4f} {ticker} @ {current_price:.2f} "
            f"(+{price_change_pct:.1f}%)"
        )
        return True

    return False


# ══════════════════════════════════════════════════════════════════════════════
#  VÒNG CHẠY CHÍNH
# ══════════════════════════════════════════════════════════════════════════════

def run_auto_trade() -> None:
    """Chạy một lượt giao dịch tự động cho toàn bộ user đang bật bot."""
    c = _get_client()
    if not c:
        print("[auto-trade] Không có kết nối cơ sở dữ liệu.")
        return

    try:
        configs_res = c.table("admin_config").select("*").eq("is_running", True).execute()
    except Exception as e:
        print(f"[auto-trade] Lỗi truy vấn danh sách user: {e}")
        return

    running_users = configs_res.data or []
    if not running_users:
        return  # Im lặng — trường hợp phổ biến nhất, không cần làm ồn log.

    print(f"[auto-trade] Đang xử lý {len(running_users)} user đang bật bot.")

    # Dự báo được dùng chung cho tất cả user trong cùng một lượt chạy:
    # cùng một mã thì kết quả mô hình như nhau, không cần tính lại.
    forecast_cache: Dict[str, Optional[Dict]] = {}

    for config in running_users:
        try:
            _process_user(config, forecast_cache)
        except Exception as e:
            print(f"[auto-trade] Lỗi khi xử lý user {config.get('user_id')}: {type(e).__name__}: {e}")


def _process_user(config: dict, forecast_cache: Dict[str, Optional[Dict]]) -> None:
    user_id = config["user_id"]
    bot_cfg = get_bot_config(user_id) or {}

    # Hết thời hạn chạy → tự dừng.
    end_time = bot_cfg.get("end_time")
    if end_time and datetime.now().isoformat() > end_time:
        print(f"  User {user_id}: hết thời hạn, đã dừng bot.")
        update_admin_config(user_id, {"is_running": False})
        return

    strategy_params = _get_strategy_params(bot_cfg)
    trade_amount = float(bot_cfg.get("amount") or 500) * strategy_params["position_scale"]
    stop_loss_pct = float(bot_cfg.get("stop_loss") or 5)
    take_profit_pct = float(bot_cfg.get("take_profit") or 15)
    min_confidence = strategy_params["min_confidence"]
    min_return = strategy_params["min_expected_return"]

    watchlist: List[str] = bot_cfg.get("assets") or get_watchlist(user_id)
    if not watchlist:
        return
    watchlist = [t.upper() for t in watchlist][:MAX_TICKERS_PER_USER]

    session = _UserSession(config)
    all_trades = sort_trades_ascending(get_trades(user_id, limit=500))

    print(
        f"  User {user_id} | {bot_cfg.get('strategy', 'balanced')} | "
        f"SL {stop_loss_pct}% | TP {take_profit_pct}% | {len(watchlist)} mã"
    )

    for ticker in watchlist:
        live = get_live_quote(ticker)
        if not live:
            continue
        current_price = live["price"]
        if current_price <= 0:
            continue

        position = compute_position_for(all_trades, ticker)

        # ── Bước 1: quản trị rủi ro trên vị thế đang mở ──
        if position["qty"] > 0:
            if _check_risk_exit(
                session, ticker, current_price, position, stop_loss_pct, take_profit_pct
            ):
                continue

        # ── Bước 2: dự báo ──
        if ticker not in forecast_cache:
            forecast_cache[ticker] = _build_forecast(ticker)
        forecast = forecast_cache[ticker]
        if not forecast:
            continue

        predicted_price = forecast["price"]
        confidence = forecast["confidence"]
        expected_return = (predicted_price - current_price) / current_price * 100

        # ── Bước 3: cổng chiến lược ──
        if confidence < min_confidence:
            print(
                f"     [-] {ticker}: độ tin cậy {confidence:.0f}% < ngưỡng {min_confidence:.0f}%"
                + ("" if forecast["has_research"] else " (chưa có phân tích tin tức)")
            )
            continue

        if abs(expected_return) < min_return:
            print(f"     [-] {ticker}: kỳ vọng {expected_return:+.2f}% < ngưỡng {min_return:.1f}%")
            continue

        # ── Bước 4: khớp lệnh ──
        if expected_return > 0:
            qty = round(trade_amount / current_price, 6)
            total_value = current_price * qty
            if qty <= 0 or session.balance < total_value:
                print(f"     [-] {ticker}: số dư không đủ ({session.balance:,.2f})")
                continue

            save_trade(user_id, ticker, "BUY", qty, current_price, total_value, "AUTO")
            session.record_buy(total_value)
            all_trades.append(
                {
                    "ticker": ticker,
                    "action": "BUY",
                    "quantity": qty,
                    "total_value": total_value,
                    "trade_time": datetime.now().isoformat(),
                }
            )
            print(
                f"     [+] MUA {qty:.6f} {ticker} @ {current_price:.2f} "
                f"(tin cậy {confidence:.0f}%, kỳ vọng +{expected_return:.1f}%)"
            )

        else:
            if position["qty"] <= 0:
                continue  # Không bán khống.

            sell_qty = min(round(trade_amount / current_price, 6), position["qty"])
            if sell_qty <= 0:
                continue

            sell_value = current_price * sell_qty
            save_trade(user_id, ticker, "SELL", sell_qty, current_price, sell_value, "AUTO")
            session.record_sell(sell_value, profitable=current_price >= position["avg_cost"])
            all_trades.append(
                {
                    "ticker": ticker,
                    "action": "SELL",
                    "quantity": sell_qty,
                    "total_value": sell_value,
                    "trade_time": datetime.now().isoformat(),
                }
            )
            print(
                f"     [+] BÁN {sell_qty:.6f} {ticker} @ {current_price:.2f} "
                f"(tin cậy {confidence:.0f}%, kỳ vọng {expected_return:.1f}%)"
            )

    # Ghi toàn bộ thay đổi xuống DB một lần duy nhất.
    session.flush()


if __name__ == "__main__":
    run_auto_trade()
