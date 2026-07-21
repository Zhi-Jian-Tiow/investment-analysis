from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.email import send_verification_email
from app.rate_limit import limiter

from app.auth.schemas import UserResponse, AuthResponse, RegisterRequest
from app.auth.service import register_user, verify_email

router = APIRouter(prefix="/auth", tags=["Auth"])


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

    background_tasks.add_task(send_verification_email, user.email, raw_token)

    response.set_cookie(
        key=settings.session_cookie_name,
        value=access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.jwt_access_token_expiry_days * 86400,
    )

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
