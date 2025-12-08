from fastapi import APIRouter
from . import auth
from . import views

api = APIRouter()
api.include_router(auth.router)
api.include_router(views.router)
