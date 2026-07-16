from __future__ import annotations

import smtplib
from email.message import EmailMessage

from config.settings import SMTP_FROM, SMTP_HOST, SMTP_PASS, SMTP_PORT, SMTP_TLS, SMTP_USER


class EmailConfigurationError(RuntimeError):
    pass


def smtp_configured() -> bool:
    return bool(SMTP_HOST and SMTP_FROM)


def send_password_reset_email(to_email: str, reset_url: str) -> None:
    if not smtp_configured():
        raise EmailConfigurationError("SMTP is not configured")

    msg = EmailMessage()
    msg["Subject"] = "Reset your ProctorAI password"
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.set_content(
        "\n".join(
            [
                "A password reset was requested for your ProctorAI account.",
                "",
                f"Open this secure link to choose a new password: {reset_url}",
                "",
                "This link expires soon and can only be used once.",
                "If you did not request this reset, ignore this email.",
            ]
        )
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
        if SMTP_TLS:
            smtp.starttls()
        if SMTP_USER:
            try:
                smtp.login(SMTP_USER, SMTP_PASS)
            except smtplib.SMTPAuthenticationError as exc:
                raise EmailConfigurationError(
                    "SMTP authentication failed. For Gmail, use a Gmail app password with SMTP."
                ) from exc
        smtp.send_message(msg)
