from unittest.mock import Mock, patch

import requests

from backend.config import Settings
from backend.models.operations import MessageDecision
from backend.services.operations_store import OperationsStore
from backend.services.telegram.bot import TelegramRagBot


def build_bot() -> TelegramRagBot:
    return TelegramRagBot(
        Mock(),
        Settings(telegram_bot_token="test-token", telegram_listener_enabled=True),
        pipeline=Mock(),
    )


def test_telegram_private_messages_are_questions() -> None:
    bot = build_bot()

    assert bot._question_to_answer({"chat": {"type": "private"}}, "How do I report spam?") == "How do I report spam?"


def test_telegram_ignores_member_removed_service_message() -> None:
    bot = build_bot()
    bot._send_message = Mock()

    bot._handle_update(
        {
            "message": {
                "message_id": 42,
                "date": 1_700_000_000,
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9001, "is_bot": False},
                "left_chat_member": {"id": 9002, "is_bot": False},
            }
        }
    )

    bot._send_message.assert_not_called()
    bot.pipeline.analyze.assert_not_called()


def test_telegram_welcomes_new_human_members() -> None:
    bot = build_bot()
    bot._send_message = Mock()

    bot._handle_update(
        {
            "message": {
                "message_id": 42,
                "date": 1_700_000_000,
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9001, "is_bot": False},
                "new_chat_members": [
                    {"id": 9002, "first_name": "An", "last_name": "Nguyễn", "is_bot": False},
                    {"id": 9003, "username": "helper_bot", "is_bot": True},
                ],
            }
        }
    )

    bot._send_message.assert_called_once_with(
        "-100123",
        "Chào An Nguyễn! Mừng bạn đến với cộng đồng. Dùng /help để xem hướng dẫn và các lệnh hỗ trợ.",
        reply_to_message_id=42,
    )
    bot.pipeline.analyze.assert_not_called()


def test_telegram_can_disable_new_member_welcome() -> None:
    bot = build_bot()
    bot.settings.telegram_welcome_new_members_enabled = False
    bot._send_message = Mock()

    bot._handle_update(
        {
            "message": {
                "message_id": 42,
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9001, "is_bot": False},
                "new_chat_members": [{"id": 9002, "first_name": "An", "is_bot": False}],
            }
        }
    )

    bot._send_message.assert_not_called()


def test_telegram_chat_member_updates_persist_join_and_leave() -> None:
    bot = build_bot()
    user = {
        "id": 9002,
        "username": "Thanh24109",
        "first_name": "Thanh",
        "last_name": "Nguyen",
        "is_bot": False,
    }

    bot._handle_chat_member_update(
        {
            "chat": {"id": -100123, "type": "supergroup"},
            "date": 1_700_000_000,
            "new_chat_member": {"status": "member", "user": user},
        }
    )

    assert bot._telegram_users_by_username[("-100123", "thanh24109")] == (
        "9002",
        "Thanh Nguyen",
    )
    assert bot.store.remember_telegram_member.call_args.kwargs["is_active_member"] is True

    bot.store.remember_telegram_member.reset_mock()
    bot._handle_chat_member_update(
        {
            "chat": {"id": -100123, "type": "supergroup"},
            "date": 1_700_000_100,
            "new_chat_member": {"status": "left", "user": user},
        }
    )

    assert ("-100123", "thanh24109") not in bot._telegram_users_by_username
    assert bot.store.remember_telegram_member.call_args.kwargs["membership_status"] == "left"
    assert bot.store.remember_telegram_member.call_args.kwargs["is_active_member"] is False


def test_telegram_member_directory_survives_restart_and_excludes_left_member(tmp_path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'telegram-members.db'}")
    store = OperationsStore(settings)
    store.remember_telegram_member(
        "-100123",
        "9002",
        display_name="Thanh Nguyen",
        username="Thanh24109",
        membership_status="member",
        is_active_member=True,
    )

    restarted_store = OperationsStore(settings)
    assert restarted_store.find_telegram_member_by_username("-100123", "@thanh24109") == (
        "9002",
        "Thanh Nguyen",
    )
    assert restarted_store.find_telegram_member_by_username("-100999", "@thanh24109") is None

    restarted_store.remember_telegram_member(
        "-100123",
        "9002",
        display_name="Thanh Nguyen",
        username="Thanh24109",
        membership_status="left",
        is_active_member=False,
    )
    assert OperationsStore(settings).find_telegram_member_by_username("-100123", "thanh24109") is None


