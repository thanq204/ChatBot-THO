from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.models.auth import UserPublic
from backend.services.auth_service import current_user

TEST_ADMIN = UserPublic(
    user_id=UUID("00000000-0000-0000-0000-000000000001"),
    email="admin@test.local",
    display_name="Test Admin",
    role="admin",
    is_root_admin=True,
    is_active=True,
    created_at=datetime.now(UTC),
)


@pytest_asyncio.fixture
async def client():
    """Async HTTP client for testing API endpoints."""
    app.dependency_overrides[current_user] = lambda: TEST_ADMIN
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(current_user, None)


@pytest.fixture
def mock_llm():
    """Mock LLM to avoid calling OpenAI during tests.

    Usage in test:
        def test_something(mock_llm):
            # LLM calls will return mock response instead of hitting OpenAI
            ...
    """
    mock = AsyncMock()
    mock.ainvoke.return_value = AsyncMock(content="Mocked LLM response")
    return mock
