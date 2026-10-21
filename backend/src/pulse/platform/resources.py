from dataclasses import dataclass

from redis import Redis
from sqlalchemy import Engine, create_engine

from pulse.platform.config import Settings


@dataclass
class Resources:
    engine: Engine
    redis: Redis

    @classmethod
    def create(cls, settings: Settings) -> "Resources":
        return cls(
            engine=create_engine(
                settings.database_url.get_secret_value(),
                pool_pre_ping=True,
                connect_args={"connect_timeout": 2, "options": "-c statement_timeout=2000"},
            ),
            redis=Redis.from_url(
                settings.redis_url.get_secret_value(),
                socket_connect_timeout=2,
                socket_timeout=2,
            ),
        )

    def close(self) -> None:
        self.redis.close()
        self.engine.dispose()
