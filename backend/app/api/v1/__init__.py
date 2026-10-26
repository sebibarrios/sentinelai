from fastapi import APIRouter

from app.api.v1 import ai, alerts, auth, dashboard, events, health, incidents, uploads, users

api_router = APIRouter(prefix="/api/v1")
for module in (health, auth, users, dashboard, incidents, uploads, events, alerts, ai):
    api_router.include_router(module.router)
