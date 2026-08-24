from datetime import UTC, datetime, timedelta

import pytest

from backend.config import Settings
from backend.models.operations import CommonMessage, MessageDecision
from backend.services.link_safety import assess_spam, canonicalize_url
from backend.services.operations_pipeline import OperationsPipeline
from backend.services.operations_store import OperationsStore


def _settings(tmp_path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'reputation.db'}",
        openai_api_key="",
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


def test_admin_confirmation_is_audited_without_reducing_exp(tmp_path) -> None:
    store = OperationsStore(_settings(tmp_path))
    helpful = _message("helpful-1", "Bạn có thể thử kiểm tra phần này trước.")
    violation = _message("violation-1", "Nội dung vi phạm")

    assert store.award_helpful_experience(helpful, 3) is True
    assert store.award_helpful_experience(helpful, 5) is False
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
    assert points == 0

    member = store.list_member_reputation()[0]
    assert member.reputation_score == 5
    assert member.positive_points == 5
    assert member.penalty_points == 0
    assert member.event_count == 1
    experience = store.list_member_experience()[0]
    assert experience.exp_score == 5
    assert experience.level == "active"


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
    store.award_helpful_experience(human, 3)
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


def test_one_case_counts_each_real_user_once_without_changing_exp(tmp_path) -> None:
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
    assert points == 0

    members = {member.platform_user_id: member for member in store.list_member_reputation()}
    assert members["member-a"].reputation_score == 0
    assert members["member-b"].reputation_score == 0

    repeated = store.decide_incident_reputation(incident_id, "confirmed", "Moderator")
    assert repeated == ("confirmed", 2, 0)
    experience = {member.platform_user_id: member for member in store.list_member_experience()}
    assert experience["member-a"].exp_score == 0


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
    exp_rules = store.list_experience_rules()
    assert len(exp_rules) == 8
    assert all(rule.points > 0 for rule in exp_rules)


def test_verified_trade_review_requires_both_parties_and_the_real_buyer(tmp_path) -> None:
    store = OperationsStore(_settings(tmp_path))
    trade = store.create_trade_case(
        platform="discord",
        community_id="guild-1",
        channel_id="trade-channel",
        buyer_id="buyer-1",
        buyer_name="Buyer",
        seller_id="seller-1",
        seller_name="Seller",
        item_summary="Bàn phím cơ cũ",
        created_by="buyer-1",
    )
    assert trade.status == "opened"

    with pytest.raises(PermissionError):
        store.confirm_trade_case(trade.trade_id, "outsider")
    trade = store.confirm_trade_case(trade.trade_id, "buyer-1")
    assert trade and trade.status == "partially_confirmed"
    with pytest.raises(ValueError, match="hai bên"):
        store.add_seller_review(
            trade.trade_id,
            buyer_id="buyer-1",
            overall_rating=5,
            item_accuracy=5,
            communication=5,
            fulfillment=5,
            would_trade_again=True,
            comment="Ổn",
        )

    trade = store.confirm_trade_case(trade.trade_id, "seller-1")
    assert trade and trade.status == "completed" and trade.completed_at is not None
    with pytest.raises(PermissionError):
        store.add_seller_review(
            trade.trade_id,
            buyer_id="outsider",
            overall_rating=1,
            item_accuracy=1,
            communication=1,
            fulfillment=1,
            would_trade_again=False,
            comment="Không phải buyer",
        )

    review = store.add_seller_review(
        trade.trade_id,
        buyer_id="buyer-1",
        overall_rating=4,
        item_accuracy=4,
        communication=5,
        fulfillment=4,
        would_trade_again=True,
        comment="Đúng mô tả, phản hồi nhanh.",
    )
    assert review.verification_status == "verified_transaction"
    with pytest.raises(ValueError, match="một đánh giá"):
        store.add_seller_review(
            trade.trade_id,
            buyer_id="buyer-1",
            overall_rating=5,
            item_accuracy=5,
            communication=5,
            fulfillment=5,
            would_trade_again=True,
            comment="Đánh giá trùng",
        )

    summary = store.list_seller_summaries()[0]
    assert summary.completed_trades == 1
    assert summary.unique_buyers == 1
    assert summary.average_rating == 4.0
    assert summary.data_status == "insufficient_data"
    assert summary.anomaly_flags == []


def test_repeated_reviews_from_one_buyer_are_flagged_for_human_review(tmp_path) -> None:
    store = OperationsStore(_settings(tmp_path))
    for index in range(3):
        trade = store.create_trade_case(
            platform="discord",
            community_id="guild-1",
            channel_id="trade-channel",
            buyer_id="buyer-1",
            buyer_name="Buyer",
            seller_id="seller-1",
            seller_name="Seller",
            item_summary=f"Sản phẩm {index}",
            created_by="buyer-1",
        )
        store.confirm_trade_case(trade.trade_id, "buyer-1")
        store.confirm_trade_case(trade.trade_id, "seller-1")
        store.add_seller_review(
            trade.trade_id,
            buyer_id="buyer-1",
            overall_rating=5,
            item_accuracy=5,
            communication=5,
            fulfillment=5,
            would_trade_again=True,
            comment="Tốt",
        )

    summary = store.list_seller_summaries()[0]
    assert summary.completed_trades == 3
    assert summary.unique_buyers == 1
    assert summary.anomaly_flags == ["buyer_concentration"]
    assert summary.data_status == "admin_review_required"


def test_seller_assessment_stays_pending_until_admin_decides(tmp_path) -> None:
    store = OperationsStore(_settings(tmp_path))
    assessment = store.create_seller_assessment(
        platform="discord",
        community_id="guild-1",
        requester_id="member-1",
        seller_id="seller-unknown",
        reason="Tôi muốn kiểm tra trước khi giao dịch.",
    )
    assert assessment.status == "open"
    assert assessment.final_decision == "pending"
    assert "không phải kết luận" in assessment.ai_summary

    decided = store.decide_seller_assessment(
        assessment.assessment_id,
        "insufficient_data",
        "Chưa có giao dịch xác thực; không thể kết luận độ tin cậy.",
        "Moderator",
    )
    assert decided and decided.status == "resolved"
    assert decided.reviewed_by == "Moderator"
