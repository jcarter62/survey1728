from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse

from app.config import SECRET_KEY
from app.db import engine, Base
from app.routers import api
from app.logging_config import setup_logging, request_client_ip, request_member_name, request_member_id
import logging
import time

app = FastAPI()

# Setup structured logging with request context
setup_logging()
logger = logging.getLogger(__name__)

# Middleware
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware to extract client IP (honoring common Cloudflare headers) and member name
@app.middleware("http")
async def add_request_context(request: Request, call_next):
    start = time.perf_counter()
    # Cloudflare may set CF-Connecting-IP or X-Forwarded-For; prefer CF header
    cf_ip = request.headers.get("CF-Connecting-IP")
    xff = request.headers.get("X-Forwarded-For")
    remote = request.client.host if request.client else "-"

    client_ip = cf_ip or (xff.split(",")[0].strip() if xff else None) or remote
    # store in contextvar for logging
    request_client_ip.set(client_ip or "-")

    # also attach to request.state for templates
    request.state.client_ip = client_ip or "-"

    # attempt to get member name from session (first + last)
    member_name = "-"
    member_id = "-"
    try:
        # Use request.scope.get to avoid AssertionError when SessionMiddleware isn't present
        sess = request.scope.get("session") or {}
        if sess:
            fn = sess.get("first_name") or ""
            ln = sess.get("last_name") or ""
            if fn or ln:
                member_name = f"{fn} {ln}".strip()
            else:
                # fallback to user_id if available
                uid = sess.get("user_id")
                if uid:
                    member_name = str(uid)
            # set member_id when available
            if sess.get("user_id"):
                member_id = str(sess.get("user_id"))
    except Exception:
        member_name = "-"
        member_id = "-"

    request_member_name.set(member_name or "-")
    request_member_id.set(member_id or "-")

    request.state.member_name = member_name or "-"
    request.state.member_id = member_id or "-"

    response = await call_next(request)

    # Access-style log with duration and response status
    try:
        status_code = response.status_code
    except Exception:
        status_code = "-"
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    logger.info(
        "%s %s %s %sms - client=%s member=%s id=%s",
        request.method,
        request.url.path,
        status_code,
        elapsed_ms,
        request.state.client_ip,
        request.state.member_name,
        request.state.member_id,
    )

    return response


templates = Jinja2Templates(directory="templates")

# Debug route to inspect/log the request context (temporary)
@app.get("/_debug/logctx")
async def debug_log_context(request: Request):
    logger.info(
        "debug log: client=%s member=%s id=%s",
        request.state.client_ip,
        request.state.member_name,
        request.state.member_id,
    )
    return JSONResponse(
        {
            "client": request.state.client_ip,
            "member": request.state.member_name,
            "member_id": request.state.member_id,
        }
    )

# Create tables that don't exist (non-destructive for existing members table)
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print("DB init error:", e)

app.include_router(api)

@app.get("/", response_class=HTMLResponse)
async def home_get(request: Request):
    return RedirectResponse(url="/login", status_code=303)

# Member dashboard now served from app.views /dashboard