def test_telegram_group_requires_command_or_bot_mention() -> None:
    bot = build_bot()
    bot._username = "community_helper"

    assert bot._question_to_answer({"chat": {"type": "group"}}, "hello everyone") is None
    assert bot._question_to_answer({"chat": {"type": "group"}}, "/ask What is the policy?") == "What is the policy?"
    assert bot._question_to_answer({"chat": {"type": "group"}}, "@community_helper help me") == "help me"


def test_telegram_answers_when_member_replies_to_the_bot() -> None:
    bot = build_bot()
    bot._username = "community_helper"
    message = {
        "chat": {"type": "group"},
        "reply_to_message": {
            "from": {
                "id": 777,
                "username": "community_helper",
                "is_bot": True,
            }
        },
    }

    assert bot._question_to_answer(message, "Giải thích rõ hơn giúp mình") == "Giải thích rõ hơn giúp mình"


def test_telegram_ignores_replies_to_another_bot() -> None:
    bot = build_bot()
    bot._username = "community_helper"
    message = {
        "chat": {"type": "group"},
        "reply_to_message": {
            "from": {
                "id": 888,
                "username": "another_bot",
                "is_bot": True,
            }
        },
    }

    assert bot._question_to_answer(message, "Tin nhắn cho bot khác") is None


def test_telegram_message_is_normalized_for_operations_pipeline() -> None:
    common = TelegramRagBot._common_message(
        {
            "message_id": 42,
            "date": 1_700_000_000,
            "text": "Need help",
            "chat": {"id": -100123, "type": "supergroup"},
            "from": {"id": 9001, "first_name": "Simon"},
            "reply_to_message": {"message_id": 41},
        }
    )

    assert common.message_id == "telegram--100123-42"
    assert common.platform == "telegram"
    assert common.parent_message_id == "41"
    assert common.author_name == "Simon"
    assert common.text == "Need help"


def test_telegram_ephemeral_message_has_a_stable_operations_id() -> None:
    common = TelegramRagBot._common_message(
        {
            "ephemeral_message_id": 77,
            "date": 1_700_000_000,
            "text": "/report",
            "chat": {"id": -100123, "type": "supergroup"},
            "from": {"id": 9001},
            "receiver_user": {"id": 9001},
        }
    )

    assert common.message_id == "telegram--100123-ephemeral-77"


def test_telegram_realtime_result_passes_through_admin_alert_gate() -> None:
    bot = build_bot()
    result = MessageDecision(
        decision="warn",
        category="harassment",
        severity="medium",
        risk_score=0.76,
        confidence=0.82,
        explanation="Conflict confirmed after three gates.",
        model_used="test-gates",
        send_to_admin=True,
    )
    bot.pipeline.analyze.return_value = result
    bot.telegram_alerts = Mock()
    bot.telegram_alerts.send_alert.return_value = True
    bot.platform_moderation = Mock()
    bot.platform_moderation.send_automatic_warning.return_value = None
    bot._send_message = Mock()

    bot._handle_update(
        {
            "update_id": 1,
            "message": {
                "message_id": 42,
                "date": 1_700_000_000,
                "text": "Mày ngu quá",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9001, "is_bot": False},
            },
        }
    )

    bot.telegram_alerts.send_alert.assert_called_once()
    sent_message, sent_result = bot.telegram_alerts.send_alert.call_args.args
    assert sent_message.message_id == "telegram--100123-42"
    assert sent_result.send_to_admin is True
    assert "⚠️" in bot._send_message.call_args.args[1]


def test_telegram_safe_untagged_message_is_moderated_silently() -> None:
    bot = build_bot()
    bot.pipeline.analyze.return_value = MessageDecision(
        decision="allow",
        category="safe",
        severity="low",
        risk_score=0.01,
        confidence=0.99,
        explanation="Nội dung an toàn.",
        model_used="test-gates",
        send_to_admin=False,
        send_to_member=True,
    )


def test_telegram_registers_report_and_trade_commands_as_ephemeral() -> None:
    bot = build_bot()
    bot.store.list_command_content.return_value = []
    response = Mock()
    response.json.return_value = {"ok": True}

    with patch("backend.services.telegram.bot.requests.post", return_value=response) as post:
        bot._register_commands()

    commands = post.call_args.kwargs["json"]["commands"]
    command_map = {item["command"]: item for item in commands}
    for name in {"report", "trade_open", "trade_confirm", "trade_review", "seller_check"}:
        assert command_map[name]["is_ephemeral"] is True
    assert "is_ephemeral" not in command_map["help"]


