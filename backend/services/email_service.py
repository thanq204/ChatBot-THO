"""Outbound email for Mod invite links.

Plain SMTP so any provider works (Gmail App Password, Outlook, a transactional
relay's SMTP endpoint, ...). Sending is best-effort: a failure here must never
block invite creation, since the Admin can always fall back to copying the
link manually from the Quan ly Mod page.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from backend.config import Settings, get_settings

logger = logging.getLogger(__name__)


def is_email_configured(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return bool(settings.smtp_host and settings.smtp_user and settings.smtp_password)


def send_mod_invite_email(to_email: str, invite_link: str, settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    if not is_email_configured(settings):
        return False

    from_name = settings.smtp_from_name.strip() or "AI Community Manager"
    from_email = settings.smtp_from_email.strip() or settings.smtp_user

    message = EmailMessage()
    message["Subject"] = "Loi moi tham gia doi kiem duyet"
    message["From"] = f"{from_name} <{from_email}>"
    message["To"] = to_email
    message.set_content(
        "Xin chao,\n\n"
        "Ban duoc moi tham gia lam Kiem duyet vien (Mod) cho cong dong.\n"
        f"Mo link sau de chap nhan hoac tu choi loi moi: {invite_link}\n\n"
        "Neu ban khong muon nhan loi moi nay, hay mo link va chon Tu choi, "
        "hoac don gian la bo qua email nay.\n\n"
        "Tran trong."
    )
    message.add_alternative(
        f"""\
<html><body style="font-family:sans-serif;line-height:1.6;color:#1f2933;">
<p>Xin chào,</p>
<p>Bạn được mời tham gia làm <strong>Kiểm duyệt viên (Mod)</strong> cho cộng đồng.</p>
<p><a href="{invite_link}" style="display:inline-block;padding:10px 18px;background:#db2777;color:#fff;
border-radius:8px;text-decoration:none;font-weight:600;">Xem lời mời</a></p>
<p>Hoặc copy link này vào trình duyệt:<br><code>{invite_link}</code></p>
<p style="color:#6b7280;font-size:13px;">Trang này cho phép chấp nhận hoặc từ chối lời mời.</p>
</body></html>""",
        subtype="html",
    )

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as client:
            if settings.smtp_use_tls:
                client.starttls()
            client.login(settings.smtp_user, settings.smtp_password)
            client.send_message(message)
        return True
    except Exception:
        logger.exception("Failed to send mod-invite email to %s", to_email)
        return False
