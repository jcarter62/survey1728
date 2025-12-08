from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse

from app.config import SECRET_KEY, COUNCIL_TITLE
from app.db import engine, Base
from app.routers import api
app = FastAPI()

# Middleware
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")

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
