"""Application error types mapped to the API's universal error schema (ADD-002):

    ErrorResponse           {"error": str, "message": str}
    ValidationErrorResponse {"error": "validation_failed", "message": str, "fields": [...]}

Route handlers raise AppError; the handler registered in app.main converts it to
the correct JSON body and status code. This keeps service-layer functions free of
any direct dependency on FastAPI's response objects.
"""

from typing import Any


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        error: str,
        message: str,
        fields: list[dict[str, Any]] | None = None,
        headers: dict[str, str] | None = None,
    ):
        self.status_code = status_code
        self.error = error
        self.message = message
        self.fields = fields
        self.headers = headers or {}
        super().__init__(message)


def validation_error(message: str, fields: list[dict[str, Any]]) -> AppError:
    """422 validation_failed — for business-rule validation failures raised
    manually in a service function (e.g. duplicate email, unknown broker_id),
    as distinct from Pydantic's own field-shape validation (handled separately
    by the RequestValidationError handler in app.main).
    """
    return AppError(422, "validation_failed", message, fields=fields)


def not_found(message: str = "The requested resource was not found.") -> AppError:
    """404 — used for both 'does not exist' and 'not owned by caller' (BAS §9:
    ownership-check failures must not be distinguishable from a missing resource).
    """
    return AppError(404, "not_found", message)


def invalid_token(message: str) -> AppError:
    """400 invalid_token — pending_tokens lookup failed: not found, expired, or
    already used (BAS Workflow 8 / Workflow 1 alternative flows).
    """
    return AppError(400, "invalid_token", message)


def invalid_credentials() -> AppError:
    """401 invalid_credentials — wrong email or password. Message is identical
    regardless of whether the email exists, to prevent account enumeration
    (BAS US-002).
    """
    return AppError(401, "invalid_credentials", "Email or password is incorrect.")


def account_locked(retry_after_seconds: int) -> AppError:
    """429 account_locked — BR-016 / EX-009: 5 failed login attempts within 10
    minutes from the same IP. Distinct from the generic rate_limit_exceeded
    code even though both use HTTP 429 (per the API error catalog, ADD-002).
    """
    return AppError(
        429,
        "account_locked",
        "Too many failed attempts. Please wait 10 minutes before trying again.",
        headers={"Retry-After": str(retry_after_seconds)},
    )


def unauthorized(error: str, message: str) -> AppError:
    """401 — for JWT-auth failures on protected endpoints: invalid_token,
    token_expired, or token_revoked (per the API error catalog, ADD-002).
    """
    return AppError(401, error, message)
