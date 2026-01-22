from __future__ import annotations

import smtplib
from email.message import EmailMessage

from .config import settings


def send_login_code(email: str, code: str) -> None:
    """Send a login code to an email address.

    EMAIL_MODE=console prints the code (dev).
    EMAIL_MODE=smtp sends via configured SMTP.
    """
    if settings.email_mode.lower() == "console":
        print(f"[EMAIL_CODE] to={email} code={code}")
        return

    if settings.email_mode.lower() != "smtp":
        raise RuntimeError(f"Unknown EMAIL_MODE: {settings.email_mode}")

    if not settings.smtp_host or not settings.smtp_user or not settings.smtp_pass:
        raise RuntimeError("SMTP is not configured (SMTP_HOST/SMTP_USER/SMTP_PASS)")

    msg = EmailMessage()
    msg["Subject"] = "Your Mixtape login code"
    msg["From"] = settings.smtp_from
    msg["To"] = email
    msg.set_content(f"Your login code is: {code}\n\nThis code expires in {settings.login_code_ttl_seconds//60} minutes.")

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as s:
        s.starttls()
        s.login(settings.smtp_user, settings.smtp_pass)
        s.send_message(msg)


