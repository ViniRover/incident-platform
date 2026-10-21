from unittest.mock import Mock
from uuid import uuid4

import pytest
from redis.exceptions import ConnectionError

from pulse.features.identity.application import IdentityService
from pulse.features.identity.domain import Member, Principal, Role
from pulse.features.identity.rate_limit import RedisRateLimiter
from pulse.features.identity.security import csrf_token, get_password_hasher, token_digest
from pulse.platform.errors import DependencyUnavailable, Forbidden, RateLimited


def test_argon2_and_session_token_separation():
    passwords = get_password_hasher()
    encoded = passwords.hash("a long passphrase")
    assert passwords.verify("a long passphrase", encoded)
    assert not passwords.verify("wrong", encoded)
    assert not passwords.verify("wrong", None)
    assert not passwords.verify("wrong", "malformed")
    assert csrf_token("session") != token_digest("session")


def test_atomic_rate_limit_and_fail_closed():
    redis = Mock()
    limiter = RedisRateLimiter(redis)
    redis.eval.return_value = 1
    limiter.check("account@example.com", 10, 60)
    assert "account@example.com" not in redis.eval.call_args.args[2]
    redis.eval.return_value = 11
    with pytest.raises(RateLimited):
        limiter.check("account@example.com", 10, 60)
    redis.eval.side_effect = ConnectionError("unavailable")
    with pytest.raises(DependencyUnavailable):
        limiter.check("account@example.com", 10, 60)


def test_member_promotion_during_authorization_is_rechecked_after_lock():
    actor = Principal(uuid4(), uuid4(), "Acme", "acme", "admin@example.com", "Admin", Role.ADMIN)
    user_id = uuid4()
    repository = Mock()
    repository.member.side_effect = [
        Member(user_id, "user@example.com", "User", Role.OPERATOR, True),
        Member(user_id, "user@example.com", "User", Role.ADMIN, True),
    ]
    service = IdentityService(repository, Mock(), 3600)
    with pytest.raises(Forbidden):
        service.update_member(actor, user_id, Role.VIEWER, False)
    repository.update_member.assert_not_called()
