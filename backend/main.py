from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.operations_routes import get_operations_pipeline
from backend.api.operations_routes import router as operations_router
from backend.api.routes import get_review_store, router
from backend.config import get_settings
from backend.services.discord.bot import DiscordRagBot
from backend.services.telegram.bot import TelegramRagBot


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    get_review_store()
    operations_pipeline = get_operations_pipeline()
    operations_pipeline.store.purge_demo_data()
    operations_pipeline.store.deduplicate_open_incidents()
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

app.include_router(router, prefix="/api/v1")
app.include_router(operations_router, prefix="/api/v1")

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
