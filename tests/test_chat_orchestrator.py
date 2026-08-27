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


def test_community_views_exclude_bot_messages_and_bot_only_incidents(tmp_path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'app.db'}")
    store = OperationsStore(settings)
    decision = allowed().model_copy(update={"decision": "hide", "category": "spam", "risk_score": 0.9})
    human = message("human-1", "member input").model_copy(
        update={"platform": "discord", "community_id": "guild", "channel_id": "general", "thread_key": "human"}
    )
    bot = human.model_copy(
        update={
            "message_id": "bot-1",
            "author_id": "bot-user",
            "text": "bot output",
            "thread_key": "bot",
            "raw": {"type": 0, "author": {"id": "bot-user", "bot": True}},
        }
    )
    store.save_message(bot, decision, None)
    bot_incident = store.upsert_incident(bot, decision)
    store.link_message_incident(bot.message_id, bot_incident.incident_id)
    store.save_message(human, decision, None)
    human_incident = store.upsert_incident(human, decision)
    store.link_message_incident(human.message_id, human_incident.incident_id)

    health = store.community_health()
    summary = store.summary()
    timeline = store.activity_timeline()
    incidents = store.list_incidents()

    assert health.messages_total == 1
    assert health.unique_members == 1
    assert summary.messages_analyzed == 1
    assert summary.open_incidents == 1
    assert timeline.scanned_total == 1
    assert len(incidents) == 1
    assert "member-1" in incidents[0].title


def test_level_one_commands_bypass_moderation() -> None:
    store = Mock()
    store.list_command_content.return_value = [
        Mock(command="daily", description="Daily task", platforms=["telegram", "discord"])
    ]
    store.get_command_content.return_value = Mock(
        body="Daily task: review chapter 2",
        platforms=["telegram", "discord"],
    )
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


def test_report_command_audits_an_unpersisted_telegram_message(tmp_path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'app.db'}")
    store = OperationsStore(settings)
    chat = ChatOrchestrator(store, settings, Mock())

    outcome = chat.reply(message("telegram-report-1", "/report 123 - spam link"))

    assert outcome.stage == "rule"
    assert len(store.list_member_reports()) == 1
    audit = store.audit()[0]
    assert audit["event_type"] == "member_report_created"
    assert audit["message_id"] is None


def test_telegram_username_lookup_is_scoped_to_the_current_trade_chat(tmp_path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'app.db'}")
    store = OperationsStore(settings)
    seller_message = message("seller-message-1", "Xin chào").model_copy(
        update={
            "community_id": "-100-old",
            "channel_id": "-100-old",
            "author_id": "6981526945",
            "author_name": "Thanh Nguyen",
            "raw": {
                "from": {
                    "id": 6981526945,
                    "username": "thanh24109",
                    "first_name": "Thanh",
                    "last_name": "Nguyen",
                    "is_bot": False,
                }
            },
        }
    )
    store.save_message(seller_message, allowed(), None)

    assert store.find_telegram_member_by_username("-100-trade", "@Thanh24109") is None

    current_trade_message = seller_message.model_copy(
        update={
            "message_id": "seller-message-2",
            "community_id": "-100-trade",
            "channel_id": "-100-trade",
        }
    )
    store.save_message(current_trade_message, allowed(), None)
    assert store.find_telegram_member_by_username("-100-trade", "@Thanh24109") == (
        "6981526945",
        "Thanh Nguyen",
    )


def test_unknown_command_stops_at_rule() -> None:
    store = Mock()
    store.get_command_content.return_value = None
    pipeline = Mock()
    outcome = ChatOrchestrator(store, Settings(discord_rag_llm_enabled=False), pipeline).reply(message("unknown-command", "/not-a-command"))

    assert outcome.stage == "rule"
    assert "Không nhận ra lệnh" in outcome.answer
    pipeline.analyze.assert_not_called()


def test_moderation_reply_never_exposes_an_old_admin_action_as_new_action() -> None:
    store = Mock()
    pipeline = Mock()
    pipeline.analyze.return_value = MessageDecision(
        decision="warn",
        category="harassment",
        severity="medium",
        risk_score=0.8,
        confidence=0.8,
        explanation="Công kích cá nhân.",
        model_used="test",
        banner="(Đã được đánh dấu: Admin action: delete_message bởi: Admin)",
        already_marked=True,
    )

    outcome = ChatOrchestrator(store, Settings(discord_rag_llm_enabled=False), pipeline).reply(
        message("moderation-1", "con chó ngu")
    )

    assert outcome.stage == "moderation"
    assert outcome.answer.startswith("[Moderation]")
    assert "delete_message" not in outcome.answer
    assert "chỉ được thực hiện sau khi Admin/Mod xác nhận" in outcome.answer
