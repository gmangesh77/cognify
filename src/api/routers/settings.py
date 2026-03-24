"""Settings router — combines sub-routers for all settings endpoints."""

from fastapi import APIRouter

from src.api.routers.settings_config import settings_config_router
from src.api.routers.settings_domains import settings_domains_router

settings_router = APIRouter()
settings_router.include_router(settings_domains_router)
settings_router.include_router(settings_config_router)
