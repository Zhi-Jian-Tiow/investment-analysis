from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _check_password_complexity(value: str) -> str:
    # VR-002: at least one uppercase letter, at least one digit. Shared by
    # every schema that accepts a NEW password (RegisterRequest,
    # PasswordResetComplete) — LoginRequest deliberately does not use this,
    # see its docstring.
    if not any(char.isupper() for char in value):
        raise ValueError("Password must contain at least one uppercase letter")
    if not any(char.isdigit() for char in value):
        raise ValueError("Password must contain at least one digit")
    return value


class RegisterRequest(BaseModel):
    """Matches components/schemas/RegisterRequest in 03-openapi-specification.md
    exactly: email, password, broker_id. (password_confirm is a frontend-only
    concern per FE-1.1 — the OpenAPI contract does not carry it.)
    """

    email: EmailStr = Field(..., max_length=254)
    password: str = Field(..., min_length=8, max_length=128)
    broker_id: UUID

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, value: str) -> str:
        return _check_password_complexity(value)


class LoginRequest(BaseModel):
    """Matches components/schemas/LoginRequest in 03-openapi-specification.md.
    No minLength/complexity check on password here (unlike RegisterRequest) —
    a legacy account could predate a password-policy change and must still be
    able to log in with whatever password it has (API security review finding
    IV-000). maxLength bounds a pathological request body cheaply.
    """

    email: EmailStr
    password: str = Field(..., max_length=128)


class PasswordResetRequest(BaseModel):
    """Matches components/schemas/PasswordResetRequest in
    03-openapi-specification.md. No uniqueness/existence check happens at the
    schema layer — the service layer deliberately treats "found" and
    "not found" identically (account enumeration protection).
    """

    email: EmailStr


class PasswordResetComplete(BaseModel):
    """Matches components/schemas/PasswordResetComplete. `token` travels in
    the request body, never the URL (BAS Workflow 8 / API security review).
    """

    token: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password_complexity(cls, value: str) -> str:
        return _check_password_complexity(value)


class MessageResponse(BaseModel):
    message: str


class JwkKey(BaseModel):
    kty: str
    use: str
    alg: str
    kid: str
    n: str
    e: str


class JwksResponse(BaseModel):
    keys: list[JwkKey]


class UserResponse(BaseModel):
    """Public user fields only — never password_hash or token_version
    (API security review PD requirement)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    email_verified: bool
    account_status: str
    trial_expiry_date: date
    subscription_start_date: date | None = None
    subscription_renewal_date: date | None = None
    default_broker_id: UUID | None = Field(None, validation_alias="default_broker_config_id")
    created_at: datetime


class AuthResponse(BaseModel):
    user: UserResponse
    expires_at: datetime
