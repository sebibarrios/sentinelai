from fastapi import APIRouter

from app.api.v1 import auth, dashboard, health, incidents, users

api_router = APIRouter(prefix="/api/v1")
for module in (health, auth, users, dashboard, incidents):
    api_router.include_router(module.router)
