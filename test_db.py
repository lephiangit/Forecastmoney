from backend.database import _get_client, get_admin_config
import sys

c = _get_client()
if not c:
    print("No client")
    sys.exit(1)

res = c.table("users").select("id, username, role").execute()
print("Users:", res.data)

for u in res.data:
    uid = u["id"]
    print(f"\n--- Checking User {uid} ({u['username']}) ---")
    
    # Check if config exists
    res_cfg = c.table("admin_config").select("*").eq("user_id", uid).execute()
    print("Existing config:", res_cfg.data)
    
    # Try get_admin_config
    cfg = get_admin_config(uid)
    print("After get_admin_config:", cfg)
    
    # Try direct update
    update_res = c.table("admin_config").update({"current_balance": 1000.0}).eq("user_id", uid).execute()
    print("Update result data:", update_res.data)
