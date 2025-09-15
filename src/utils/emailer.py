from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from pathlib import Path
import mimetypes
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
    # Support both our standard names and the user's existing names without forcing renames
    host = os.getenv("SMTP_HOST") or os.getenv("SMTP_SERVER", "")
    port = int(os.getenv("SMTP_PORT", os.getenv("SMTP_SERVER_PORT", "587")))
    username = os.getenv("SMTP_USERNAME") or os.getenv("SENDER_EMAIL", "")
    password = os.getenv("SMTP_PASSWORD") or os.getenv("SENDER_PASSWORD", "")
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes", "on"}
    # from address: ALERT_FROM_EMAIL overrides; otherwise use provided sender email/username
    from_addr = os.getenv("ALERT_FROM_EMAIL") or os.getenv("SENDER_EMAIL") or username

    if not (host and username and password):
        raise RuntimeError(
            "SMTP configuration missing. Provide either (SMTP_HOST/SMTP_USERNAME/SMTP_PASSWORD) "
            "or (SMTP_SERVER/SENDER_EMAIL/SENDER_PASSWORD) in .env"
        )

    try:
        if from_addr:
            validate_email(from_addr)
    except EmailNotValidError as e:
        raise RuntimeError(f"Invalid ALERT_FROM_EMAIL: {e}")

    return SMTPConfig(host, port, username, password, use_tls, from_addr)


def send_email(
    to_addr: str,
    subject: str,
    body: str,
    config: Optional[SMTPConfig] = None,
    attachments: Optional[list[str | Path]] = None,
) -> None:
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

    # Attach any provided files
    for att in (attachments or []):
        try:
            p = Path(att)
            if not p.exists() or not p.is_file():
                continue
            ctype, encoding = mimetypes.guess_type(p.name)
            if ctype is None:
                maintype, subtype = "application", "octet-stream"
            else:
                maintype, subtype = ctype.split("/", 1)
            with p.open("rb") as fh:
                data = fh.read()
            msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=p.name)
        except Exception:
            # Skip problematic attachments but still send email
            continue

    if config.use_tls:
        with smtplib.SMTP(config.host, config.port) as server:
            server.starttls()
            server.login(config.username, config.password)
            server.send_message(msg)
    else:
        with smtplib.SMTP_SSL(config.host, config.port) as server:
            server.login(config.username, config.password)
            server.send_message(msg)
