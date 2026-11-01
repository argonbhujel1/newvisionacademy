from flask import current_app, render_template_string
from flask_mail import Message
from utils.timezone import now_nepal, format_date, format_time


def send_email(subject, recipients, html_body, text_body=None):
    """Send an email using Flask-Mail. Returns True on success."""
    from app import mail  # late import to avoid circular

    if not current_app.config.get("MAIL_USERNAME"):
        current_app.logger.warning("Mail not configured; skipping email send.")
        return False
    try:
        msg = Message(
            subject=subject,
            recipients=recipients if isinstance(recipients, list) else [recipients],
            html=html_body,
            body=text_body or "",
        )
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Email send error: {e}")
        return False


def render_template_vars(template_body, **kwargs):
    """Replace {{var}} placeholders in email templates."""
    body = template_body or ""
    for key, value in kwargs.items():
        body = body.replace("{{" + key + "}}", str(value or ""))
        body = body.replace("{{ " + key + " }}", str(value or ""))
    # Common defaults
    now = now_nepal()
    body = body.replace("{{date}}", format_date(now))
    body = body.replace("{{time}}", format_time(now))
    return body


def get_response_time_text(settings):
    """Return human-readable response time text from settings."""
    if not settings:
        return "as soon as possible"
    rt = getattr(settings, "response_time", None) or "30 minutes"
    if rt == "Immediately":
        return "immediately"
    if rt == "Custom":
        return getattr(settings, "custom_response_time", "as soon as possible") or "as soon as possible"
    return rt
