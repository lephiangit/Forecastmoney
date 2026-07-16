"""
routers/notifications.py - Notifications endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional

from backend.routers.auth import get_current_user, get_current_admin
from backend.database import _get_client

router = APIRouter()

class NotificationRequest(BaseModel):
    title: str
    message: str
    user_id: Optional[int] = None  # None for global broadcast

@router.get("/notifications")
async def get_notifications(user: dict = Depends(get_current_user)):
    user_id = user["user_id"]
    c = _get_client()
    if not c:
        return {"success": False, "notifications": []}
    
    # Fetch notifications that belong to this user OR are global (user_id IS NULL)
    # Supabase syntax for OR: .or_("user_id.eq.{},user_id.is.null".format(user_id))
    try:
        from datetime import datetime, timedelta
        ten_days_ago = (datetime.utcnow() - timedelta(days=10)).isoformat()
        
        res = (c.table("notifications")
               .select("*")
               .gte("created_at", ten_days_ago)
               .or_(f"user_id.eq.{user_id},user_id.is.null")
               .order("created_at", desc=True)
               .limit(50)
               .execute())
        return {"success": True, "notifications": res.data or []}
    except Exception as e:
        print(f"Error fetching notifications: {e}")
        return {"success": False, "notifications": []}

@router.post("/notifications/{notif_id}/read")
async def mark_notification_read(notif_id: int, user: dict = Depends(get_current_user)):
    c = _get_client()
    if not c:
        raise HTTPException(500, "DB connection error")
    
    # Mark as read. (Ideally, global notifications need a separate user_notifications mapping to track read status, 
    # but for simplicity we will just mark the global notification as read for everyone, OR just ignore it.)
    try:
        # Check if the notification exists
        notif = c.table("notifications").select("*").eq("id", notif_id).execute()
        if not notif.data:
            raise HTTPException(404, "Notification not found")
            
        c.table("notifications").update({"is_read": True}).eq("id", notif_id).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, f"DB Error: {str(e)}")

@router.delete("/notifications/{notif_id}")
async def delete_notification(notif_id: int, user: dict = Depends(get_current_user)):
    c = _get_client()
    if not c:
        raise HTTPException(500, "DB connection error")
    
    try:
        # Check if the notification exists and belongs to the user
        notif = c.table("notifications").select("*").eq("id", notif_id).execute()
        if not notif.data:
            raise HTTPException(404, "Notification not found")
            
        if notif.data[0]["user_id"] != user["user_id"]:
            raise HTTPException(403, "Not authorized to delete this notification")
            
        c.table("notifications").delete().eq("id", notif_id).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, f"DB Error: {str(e)}")

@router.post("/admin/notifications")
async def create_notification(req: NotificationRequest, admin: dict = Depends(get_current_admin)):
    c = _get_client()
    if not c:
        raise HTTPException(500, "DB connection error")
    
    try:
        data = {
            "title": req.title,
            "message": req.message,
            "user_id": req.user_id,
            "is_read": False
        }
        res = c.table("notifications").insert(data).execute()
        return {"success": True, "notification": res.data[0] if res.data else None}
    except Exception as e:
        raise HTTPException(500, f"Error creating notification: {str(e)}")


# ── Price Alerts ──────────────────────────────────────────────────────────────

class PriceAlertRequest(BaseModel):
    ticker: str
    condition: str  # "above" | "below"
    target_price: float


@router.post("/alerts")
async def create_alert(req: PriceAlertRequest, user: dict = Depends(get_current_user)):
    """Create a new price alert."""
    if req.condition not in ("above", "below"):
        raise HTTPException(400, "condition must be 'above' or 'below'")
    if req.target_price <= 0:
        raise HTTPException(400, "target_price must be positive")

    from backend.database import create_price_alert
    alert = create_price_alert(
        user_id=user["user_id"],
        ticker=req.ticker.upper(),
        condition=req.condition,
        target_price=req.target_price,
    )
    if alert is None:
        raise HTTPException(500, "Failed to create alert")
    return {"success": True, "alert": alert}


@router.get("/alerts")
async def get_alerts(user: dict = Depends(get_current_user)):
    """Get all price alerts for the current user."""
    from backend.database import get_user_alerts
    alerts = get_user_alerts(user["user_id"])
    return {"success": True, "alerts": alerts}


@router.delete("/alerts/{alert_id}")
async def remove_alert(alert_id: int, user: dict = Depends(get_current_user)):
    """Delete a price alert."""
    from backend.database import delete_price_alert
    success = delete_price_alert(alert_id, user["user_id"])
    if not success:
        raise HTTPException(404, "Alert not found or already deleted")
    return {"success": True}

