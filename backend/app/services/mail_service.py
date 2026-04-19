"""
Mail service — sends transactional emails via SMTP.

Falls back to console logging when SMTP env vars are not configured,
making this safe for local development without a mail server.

Uses stdlib smtplib + email.mime (no external dependencies).
HTML bodies are rendered from Jinja2 templates.
"""
import logging
import os
import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

load_dotenv()

logger = logging.getLogger(__name__)

# ─── SMTP configuration from environment ─────────────────────────────────────
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Mov-Sug")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# ─── Jinja2 template environment ─────────────────────────────────────────────
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=True,
)


def _is_smtp_configured() -> bool:
    """Check whether all required SMTP env vars are set."""
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD and SMTP_FROM_EMAIL)


def _send_in_background(to: str, subject: str, html_body: str) -> None:
    """
    Send an email in a background thread so the API response is not blocked.
    Errors are logged but never bubble up to the caller.
    """
    def _worker():
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_FROM_EMAIL, to, msg.as_string())

            logger.info("Email sent to %s: %s", to, subject)
        except Exception:
            logger.exception("Failed to send email to %s", to)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


def send_email(to: str, subject: str, html_body: str) -> None:
    """
    Public entry point for sending an email.

    If SMTP is not configured, logs the email content to the console
    so developers can verify emails without a real mail server.
    """
    if not _is_smtp_configured():
        logger.info(
            "[MAIL-DEV] To: %s | Subject: %s\n--- HTML Body (truncated) ---\n%s\n---",
            to,
            subject,
            html_body[:500],
        )
        return

    _send_in_background(to, subject, html_body)


# ─── Template-based convenience methods ───────────────────────────────────────


def send_welcome_email(email: str) -> None:
    """Send a welcome email after successful registration."""
    template = _jinja_env.get_template("welcome_email.html")
    html = template.render(email=email, frontend_url=FRONTEND_URL)
    send_email(to=email, subject="Welcome to Mov-Sug! 🎬", html_body=html)


def send_password_reset_email(email: str, token: str) -> None:
    """Send a password-reset email with a tokenized link."""
    reset_url = f"{FRONTEND_URL}/reset-password?token={token}"
    template = _jinja_env.get_template("password_reset_email.html")
    html = template.render(email=email, reset_url=reset_url)
    send_email(to=email, subject="Reset your Mov-Sug password 🔒", html_body=html)
