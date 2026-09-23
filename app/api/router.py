"""
Mounts every domain router we have under /api/v0

if u want to add a domain, create one under app/<new domain> and create a router.py file like all the other
domains, then import it here as per the rest of them
"""

from fastapi import APIRouter

from app.auth.router import router as auth_router
from app.locations.router import router as locations_router
from app.me.router import router as me_router
from app.orders.router import router as orders_router
from app.organisations.router import router as organisations_router
from app.runs.router import router as runs_router
from app.volunteers.router import router as volunteers_router

api_router = APIRouter(prefix="/api/v0")

for domain_router in (
    auth_router,
    me_router,
    orders_router,
    runs_router,
    volunteers_router,
    organisations_router,
    locations_router,
):
    api_router.include_router(domain_router)
