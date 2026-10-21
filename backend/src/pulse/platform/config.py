from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PULSE_")

    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://pulse:pulse_local_only@localhost:5432/pulse"
    )
    redis_url: SecretStr = SecretStr("redis://localhost:6379/0")


@lru_cache
def get_settings() -> Settings:
    return Settings()
