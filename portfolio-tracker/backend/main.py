import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRouter

from auth import require_api_key
from config import settings
from database import AsyncSessionLocal, init_db
from routers import accounts, portfolio, upload, compliance, history, sync

logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler()


async def _scheduled_price_refresh() -> None:
    """Background job: refresh prices every 30 minutes."""
    try:
        async with AsyncSessionLocal() as db:
            from services.prices import refresh_prices
            result = await refresh_prices(db)
            logger.info("Scheduled price refresh: %s", result)
    except Exception as e:
        logger.warning("Scheduled price refresh failed: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    _scheduler.add_job(
        _scheduled_price_refresh,
        trigger=IntervalTrigger(minutes=30),
        id="price_refresh",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Price refresh scheduler started (every 30 min)")
    yield
    _scheduler.shutdown(wait=False)


# Allowed origins: localhost for dev, plus any configured frontend URLs
_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
]
if settings.frontend_url:
    _ALLOWED_ORIGINS.append(settings.frontend_url)

app = FastAPI(
    title="Portfolio Manager",
    description="Personal portfolio management and risk analysis platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_auth = {"dependencies": [Depends(require_api_key)]}

app.include_router(accounts.router,    **_auth)
app.include_router(portfolio.router,   **_auth)
app.include_router(upload.router,      **_auth)
app.include_router(compliance.router,  **_auth)
app.include_router(history.router,     **_auth)
app.include_router(sync.router,        **_auth)


# Public endpoints — no API key required (health checks, uptime monitors)
public_router = APIRouter()

@public_router.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok", "version": "0.1.0"}

app.include_router(public_router)
