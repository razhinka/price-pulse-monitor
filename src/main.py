import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.routes import router
from src.config import settings
from src.db.repositories import seed_demo_catalog
from src.db.session import async_session_factory, init_db
from src.services.cache_service import cache_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Initializing PricePulse database and demo catalog...")
    await init_db()
    async with async_session_factory() as session:
        await seed_demo_catalog(session)
    yield
    await cache_service.close()


app = FastAPI(
    title=settings.app_title,
    version="1.0.0",
    description="REST API и аналитический дашборд мониторинга цен конкурентов.",
    lifespan=lifespan,
)

app.include_router(router)
