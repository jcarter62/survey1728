from datetime import date, datetime
from typing import List, Dict

from fastapi import APIRouter, Depends, Request, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

import logging

from .db import get_db
from .models import Activity, Member
from .config import COUNCIL_TITLE, EMAIL_TEXT

from .email_sender import EMailSender
from dotenv import load_dotenv
import os

load_dotenv()

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Detailed Form 1728 Section 1 activities grouped as in prompts.txt
FAITH_ACTIVITIES: List[str] = [
    "Refund Support Vocations Program",
    "Church Facilities",
    "Catholic Schools/Seminaries",
    "Religious/Vocations Education",
    "Prayer & Study Programs",
    "Sacramental Gifts",
    "Miscellaneous Faith Activities",
]

FAMILY_ACTIVITIES: List[str] = [
    "Food for Families",
    "Family Formation Programs",
    "Keep Christ in Christmas",
    "Family Week",
    "Family Prayer Night",
    "Miscellaneous Family Programs",
]

COMMUNITY_ACTIVITIES: List[str] = [
    "Coats For Kids",
    "Global Wheelchair Mission",
    "Habitat for Humanity",
    "Disaster Preparedness/Relief",
    "Physically Disabled/Intellectual Disabilities",
    "Elderly/Widow(er) Care",
    "Hospitals/Health Organizations",
    "Columbian Squires",
    "Scouting/Youth Groups",
    "Athletics",
    "Youth Welfare/Service",
    "Scholarships/Education",
    "Veteran Military/VAVS",
    "Miscellaneous Community/Youth Activities",
]

LIFE_ACTIVITIES: List[str] = [
    "Special Olympics",
    "Marches for Life",
    "Ultrasound Initiative",
    "Pregnancy Center Support",
    "Christian Refugee Relief",
    "Memorials to Unborn Children",
    "Miscellaneous Life Activities",
]

OTHER_QUANTITATIVE: List[str] = [
    "Visits to the Sick",
    "Visits to the Bereaved",
    "Number of Blood Donations",
    "Masses Held for Members",
    "Hours of Fraternal Service to Sick/Disabled Members and their Families",
]

# Items which are quantities (counts) and should NOT be counted as volunteer hours
QUANTITY_EXCLUDE_HOURS: List[str] = [
    "Visits to the Sick",
    "Visits to the Bereaved",
    "Number of Blood Donations",
    "Masses Held for Members",
]

# For simplicity we still store all metrics in the Activity table, using
# category as the exact label from above. For OTHER_QUANTITATIVE rows we
# store the quantity in Activity.hours and leave amount at 0.

def get_current_member(request: Request, db: Session) -> Member | None:
    # access the session via request.scope to avoid AssertionError if middleware not installed
    sess = request.scope.get("session") or {}
    user_id = sess.get("user_id")
    if not user_id:
        return None
    return db.query(Member).filter(Member.id == user_id).first()


def require_admin(member: Member | None) -> None:
    if not member or not getattr(member, "is_admin", False):
        raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    member = get_current_member(request, db)
    if not member:
        return RedirectResponse("/login", status_code=303)

    activities = db.query(Activity).filter(Activity.member_id == member.id).all()
    # Exclude quantity-only categories from the total volunteer hours
    total_hours = sum(a.hours for a in activities if str(a.category) not in QUANTITY_EXCLUDE_HOURS)
    total_amount = sum(a.amount for a in activities)

    category_totals: Dict[str, Dict[str, float]] = {}
    for a in activities:
        cat = str(a.category)
        category_totals.setdefault(cat, {"hours": 0.0, "amount": 0.0})
        category_totals[cat]["hours"] += a.hours
        category_totals[cat]["amount"] += a.amount

    grouped = {
        "Faith": [(label, category_totals.get(label, {"hours": 0.0, "amount": 0.0})) for label in FAITH_ACTIVITIES],
        "Family": [(label, category_totals.get(label, {"hours": 0.0, "amount": 0.0})) for label in FAMILY_ACTIVITIES],
        "Community": [(label, category_totals.get(label, {"hours": 0.0, "amount": 0.0})) for label in COMMUNITY_ACTIVITIES],
        "Life": [(label, category_totals.get(label, {"hours": 0.0, "amount": 0.0})) for label in LIFE_ACTIVITIES],
        "Other": [(label, category_totals.get(label, {"hours": 0.0, "amount": 0.0})) for label in OTHER_QUANTITATIVE],
    }

    return templates.TemplateResponse(
        "member/dashboard.html",
        {
            "request": request,
            "member": member,
            "council_title": COUNCIL_TITLE,
            "total_hours": total_hours,
            "total_amount": total_amount,
            "grouped": grouped,
        },
    )


