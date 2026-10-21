from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PULSE_")

    database_url: SecretStr
    redis_url: SecretStr


@lru_cache
def get_settings() -> Settings:
    return Settings()
