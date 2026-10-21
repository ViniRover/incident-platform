from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    StringConstraints,
    field_validator,
)

from pulse.features.identity.dependencies import (
    SESSION_COOKIE,
    CurrentPrincipal,
    Identity,
    Limiter,
    check_origin,
)
from pulse.features.identity.domain import Principal, Role
from pulse.features.identity.security import csrf_token

router = APIRouter(tags=["identity"])
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Slug = Annotated[
    str, StringConstraints(pattern=r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", max_length=63)
]
Password = Annotated[SecretStr, Field(min_length=15, max_length=128)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterRequest(Input):
    tenant_name: Name
    tenant_slug: Slug
    name: Name
    email: EmailStr = Field(max_length=254)
    password: Password

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class LoginRequest(Input):
    tenant_slug: Slug
    email: EmailStr = Field(max_length=254)
    password: SecretStr = Field(min_length=1, max_length=128)


class MemberCreate(Input):
    name: Name
    email: EmailStr = Field(max_length=254)
    password: Password
    role: Role


class MemberUpdate(Input):
    role: Role
    is_active: bool


class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    email: str
    role: Role
    is_active: bool


class SessionResponse(BaseModel):
    user_id: UUID
    tenant_id: UUID
    tenant_name: str
    tenant_slug: str
    email: str
    name: str
    role: Role
    csrf_token: str


def _session_response(principal: Principal, token: str) -> SessionResponse:
    return SessionResponse(
        **asdict(principal),
        csrf_token=csrf_token(token),
    )


def _set_cookie(response: Response, request: Request, token: str) -> None:
    settings = request.app.state.settings
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
        max_age=settings.session_ttl_seconds,
    )
    response.headers["Cache-Control"] = "no-store"


@router.post(
    "/auth/register",
    response_model=SessionResponse,
    status_code=201,
    operation_id="register_account",
)
def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    identity: Identity,
    limiter: Limiter,
) -> SessionResponse:
    check_origin(request)
    limiter.check("register:" + (request.client.host if request.client else "unknown"), 5, 60)
    token = identity.register(
        body.tenant_name,
        body.tenant_slug,
        body.name,
        str(body.email),
        body.password.get_secret_value(),
    )
    _set_cookie(response, request, token)
    return _session_response(identity.resolve(token), token)


@router.post("/auth/login", response_model=SessionResponse, operation_id="login")
def login(
    body: LoginRequest, request: Request, response: Response, identity: Identity, limiter: Limiter
) -> SessionResponse:
    check_origin(request)
    limiter.check("login-ip:" + (request.client.host if request.client else "unknown"), 60, 60)
    limiter.check(f"login-account:{body.tenant_slug}:{str(body.email).lower()}", 10, 60)
    token = identity.login(
        body.tenant_slug, str(body.email).lower(), body.password.get_secret_value()
    )
    old_token = request.cookies.get(SESSION_COOKIE)
    if old_token:
        identity.logout(old_token)
    _set_cookie(response, request, token)
    return _session_response(identity.resolve(token), token)


@router.get("/auth/me", response_model=SessionResponse, operation_id="current_session")
def me(request: Request, response: Response, principal: CurrentPrincipal) -> SessionResponse:
    response.headers["Cache-Control"] = "no-store"
    return _session_response(principal, request.cookies[SESSION_COOKIE])


@router.post("/auth/logout", status_code=204, operation_id="logout")
def logout(
    request: Request, response: Response, principal: CurrentPrincipal, identity: Identity
) -> None:
    identity.logout(request.cookies[SESSION_COOKIE])
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=request.app.state.settings.cookie_secure,
        httponly=True,
        samesite="strict",
    )


@router.get("/members", response_model=list[MemberResponse], operation_id="list_members")
def members(
    principal: CurrentPrincipal,
    identity: Identity,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    return identity.members(principal, offset, limit)


@router.post(
    "/members", response_model=MemberResponse, status_code=201, operation_id="create_member"
)
def add_member(body: MemberCreate, principal: CurrentPrincipal, identity: Identity):
    return identity.add_member(
        principal, body.name, str(body.email).lower(), body.password.get_secret_value(), body.role
    )


@router.patch("/members/{user_id}", response_model=MemberResponse, operation_id="update_member")
def update_member(
    user_id: UUID, body: MemberUpdate, principal: CurrentPrincipal, identity: Identity
):
    return identity.update_member(principal, user_id, body.role, body.is_active)