def test_telegram_send_message_uses_ephemeral_target_and_reply() -> None:
    bot = build_bot()
    response = Mock()

    with patch("backend.services.telegram.bot.requests.post", return_value=response) as post:
        bot._send_message(
            "-100123",
            "Thông tin riêng",
            ephemeral_user_id=9001,
            reply_to_ephemeral_message_id=77,
            force_reply=True,
            force_reply_placeholder="Nhập mã giao dịch TRD-...",
        )

    payload = post.call_args.kwargs["json"]
    assert payload["ephemeral_message_parameters"] == {"receiver_user_id": 9001}
    assert payload["reply_parameters"] == {"ephemeral_message_id": 77}
    assert payload["reply_markup"] == {
        "force_reply": True,
        "input_field_placeholder": "Nhập mã giao dịch TRD-...",
    }


def test_telegram_send_message_retries_one_connection_reset() -> None:
    bot = build_bot()
    response = Mock()
    reset = requests.ConnectionError(
        "connection aborted",
        ConnectionResetError(10054, "connection reset"),
    )

    with patch("backend.services.telegram.bot.requests.post", side_effect=[reset, response]) as post:
        bot._send_message("-100123", "Thử gửi lại")

    assert post.call_count == 2
    response.raise_for_status.assert_called_once()
    bot.telegram_alerts = Mock()
    bot.telegram_alerts.send_alert.return_value = False
    bot.platform_moderation = Mock()
    bot.platform_moderation.send_automatic_warning.return_value = None
    bot._send_message = Mock()

    bot._handle_update(
        {
            "message": {
                "message_id": 42,
                "date": 1_700_000_000,
                "text": "Chào mọi người",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9001, "is_bot": False},
            }
        }
    )

    bot.pipeline.analyze.assert_called_once()
    bot._send_message.assert_not_called()


def test_telegram_suppresses_repeated_member_moderation_notice() -> None:
    bot = build_bot()
    bot.pipeline.analyze.return_value = MessageDecision(
        decision="warn",
        category="harassment",
        severity="medium",
        risk_score=0.8,
        confidence=0.9,
        explanation="Nội dung công kích.",
        model_used="test-gates",
        send_to_admin=False,
        send_to_member=False,
    )
    bot.telegram_alerts = Mock()
    bot.telegram_alerts.send_alert.return_value = False
    bot.platform_moderation = Mock()
    bot.platform_moderation.send_automatic_warning.return_value = None
    bot._send_message = Mock()

    bot._handle_update(
        {
            "message": {
                "message_id": 42,
                "date": 1_700_000_000,
                "text": "Tin nhắn lặp lại đã được cảnh báo",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9001, "is_bot": False},
            }
        }
    )

    bot._send_message.assert_not_called()


def test_telegram_replies_to_the_message_that_asked_the_question() -> None:
    bot = build_bot()
    bot.chat = Mock()
    bot.chat.reply.return_value = Mock(answer="Hello", moderation=None, stage="rule")
    bot._send_message = Mock()

    bot._handle_update(
        {
            "message": {
                "message_id": 42,
                "date": 1_700_000_000,
                "text": "/help",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9001, "is_bot": False},
            }
        }
    )

    bot._send_message.assert_called_once_with("-100123", "Hello", reply_to_message_id=42)


def test_telegram_custom_command_is_answered_when_scoped_to_telegram() -> None:
    bot = build_bot()
    bot.store.get_command_content.return_value = Mock(platforms=["telegram"])

    assert bot._question_to_answer({"chat": {"type": "group"}}, "/gioithieu") == "/gioithieu"


