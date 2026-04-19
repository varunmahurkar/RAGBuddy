"""
router.py — mounts all API sub-routers under /api prefix.
"""
from fastapi import APIRouter

from api.documents import router as documents_router
from api.health import router as health_router
from api.history import router as history_router
from api.kb import router as kb_router
from api.query import router as query_router

api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
api_router.include_router(documents_router)
api_router.include_router(kb_router)
api_router.include_router(query_router)
api_router.include_router(history_router)
