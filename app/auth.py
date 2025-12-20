from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from .db import get_db
from .models import Member
from .config import COUNCIL_TITLE
import json

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/login")
def login_get(request: Request):
    context = {
        "request": request,
        "council_title": COUNCIL_TITLE,
    }
    return templates.TemplateResponse("auth/login.html", context=context)

@router.post("/login")
def login_post(
    request: Request,
    last_name: str = Form(...),
    access_code: str = Form(...),
    db: Session = Depends(get_db),
):
    # Trim inputs (we'll use ilike for case-insensitive comparison)
    last_name_trim = (last_name or "").strip()
    access_code_trim = (access_code or "").strip()

    member = (
        db.query(Member)
        .filter(Member.last_name.ilike(last_name_trim))
        .filter(Member.access_code.ilike(access_code_trim))
        .first()
    )
    if not member:
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Invalid credentials"},
            status_code=400,
        )

    # Access the underlying session mapping safely
    sess = request.scope.get("session")
    if sess is None:
        # SessionMiddleware not installed or session not available
        raise HTTPException(status_code=500, detail="SessionMiddleware not installed; cannot set session")

    # store user id and name in the session so middleware/logging can pick it up
    sess["user_id"] = member.id
    sess["first_name"] = member.first_name or ""
    sess["last_name"] = member.last_name or ""
    # store name also in the session for server-side convenience
    FullName = f"{member.first_name or ''} {member.last_name or ''}".strip()
    sess["full_name"] = FullName

    # Return HTML that sets localStorage.full_name and localStorage.member_id then navigates to /activities
    # Use json.dumps to safely escape the values for embedding in JS
    js_fullname = json.dumps(FullName)
    js_member_id = json.dumps(member.member_number or "")
    html = (
        "<!doctype html><html><head><meta charset=\"utf-8\"></head><body>"
        f"<script>try{{localStorage.setItem('full_name',{js_fullname});localStorage.setItem('member_id',{js_member_id});}}catch(e){{console.warn('localStorage not available',e);}}"
        "window.location.replace('/activities');</script>"
        "</body></html>"
    )
    return HTMLResponse(content=html, status_code=200)

@router.post("/logout")
def logout(request: Request):
    # Clear server-side session if present
    sess = request.scope.get("session")
    if sess is not None:
        sess.clear()

    # Return HTML that clears localStorage keys in the browser then redirects to /login
    html = (
        "<!doctype html><html><head><meta charset=\"utf-8\"></head><body>"
        "<script>try{localStorage.removeItem('full_name');localStorage.removeItem('member_id');}catch(e){console.warn('localStorage not available',e);}"
        "window.location.replace('/login');</script>"
        "</body></html>"
    )

    return HTMLResponse(content=html, status_code=200)