def test_telegram_report_menu_command_prompts_then_uses_the_next_message() -> None:
    bot = build_bot()
    bot.chat = Mock()
    bot.chat.reply.return_value = Mock(answer="Đã tạo báo cáo REP-ABC123.")
    bot._send_message = Mock()

    bot._handle_update(
        {
            "message": {
                "message_id": 41,
                "ephemeral_message_id": 71,
                "date": 1_700_000_000,
                "text": "/report",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9001, "is_bot": False},
            }
        }
    )

    prompt_call = bot._send_message.call_args
    assert "mô tả ngắn" in prompt_call.args[1]
    assert prompt_call.kwargs["force_reply"] is True
    assert prompt_call.kwargs["ephemeral_user_id"] == 9001
    assert prompt_call.kwargs["reply_to_ephemeral_message_id"] == 71

    bot._send_message.reset_mock()
    bot._handle_update(
        {
            "message": {
                "message_id": 42,
                "ephemeral_message_id": 72,
                "date": 1_700_000_001,
                "text": "Tin nhắn 123 có liên kết lừa đảo",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9001, "is_bot": False},
            }
        }
    )

    submitted = bot.chat.reply.call_args.args[0]
    assert submitted.text == "/report Tin nhắn 123 có liên kết lừa đảo"
    assert "REP-ABC123" in bot._send_message.call_args.args[1]
    assert bot._send_message.call_args.kwargs["ephemeral_user_id"] == 9001
    assert bot._send_message.call_args.kwargs["reply_to_ephemeral_message_id"] == 72


def test_telegram_deletes_a_visible_mobile_report_reply_before_processing() -> None:
    bot = build_bot()
    bot.chat = Mock()
    bot.chat.reply.return_value = Mock(answer="Đã tạo báo cáo REP-ABC123.")
    bot._send_message = Mock()
    bot._delete_message = Mock(return_value=True)

    bot._handle_update(
        {
            "message": {
                "message_id": 41,
                "ephemeral_message_id": 71,
                "date": 1_700_000_000,
                "text": "/report",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9001, "is_bot": False},
            }
        }
    )
    bot._handle_update(
        {
            "message": {
                "message_id": 42,
                "date": 1_700_000_001,
                "text": "Tin nhắn 123 có liên kết lừa đảo",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9001, "is_bot": False},
            }
        }
    )

    bot._delete_message.assert_called_once_with("-100123", 42)
    submitted = bot.chat.reply.call_args.args[0]
    assert submitted.text == "/report Tin nhắn 123 có liên kết lừa đảo"


def test_telegram_report_reply_recovers_after_worker_restart() -> None:
    bot = build_bot()
    bot._username = "community_helper"
    bot.chat = Mock()
    bot.chat.reply.return_value = Mock(answer="Đã tạo báo cáo REP-ABC123.")
    bot._send_message = Mock()

    bot._handle_update(
        {
            "message": {
                "message_id": 42,
                "ephemeral_message_id": 72,
                "date": 1_700_000_001,
                "text": "Test",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9001, "is_bot": False},
                "reply_to_message": {
                    "ephemeral_message_id": 71,
                    "date": 1_700_000_000,
                    "text": (
                        "Hãy gửi liên kết hoặc mã tin nhắn kèm mô tả ngắn về nội dung cần báo cáo.\n"
                        "Gửi /cancel để hủy."
                    ),
                    "from": {
                        "id": 777,
                        "username": "community_helper",
                        "is_bot": True,
                    },
                },
            }
        }
    )

    submitted = bot.chat.reply.call_args.args[0]
    assert submitted.text == "/report Test"
    assert "REP-ABC123" in bot._send_message.call_args.args[1]


def test_telegram_trade_menu_command_prompts_then_preserves_replied_seller() -> None:
    bot = build_bot()
    bot.settings.telegram_trade_chat_id = "-100123"
    bot.store.find_blocked_links.return_value = []
    bot.store.create_trade_case.return_value = Mock(trade_id="TRD-ABC123")
    bot._send_message = Mock()

    bot._handle_update(
        {
            "message": {
                "message_id": 41,
                "ephemeral_message_id": 81,
                "date": 1_700_000_000,
                "text": "/trade_open",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9001, "first_name": "Buyer", "is_bot": False},
                "reply_to_message": {
                    "message_id": 40,
                    "from": {"id": 9002, "first_name": "Seller", "is_bot": False},
                },
            }
        }
    )

    assert bot._send_message.call_args.kwargs["force_reply"] is True
    assert bot._send_message.call_args.kwargs["ephemeral_user_id"] == 9001
    assert bot._send_message.call_args.kwargs["reply_to_ephemeral_message_id"] == 81

    bot._send_message.reset_mock()
    bot._handle_update(
        {
            "message": {
                "message_id": 42,
                "ephemeral_message_id": 82,
                "date": 1_700_000_001,
                "text": "Bàn phím cơ",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9001, "first_name": "Buyer", "is_bot": False},
            }
        }
    )

    assert bot.store.create_trade_case.call_args.kwargs["seller_id"] == "9002"
    assert bot.store.create_trade_case.call_args.kwargs["item_summary"] == "Bàn phím cơ"
    assert bot._send_message.call_args.kwargs["ephemeral_user_id"] == 9001
    assert bot._send_message.call_args.kwargs["reply_to_ephemeral_message_id"] == 82


