from datetime import UTC, datetime
from unittest.mock import Mock

from backend.config import Settings
from backend.models.operations import CommonMessage, MessageDecision
from backend.services.chat_orchestrator import ChatOrchestrator
from backend.services.operations_store import OperationsStore


def message(message_id: str, text: str) -> CommonMessage:
    return CommonMessage(message_id=message_id, platform="telegram", author_id="member-1", text=text, timestamp=datetime.now(UTC))


def allowed() -> MessageDecision:
    return MessageDecision(decision="allow", category="safe", severity="low", risk_score=0.0, confidence=1.0, explanation="safe", model_used="test")


def test_moderation_precedes_faq(tmp_path) -> None:
    store = OperationsStore(Settings(database_url=f"sqlite:///{tmp_path / 'app.db'}"))
    store.upsert_faq("FAQ-1", __import__("backend.models.operations", fromlist=["FAQUpsertRequest"]).FAQUpsertRequest(question="How do I report spam?", answer="Use the report command."))
    pipeline = Mock()
    pipeline.analyze.return_value = allowed()

    outcome = ChatOrchestrator(store, Settings(database_url=f"sqlite:///{tmp_path / 'app.db'}"), pipeline).reply(message("m1", "How do I report spam?"))

    assert outcome.stage == "faq"
    assert outcome.answer == "Use the report command."
    pipeline.analyze.assert_called_once()


def test_unanswered_questions_create_one_suggestion_after_threshold(tmp_path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'app.db'}", discord_rag_llm_enabled=False)
    store = OperationsStore(settings)
    pipeline = Mock()
    pipeline.analyze.return_value = allowed()
    chat = ChatOrchestrator(store, settings, pipeline)
    for index in range(3):
        chat.reply(message(f"m{index}", "Where is the quantum cafeteria menu?"))

    suggestions = store.list_faq_suggestions()
    assert len(suggestions) == 1
    assert suggestions[0].question_count == 3


def test_community_health_counts_spam(tmp_path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'app.db'}")
    store = OperationsStore(settings)
    decision = allowed().model_copy(update={"decision": "hide", "category": "spam", "risk_score": 0.9})
    store.save_message(message("spam-1", "free money click link"), decision, None)

    health = store.community_health()

    assert health.messages_total == 1
    assert health.spam_count == 1
    assert health.risky_count == 1


def test_level_one_commands_bypass_moderation() -> None:
    store = Mock()
    store.get_command_content.return_value = Mock(body="Daily task: review chapter 2")
    pipeline = Mock()
    chat = ChatOrchestrator(store, Settings(discord_rag_llm_enabled=False), pipeline)

    help_outcome = chat.reply(message("command-help", "/help"))
    daily_outcome = chat.reply(message("command-daily", "/daily"))
    report_outcome = chat.reply(message("command-report", "/report 123 - spam link"))

    assert help_outcome.stage == "rule"
    assert "/daily" in help_outcome.answer
    assert daily_outcome.stage == "rule"
    assert daily_outcome.answer == "Daily task: review chapter 2"
    assert report_outcome.stage == "rule"
    pipeline.analyze.assert_not_called()


def test_unknown_command_stops_at_rule() -> None:
    pipeline = Mock()
    outcome = ChatOrchestrator(Mock(), Settings(discord_rag_llm_enabled=False), pipeline).reply(message("unknown-command", "/not-a-command"))

    assert outcome.stage == "rule"
    assert "Không nhận ra lệnh" in outcome.answer
    pipeline.analyze.assert_not_called()
