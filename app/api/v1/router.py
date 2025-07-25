"""
Main API router for v1 endpoints.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import health, auth, integrations, tickets, bot, admin

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(integrations.router, prefix="/integrations", tags=["integrations"])
api_router.include_router(tickets.router, prefix="/tickets", tags=["tickets"])
api_router.include_router(bot.router, prefix="/bot", tags=["bot"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])