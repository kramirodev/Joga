"""Router agregado da API v1."""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.matches import router as matches_router
from app.api.v1.matchmaking import router as matchmaking_router
from app.api.v1.profile import router as profile_router
from app.api.v1.ratings import router as ratings_router
from app.api.v1.results import router as results_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(profile_router)
api_router.include_router(matchmaking_router)
api_router.include_router(matches_router)
api_router.include_router(results_router)
api_router.include_router(ratings_router)
