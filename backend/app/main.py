from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import router as auth_router
from app.config import get_settings
from app.database import get_db
from app.errors import AppError
from app.portfolio.router import router as portfolio_router
from app.rate_limit import limiter


def create_app() -> FastAPI:
    app = FastAPI(title="BursaTrack API", version="0.1.0")

    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    # allow_credentials=True is required for the HTTP-only session cookie to
    # be sent cross-origin (frontend on :3000, backend on :8000 in dev) — see
    # architecture §14.3. That flag makes a wildcard allow_origins invalid
    # per the CORS spec, so this must be a concrete origin list.
    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        body = {"error": exc.error, "message": exc.message}
        if exc.fields:
            body["fields"] = exc.fields
        return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers or None)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Normalizes FastAPI/Pydantic's default 422 body into the API's universal
        # ValidationErrorResponse shape (ADD-002).
        fields = [
            {
                "field": str(err["loc"][-1]) if err.get("loc") else "body",
                "constraint": err.get("msg", "Invalid value"),
                "received": None,
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation_failed",
                "message": "One or more fields failed validation.",
                "fields": fields,
            },
        )

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        response = JSONResponse(
            status_code=429,
            content={"error": "rate_limit_exceeded", "message": "Too many requests. Please try again later."},
        )
        response.headers["Retry-After"] = "60"
        return response

    app.include_router(auth_router)
    app.include_router(portfolio_router)

    @app.get("/health")
    async def health_check(db: AsyncSession = Depends(get_db)):
        try:
            await db.execute(text("SELECT 1"))
            return {"status": "ok", "db": "ok"}
        except Exception:
            raise HTTPException(status_code=503, detail={"status": "error", "db": "unreachable"})

    return app


app = create_app()
