"""
Mail service — sends transactional emails via Gmail SMTP (SSL).

Falls back to console logging when SMTP_PASSWORD is not configured,
making this safe for local development without a mail server.

Uses stdlib smtplib + email.mime (no external dependencies).
HTML bodies are rendered from Jinja2 templates.
"""
import logging
import os
import smtplib
import threading
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from urllib.parse import urlencode

from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

load_dotenv()

logger = logging.getLogger(__name__)

# ─── SMTP configuration (Gmail SSL defaults) ─────────────────────────────────
# All values can be overridden via environment variables.
# Only SMTP_PASSWORD *must* come from the .env file for security.
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "noreply.tltn@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Laetus")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "noreply.tltn@gmail.com")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# ─── Jinja2 template environment ─────────────────────────────────────────────
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=True,
)


def _is_smtp_configured() -> bool:
    """Check whether the SMTP password is set (the only required secret)."""
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD and SMTP_FROM_EMAIL)


# ─── Startup validation ──────────────────────────────────────────────────────
# Log a clear message so operators know whether email is enabled or disabled.
# Never reveals actual secrets — only whether they're present.
if _is_smtp_configured():
    logger.info(
        "SMTP configured: host=%s port=%s from=%s — emails will be sent.",
        SMTP_HOST, SMTP_PORT, SMTP_FROM_EMAIL,
    )
else:
    _missing = []
    if not SMTP_HOST:     _missing.append("SMTP_HOST")
    if not SMTP_USER:     _missing.append("SMTP_USER")
    if not SMTP_PASSWORD: _missing.append("SMTP_PASSWORD")
    if not SMTP_FROM_EMAIL: _missing.append("SMTP_FROM_EMAIL")
    logger.warning(
        "SMTP NOT configured (missing: %s). Emails will be logged to console only.",
        ", ".join(_missing),
    )


# ─── URL helpers ──────────────────────────────────────────────────────────────


def build_frontend_url(path: str, **query_params: str) -> str:
    """
    Build a full frontend URL from the configured FRONTEND_URL base.

    - Strips whitespace and trailing slashes from the base.
    - URL-encodes all query parameters.
    - Prevents double slashes between base and path.
    """
    base = FRONTEND_URL.strip().rstrip("/")
    # Ensure path starts with exactly one /
    clean_path = "/" + path.lstrip("/")
    if query_params:
        return f"{base}{clean_path}?{urlencode(query_params)}"
    return f"{base}{clean_path}"


def format_expiry_text(minutes: int) -> str:
    """
    Convert a minute-based expiry into a readable string.

    Examples:
        15  → "15 minutes"
        60  → "1 hour"
        120 → "2 hours"
        90  → "90 minutes"
    """
    if minutes <= 0:
        return "a few moments"
    if minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} hour" if hours == 1 else f"{hours} hours"
    return f"{minutes} minutes" if minutes != 1 else "1 minute"


# ─── Email sending ────────────────────────────────────────────────────────────


def _send_in_background(
    to: str, subject: str, html_body: str, text_body: str | None = None,
) -> None:
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
            # Attach text/plain first, then text/html (RFC 2046: last = preferred)
            if text_body:
                msg.attach(MIMEText(text_body, "plain", "utf-8"))
            msg.attach(MIMEText(html_body, "html", "utf-8"))

            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_FROM_EMAIL, to, msg.as_string())

            logger.info("Email sent to %s: %s", to, subject)
        except Exception:
            logger.exception("Failed to send email to %s", to)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


def send_email(
    to: str, subject: str, html_body: str, text_body: str | None = None,
) -> None:
    """
    Public entry point for sending an email.

    If SMTP is not configured (SMTP_PASSWORD not set), logs the email content
    to the console so developers can verify emails without a real mail server.
    """
    if not _is_smtp_configured():
        logger.info(
            "[MAIL-DEV] To: %s | Subject: %s\n--- HTML Body (truncated) ---\n%s\n---",
            to,
            subject,
            html_body[:500],
        )
        return

    _send_in_background(to, subject, html_body, text_body)


# ─── Template-based convenience methods ───────────────────────────────────────


def send_welcome_email(email: str) -> None:
    """Send a welcome email after successful registration."""
    template = _jinja_env.get_template("welcome_email.html")
    html = template.render(email=email, frontend_url=FRONTEND_URL)
    send_email(to=email, subject="Welcome to Laetus! 🎬", html_body=html)


def send_password_reset_email(email: str, token: str) -> None:
    """Send a password-reset email with a tokenized link."""
    from ..services.auth_service import PASSWORD_RESET_TOKEN_EXPIRE_MINUTES

    reset_url = build_frontend_url("reset-password", token=token)
    expiry_text = format_expiry_text(PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
    year = datetime.now(timezone.utc).year

    html_template = _jinja_env.get_template("password_reset_email.html")
    html = html_template.render(
        reset_url=reset_url, expiry_text=expiry_text, year=year,
    )

    text_template = _jinja_env.get_template("password_reset_email.txt")
    text = text_template.render(
        reset_url=reset_url, expiry_text=expiry_text, year=year,
    )

    send_email(
        to=email,
        subject="Reset your Laetus password",
        html_body=html,
        text_body=text,
    )


def send_password_change_email(email: str, token: str) -> None:
    """Send a confirmation email for an authenticated password change."""
    confirm_url = build_frontend_url("confirm-password-change", token=token)
    template = _jinja_env.get_template("password_change_confirm_email.html")
    html = template.render(email=email, confirm_url=confirm_url)
    send_email(to=email, subject="Confirm your Laetus password change 🔐", html_body=html)
