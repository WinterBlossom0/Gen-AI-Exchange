from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Optional

from email_validator import validate_email, EmailNotValidError


@dataclass
class SMTPConfig:
    host: str
    port: int
    username: str
    password: str
    use_tls: bool = True
    from_addr: Optional[str] = None


def load_smtp_config() -> SMTPConfig:
    host = os.getenv("SMTP_HOST", "")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "")
    password = os.getenv("SMTP_PASSWORD", "")
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes", "on"}
    from_addr = os.getenv("ALERT_FROM_EMAIL", username)

    if not (host and username and password):
        raise RuntimeError("SMTP configuration missing. Set SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD in .env")

    try:
        if from_addr:
            validate_email(from_addr)
    except EmailNotValidError as e:
        raise RuntimeError(f"Invalid ALERT_FROM_EMAIL: {e}")

    return SMTPConfig(host, port, username, password, use_tls, from_addr)


def send_email(to_addr: str, subject: str, body: str, config: Optional[SMTPConfig] = None) -> None:
    if config is None:
        config = load_smtp_config()

    try:
        validate_email(to_addr)
    except EmailNotValidError as e:
        raise RuntimeError(f"Invalid recipient email: {e}")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config.from_addr or config.username
    msg["To"] = to_addr
    msg.set_content(body)

    if config.use_tls:
        with smtplib.SMTP(config.host, config.port) as server:
            server.starttls()
            server.login(config.username, config.password)
            server.send_message(msg)
    else:
        with smtplib.SMTP_SSL(config.host, config.port) as server:
            server.login(config.username, config.password)
            server.send_message(msg)