def test_telegram_cancel_clears_a_pending_command() -> None:
    bot = build_bot()
    bot._send_message = Mock()

    bot._handle_update(
        {
            "message": {
                "message_id": 41,
                "text": "/report",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9001, "is_bot": False},
            }
        }
    )
    bot._handle_update(
        {
            "message": {
                "message_id": 42,
                "text": "/cancel",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9001, "is_bot": False},
            }
        }
    )

    assert ("-100123", "9001") not in bot._pending_commands
    assert "Đã hủy" in bot._send_message.call_args.args[1]


def test_telegram_trade_open_uses_replied_member_as_seller() -> None:
    bot = build_bot()
    bot.settings.telegram_trade_chat_id = "-100123"
    bot.store.find_blocked_links.return_value = []
    bot.store.create_trade_case.return_value = Mock(trade_id="TRD-ABC123")
    bot._send_message = Mock()

    bot._handle_update(
        {
            "message": {
                "message_id": 42,
                "date": 1_700_000_000,
                "text": "/trade_open Bàn phím cơ",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9001, "first_name": "Buyer", "is_bot": False},
                "reply_to_message": {
                    "message_id": 41,
                    "from": {"id": 9002, "first_name": "Seller", "is_bot": False},
                },
            }
        }
    )

    bot.store.create_trade_case.assert_called_once_with(
        platform="telegram",
        community_id="-100123",
        channel_id="-100123",
        buyer_id="9001",
        buyer_name="Buyer",
        seller_id="9002",
        seller_name="Seller",
        item_summary="Bàn phím cơ",
        created_by="9001",
        evidence_urls=[],
    )
    assert "TRD-ABC123" in bot._send_message.call_args.args[1]
    assert "người mua Buyer" in bot._send_message.call_args.args[1]
    assert "người bán Seller" in bot._send_message.call_args.args[1]
    assert "buyer 9001" not in bot._send_message.call_args.args[1]
    assert "seller 9002" not in bot._send_message.call_args.args[1]


def test_telegram_trade_open_resolves_seller_username_seen_in_the_group() -> None:
    bot = build_bot()
    bot.settings.telegram_trade_chat_id = "-100123"
    bot.store.find_blocked_links.return_value = []
    bot.store.create_trade_case.return_value = Mock(trade_id="TRD-ABC123")
    bot._send_message = Mock()
    bot._remember_telegram_user(
        "-100123",
        {
            "id": 9002,
            "username": "Peace_Chill_08",
            "first_name": "Seller",
            "is_bot": False,
        },
    )

    bot._handle_update(
        {
            "message": {
                "message_id": 42,
                "date": 1_700_000_000,
                "text": "/trade_open @peace_chill_08 Sách lập trình",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9001, "first_name": "Buyer", "is_bot": False},
            }
        }
    )

    bot.store.create_trade_case.assert_called_once_with(
        platform="telegram",
        community_id="-100123",
        channel_id="-100123",
        buyer_id="9001",
        buyer_name="Buyer",
        seller_id="9002",
        seller_name="Seller",
        item_summary="Sách lập trình",
        created_by="9001",
        evidence_urls=[],
    )


def test_telegram_trade_open_resolves_a_persisted_seller_after_restart() -> None:
    bot = build_bot()
    bot.settings.telegram_trade_chat_id = "-100123"
    bot.store.find_blocked_links.return_value = []
    bot.store.find_telegram_member_by_username.return_value = ("9002", "Thanh")
    bot.store.create_trade_case.return_value = Mock(trade_id="TRD-ABC123")
    bot._send_message = Mock()

    bot._handle_update(
        {
            "message": {
                "message_id": 42,
                "date": 1_700_000_000,
                "text": "/trade_open @thanh24109 Sách lập trình",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9001, "first_name": "Buyer", "is_bot": False},
            }
        }
    )

    bot.store.find_telegram_member_by_username.assert_called_once_with("-100123", "thanh24109")
    bot.store.create_trade_case.assert_called_once_with(
        platform="telegram",
        community_id="-100123",
        channel_id="-100123",
        buyer_id="9001",
        buyer_name="Buyer",
        seller_id="9002",
        seller_name="Thanh",
        item_summary="Sách lập trình",
        created_by="9001",
        evidence_urls=[],
    )


