import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


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
    allow_headers=["Accept", "Content-Type"],
)


@app.get("/health")
def get_health() -> dict[str, str]:
    return HEALTH_RESPONSE
