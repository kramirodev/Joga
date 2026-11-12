"""Router agregado da API v1."""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.bookings import router as bookings_router
from app.api.v1.chat import router as chat_router
from app.api.v1.health import router as health_router
from app.api.v1.matches import router as matches_router
from app.api.v1.matchmaking import router as matchmaking_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.payments import router as payments_router
from app.api.v1.presence import router as presence_router
from app.api.v1.pricing import router as pricing_router
from app.api.v1.profile import router as profile_router
from app.api.v1.progress import router as progress_router
from app.api.v1.ratings import router as ratings_router
from app.api.v1.results import router as results_router
from app.api.v1.social import router as social_router
from app.api.v1.substitutions import router as substitutions_router
from app.api.v1.tickets import router as tickets_router
from app.api.v1.venues import router as venues_router
from app.api.v1.web_auth import router as web_auth_router
from app.api.v1.ws import router as ws_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(profile_router)
api_router.include_router(matchmaking_router)
api_router.include_router(matches_router)
api_router.include_router(results_router)
api_router.include_router(ratings_router)
api_router.include_router(organizations_router)
api_router.include_router(venues_router)
api_router.include_router(pricing_router)
api_router.include_router(progress_router)
api_router.include_router(bookings_router)
api_router.include_router(substitutions_router)
api_router.include_router(tickets_router)
api_router.include_router(presence_router)
api_router.include_router(payments_router)
api_router.include_router(chat_router)
api_router.include_router(social_router)
api_router.include_router(web_auth_router)
api_router.include_router(ws_router)
