import secrets
from typing import Annotated

from fastapi import Depends, Header, Request, Security
from fastapi.security import APIKeyCookie

from pulse.features.identity.application import IdentityService
from pulse.features.identity.domain import Principal
from pulse.features.identity.rate_limit import RateLimiter, RedisRateLimiter
from pulse.features.identity.repository import SqlIdentityRepository
from pulse.features.identity.security import csrf_token, get_password_hasher
from pulse.platform.database import DatabaseSession
from pulse.platform.errors import Forbidden, Unauthenticated

SESSION_COOKIE = "pulse_session"
session_cookie = APIKeyCookie(
    name=SESSION_COOKIE,
    scheme_name="SessionCookie",
    auto_error=False,
    description=(
        "HttpOnly session cookie. Unsafe methods also require "
        "X-CSRF-Token from the session response."
    ),
)


def get_identity_service(request: Request, session: DatabaseSession) -> IdentityService:
    return IdentityService(
        SqlIdentityRepository(session),
        get_password_hasher(),
        request.app.state.settings.session_ttl_seconds,
    )


Identity = Annotated[IdentityService, Depends(get_identity_service, scope="function")]


def get_rate_limiter(request: Request) -> RateLimiter:
    return RedisRateLimiter(request.app.state.resources.redis)


Limiter = Annotated[RateLimiter, Depends(get_rate_limiter)]


def check_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin not in request.app.state.settings.allowed_origins:
        raise Forbidden("Request origin is not allowed.")
    if not origin and request.headers.get("sec-fetch-site") == "cross-site":
        raise Forbidden("Cross-site requests are not allowed.")


def get_principal(
    request: Request,
    identity: Identity,
    token: Annotated[str | None, Security(session_cookie)],
    csrf: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> Principal:
    if not token or len(token) > 128:
        raise Unauthenticated("Authentication required.")
    principal = identity.resolve(token)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        check_origin(request)
        supplied = csrf or ""
        if not secrets.compare_digest(supplied.encode(), csrf_token(token).encode()):
            raise Forbidden("Invalid CSRF token.")
    return principal


CurrentPrincipal = Annotated[Principal, Depends(get_principal, scope="function")]
