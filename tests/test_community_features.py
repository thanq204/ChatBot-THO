from datetime import UTC, datetime

from src.config import Settings
from src.models.community import ConversationMessage, ConversationThread
from src.services.community_store import CommunityStore
from src.services.conversation_analysis import ConversationAnalysisService
from src.services.youtube_connector import YouTubeConnector, YouTubeConfigurationError


def make_thread(texts: list[str]) -> ConversationThread:
    now = datetime.now(UTC)
    return ConversationThread(
        thread_id="TEST-THREAD", platform="youtube", community_id="test", channel_id="channel",
        video_id="dQw4w9WgXcQ", messages=[
            ConversationMessage(message_id=f"m{index}", parent_message_id="m0" if index else None,
                                 author_id=f"user-{index}", text=text, timestamp=now)
            for index, text in enumerate(texts)
        ], source_mode="imported_dataset", action_mode="simulated", imported_at=now,
    )


def test_analysis_detects_escalation_and_recommends_mediation():
    thread = make_thread(["Đừng có nói kiểu đó, mày vô dụng!", "Im đi, tao sẽ tìm ra mày."])
    analysis = ConversationAnalysisService(Settings(moderation_mode="mock")).analyze(thread)
    assert analysis.escalation_score >= 0.65
    assert analysis.conversation_stage in {"escalating", "critical"}
    assert analysis.triggers
    assert analysis.needs_intervention is True


def test_store_round_trip_preserves_messages_and_analysis(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'community.db'}", moderation_mode="mock")
    store = CommunityStore(settings=settings)
    thread = make_thread(["Xin chào", "Cảm ơn bạn!"])
    analysis = ConversationAnalysisService(settings).analyze(thread)
    stored = store.upsert_thread(thread.model_copy(update={"analysis": analysis}))
    assert stored.thread_id == "TEST-THREAD"
    assert len(store.get_thread("TEST-THREAD").messages) == 2
    assert store.health().total_conversations == 1


def test_youtube_parser_accepts_common_urls_and_rejects_unknown_input():
    connector = YouTubeConnector(settings=Settings(database_url="sqlite:///./data/test-youtube.db"))
    assert connector.parse_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert connector.parse_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    try:
        connector.parse_video_id("not-a-youtube-link")
    except YouTubeConfigurationError:
        pass
    else:
        raise AssertionError("invalid YouTube input should be rejected")
