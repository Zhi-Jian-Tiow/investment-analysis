from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.email import send_password_reset_email, send_verification_email
from app.rate_limit import limiter

from app.auth.dependencies import get_current_user
from app.auth.lockout import tracker as login_lockout_tracker
from app.auth.models import User
from app.auth.schemas import (
    AuthResponse,
    JwksResponse,
    LoginRequest,
    MessageResponse,
    PasswordResetComplete,
    PasswordResetRequest,
    RegisterRequest,
    UserResponse,
)
from app.auth.security import build_jwks
from app.auth.service import (
    authenticate_user,
    issue_access_token,
    logout_user,
    register_user,
    request_password_reset,
    reset_password,
    verify_email,
)
from app.errors import AppError, account_locked

GENERIC_PASSWORD_RESET_MESSAGE = "If an account with that email exists, a reset link has been sent."

router = APIRouter(prefix="/auth", tags=["Auth"])


def _set_session_cookie(response: Response, settings: Settings, access_token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.jwt_access_token_expiry_days * 86400,
    )


@router.post("/register", response_model=AuthResponse, status_code=201)
@limiter.limit("3/minute")
async def register(
    request: Request,
    payload: RegisterRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    user, raw_token, access_token, expires_at = await register_user(
        db,
        email=payload.email,
        password=payload.password,
        broker_id=payload.broker_id,
        settings=settings,
    )

    background_tasks.add_task(send_verification_email, user.email, raw_token, settings)
    _set_session_cookie(response, settings, access_token)

    return AuthResponse(user=UserResponse.model_validate(user), expires_at=expires_at)


@router.get("/verify", response_model=UserResponse)
@limiter.limit("10/minute")
async def verify_register_email(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    user = await verify_email(db, token)
    return UserResponse.model_validate(user)


@router.post("/login", response_model=AuthResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    ip = get_remote_address(request)

    remaining = login_lockout_tracker.seconds_until_unlocked(ip)
    if remaining is not None:
        raise account_locked(remaining)

    try:
        user, access_token, expires_at = await authenticate_user(
            db, email=payload.email, password=payload.password, settings=settings
        )
    except AppError as exc:
        # Only a credential failure counts toward the lockout — an unrelated
        # error (e.g. a DB hiccup) must not lock the caller out.
        if exc.error == "invalid_credentials":
            login_lockout_tracker.record_failure(ip)
        raise

    login_lockout_tracker.record_success(ip)
    _set_session_cookie(response, settings, access_token)

    return AuthResponse(user=UserResponse.model_validate(user), expires_at=expires_at)


@router.post("/logout", status_code=204)
@limiter.limit("60/minute")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> None:
    await logout_user(db, current_user)
    response.delete_cookie(key=settings.session_cookie_name)


@router.post("/refresh", response_model=AuthResponse)
@limiter.limit("60/minute")
async def refresh(
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> AuthResponse:
    access_token, expires_at = issue_access_token(current_user, settings)
    _set_session_cookie(response, settings, access_token)

    return AuthResponse(user=UserResponse.model_validate(current_user), expires_at=expires_at)


@router.get("/jwks.json", response_model=JwksResponse)
async def jwks(settings: Settings = Depends(get_settings)) -> JwksResponse:
    return JwksResponse.model_validate(build_jwks(settings.jwt_public_key))


@router.post("/password-reset-request", response_model=MessageResponse)
@limiter.limit("3/minute")
async def password_reset_request(
    request: Request,
    payload: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> MessageResponse:
    user, raw_token = await request_password_reset(db, email=payload.email)

    # Only queue the email when an account actually exists. The HTTP response
    # itself never varies (account enumeration protection, BAS Workflow 8).
    if user is not None:
        background_tasks.add_task(send_password_reset_email, user.email, raw_token, settings)

    return MessageResponse(message=GENERIC_PASSWORD_RESET_MESSAGE)


@router.post("/password-reset", response_model=MessageResponse)
@limiter.limit("10/minute")
async def password_reset(
    request: Request,
    payload: PasswordResetComplete,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await reset_password(db, raw_token=payload.token, new_password=payload.new_password)
    return MessageResponse(message="Password updated successfully. Please log in.")
