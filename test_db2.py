from backend.database import _get_client
c = _get_client()
res = c.table("users").select("id, username, admin_config(current_balance)").execute()
for u in res.data:
    print(u)
