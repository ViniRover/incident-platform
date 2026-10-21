from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError


class PostgresProbe:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def check(self) -> bool:
        try:
            with self._engine.connect() as connection:
                return bool(connection.execute(text("SELECT 1")).scalar_one())
        except SQLAlchemyError:
            return False


class RedisProbe:
    def __init__(self, client: Redis) -> None:
        self._client = client

    def check(self) -> bool:
        try:
            return bool(self._client.ping())
        except RedisError:
            return False
