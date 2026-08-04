from datetime import UTC, datetime

from src.config import Settings
from src.models.community import ConversationMessage, ConversationThread
from src.services.embedding_memory import EmbeddingMemory


def make_thread(thread_id: str, text: str) -> ConversationThread:
    return ConversationThread(
        thread_id=thread_id,
        platform="youtube",
        community_id="test",
        channel_id="channel",
        video_id="video",
        messages=[ConversationMessage(message_id=f"{thread_id}-1", author_id="user", text=text, timestamp=datetime.now(UTC))],
        source_mode="public_api",
        action_mode="simulated",
        imported_at=datetime.now(UTC),
    )


def test_embedding_memory_persists_and_returns_exact_match(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'embedding.db'}", moderation_mode="mock")
    memory = EmbeddingMemory(settings)
    memory._embed = lambda text: [1.0, 0.0]  # type: ignore[method-assign]
    reviewed = make_thread("reviewed", "Please hide this repeated abusive comment")
    reviewed = reviewed.model_copy(update={"analysis": None})

    memory.remember_review(reviewed, "INT-1", "hide", "Admin")
    matches = memory.search(make_thread("new", "Please hide this repeated abusive comment"))

    assert matches
    assert matches[0]["score"] == 1.0
    assert matches[0]["admin_action"] == "hide"
