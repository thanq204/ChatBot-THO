from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes import get_review_store, router
from src.api.community_routes import get_analysis_service, get_community_store, router as community_router
from src.config import get_settings
from src.services.community_demo import seed_demo


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    get_review_store()
    community_store = get_community_store()
    seed_demo(community_store, get_analysis_service())
    print(f"Starting {settings.app_name} in {settings.app_env} mode")
    yield
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
app.include_router(community_router, prefix="/api/v1")

WEB_DIR = Path(__file__).resolve().parent / "web"
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/", include_in_schema=False)
@app.get("/member", include_in_schema=False)
async def member_page():
    return FileResponse(WEB_DIR / "member.html")


@app.get("/admin", include_in_schema=False)
async def admin_page():
    return FileResponse(WEB_DIR / "admin.html")


@app.get("/youtube", include_in_schema=False)
async def youtube_page():
    return FileResponse(WEB_DIR / "youtube.html")


@app.get("/moderation-admin", include_in_schema=False)
async def moderation_admin_page():
    return FileResponse(WEB_DIR / "moderation-admin.html")


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env}