def test_telegram_trade_open_explains_how_to_resolve_an_unknown_username() -> None:
    bot = build_bot()
    bot.settings.telegram_trade_chat_id = "-100123"
    bot.store.find_blocked_links.return_value = []
    bot._send_message = Mock()

    bot._handle_update(
        {
            "message": {
                "message_id": 42,
                "date": 1_700_000_000,
                "text": "/trade_open @unknown_seller Sách lập trình",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9001, "first_name": "Buyer", "is_bot": False},
            }
        }
    )

    bot.store.create_trade_case.assert_not_called()
    assert "Seller hãy gửi một tin nhắn" in bot._send_message.call_args.args[1]


def test_telegram_trade_open_keeps_seller_when_item_description_is_too_short() -> None:
    bot = build_bot()
    bot._username = "community_helper"
    bot.settings.telegram_trade_chat_id = "-100123"
    bot.store.find_blocked_links.return_value = []
    bot.store.find_telegram_member_by_username.return_value = ("6981526945", "Thanh Nguyen")
    bot.store.create_trade_case.return_value = Mock(trade_id="TRD-ABC123")
    bot._send_message = Mock()

    bot._handle_update(
        {
            "message": {
                "message_id": 41,
                "ephemeral_message_id": 81,
                "date": 1_700_000_000,
                "text": "/trade_open @thanh24109 a",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 6593452247, "first_name": "Simon", "is_bot": False},
            }
        }
    )

    assert "không cần nhập lại seller" in bot._send_message.call_args.args[1]
    assert bot._send_message.call_args.kwargs["force_reply"] is True
    assert ("-100123", "6593452247") in bot._pending_commands

    bot._send_message.reset_mock()
    bot._handle_update(
        {
            "message": {
                "message_id": 42,
                "ephemeral_message_id": 82,
                "date": 1_700_000_001,
                "text": "Sách lập trình Python",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 6593452247, "first_name": "Simon", "is_bot": False},
                "reply_to_message": {
                    "ephemeral_message_id": 90,
                    "text": "Mô tả món hàng phải dài từ 3 đến 500 ký tự.",
                    "from": {
                        "id": 777,
                        "username": "community_helper",
                        "is_bot": True,
                    },
                },
            }
        }
    )

    bot.store.create_trade_case.assert_called_once_with(
        platform="telegram",
        community_id="-100123",
        channel_id="-100123",
        buyer_id="6593452247",
        buyer_name="Simon",
        seller_id="6981526945",
        seller_name="Thanh Nguyen",
        item_summary="Sách lập trình Python",
        created_by="6593452247",
        evidence_urls=[],
    )


def test_telegram_trade_confirm_records_the_current_member() -> None:
    bot = build_bot()
    bot.settings.telegram_trade_chat_id = "-100123"
    bot.store.find_blocked_links.return_value = []
    bot.store.confirm_trade_case.return_value = Mock(trade_id="TRD-ABC123", status="partially_confirmed")
    bot._send_message = Mock()

    bot._handle_update(
        {
            "message": {
                "message_id": 42,
                "date": 1_700_000_000,
                "text": "/trade_confirm trd-abc123",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9002, "is_bot": False},
            }
        }
    )

    bot.store.confirm_trade_case.assert_called_once_with("TRD-ABC123", "9002")
    assert "đang chờ bên còn lại" in bot._send_message.call_args.args[1]


