from fastapi import Request, HTTPException

def require_login(request: Request):
    # Access session via request.scope to avoid AssertionError when SessionMiddleware isn't present
    sess = request.scope.get("session") or {}
    if not sess.get("user_id"):
        raise HTTPException(status_code=401, detail="Not authenticated")
