"""Application settings, read from environment variables (see /.env.example).

Three explicit runtime modes:

* ``development`` (default) - permissive, used by ``make dev-back`` and tests.
* ``test``                  - used by the test suite; never production-safe.
* ``production``            - refuses to start with insecure defaults, so a weak
  ``JWT_SECRET`` or a non-Secure session cookie can never reach production silently.
"""

from datetime import date
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_parents = Path(__file__).resolve().parents
REPO_ROOT = _parents[3] if len(_parents) > 3 else Path("/")  # in Docker, DATA_DIR env is used

# Values that must never be used as a real signing key.
_INSECURE_JWT_SECRETS = frozenset({
    "",
    "dev-only-insecure-secret-change-me-in-env",
    "replace-with-a-long-random-string-at-least-32-chars",
    "secret",
    "changeme",
    "change-me",
})


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")

    environment: Environment = Environment.DEVELOPMENT

    database_url: str = "postgresql+psycopg://merchantpay:merchantpay@localhost:5433/merchantpay"

    # --- session / token -----------------------------------------------------
    jwt_secret: str = "dev-only-insecure-secret-change-me-in-env"
    jwt_ttl_minutes: int = Field(default=480, ge=1, le=60 * 24 * 30)
    jwt_issuer: str = "merchant-pay"
    jwt_audience: str = "merchant-pay-api"
    cookie_name: str = "mp_session"
    cookie_secure: bool = False
    cookie_domain: str | None = None
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    # --- CORS ----------------------------------------------------------------
    cors_origins: list[str] = ["http://localhost:5173"]

    # --- login throttling ----------------------------------------------------
    login_max_attempts: int = Field(default=5, ge=1, le=100)
    login_window_seconds: int = Field(default=300, ge=10, le=86_400)
    login_lockout_seconds: int = Field(default=900, ge=10, le=86_400)

    # --- data / clock --------------------------------------------------------
    data_dir: Path = REPO_ROOT / "data"
    timezone: str = "Africa/Algiers"
    # DEMO_TODAY freezes the clock (and therefore the alert windows) for a reproducible demo.
    demo_today: date | None = None

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION

    def validate_runtime(self) -> None:
        """Fail fast instead of silently booting an insecure production instance.

        Called from ``create_app`` so every entry point (uvicorn, tests, seed) is covered.
        """
        problems: list[str] = []

        if len(self.jwt_secret) < 16:
            problems.append("JWT_SECRET must be at least 16 characters")
        if self.cookie_samesite == "none" and not self.cookie_secure:
            problems.append("COOKIE_SAMESITE=none requires COOKIE_SECURE=true")
        if not self.cors_origins:
            problems.append("CORS_ORIGINS must list at least one trusted origin")

        if self.is_production:
            if self.jwt_secret in _INSECURE_JWT_SECRETS or len(self.jwt_secret) < 32:
                problems.append(
                    "JWT_SECRET is missing, a known default, or shorter than 32 characters. "
                    "Generate one (e.g. `python -c 'import secrets; print(secrets.token_urlsafe(48))'`)"
                )
            if not self.cookie_secure:
                problems.append("COOKIE_SECURE must be true in production (HTTPS-only session cookie)")
            if any(not origin.startswith("https://") for origin in self.cors_origins):
                problems.append("Every CORS_ORIGINS entry must use https:// in production")
            if self.demo_today is not None:
                problems.append("DEMO_TODAY must be unset in production (it freezes the business clock)")

        if problems:
            raise RuntimeError(
                "Unsafe configuration for "
                f"ENVIRONMENT={self.environment.value}: " + "; ".join(problems)
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
