"""
routers/notifications.py – Thông báo hệ thống và cảnh báo giá.

Hai lỗi được sửa ở bản này:

1. **IDOR khi đánh dấu đã đọc.** Bản cũ chỉ kiểm tra thông báo có tồn tại, không
   kiểm tra nó có thuộc về người gọi hay không — bất kỳ ai đăng nhập cũng đánh dấu
   được thông báo của người khác.

2. **Trạng thái đọc của thông báo chung (broadcast).** Bản cũ set `is_read = true`
   trực tiếp trên bản ghi, nghĩa là một người đọc thì tất cả mọi người đều thấy
   thông báo đó đã đọc. Nay trạng thái đọc của thông báo chung được lưu riêng
   theo từng người ở bảng `notification_reads`.

LƯU Ý ĐƯỜNG DẪN: router này khai báo đường dẫn đầy đủ (kể cả `/admin/notifications`)
nên KHÔNG được gắn prefix khi include ở main.py.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.database import _get_client
from backend.routers.auth import get_current_admin, get_current_user
from backend.security import log_and_raise, validate_ticker_format

router = APIRouter()

MAX_ALERTS_PER_USER = 30
NOTIFICATION_RETENTION_DAYS = 30


class NotificationRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=2000)
    user_id: Optional[int] = None  # None = gửi cho toàn bộ người dùng


class PriceAlertRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)
    condition: str = Field(pattern="^(above|below)$")
    target_price: float = Field(gt=0, le=100_000_000)


# ══════════════════════════════════════════════════════════════════════════════
#  THÔNG BÁO
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_read_ids(client, user_id: int) -> set:
    """Lấy tập id thông báo mà người dùng này đã đánh dấu đọc."""
    try:
        res = client.table("notification_reads").select("notification_id").eq(
            "user_id", user_id
        ).execute()
        return {r["notification_id"] for r in res.data or []}
    except Exception:
        # Bảng chưa được tạo (chưa chạy migration) — coi như chưa đọc gì.
        # Hệ thống vẫn chạy được, chỉ là thông báo chung luôn hiển thị chưa đọc.
        return set()


@router.get("/notifications")
def get_notifications(user: dict = Depends(get_current_user)):
    user_id = user["user_id"]
    c = _get_client()
    if not c:
        return {"success": False, "notifications": []}

    try:
        from datetime import datetime, timedelta, timezone

        cutoff = (datetime.now(timezone.utc) - timedelta(days=NOTIFICATION_RETENTION_DAYS)).isoformat()

        res = (
            c.table("notifications")
            .select("*")
            .gte("created_at", cutoff)
            .or_(f"user_id.eq.{user_id},user_id.is.null")
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        rows = res.data or []
        read_ids = _fetch_read_ids(c, user_id)

        notifications = []
        for r in rows:
            is_global = r.get("user_id") is None
            # Thông báo riêng dùng cờ trên chính bản ghi; thông báo chung tra bảng phụ.
            is_read = (r["id"] in read_ids) if is_global else bool(r.get("is_read"))
            notifications.append({**r, "is_read": is_read, "is_global": is_global})

        return {
            "success": True,
            "notifications": notifications,
            "unread_count": sum(1 for n in notifications if not n["is_read"]),
        }
    except Exception as e:
        print(f"[notifications] Lỗi khi lấy danh sách: {e}")
        return {"success": False, "notifications": [], "unread_count": 0}


@router.post("/notifications/{notif_id}/read")
def mark_notification_read(notif_id: int, user: dict = Depends(get_current_user)):
    user_id = user["user_id"]
    c = _get_client()
    if not c:
        raise HTTPException(503, "Không kết nối được cơ sở dữ liệu.")

    try:
        res = c.table("notifications").select("id, user_id").eq("id", notif_id).execute()
        if not res.data:
            raise HTTPException(404, "Không tìm thấy thông báo.")

        owner_id = res.data[0].get("user_id")

        if owner_id is None:
            # Thông báo chung: ghi trạng thái đọc riêng cho người này.
            c.table("notification_reads").upsert(
                {"user_id": user_id, "notification_id": notif_id},
                on_conflict="user_id,notification_id",
            ).execute()
        elif int(owner_id) == int(user_id):
            c.table("notifications").update({"is_read": True}).eq("id", notif_id).execute()
        else:
            # Không tiết lộ rằng thông báo tồn tại nhưng thuộc về người khác.
            raise HTTPException(404, "Không tìm thấy thông báo.")

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        log_and_raise("mark_notification_read", e, 500, "Không cập nhật được trạng thái thông báo.")


@router.delete("/notifications/{notif_id}")
def delete_notification(notif_id: int, user: dict = Depends(get_current_user)):
    user_id = user["user_id"]
    c = _get_client()
    if not c:
        raise HTTPException(503, "Không kết nối được cơ sở dữ liệu.")

    try:
        res = c.table("notifications").select("id, user_id").eq("id", notif_id).execute()
        if not res.data:
            raise HTTPException(404, "Không tìm thấy thông báo.")

        owner_id = res.data[0].get("user_id")

        if owner_id is None:
            # Người dùng thường không được xoá thông báo chung của cả hệ thống —
            # chỉ ẩn nó đi bằng cách đánh dấu đã đọc.
            c.table("notification_reads").upsert(
                {"user_id": user_id, "notification_id": notif_id},
                on_conflict="user_id,notification_id",
            ).execute()
            return {"success": True, "message": "Đã ẩn thông báo chung khỏi danh sách của bạn."}

        if int(owner_id) != int(user_id):
            raise HTTPException(404, "Không tìm thấy thông báo.")

        c.table("notifications").delete().eq("id", notif_id).eq("user_id", user_id).execute()
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        log_and_raise("delete_notification", e, 500, "Không xoá được thông báo.")


@router.post("/admin/notifications")
def create_notification(req: NotificationRequest, admin: dict = Depends(get_current_admin)):
    c = _get_client()
    if not c:
        raise HTTPException(503, "Không kết nối được cơ sở dữ liệu.")

    try:
        if req.user_id is not None:
            target = c.table("users").select("id").eq("id", req.user_id).execute()
            if not target.data:
                raise HTTPException(404, "Không tìm thấy người dùng nhận thông báo.")

        res = c.table("notifications").insert(
            {
                "title": req.title.strip(),
                "message": req.message.strip(),
                "user_id": req.user_id,
                "is_read": False,
            }
        ).execute()
        return {"success": True, "notification": res.data[0] if res.data else None}
    except HTTPException:
        raise
    except Exception as e:
        log_and_raise("create_notification", e, 500, "Không tạo được thông báo.")


# ══════════════════════════════════════════════════════════════════════════════
#  CẢNH BÁO GIÁ
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/alerts")
def create_alert(req: PriceAlertRequest, user: dict = Depends(get_current_user)):
    from backend.database import create_price_alert, get_user_alerts

    user_id = user["user_id"]
    ticker = validate_ticker_format(req.ticker)

    active_alerts = [a for a in get_user_alerts(user_id) if not a.get("is_triggered")]
    if len(active_alerts) >= MAX_ALERTS_PER_USER:
        raise HTTPException(
            400,
            f"Bạn đã đạt giới hạn {MAX_ALERTS_PER_USER} cảnh báo đang hoạt động. "
            "Hãy xoá bớt cảnh báo cũ.",
        )

    alert = create_price_alert(
        user_id=user_id,
        ticker=ticker,
        condition=req.condition,
        target_price=req.target_price,
    )
    if alert is None:
        raise HTTPException(500, "Không tạo được cảnh báo giá.")
    return {"success": True, "alert": alert}


@router.get("/alerts")
def get_alerts(user: dict = Depends(get_current_user)):
    from backend.database import get_user_alerts

    alerts = get_user_alerts(user["user_id"])
    return {
        "success": True,
        "alerts": alerts,
        "active_count": sum(1 for a in alerts if not a.get("is_triggered")),
    }


@router.delete("/alerts/{alert_id}")
def remove_alert(alert_id: int, user: dict = Depends(get_current_user)):
    from backend.database import delete_price_alert

    if not delete_price_alert(alert_id, user["user_id"]):
        raise HTTPException(404, "Không tìm thấy cảnh báo hoặc cảnh báo đã bị xoá.")
    return {"success": True}
