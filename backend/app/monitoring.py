"""Sentry Cron Monitoring / alerting stand-in. No SENTRY_DSN is configured
anywhere in this codebase yet (Epic 9 — see architecture §18.2/DEP-9.x) and
the sentry-sdk isn't installed, so every "Sentry check-in" / "Sentry alert"
requirement in Epic 5's stories is satisfied via structured structlog events
instead — same deferral already applied to email-delivery failure alerts
(app/email.py). Swap the bodies of these two functions for real
sentry_sdk.crons.capture_checkin(...) / sentry_sdk.capture_message(...) calls
once Epic 9 provisions a DSN; every call site stays the same.
"""

import structlog

logger = structlog.get_logger()


def sentry_checkin(monitor_slug: str, status: str, **context: object) -> None:
    """status: 'ok' | 'error' | 'in_progress' (Sentry Cron Monitoring's own
    vocabulary, kept identical here so the eventual swap is a body-only
    change)."""
    logger.info("sentry_checkin", monitor_slug=monitor_slug, status=status, **context)


def sentry_alert(level: str, message: str, **context: object) -> None:
    """level: 'warning' | 'critical'."""
    log = logger.critical if level == "critical" else logger.warning
    log("sentry_alert", level=level, message=message, **context)
