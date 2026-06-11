"""Email client — Jinja2 rendering + fastapi-mail SMTP delivery."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from app.core.logging import get_logger

_log = get_logger("email")

_template_dir = Path(__file__).resolve().parent.parent / "templates"
_env = Environment(loader=FileSystemLoader(str(_template_dir)), autoescape=True)


def render_template(name: str, **context: object) -> str:
    template = _env.get_template(name)
    return template.render(**context)


async def send_email(to: str, subject: str, template_name: str, context: dict) -> None:  # type: ignore[type-arg]
    """Send an HTML email via SMTP using fastapi-mail.

    Set SUPPRESS_EMAIL_SEND=true in tests to skip actual delivery.
    """
    from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

    from app.config import get_settings

    s = get_settings()

    use_starttls = s.smtp_port == 587 and s.smtp_tls
    use_ssl = s.smtp_port == 465

    _log.info(
        "email_send_start",
        recipient=to,
        subject=subject,
        template=template_name,
        smtp_host=s.smtp_host,
        smtp_port=s.smtp_port,
        suppress_send=s.suppress_email_send,
    )

    conf = ConnectionConfig(
        MAIL_USERNAME=s.smtp_username,
        MAIL_PASSWORD=s.smtp_password,
        MAIL_FROM=s.smtp_from_email,
        MAIL_FROM_NAME=s.smtp_from_name,
        MAIL_PORT=s.smtp_port,
        MAIL_SERVER=s.smtp_host,
        MAIL_STARTTLS=use_starttls,
        MAIL_SSL_TLS=use_ssl,
        USE_CREDENTIALS=bool(s.smtp_username),
        VALIDATE_CERTS=True,
        SUPPRESS_SEND=s.suppress_email_send,
    )

    if s.suppress_email_send:
        _log.info(
            "email_send_suppressed",
            recipient=to,
            template=template_name,
            reason="SUPPRESS_EMAIL_SEND=true",
        )

    try:
        html = render_template(template_name, **context)
    except Exception as exc:
        _log.error(
            "email_template_render_failed",
            recipient=to,
            template=template_name,
            exc=str(exc),
            exc_info=True,
        )
        raise

    msg = MessageSchema(
        subject=subject,
        recipients=[to],
        body=html,
        subtype=MessageType.html,
    )
    fm = FastMail(conf)

    try:
        await fm.send_message(msg)
    except Exception as exc:
        _log.error(
            "email_smtp_failed",
            recipient=to,
            subject=subject,
            template=template_name,
            smtp_host=s.smtp_host,
            smtp_port=s.smtp_port,
            exc=str(exc),
            exc_info=True,
        )
        raise

    _log.info(
        "email_sent_success",
        recipient=to,
        subject=subject,
        template=template_name,
        smtp_host=s.smtp_host,
    )
