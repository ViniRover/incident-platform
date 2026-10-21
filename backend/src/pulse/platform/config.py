from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PULSE_")

    database_url: SecretStr
    redis_url: SecretStr
    cookie_secure: bool = False
    session_ttl_seconds: int = Field(default=28800, ge=300, le=86400)
    allowed_origins: list[str] = [
        "http://localhost:8080",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