@router.get("/activities", response_class=HTMLResponse)
async def activities_get(request: Request, db: Session = Depends(get_db)):
    member = get_current_member(request, db)
    if not member:
        return RedirectResponse("/login", status_code=303)

    activities = db.query(Activity).filter(Activity.member_id == member.id).all()
    activity_map = {str(a.category): a for a in activities}

    return templates.TemplateResponse(
        "member/activities.html",
        {
            "request": request,
            "member": member,
            "faith": FAITH_ACTIVITIES,
            "family": FAMILY_ACTIVITIES,
            "community": COMMUNITY_ACTIVITIES,
            "life": LIFE_ACTIVITIES,
            "other": OTHER_QUANTITATIVE,
            "activity_map": activity_map,
            "today": date.today(),
            "error": None,
        },
    )


@router.post("/activities")
async def activities_post(request: Request, db: Session = Depends(get_db)):
    member = get_current_member(request, db)
    if not member:
        return RedirectResponse(url="/login", status_code=303)

    form = await request.form()

    def upsert(category: str, hours_raw: str, amount_raw: str, quantity_only: bool = False):
        try:
            if quantity_only:
                hours = float(hours_raw or "0")
                amount = 0.0
            else:
                hours = float(hours_raw or "0")
                amount = float(amount_raw or "0")
        except ValueError:
            raise ValueError("invalid")
        if hours < 0 or amount < 0:
            raise ValueError("negative")

        existing = (
            db.query(Activity)
            .filter(Activity.member_id == member.id, Activity.category == category)
            .first()
        )
        if existing:
            existing.hours = hours
            existing.amount = amount
            existing.date = date.today()
        else:
            if hours > 0 or amount > 0:
                db.add(
                    Activity(
                        member_id=member.id,
                        category=category,
                        description=f"Form 1728 Section 1 - {category}",
                        date=date.today(),
                        hours=hours,
                        amount=amount,
                    )
                )

    try:
        for category in FAITH_ACTIVITIES + FAMILY_ACTIVITIES + COMMUNITY_ACTIVITIES + LIFE_ACTIVITIES:
            hours_key = f"hours_{category}"
            amount_key = f"amount_{category}"
            upsert(category, form.get(hours_key, "0"), form.get(amount_key, "0"), quantity_only=False)

        for category in OTHER_QUANTITATIVE:
            qty_key = f"qty_{category}"
            upsert(category, form.get(qty_key, "0"), "0", quantity_only=True)

        db.commit()
    except ValueError as e:
        activities = db.query(Activity).filter(Activity.member_id == member.id).all()
        activity_map = {str(a.category): a for a in activities}
        msg = "Please enter valid numbers for all fields." if str(e) == "invalid" else "Values must be non-negative."
        return templates.TemplateResponse(
            "member/activities.html",
            {
                "request": request,
                "member": member,
                "faith": FAITH_ACTIVITIES,
                "family": FAMILY_ACTIVITIES,
                "community": COMMUNITY_ACTIVITIES,
                "life": LIFE_ACTIVITIES,
                "other": OTHER_QUANTITATIVE,
                "activity_map": activity_map,
                "today": date.today(),
                "error": msg,
            },
            status_code=400,
        )

    return RedirectResponse("/dashboard", status_code=303)


