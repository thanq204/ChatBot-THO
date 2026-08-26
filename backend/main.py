import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api.auth_routes import router as auth_router
from backend.api.operations_routes import get_operations_pipeline
from backend.api.operations_routes import router as operations_router
from backend.api.routes import get_review_store, router
from backend.config import get_settings
from backend.services.auth_service import current_user, get_auth_store
from backend.services.database import close_postgres_pools, warm_postgres_pool
from backend.services.discord.bot import DiscordRagBot
from backend.services.telegram.bot import TelegramRagBot

logger = logging.getLogger(__name__)

MAX_API_REQUEST_BYTES = 12 * 1024 * 1024


class RequestSafetyMiddleware:
    """Reject oversized API bodies and attach browser hardening headers."""

    def __init__(self, app: Any, *, max_body_bytes: int, production: bool) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes
        self.production = production

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path") or "")
        if path.startswith("/api/"):
            headers = {key.lower(): value for key, value in scope.get("headers", [])}
            raw_length = headers.get(b"content-length")
            try:
                if raw_length and (int(raw_length) < 0 or int(raw_length) > self.max_body_bytes):
                    await JSONResponse(
                        {"detail": "Request vượt quá giới hạn 12 MB."},
                        status_code=413,
                    )(scope, receive, send)
                    return
            except ValueError:
                await JSONResponse({"detail": "Content-Length không hợp lệ."}, status_code=400)(scope, receive, send)
                return

        received = 0

        async def limited_receive() -> dict[str, Any]:
            nonlocal received
            message = await receive()
            if path.startswith("/api/") and message.get("type") == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_body_bytes:
                    raise ValueError("request-body-too-large")
            return message

        async def secure_send(message: dict[str, Any]) -> None:
            if message.get("type") == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-frame-options", b"DENY"),
                        (b"referrer-policy", b"strict-origin-when-cross-origin"),
                        (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                    ]
                )
                if self.production:
                    headers.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, limited_receive, secure_send)
        except ValueError as exc:
            if str(exc) != "request-body-too-large":
                raise
            await JSONResponse(
                {"detail": "Request vượt quá giới hạn 12 MB."},
                status_code=413,
            )(scope, receive, secure_send)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    discord_rag_bot: DiscordRagBot | None = None
    telegram_rag_bot: TelegramRagBot | None = None
    # Everything that can open a pooled PostgreSQL connection lives inside this
    # try, so a partial startup failure (e.g. Supabase's session-pooler client
    # cap) still reaches `close_postgres_pools()` in finally instead of leaking
    # connections that then compound across every `--reload` restart.
    try:
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
        yield
    finally:
        if discord_rag_bot:
            discord_rag_bot.stop()
        if telegram_rag_bot:
            telegram_rag_bot.stop()
        close_postgres_pools()
        print("Shutting down...")


settings = get_settings()
production = settings.app_env == "production"
app = FastAPI(
    title="AI20K Agent",
    description="AI Agent built with LangGraph",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if production else "/docs",
    redoc_url=None if production else "/redoc",
    openapi_url=None if production else "/openapi.json",
)

app.add_middleware(
    RequestSafetyMiddleware,
    max_body_bytes=MAX_API_REQUEST_BYTES,
    production=production,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
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
            raise HTTPException(status_code=404, detail="Không tìm thấy tài nguyên.")
        candidate = (FRONTEND_DIST / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(FRONTEND_DIST):
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
