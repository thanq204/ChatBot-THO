from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.operations_routes import get_operations_pipeline
from backend.api.operations_routes import router as operations_router
from backend.api.auth_routes import router as auth_router
from backend.api.routes import get_review_store, router
from backend.config import get_settings
from backend.services.discord.bot import DiscordRagBot
from backend.services.telegram.bot import TelegramRagBot
from backend.services.auth_service import current_user, get_auth_store
from backend.services.database import close_postgres_pools, warm_postgres_pool

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    warm_postgres_pool(
        settings.faq_pg_dsn,
        settings.postgres_pool_min_size,
        settings.postgres_pool_max_size,
    )
    get_auth_store()
    get_review_store()
    operations_pipeline = get_operations_pipeline()
    if settings.operations_startup_maintenance_enabled:
        if settings.operations_demo_mode:
            try:
                operations_pipeline.store.purge_demo_data()
            except Exception:
                logger.exception("Demo-data cleanup failed; continuing application startup.")
        try:
            operations_pipeline.store.deduplicate_open_incidents()
        except Exception:
            logger.exception("Incident deduplication failed; continuing application startup.")
    discord_rag_bot = DiscordRagBot(operations_pipeline.store, settings, pipeline=operations_pipeline)
    telegram_rag_bot = TelegramRagBot(operations_pipeline.store, settings, pipeline=operations_pipeline)
    discord_rag_bot.start()
    telegram_rag_bot.start()
    print(f"Starting {settings.app_name} in {settings.app_env} mode")
    try:
        yield
    finally:
        discord_rag_bot.stop()
        telegram_rag_bot.stop()
        close_postgres_pools()
        print("Shutting down...")


app = FastAPI(
    title="AI20K Agent",
    description="AI Agent built with LangGraph",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(router, prefix="/api/v1")
app.include_router(operations_router, prefix="/api/v1", dependencies=[Depends(current_user)])

@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env}


# The React app is built by `npm run build` in frontend/ and emitted to frontend/dist.
# In development the Vite dev server owns the UI and proxies /api here, so dist/ may
# not exist yet; the backend must still start and serve the API in that case.
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if (FRONTEND_DIST / "index.html").exists():
    app.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_DIST / "assets"),
        name="assets",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        """Serve built files directly, and hand every other path to the router."""
        if full_path.startswith(("api/", "health", "docs", "redoc", "openapi.json")):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (FRONTEND_DIST / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(FRONTEND_DIST):
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