@router.get("/admin/report", response_class=HTMLResponse)
async def admin_report(request: Request, db: Session = Depends(get_db)):
    member = get_current_member(request, db)
    require_admin(member)

    activities = db.query(Activity).all()

    # Aggregate across all members by category
    category_totals: Dict[str, Dict[str, float]] = {}
    for a in activities:
        cat = str(a.category)
        category_totals.setdefault(cat, {"hours": 0.0, "amount": 0.0})
        category_totals[cat]["hours"] += a.hours
        category_totals[cat]["amount"] += a.amount

    grouped = {
        "Faith": [(label, category_totals.get(label, {"hours": 0.0, "amount": 0.0})) for label in FAITH_ACTIVITIES],
        "Family": [(label, category_totals.get(label, {"hours": 0.0, "amount": 0.0})) for label in FAMILY_ACTIVITIES],
        "Community": [(label, category_totals.get(label, {"hours": 0.0, "amount": 0.0})) for label in COMMUNITY_ACTIVITIES],
        "Life": [(label, category_totals.get(label, {"hours": 0.0, "amount": 0.0})) for label in LIFE_ACTIVITIES],
        "Other": [(label, category_totals.get(label, {"hours": 0.0, "amount": 0.0})) for label in OTHER_QUANTITATIVE],
    }

    # Per-member aggregates
    members = db.query(Member).order_by(Member.last_name, Member.first_name).all()
    member_totals: Dict[int, Dict[str, float]] = {int(getattr(m, "id")): {"hours": 0.0, "amount": 0.0} for m in members}
    for a in activities:
        mid = int(getattr(a, "member_id"))
        if mid not in member_totals:
            # skip activities for members not in list (shouldn't happen)
            continue
        # Only add to hours if this category represents hours, not a quantity-only item
        if str(a.category) not in QUANTITY_EXCLUDE_HOURS:
            member_totals[mid]["hours"] += a.hours
        # amounts are always monetary
        member_totals[mid]["amount"] += a.amount

    # Build a server-side list of member_numbers for members who have reported
    member_numbers: List[str] = []
    for m in members:
        totals = member_totals.get(int(getattr(m, "id")))
        hours = totals["hours"] if totals else 0.0
        amount = totals["amount"] if totals else 0.0
        if hours <= 0 and amount <= 0:
            member_numbers.append(str(getattr(m, "member_number")))

    return templates.TemplateResponse(
        "admin/report.html",
        {
            "request": request,
            "member": member,
            "council_title": COUNCIL_TITLE,
            "grouped": grouped,
            "members": members,
            "member_totals": member_totals,
            "not_reported": member_numbers,
        },
    )

