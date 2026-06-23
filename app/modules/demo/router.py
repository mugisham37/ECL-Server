from fastapi import APIRouter, Request, status
from pydantic import BaseModel, EmailStr

from app.config import get_settings
from app.core.email import send_email
from app.core.limiter import limiter
from app.core.logging import get_logger

router = APIRouter(prefix="/demo", tags=["demo"])
_log = get_logger("demo")


class DemoRequest(BaseModel):
    name: str
    company: str
    email: EmailStr
    role: str
    portfolioSize: str
    message: str = ""


@router.post("", status_code=status.HTTP_200_OK)
@limiter.limit("10/hour")
async def submit_demo_request(request: Request, body: DemoRequest) -> dict:  # type: ignore[type-arg]
    settings = get_settings()

    notification_email = settings.demo_notification_email or settings.smtp_from_email

    _log.info(
        "demo_request_received",
        name=body.name,
        company=body.company,
        email=body.email,
        role=body.role,
        portfolio_size=body.portfolioSize,
    )

    await send_email(
        to=notification_email,
        subject=f"Demo request — {body.name} ({body.company})",
        template_name="demo_request.html",
        context={
            "name": body.name,
            "company": body.company,
            "email": body.email,
            "role": body.role,
            "portfolio_size": body.portfolioSize,
            "message": body.message or "—",
        },
    )

    return {"ok": True}
