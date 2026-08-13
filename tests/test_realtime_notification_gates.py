from datetime import UTC, datetime, timedelta

from backend.config import Settings
from backend.models.operations import CommonMessage, MessageDecision, PolicyUpsertRequest
from backend.services.operations_pipeline import OperationsPipeline
from backend.services.operations_store import OperationsStore
from backend.services.telegram.alerts import TelegramAlertSender


def _message(message_id: str, text: str, *, seconds: int = 0) -> CommonMessage:
    return CommonMessage(
        message_id=message_id,
        platform="discord",
        community_id="guild-1",
        channel_id="channel-1",
        author_id="member-1",
        text=text,
        timestamp=datetime.now(UTC) + timedelta(seconds=seconds),
    )


def _settings(tmp_path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'app.db'}",
        openai_api_key="",
        operations_use_llm=False,
        enable_case_based_learning=True,
    )


def _allowed() -> MessageDecision:
    return MessageDecision(
        decision="allow",
        category="safe",
        severity="low",
        risk_score=0.0,
        confidence=1.0,
        explanation="safe",
        model_used="test",
    )


def test_gate1_uses_active_admin_policy(tmp_path) -> None:
    settings = _settings(tmp_path)
    store = OperationsStore(settings)
    store.upsert_policy(
        "POL-CUSTOM",
        PolicyUpsertRequest(
            name="Custom conflict phrase",
            description="Team-specific phrase",
            category="harassment",
            action="warn",
            trigger_terms=["đồ ngốc"],
        ),
    )

    result = OperationsPipeline(store, settings).analyze(_message("policy-1", "Bạn đúng là đồ ngốc"), [])

    assert result.decision == "warn"
    assert result.gates[0].label == "policy:POL-CUSTOM"
    assert result.send_to_admin is True


def test_gate2_automatically_reads_nearby_context(tmp_path) -> None:
    settings = _settings(tmp_path)
    store = OperationsStore(settings)
    prior = _message("context-1", "Tụi mình đang đùa thôi nha haha")
    store.save_message(prior, _allowed(), None)

    result = OperationsPipeline(store, settings).analyze(
        _message("context-2", "Mày ngu quá", seconds=1),
    )

    assert result.decision == "allow"
    assert result.gates[1].label == "context_deescalated_joke"
    assert result.send_to_admin is False


def test_gate3_suppresses_case_after_human_resolution(tmp_path) -> None:
    settings = _settings(tmp_path)
    store = OperationsStore(settings)
    pipeline = OperationsPipeline(store, settings)

    first = pipeline.analyze(_message("memory-1", "Mày ngu quá"), [])
    assert first.incident_id
    store.update_incident(first.incident_id, "resolved", "mod-lan", "công kích cá nhân")

    repeated = pipeline.analyze(_message("memory-2", "Mày ngu quá", seconds=1), [])

    assert repeated.decision == "warn"
    assert repeated.already_marked is True
    assert repeated.send_to_admin is False
    assert repeated.incident_id is None
    assert repeated.matched_mark_id
    assert repeated.banner and "mod-lan" in repeated.banner
    assert TelegramAlertSender.should_alert(repeated, 0.55) is False
    assert len(store.list_incidents()) == 1


def test_gate3_keeps_a_different_new_case_for_admin(tmp_path) -> None:
    settings = _settings(tmp_path)
    store = OperationsStore(settings)
    pipeline = OperationsPipeline(store, settings)

    first = pipeline.analyze(_message("different-1", "Mày ngu quá"), [])
    assert first.incident_id
    store.update_incident(first.incident_id, "resolved", "mod-lan", "công kích cá nhân")

    new_case = pipeline.analyze(_message("different-2", "Im đi, đồ vô dụng", seconds=1), [])

    assert new_case.decision == "warn"
    assert new_case.already_marked is False
    assert new_case.send_to_admin is True
    assert new_case.incident_id
    assert len(store.list_incidents()) == 2