@router.post('/admin/notify/{member_number}')
async def admin_notify_member(member_number: str, request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    member = get_current_member(request, db)
    require_admin(member)

    target_member = db.query(Member).filter(Member.member_number == member_number).first()
    if not target_member:
        raise HTTPException(status_code=404, detail="Member not found")

    # Determine if target has a valid access_code
    access_code = target_member.access_code
    if not access_code or access_code.strip() == "":
        # If not, generate and assign a new one
        from .access_code import AccessCode
        ac = AccessCode(db)
        # ensure we pass a plain int to satisfy the type checker
        access_code = ac.assign_access_code(int(getattr(target_member, "id")))

    target_member_email = target_member.email
    email_template_file_path = os.getenv("EMAIL_TEXT", EMAIL_TEXT)
    # expand ~ and environment variables and resolve to absolute path
    email_template_file_path = os.path.expanduser(os.path.expandvars(email_template_file_path))
    if not os.path.isabs(email_template_file_path):
        email_template_file_path = os.path.abspath(email_template_file_path)

    if not os.path.exists(email_template_file_path):
        # Provide a clear error to the admin/user instead of crashing the server
        raise HTTPException(status_code=500, detail=f"Email template not found: {email_template_file_path}")

    # load email-notification template (utf-8)
    with open(email_template_file_path, "r", encoding="utf-8") as f:
        email_text = f.read()

    # replace {name} placeholder with member's name
    email_text = email_text.replace("{name}", f"{target_member.first_name} {target_member.last_name}")
    email_text = email_text.replace('{last_name}', target_member.last_name or "")
    email_text = email_text.replace('{url}', os.getenv('URL', 'http://localhost:8000'))
    email_text = email_text.replace("{access_code}", access_code)

    # load email subject from environment or use default
    email_subject = os.getenv('EMAIL_SUBJECT', f"Notification from {COUNCIL_TITLE}")

    es = EMailSender()
    # Schedule synchronous send in background to avoid blocking the request
    # es.send_email(str(target_member_email), email_subject, email_text, False)
    background_tasks.add_task(
        es.send_email,
        str(target_member_email),
        email_subject,
        email_text,
        False
    )
    return { "status": "ok" }

@router.post('/admin/remove_member_record/{member_number}')
async def admin_remove_member_record(member_number: str, request: Request, db: Session = Depends(get_db)):
    member = get_current_member(request, db)
    require_admin(member)
    target_member = db.query(Member).filter(Member.member_number == member_number).first()
    if not target_member:
        raise HTTPException(status_code=404, detail="Member not found")
    try:
        # First delete associated activities
        db.query(Activity).filter(Activity.member_id == target_member.id).delete()
        # Then delete the member record
        db.delete(target_member)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to remove member record: {e}")
    return RedirectResponse("/admin/report", status_code=303)

@router.get("/import/membership", response_class=HTMLResponse)
async def import_members_get(request: Request, db: Session = Depends(get_db)):
    member = get_current_member(request, db)
#    require_admin(member)
    return templates.TemplateResponse(
        "admin/import_members.html",
        {
            "request": request,
            "member": member,
            "council_title": COUNCIL_TITLE,
            "error": None,
            "result": None,
        },
    )


@router.post("/import/membership", response_class=HTMLResponse)
async def import_members_post(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a CSV, truncate the members table, and import new members.

    Expected CSV headers (at minimum): member_number, first_name, last_name
    Optional headers: mobile_phone, email, access_code, is_admin
    """
    member = get_current_member(request, db)

    if not file.filename.lower().endswith(".csv"):
        return templates.TemplateResponse(
            "admin/import_members.html",
            {
                "request": request,
                "member": member,
                "council_title": COUNCIL_TITLE,
                "error": "Please upload a .csv file",
                "result": None,
            },
            status_code=400,
        )

    import io
    import csv

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except Exception:
        text = content.decode("utf-8", errors="replace")

    reader = csv.DictReader(io.StringIO(text))

    # Basic validation of required columns
    required_cols = ["Membership Number", "First Name", "Last Name", "Cell Phone", "Primary Email"]
    missing_cols = [c for c in required_cols if c not in (reader.fieldnames or [])]
    if missing_cols:
        return templates.TemplateResponse(
            "admin/import_members.html",
            {
                "request": request,
                "member": member,
                "council_title": COUNCIL_TITLE,
                "error": f"Missing required columns in CSV: {', '.join(missing_cols)}",
                "result": None,
            },
            status_code=400,
        )

    # Truncate existing members table
    try:
        db.query(Member).delete()
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to truncate members table: {e}")

    imported = 0
    skipped = 0
    errors = []

    for i, row in enumerate(reader, start=1):
        # skip entirely empty rows
        if not any((v or "").strip() for v in row.values()):
            skipped += 1
            continue

        try:
            m = Member(
                member_number=(row.get("Membership Number") or "").strip(),
                first_name=(row.get("First Name") or "").strip(),
                last_name=(row.get("Last Name") or "").strip(),
                mobile_phone=(row.get("Cell Phone") or "").strip(),
                email=(row.get("Primary Email") or "").strip(),
            )

            # optional fields
            if "access_code" in (reader.fieldnames or []):
                try:
                    if hasattr(m, "access_code"):
                        m.access_code = (row.get("access_code") or "").strip() or None
                except Exception:
                    pass

            if "is_admin" in (reader.fieldnames or []):
                val = (row.get("is_admin") or "").strip().lower()
                if val in ("1", "true", "yes", "y"):
                    try:
                        if hasattr(m, "is_admin"):
                            m.is_admin = True
                    except Exception:
                        pass

            db.add(m)
            imported += 1
        except Exception as e:
            errors.append(f"Row {i}: {e}")

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to commit imported members: {e}")

    # now set the access_codes for those members missing one
    from .access_code import AccessCode
    ac = AccessCode(db)
    members_without_ac = db.query(Member).filter((Member.access_code == None) | (Member.access_code == "")).all()
    for m in members_without_ac:
        ac.assign_access_code(int(getattr(m, "id")))

    result = {"imported": imported, "skipped": skipped, "errors": errors}

    return templates.TemplateResponse(
        "admin/import_members.html",
        {
            "request": request,
            "member": member,
            "council_title": COUNCIL_TITLE,
            "error": None,
            "result": result,
        },
    )


@router.get("/static/{filename}", response_class=HTMLResponse)
async def static_files(filename: str, request: Request):
    return FileResponse(f"static/{filename}")

@router.post("/admin/promote")
async def admin_promote_member(request: Request, member_number: str = Form(...), db: Session = Depends(get_db)):

    member = get_current_member(request, db)
#    require_admin(member)

    target_member = db.query(Member).filter(Member.member_number == member_number).first()
    if not target_member:
        raise HTTPException(status_code=404, detail="Member not found")

    try:
        if hasattr(target_member, "is_admin"):
            target_member.is_admin = True
            db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to promote member: {e}")

    return RedirectResponse("/dashboard", status_code=303)

@router.post('/api/activity-update')
async def api_activity_update(request: Request, db: Session = Depends(get_db)):
    """Receive JSON updates for a single activity and upsert into the Activity table for the current member.

    Expected JSON shape:
    {
        "category": "Activity Label",
        "hours": 1.5,           # optional, defaults to 0
        "amount": 10.0,         # optional, defaults to 0
        "quantity_only": false  # optional, true if this is a quantity-only field
    }
    """
    member = get_current_member(request, db)
    if not member:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    category = payload.get("category")
    if not category:
        return JSONResponse({"error": "missing_category"}, status_code=400)

    quantity_only = bool(payload.get("quantity_only", False))

    # parse numeric inputs defensively
    def to_float(v):
        try:
            if v is None or v == "":
                return 0.0
            return float(v)
        except Exception:
            raise ValueError("invalid_number")

    try:
        if quantity_only:
            hours = to_float(payload.get("hours", 0))
            amount = 0.0
        else:
            hours = to_float(payload.get("hours", 0))
            amount = to_float(payload.get("amount", 0))
    except ValueError:
        return JSONResponse({"error": "invalid_number"}, status_code=400)

    if hours < 0 or amount < 0:
        return JSONResponse({"error": "negative_value"}, status_code=400)

    existing = (
        db.query(Activity)
        .filter(Activity.member_id == member.id, Activity.category == category)
        .first()
    )

    try:
        if existing:
            existing.hours = hours
            existing.amount = amount
            existing.date = date.today()
        else:
            # Only create a new row if there's something to store (keep DB cleaner)
            if hours > 0 or amount > 0 or quantity_only:
                db.add(
                    Activity(
                        member_id=member.id,
                        category=category,
                        description=f"Form 1728 Section 1 - {category}",
                        date=date.today(),
                        hours=hours,
                        amount=amount,
                    )
                )
        db.commit()
    except Exception as e:
        db.rollback()
        return JSONResponse({"error": "db_error", "detail": str(e)}, status_code=500)

    # Determine client IP (respect CF and X-Forwarded-For headers)
    client_ip = request.headers.get("CF-Connecting-IP") or request.headers.get("X-Forwarded-For")
    if client_ip:
        client_ip = client_ip.split(",")[0].strip()
    else:
        client = getattr(request, 'client', None)
        client_ip = client.host if client else 'unknown'

    # Log autosave details
    try:
        logger.info(
            "autosave: member_id=%s member=%s %s category=%r hours=%s amount=%s qty_only=%s ip=%s",
            getattr(member, 'id', 'unknown'),
            getattr(member, 'first_name', ''),
            getattr(member, 'last_name', ''),
            category,
            hours,
            amount,
            quantity_only,
            client_ip,
        )
    except Exception:
        # ensure logging never breaks the response
        logger.exception("Failed to log autosave")

    # use timezone-aware UTC timestamp
    from datetime import timezone
    saved_at = datetime.now(timezone.utc).isoformat()

    return JSONResponse({"status": "ok", "saved_at": saved_at})
