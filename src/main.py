from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes import get_review_store, router
from src.api.operations_routes import get_operations_pipeline, router as operations_router
from src.config import get_settings
from src.services.discord_rag_bot import DiscordRagBot


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    get_review_store()
    operations_pipeline = get_operations_pipeline()
    operations_pipeline.store.purge_demo_data()
    operations_pipeline.store.deduplicate_open_incidents()
    discord_rag_bot = DiscordRagBot(operations_pipeline.store, settings, pipeline=operations_pipeline)
    discord_rag_bot.start()
    print(f"Starting {settings.app_name} in {settings.app_env} mode")
    try:
        yield
    finally:
        discord_rag_bot.stop()
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

WEB_DIR = Path(__file__).resolve().parent / "web"
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/", include_in_schema=False)
@app.get("/member", include_in_schema=False)
async def member_page():
    return FileResponse(WEB_DIR / "member.html")


@app.get("/admin", include_in_schema=False)
async def admin_page():
    return RedirectResponse("/operations", status_code=307)


@app.get("/moderation-admin", include_in_schema=False)
async def moderation_admin_page():
    return FileResponse(WEB_DIR / "moderation-admin.html")


@app.get("/operations", include_in_schema=False)
async def operations_page():
    return FileResponse(WEB_DIR / "operations.html")


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env}