def test_telegram_sender_allows_only_a_new_case_after_all_gates(tmp_path) -> None:
    settings = _settings(tmp_path)
    store = OperationsStore(settings)
    pipeline = OperationsPipeline(store, settings)

    first = pipeline.analyze(_message("telegram-gate-1", "Mày ngu quá"), [])
    assert TelegramAlertSender.should_alert(first, 0.55) is True
    assert first.incident_id
    store.update_incident(first.incident_id, "resolved", "mod-lan", "công kích cá nhân")

    duplicate = pipeline.analyze(_message("telegram-gate-2", "Mày ngu quá", seconds=1), [])
    assert duplicate.gates[2].label == "approved_case_match"
    assert TelegramAlertSender.should_alert(duplicate, 0.55) is False


def test_game_invitation_with_ambiguous_danh_is_not_sent_to_admin(tmp_path) -> None:
    settings = _settings(tmp_path)
    store = OperationsStore(settings)

    result = OperationsPipeline(store, settings).analyze(
        _message("benign-game-1", "đánh liên quân không anh em"),
        [],
    )

    assert result.gates[0].category == "violence"
    assert result.gates[1].label == "context_deescalated_benign_activity"
    assert result.decision == "allow"
    assert result.send_to_admin is False
    assert result.send_to_member is False
    assert result.incident_id is None
    assert TelegramAlertSender.should_alert(result, 0.55) is False


def test_real_threat_with_danh_still_goes_to_admin(tmp_path) -> None:
    settings = _settings(tmp_path)
    store = OperationsStore(settings)

    result = OperationsPipeline(store, settings).analyze(
        _message("real-threat-1", "Tao sẽ đánh mày"),
        [],
    )

    assert result.decision == "hold_for_review"
    assert result.send_to_admin is True
    assert result.send_to_member is True
    assert result.incident_id
    assert TelegramAlertSender.should_alert(result, 0.55) is True


def test_screenshot_slang_threats_are_sent_but_game_invite_is_not(tmp_path) -> None:
    base_settings = _settings(tmp_path)
    cases = [
        ("đánh liên quân không anh em", False),
        ("M có thích không bố đập cho phát giờ", True),
        ("T sẽ đánh m", True),
        ("Bố chém chết m giờ", True),
    ]

    for index, (text, expected_alert) in enumerate(cases):
        settings = base_settings.model_copy(
            update={"database_url": f"sqlite:///{tmp_path / f'case-{index}.db'}"}
        )
        store = OperationsStore(settings)
        result = OperationsPipeline(store, settings).analyze(
            _message(f"screenshot-{index}", text),
            [],
        )

        assert TelegramAlertSender.should_alert(result, 0.55) is expected_alert
        assert bool(result.incident_id) is expected_alert


def test_common_benign_idioms_do_not_become_threats(tmp_path) -> None:
    base_settings = _settings(tmp_path)
    examples = ("đánh giá m tốt", "chém gió thôi", "đập hộp điện thoại", "giết thời gian")
    for index, text in enumerate(examples):
        settings = base_settings.model_copy(
            update={"database_url": f"sqlite:///{tmp_path / f'idiom-{index}.db'}"}
        )
        store = OperationsStore(settings)
        result = OperationsPipeline(store, settings).analyze(_message(f"idiom-{index}", text), [])

        assert TelegramAlertSender.should_alert(result, 0.55) is False


def test_identical_threat_is_notified_once_but_escalation_is_not_suppressed(tmp_path) -> None:
    settings = _settings(tmp_path)
    store = OperationsStore(settings)
    pipeline = OperationsPipeline(store, settings)

    first = pipeline.analyze(_message("burst-1", "M có thích không bố đập cho phát giờ"), [])
    repeated = pipeline.analyze(
        _message("burst-2", "M có thích không bố đập cho phát giờ", seconds=1),
        [],
    )
    escalation = pipeline.analyze(_message("burst-3", "Bố chém chết m giờ", seconds=2), [])

    assert TelegramAlertSender.should_alert(first, 0.55) is True
    assert first.send_to_member is True
    assert repeated.gates[2].label == "recent_duplicate"
    assert TelegramAlertSender.should_alert(repeated, 0.55) is False
    assert repeated.send_to_member is False
    assert repeated.incident_id == first.incident_id
    assert TelegramAlertSender.should_alert(escalation, 0.55) is True
    assert escalation.send_to_member is True
