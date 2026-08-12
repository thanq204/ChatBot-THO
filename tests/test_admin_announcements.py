from backend.config import Settings
from backend.services.admin_announcements import AdminAnnouncementSender


def test_announcement_reports_missing_discord_configuration() -> None:
    result = AdminAnnouncementSender(Settings(discord_bot_token="", discord_default_channel_id="")).send("Study group update", "discord")

    assert result.platform == "discord"
    assert result.delivered is False
    assert "DISCORD_BOT_TOKEN" in result.detail


def test_announcement_reports_missing_telegram_configuration() -> None:
    result = AdminAnnouncementSender(Settings(telegram_bot_token="", telegram_default_chat_id="")).send("Study group update", "telegram")

    assert result.platform == "telegram"
    assert result.delivered is False
    assert "TELEGRAM_BOT_TOKEN" in result.detail
