"""Application settings, read from environment variables (see /.env.example)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_parents = Path(__file__).resolve().parents
REPO_ROOT = _parents[3] if len(_parents) > 3 else Path("/")  # in Docker, DATA_DIR env is used


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")

    database_url: str = "postgresql+psycopg://merchantpay:merchantpay@localhost:5433/merchantpay"
    jwt_secret: str = "dev-only-insecure-secret-change-me-in-env"
    jwt_ttl_minutes: int = 480
    cookie_secure: bool = False
    cors_origins: list[str] = ["http://localhost:5173"]
    data_dir: Path = REPO_ROOT / "data"
    timezone: str = "Africa/Algiers"


@lru_cache
def get_settings() -> Settings:
    return Settings()
