from fastapi import Request, HTTPException

def require_login(request: Request):
    if not request.session.get("user_id"):
        raise HTTPException(status_code=401, detail="Not authenticated")

