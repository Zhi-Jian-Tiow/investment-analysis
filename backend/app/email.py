"""Transactional email dispatch (architecture §11.3 — Resend, via BackgroundTasks).

Retry policy matches architecture §15.2: 1 in-task retry on failure. The
"then Sentry" half of that policy is a structlog ERROR log for now — Sentry
itself isn't wired up until the observability epic (Epic 9); swap the final
except branch's logging call for sentry_sdk.capture_exception when it lands.

resend.api_key is global, mutable state owned by the SDK itself, not
something this module controls — it's set immediately before every call
(cheap) rather than once at import time, so a settings change always takes
effect, including between test runs that use different Settings instances.
"""

import asyncio

import resend
import structlog

from app.config import Settings

logger = structlog.get_logger(__name__)

_RETRY_DELAY_SECONDS = 1


async def _send_with_retry(
    *, settings: Settings, to_email: str, subject: str, html: str, event: str
) -> None:
    """Never raises — a failed send must not block or fail the calling flow
    (BAS EX-007 for registration, EX-011 for password reset). `event` is the
    structlog event-name prefix, e.g. "email.verification" or
    "email.password_reset" — suffixed with ".sent", ".retrying", or
    ".send_failed" depending on outcome.
    """
    resend.api_key = settings.resend_api_key
    params = {
        "from": settings.email_from_address,
        "to": [to_email],
        "subject": subject,
        "html": html,
    }

    loop = asyncio.get_event_loop()
    for attempt in range(2):
        try:
            # resend's SDK is synchronous (built on `requests`); run it off
            # the event loop so a slow/hanging call doesn't block other
            # in-flight requests, same reasoning as the bcrypt executor calls.
            await loop.run_in_executor(None, resend.Emails.send, params)
            logger.info(f"{event}.sent", to=to_email)
            return
        except Exception as exc:
            if attempt == 0:
                logger.warning(f"{event}.retrying", to=to_email, error=str(exc))
                await asyncio.sleep(_RETRY_DELAY_SECONDS)
                continue
            logger.error(f"{event}.send_failed", to=to_email, error=str(exc))


async def send_verification_email(to_email: str, raw_token: str, settings: Settings) -> None:
    verify_url = f"{settings.frontend_base_url}/verify?token={raw_token}"
    html = (
        "<p>Welcome to BursaTrack. Please verify your email address to secure your account.</p>"
        f'<p><a href="{verify_url}">Verify my email</a></p>'
        "<p>This link expires in 24 hours. If you didn't create a BursaTrack account, "
        "you can ignore this email.</p>"
    )
    await _send_with_retry(
        settings=settings,
        to_email=to_email,
        subject="Verify your BursaTrack email",
        html=html,
        event="email.verification",
    )


async def send_password_reset_email(to_email: str, raw_token: str, settings: Settings) -> None:
    reset_url = f"{settings.frontend_base_url}/reset-password?token={raw_token}"
    html = (
        "<p>We received a request to reset your BursaTrack password.</p>"
        f'<p><a href="{reset_url}">Reset my password</a></p>'
        "<p>This link expires in 1 hour. If you didn't request this, you can safely ignore this email.</p>"
    )
    await _send_with_retry(
        settings=settings,
        to_email=to_email,
        subject="Reset your BursaTrack password",
        html=html,
        event="email.password_reset",
    )
