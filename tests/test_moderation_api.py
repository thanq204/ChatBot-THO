from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.api import routes
from backend.config import Settings
from backend.main import FRONTEND_DIST, app
from backend.models.auth import UserPublic
from backend.services.auth_service import current_user
from backend.services.moderation import ModerationEngine
from backend.services.review_store import ReviewStore


@pytest.fixture
def moderation_api_store(monkeypatch, tmp_path):
    store = ReviewStore(f"sqlite:///{tmp_path / 'api-reviews.db'}")
    monkeypatch.setattr(routes, "_review_store", store)
    monkeypatch.setattr(routes, "_moderation_engine", ModerationEngine(Settings(moderation_mode="mock", gemini_api_key="")))
    admin = UserPublic(
        user_id=uuid4(),
        email="admin@test.local",
        display_name="Test Admin",
        role="admin",
        is_root_admin=True,
        is_active=True,
        created_at=datetime.now(UTC),
    )
    app.dependency_overrides[current_user] = lambda: admin
    yield store
    app.dependency_overrides.pop(current_user, None)


@pytest.mark.asyncio
async def test_member_to_admin_to_audit_flow(client, moderation_api_store):
    submitted = await client.post(
        "/api/v1/moderation/submit",
        json={"user_id": "U005", "role": "member", "channel": "project", "text": "Làm ăn kiểu này thì nghỉ luôn đi.", "recent_context": ["Bạn gửi lại file giúp mình nhé."]},
    )
    assert submitted.status_code == 200
    data = submitted.json()
    assert data["moderation"]["action"] == "review"
    review_id = data["review"]["review_id"]

    queue = await client.get("/api/v1/moderation/review-queue")
    assert len(queue.json()) == 1
    decision = await client.post(
        f"/api/v1/moderation/review-queue/{review_id}/decision",
        json={"action": "allow", "reviewer": "Admin", "admin_note": "Context is harmless."},
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "reviewed"

    audit = await client.get("/api/v1/moderation/audit-logs")
    assert audit.status_code == 200
    assert audit.json()[0]["admin_action"] == "allow"


@pytest.mark.asyncio
async def test_member_content_must_not_be_empty(client, moderation_api_store):
    response = await client.post("/api/v1/moderation/submit", json={"user_id": "U001", "text": ""})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_gemini_mode_without_key_returns_configuration_error(client, monkeypatch, tmp_path):
    monkeypatch.setattr(routes, "_moderation_engine", ModerationEngine(Settings(moderation_mode="gemini", gemini_api_key="")))
    monkeypatch.setattr(routes, "_review_store", ReviewStore(f"sqlite:///{tmp_path / 'missing-key.db'}"))

    response = await client.post(
        "/api/v1/moderation/submit",
        json={"user_id": "U001", "text": "Xin chào"},
    )

    assert response.status_code == 503
    assert "GEMINI_API_KEY" in response.json()["detail"]


@pytest.mark.asyncio
async def test_health_is_served(client):
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_spa_fallback_serves_the_react_shell(client):
    """Client-side routes must resolve to index.html, not 404.

    Skipped when the frontend has not been built, since dist/ is a build artifact
    and the backend is expected to run without it during API-only development.
    """
    if not (FRONTEND_DIST / "index.html").exists():
        pytest.skip("frontend/dist not built")

    for path in ("/", "/operations", "/review-queue", "/member"):
        response = await client.get(path)
        assert response.status_code == 200
        assert "<div id=\"root\">" in response.text


@pytest.mark.asyncio
async def test_moderation_status_does_not_expose_api_key(client, monkeypatch):
    monkeypatch.setattr(routes, "_moderation_engine", ModerationEngine(Settings(moderation_mode="gemini", gemini_api_key="secret-value")))

    response = await client.get("/api/v1/moderation/status")

    assert response.status_code == 200
    assert response.json()["configured"] is True
    assert "secret-value" not in response.text