def test_telegram_trade_confirm_prompts_then_uses_the_next_message() -> None:
    bot = build_bot()
    bot.settings.telegram_trade_chat_id = "-100123"
    bot.store.find_blocked_links.return_value = []
    bot.store.confirm_trade_case.return_value = Mock(
        trade_id="TRD-ABC123",
        status="partially_confirmed",
    )
    bot._send_message = Mock()

    bot._handle_update(
        {
            "message": {
                "message_id": 41,
                "ephemeral_message_id": 81,
                "date": 1_700_000_000,
                "text": "/trade_confirm",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9002, "is_bot": False},
            }
        }
    )

    assert bot._send_message.call_args.kwargs["force_reply"] is True
    assert bot._send_message.call_args.kwargs["ephemeral_user_id"] == 9002
    assert bot._send_message.call_args.kwargs["force_reply_placeholder"] == "Nhập mã giao dịch TRD-..."

    bot._send_message.reset_mock()
    bot._handle_update(
        {
            "message": {
                "message_id": 42,
                "ephemeral_message_id": 82,
                "date": 1_700_000_001,
                "text": "TRD-ABC123",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9002, "is_bot": False},
            }
        }
    )

    bot.store.confirm_trade_case.assert_called_once_with("TRD-ABC123", "9002")
    assert bot._send_message.call_args.kwargs["ephemeral_user_id"] == 9002


def test_telegram_trade_review_parses_ratings_and_comment() -> None:
    bot = build_bot()
    bot.settings.telegram_trade_chat_id = "-100123"
    bot.store.find_blocked_links.return_value = []
    bot.store.add_seller_review.return_value = Mock(review_id="SRV-ABC123")
    bot._send_message = Mock()

    bot._handle_update(
        {
            "message": {
                "message_id": 42,
                "date": 1_700_000_000,
                "text": "/trade_review TRD-ABC123 5 4 5 5 có Giao hàng đúng hẹn",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9001, "is_bot": False},
            }
        }
    )

    bot.store.add_seller_review.assert_called_once_with(
        "TRD-ABC123",
        buyer_id="9001",
        overall_rating=5,
        item_accuracy=4,
        communication=5,
        fulfillment=5,
        would_trade_again=True,
        comment="Giao hàng đúng hẹn",
    )


def test_telegram_trade_review_prompts_then_uses_the_next_message() -> None:
    bot = build_bot()
    bot.settings.telegram_trade_chat_id = "-100123"
    bot.store.find_blocked_links.return_value = []
    bot.store.add_seller_review.return_value = Mock(review_id="SRV-ABC123")
    bot._send_message = Mock()

    bot._handle_update(
        {
            "message": {
                "message_id": 41,
                "ephemeral_message_id": 81,
                "date": 1_700_000_000,
                "text": "/trade_review",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9001, "is_bot": False},
            }
        }
    )

    assert bot._send_message.call_args.kwargs["force_reply"] is True
    assert bot._send_message.call_args.kwargs["ephemeral_user_id"] == 9001

    bot._send_message.reset_mock()
    bot._handle_update(
        {
            "message": {
                "message_id": 42,
                "ephemeral_message_id": 82,
                "date": 1_700_000_001,
                "text": "TRD-ABC123 5 4 5 5 có Giao hàng đúng hẹn",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9001, "is_bot": False},
            }
        }
    )

    bot.store.add_seller_review.assert_called_once_with(
        "TRD-ABC123",
        buyer_id="9001",
        overall_rating=5,
        item_accuracy=4,
        communication=5,
        fulfillment=5,
        would_trade_again=True,
        comment="Giao hàng đúng hẹn",
    )
    assert bot._send_message.call_args.kwargs["ephemeral_user_id"] == 9001


def test_telegram_seller_check_accepts_an_explicit_seller_id() -> None:
    bot = build_bot()
    bot.settings.telegram_trade_chat_id = "-100123"
    bot.store.find_blocked_links.return_value = []
    bot.store.create_seller_assessment.return_value = Mock(assessment_id="SAS-ABC123")
    bot._send_message = Mock()

    bot._handle_update(
        {
            "message": {
                "message_id": 42,
                "date": 1_700_000_000,
                "text": "/seller_check 9002 Giá bán đáng ngờ",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9001, "is_bot": False},
            }
        }
    )

    bot.store.create_seller_assessment.assert_called_once_with(
        platform="telegram",
        community_id="-100123",
        requester_id="9001",
        seller_id="9002",
        reason="Giá bán đáng ngờ",
    )


def test_telegram_trade_commands_are_locked_outside_the_configured_chat() -> None:
    bot = build_bot()
    bot.settings.telegram_trade_chat_id = "-100999"
    bot.store.find_blocked_links.return_value = []
    bot._send_message = Mock()

    bot._handle_update(
        {
            "message": {
                "message_id": 42,
                "date": 1_700_000_000,
                "text": "/trade_confirm TRD-ABC123",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9001, "is_bot": False},
            }
        }
    )

    bot.store.confirm_trade_case.assert_not_called()
    assert "chỉ dùng trong nhóm Telegram giao dịch" in bot._send_message.call_args.args[1]


