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
