from datetime import UTC, datetime, timedelta

from backend.config import Settings
from backend.models.operations import CommonMessage, MessageDecision
from backend.services.link_safety import assess_spam, canonicalize_url
from backend.services.operations_pipeline import OperationsPipeline
from backend.services.operations_store import OperationsStore


def _settings(tmp_path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'reputation.db'}",
        operations_use_llm=False,
        reputation_helpful_reaction_threshold=3,
        reputation_block_link_reaction_threshold=3,
    )


def _message(message_id: str, text: str, author_id: str = "member-1") -> CommonMessage:
    return CommonMessage(
        message_id=message_id,
        platform="discord",
        community_id="guild-1",
        channel_id="channel-1",
        author_id=author_id,
        author_name="Thành viên thử nghiệm",
        text=text,
        timestamp=datetime.now(UTC),
    )


def _decision(category: str, severity: str, decision: str = "warn") -> MessageDecision:
    return MessageDecision(
        decision=decision,
        category=category,
        severity=severity,
        risk_score=0.9,
        confidence=0.9,
        explanation="test",
        model_used="test",
    )


def test_normal_single_link_is_not_spam() -> None:
    result = assess_spam("Tài liệu buổi học: https://docs.python.org/3/")

    assert result.suspicious is False
    assert result.urls == ("https://docs.python.org/3",)


def test_phishing_link_has_transparent_high_risk_evidence() -> None:
    result = assess_spam("Xác minh tài khoản ngay, gửi mã OTP tại https://bit.ly/nhan-qua")

    assert result.risk_score >= 0.9
    assert result.label == "credential_phishing"
    assert any("OTP" in evidence or "đăng nhập" in evidence for evidence in result.evidence)
    assert any("rút gọn" in evidence for evidence in result.evidence)


def test_third_identical_message_in_window_is_spam(tmp_path) -> None:
    settings = _settings(tmp_path)
    pipeline = OperationsPipeline(OperationsStore(settings), settings)

    first = pipeline.analyze(_message("repeat-1", "Tham gia khóa học mới của mình nhé"), [])
    second = pipeline.analyze(_message("repeat-2", "Tham gia khóa học mới của mình nhé"), [])
    third = pipeline.analyze(_message("repeat-3", "Tham gia khóa học mới của mình nhé"), [])

    assert first.decision == "allow"
    assert second.decision == "allow"
    assert third.category == "spam"
    assert third.gates[0].label == "repeated_message"
    assert third.decision == "hide"


def test_penalty_is_applied_only_when_admin_confirms_community_case(tmp_path) -> None:
    store = OperationsStore(_settings(tmp_path))
    helpful = _message("helpful-1", "Bạn có thể thử kiểm tra phần này trước.")
    violation = _message("violation-1", "Nội dung vi phạm")

    assert store.award_helpful_reputation(helpful, 3) is True
    assert store.award_helpful_reputation(helpful, 5) is False
    decision = _decision("harassment", "high")
    store.save_message(violation, decision, None)
    incident = store.upsert_incident(violation, decision)
    store.link_message_incident(violation.message_id, incident.incident_id)

    members = {member.platform_user_id: member for member in store.list_member_reputation()}
    assert members["member-1"].reputation_score == 5
    assert members["member-1"].positive_points == 5
    assert members["member-1"].penalty_points == 0
    assert members["member-1"].event_count == 1

    outcome, affected, points = store.decide_incident_reputation(
        incident.incident_id,
        "confirmed",
        "Admin",
    )
    assert outcome == "confirmed"
    assert affected == 1
    assert points == -2

    member = store.list_member_reputation()[0]
    assert member.reputation_score == 3
    assert member.positive_points == 5
    assert member.penalty_points == 2
    assert member.event_count == 2


