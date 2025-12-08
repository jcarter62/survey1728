from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from .db import get_db
from .models import Member
from .config import COUNCIL_TITLE

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
    member_number: str = Form(...),
    db: Session = Depends(get_db),
):
    member = (
        db.query(Member)
        .filter(Member.last_name.ilike(last_name.strip()))
        .filter(Member.member_number == member_number.strip())
        .first()
    )
    if not member:
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Invalid credentials"},
            status_code=400,
        )
    request.session["user_id"] = member.id
    return RedirectResponse(url="/dashboard", status_code=303)

@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
