from typing import Protocol

from redis import Redis
from redis.exceptions import RedisError

from pulse.features.identity.security import token_digest
from pulse.platform.errors import DependencyUnavailable, RateLimited


class RateLimiter(Protocol):
    def check(self, key: str, limit: int, seconds: int) -> None: ...


class RedisRateLimiter:
    _SCRIPT = """
    local count = redis.call('INCR', KEYS[1])
    if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
    return count
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    def check(self, key: str, limit: int, seconds: int) -> None:
        try:
            count = self._redis.eval(self._SCRIPT, 1, "pulse:auth:" + token_digest(key), seconds)
        except RedisError as error:
            raise DependencyUnavailable("Authentication temporarily unavailable.") from error
        if int(count) > limit:
            raise RateLimited("Too many attempts. Try again later.")
