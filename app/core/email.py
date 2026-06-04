"""Email client — Jinja2 rendering + fastapi-mail SMTP delivery."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

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

    conf = ConnectionConfig(
        MAIL_USERNAME=s.smtp_username,
        MAIL_PASSWORD=s.smtp_password,
        MAIL_FROM=s.smtp_from_email,
        MAIL_FROM_NAME=s.smtp_from_name,
        MAIL_PORT=s.smtp_port,
        MAIL_SERVER=s.smtp_host,
        MAIL_STARTTLS=s.smtp_tls,
        MAIL_SSL_TLS=False,
        USE_CREDENTIALS=bool(s.smtp_username),
        VALIDATE_CERTS=True,
        SUPPRESS_SEND=s.suppress_email_send,
    )

    html = render_template(template_name, **context)
    msg = MessageSchema(
        subject=subject,
        recipients=[to],
        body=html,
        subtype=MessageType.html,
    )
    fm = FastMail(conf)
    await fm.send_message(msg)