def test_telegram_deletes_a_known_blocked_link_before_answering() -> None:
    bot = build_bot()
    bot.store.find_blocked_links.return_value = [Mock(canonical_url="https://bad.example/")]
    bot._delete_message = Mock(return_value=True)
    bot.pipeline.analyze.return_value = Mock(incident_id="INC-1")
    bot.telegram_alerts = Mock()

    bot._handle_update(
        {
            "message": {
                "message_id": 42,
                "date": 1_700_000_000,
                "text": "https://bad.example/",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 9001, "is_bot": False},
            }
        }
    )

    bot._delete_message.assert_called_once_with("-100123", 42)
    bot.telegram_alerts.send_blocked_link_alert.assert_called_once()


def test_telegram_helpful_reactions_award_reputation_at_threshold() -> None:
    bot = build_bot()
    bot.settings.reputation_helpful_reaction_threshold = 1
    common = TelegramRagBot._common_message(
        {
            "message_id": 42,
            "date": 1_700_000_000,
            "text": "Useful answer",
            "chat": {"id": -100123, "type": "supergroup"},
            "from": {"id": 9001},
        }
    )
    bot._message_cache[("-100123", "42")] = common

    bot._handle_reaction_update(
        {
            "chat": {"id": -100123},
            "message_id": 42,
            "user": {"id": 9002},
            "old_reaction": [],
            "new_reaction": [{"type": "emoji", "emoji": "👍"}],
        }
    )

    bot.store.award_helpful_reputation.assert_called_once_with(common, 1, reaction_emoji="👍")


def test_telegram_anonymous_actor_reaction_awards_reputation() -> None:
    bot = build_bot()
    bot.settings.reputation_helpful_reaction_threshold = 1
    common = TelegramRagBot._common_message(
        {
            "message_id": 42,
            "date": 1_700_000_000,
            "text": "Useful answer",
            "chat": {"id": -100123, "type": "supergroup"},
            "from": {"id": 9001},
        }
    )
    bot._message_cache[("-100123", "42")] = common

    bot._handle_reaction_update(
        {
            "chat": {"id": -100123},
            "message_id": 42,
            "actor_chat": {"id": -100987},
            "old_reaction": [],
            "new_reaction": [{"type": "emoji", "emoji": "👍"}],
        }
    )

    bot.store.award_helpful_reputation.assert_called_once_with(common, 1, reaction_emoji="👍")


def test_telegram_anonymous_reaction_count_awards_reputation_at_threshold() -> None:
    bot = build_bot()
    bot.settings.reputation_helpful_reaction_threshold = 1
    common = TelegramRagBot._common_message(
        {
            "message_id": 42,
            "date": 1_700_000_000,
            "text": "Useful answer",
            "chat": {"id": -100123, "type": "supergroup"},
            "from": {"id": 9001},
        }
    )
    bot._message_cache[("-100123", "42")] = common

    bot._handle_reaction_count_update(
        {
            "chat": {"id": -100123},
            "message_id": 42,
            "reactions": [{"type": {"type": "emoji", "emoji": "👍"}, "total_count": 1}],
        }
    )

    bot.store.award_helpful_reputation.assert_called_once_with(common, 1, reaction_emoji="👍")


def test_telegram_reaction_loads_a_persisted_message_after_restart() -> None:
    bot = build_bot()
    bot.settings.reputation_helpful_reaction_threshold = 1
    common = TelegramRagBot._common_message(
        {
            "message_id": 42,
            "date": 1_700_000_000,
            "text": "Useful answer",
            "chat": {"id": -100123, "type": "supergroup"},
            "from": {"id": 9001},
        }
    )
    bot.store.get_message.return_value = common

    bot._handle_reaction_count_update(
        {
            "chat": {"id": -100123},
            "message_id": 42,
            "reactions": [{"type": {"type": "emoji", "emoji": "👍"}, "total_count": 1}],
        }
    )

    bot.store.get_message.assert_called_once_with("telegram--100123-42")
    bot.store.award_helpful_reputation.assert_called_once_with(common, 1, reaction_emoji="👍")
