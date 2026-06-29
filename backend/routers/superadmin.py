\"\"\"\nrouters/superadmin.py – DEPRECATED\n\nThis module is superseded by admin.py which provides the same user management\nfunctionality (balance updates, user deletion) under the /admin prefix.\nFrontend exclusively calls /admin/users/* endpoints.\n\nKeep this file for backward compatibility but do NOT add new endpoints here.\nConsider removing in a future cleanup.\n\"\"\"\nfrom fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List

from backend.routers.auth import get_current_user
from backend.database import _get_client

router = APIRouter()

def require_superadmin(current_user: dict = Depends(get_current_user)):
    if current_user.get("username") != "admin":
        raise HTTPException(status_code=403, detail="Superadmin access required")
    return current_user

class BalanceUpdate(BaseModel):
    new_balance: float

@router.get("/users")
async def get_all_users(admin: dict = Depends(require_superadmin)):
    c = _get_client()
    if not c:
        raise HTTPException(status_code=500, detail="DB Error")
    
    # Fetch all users
    users_res = c.table("users").select("id, username, created_at").execute()
    users = users_res.data or []
    
    # Fetch all balances
    configs_res = c.table("admin_config").select("*").execute()
    configs = {row["user_id"]: row for row in (configs_res.data or [])}
    
    # Merge
    result = []
    for u in users:
        conf = configs.get(u["id"], {"current_balance": 0.0, "total_pnl": 0.0, "is_running": False})
        result.append({
            "id": u["id"],
            "username": u["username"],
            "created_at": u["created_at"],
            "balance": conf.get("current_balance", 0.0),
            "pnl": conf.get("total_pnl", 0.0),
            "is_running": conf.get("is_running", False)
        })
        
    return {"success": True, "users": result}

@router.post("/users/{user_id}/balance")
async def update_user_balance(user_id: int, req: BalanceUpdate, admin: dict = Depends(require_superadmin)):
    c = _get_client()
    if not c:
        raise HTTPException(status_code=500, detail="DB Error")
        
    # Check if config exists
    conf = c.table("admin_config").select("id").eq("user_id", user_id).execute()
    if not conf.data:
        # Create
        c.table("admin_config").insert({
            "user_id": user_id,
            "initial_balance": req.new_balance,
            "current_balance": req.new_balance,
            "total_pnl": 0.0
        }).execute()
    else:
        # Update
        c.table("admin_config").update({
            "current_balance": req.new_balance
        }).eq("user_id", user_id).execute()
        
    return {"success": True, "message": "Balance updated"}

@router.delete("/users/{user_id}")
async def delete_user(user_id: int, admin: dict = Depends(require_superadmin)):
    c = _get_client()
    if not c:
        raise HTTPException(status_code=500, detail="DB Error")
    
    # Delete user from users table (cascade will handle the rest)
    c.table("users").delete().eq("id", user_id).execute()
    return {"success": True, "message": "User deleted"}
