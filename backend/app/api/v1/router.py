"""Router agregado da API v1."""

from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.admin_venues import router as admin_venues_router
from app.api.v1.app_config import router as app_config_router
from app.api.v1.auth import router as auth_router
from app.api.v1.avatar import router as avatar_router
from app.api.v1.bookings import router as bookings_router
from app.api.v1.catalog import router as catalog_router
from app.api.v1.chat import router as chat_router
from app.api.v1.clans import router as clans_router
from app.api.v1.discovery import router as discovery_router
from app.api.v1.email_auth import router as email_auth_router
from app.api.v1.geo import router as geo_router
from app.api.v1.health import router as health_router
from app.api.v1.legal import router as legal_router
from app.api.v1.matches import router as matches_router
from app.api.v1.matchmaking import router as matchmaking_router
from app.api.v1.moderation import router as moderation_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.passes import router as passes_router
from app.api.v1.payments import router as payments_router
from app.api.v1.presence import router as presence_router
from app.api.v1.pricing import router as pricing_router
from app.api.v1.profile import router as profile_router
from app.api.v1.progress import router as progress_router
from app.api.v1.ratings import router as ratings_router
from app.api.v1.results import router as results_router
from app.api.v1.social import router as social_router
from app.api.v1.stats import router as stats_router
from app.api.v1.substitutions import router as substitutions_router
from app.api.v1.tickets import router as tickets_router
from app.api.v1.users import router as users_router
from app.api.v1.venues import router as venues_router
from app.api.v1.web_auth import router as web_auth_router
from app.api.v1.ws import router as ws_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(app_config_router)
api_router.include_router(auth_router)
api_router.include_router(avatar_router)
api_router.include_router(email_auth_router)
api_router.include_router(legal_router)
api_router.include_router(catalog_router)
api_router.include_router(profile_router)
api_router.include_router(users_router)
api_router.include_router(admin_router)
api_router.include_router(admin_venues_router)
api_router.include_router(matchmaking_router)
api_router.include_router(matches_router)
api_router.include_router(results_router)
api_router.include_router(ratings_router)
api_router.include_router(organizations_router)
api_router.include_router(venues_router)
api_router.include_router(pricing_router)
api_router.include_router(discovery_router)
api_router.include_router(geo_router)
api_router.include_router(progress_router)
api_router.include_router(bookings_router)
api_router.include_router(substitutions_router)
api_router.include_router(tickets_router)
api_router.include_router(passes_router)
api_router.include_router(presence_router)
api_router.include_router(payments_router)
api_router.include_router(chat_router)
api_router.include_router(social_router)
api_router.include_router(clans_router)
api_router.include_router(stats_router)
api_router.include_router(notifications_router)
api_router.include_router(moderation_router)
api_router.include_router(web_auth_router)
api_router.include_router(ws_router)