def test_reputation_leaderboard_includes_telegram_and_excludes_bots_and_demo_records(tmp_path) -> None:
    store = OperationsStore(_settings(tmp_path))
    human = _message("human-1", "Xin chào", author_id="human-1")
    bot = _message("bot-1", "Phản hồi tự động", author_id="bot-1").model_copy(
        update={"author_name": "CHAT-10", "raw": {"author_is_bot": True}}
    )
    demo = human.model_copy(
        update={"message_id": "demo-1", "platform": "demo", "author_id": "demo-user"}
    )
    telegram = human.model_copy(
        update={"message_id": "telegram-1", "platform": "telegram", "author_id": "telegram-user"}
    )
    second_guild = human.model_copy(
        update={
            "message_id": "human-2",
            "community_id": "guild-2",
            "author_name": "Tên mới nhất",
            "timestamp": human.timestamp + timedelta(seconds=1),
        }
    )
    safe = _decision("safe", "low", decision="allow")

    store.save_message(human, safe, None)
    store.save_message(bot, safe, None)
    store.save_message(demo, safe, None)
    store.save_message(telegram, safe, None)
    store.save_message(second_guild, safe, None)
    store.award_helpful_reputation(human, 3)
    members = store.list_member_reputation()
    assert [member.platform_user_id for member in members] == ["human-1", "telegram-user"]
    assert members[0].display_name == "Tên mới nhất"
    assert members[0].reputation_score == 5
    assert members[0].event_count == 1
    assert members[1].platform == "telegram"


def test_rejected_link_is_blocked_but_penalty_waits_for_admin(tmp_path) -> None:
    settings = _settings(tmp_path)
    store = OperationsStore(settings)
    original = _message("link-original", "Xem tại https://Example.com/a/?utm_source=chat")
    store.save_message(original, _decision("safe", "low", decision="allow"), None)

    assert store.flag_links_from_reactions(original, ["https://example.com/a/?utm_source=chat"], 3) is True
    assert store.flag_links_from_reactions(original, ["https://example.com/a"], 4) is False
    assert canonicalize_url("https://Example.com/a/?utm_source=chat") == "https://example.com/a"
    assert store.find_blocked_links("Gửi lại https://example.com/a#section")

    repeated = _message("link-repeat", "Gửi lại https://example.com/a#section", author_id="member-2")
    result = OperationsPipeline(store, settings).analyze(repeated, [])

    assert result.category == "spam"
    assert result.gates[0].label == "blocked_link"
    assert result.risk_score == 1.0
    members = {member.platform_user_id: member for member in store.list_member_reputation()}
    assert members["member-1"].reputation_score == 0
    assert members["member-2"].reputation_score == 0
    assert len(store.list_flagged_links()) == 1


def test_one_case_penalizes_each_real_user_once_even_with_many_messages(tmp_path) -> None:
    store = OperationsStore(_settings(tmp_path))
    messages = [
        _message("case-a-1", "Tin vi phạm một", author_id="member-a"),
        _message("case-a-2", "Tin vi phạm hai", author_id="member-a"),
        _message("case-b-1", "Tin vi phạm ba", author_id="member-b"),
    ]
    decisions = [
        _decision("harassment", "medium"),
        _decision("harassment", "high"),
        _decision("harassment", "medium"),
    ]
    incident_id = ""
    for message, decision in zip(messages, decisions):
        store.save_message(message, decision, None)
        incident = store.upsert_incident(message, decision)
        incident_id = incident.incident_id
        store.link_message_incident(message.message_id, incident_id)

    outcome, affected, points = store.decide_incident_reputation(incident_id, "confirmed", "Moderator")
    assert outcome == "confirmed"
    assert affected == 2
    assert points == -3

    members = {member.platform_user_id: member for member in store.list_member_reputation()}
    assert members["member-a"].reputation_score == -2
    assert members["member-b"].reputation_score == -1

    repeated = store.decide_incident_reputation(incident_id, "confirmed", "Moderator")
    assert repeated == ("confirmed", 2, -3)
    members = {member.platform_user_id: member for member in store.list_member_reputation()}
    assert members["member-a"].reputation_score == -2


def test_new_engagement_rules_are_drafts_with_anti_farm_limits(tmp_path) -> None:
    store = OperationsStore(_settings(tmp_path))
    rules = {rule.rule_id: rule for rule in store.list_reputation_rules()}

    assert len(rules) == 12
    assert rules["REP-HELPFUL-ANSWER"].active is True
    assert rules["REP-DAILY-ACTIVE"].active is False
    assert rules["REP-DAILY-ACTIVE"].daily_limit == 1
    assert rules["REP-WEEKLY-HELPER"].weekly_limit == 1
    assert rules["REP-PENALTY-SPAM"].points == -5
    assert rules["REP-PENALTY-SPAM"].trigger_mode == "admin_review"
