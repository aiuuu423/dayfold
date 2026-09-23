import os

from fastapi import Depends, FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.auth.cloudbase import (
    AuthProviderUnavailable,
    CloudBaseAuthAdapter,
    InvalidToken,
    TokenExpired,
)


DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:8000",
    "http://127.0.0.1:8000",
)

HEALTH_RESPONSE = {
    "status": "ok",
    "service": "dayfold-api",
    "environment": "preview",
    "version": "p1-probe",
}


def parse_allowed_origins(raw_origins: str | None) -> tuple[str, ...]:
    if not raw_origins:
        return DEFAULT_ALLOWED_ORIGINS

    origins = tuple(
        dict.fromkeys(origin.strip() for origin in raw_origins.split(",") if origin.strip())
    )
    if "*" in origins:
        raise ValueError("Wildcard CORS origins are not allowed")

    return origins


app = FastAPI(
    title="Dayfold API Preview",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_allowed_origins(os.getenv("DAYFOLD_ALLOWED_ORIGINS")),
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["Accept", "Authorization", "Content-Type"],
)


def get_auth_adapter() -> CloudBaseAuthAdapter | None:
    environment_id = os.getenv("DAYFOLD_CLOUDBASE_ENV_ID")
    if not environment_id:
        return None
    return CloudBaseAuthAdapter(environment_id)


def auth_error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


@app.get("/health")
def get_health() -> dict[str, str]:
    return HEALTH_RESPONSE


@app.get("/v1/auth/probe")
async def get_auth_probe(
    authorization: str | None = Header(default=None),
    adapter: CloudBaseAuthAdapter | None = Depends(get_auth_adapter),
):
    if not authorization:
        return auth_error(401, "INVALID_TOKEN", "Authentication is required.")

    scheme, separator, token = authorization.partition(" ")
    if (
        not separator
        or scheme.lower() != "bearer"
        or not token
        or token != token.strip()
        or " " in token
    ):
        return auth_error(401, "INVALID_TOKEN", "Authentication is required.")
    if adapter is None:
        return auth_error(
            503,
            "AUTH_PROVIDER_UNAVAILABLE",
            "Authentication provider is unavailable.",
        )

    try:
        await adapter.verify_access_token(token)
    except (InvalidToken, TokenExpired):
        return auth_error(401, "INVALID_TOKEN", "Authentication is required.")
    except AuthProviderUnavailable:
        return auth_error(
            503,
            "AUTH_PROVIDER_UNAVAILABLE",
            "Authentication provider is unavailable.",
        )

    return {"status": "authenticated"}
