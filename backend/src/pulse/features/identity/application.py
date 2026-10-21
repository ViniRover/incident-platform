import secrets
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from pulse.features.identity.domain import Credentials, Member, Principal, Role
from pulse.platform.errors import NotFound, Unauthenticated


class IdentityRepository(Protocol):
    def register(
        self, tenant_name: str, tenant_slug: str, name: str, email: str, password_hash: str
    ) -> UUID: ...
    def credentials(self, tenant_slug: str, email: str) -> Credentials | None: ...
    def add_session(self, user_id: UUID, token: str, expires_at: datetime) -> None: ...
    def resolve(self, token: str) -> Principal | None: ...
    def revoke(self, token: str) -> None: ...
    def members(self, tenant_id: UUID, offset: int, limit: int) -> list[Member]: ...
    def member(self, tenant_id: UUID, user_id: UUID, lock: bool = False) -> Member | None: ...
    def add_member(
        self, tenant_id: UUID, name: str, email: str, password_hash: str, role: Role
    ) -> Member: ...
    def update_member(
        self, tenant_id: UUID, user_id: UUID, role: Role, is_active: bool
    ) -> Member: ...


class Passwords(Protocol):
    def hash(self, password: str) -> str: ...
    def verify(self, password: str, password_hash: str | None) -> bool: ...


class IdentityService:
    def __init__(
        self, repository: IdentityRepository, passwords: Passwords, ttl_seconds: int
    ) -> None:
        self._repository = repository
        self._passwords = passwords
        self._ttl = ttl_seconds

    def register(
        self, tenant_name: str, tenant_slug: str, name: str, email: str, password: str
    ) -> str:
        user_id = self._repository.register(
            tenant_name, tenant_slug, name, email, self._passwords.hash(password)
        )
        return self._start_session(user_id)

    def login(self, tenant_slug: str, email: str, password: str) -> str:
        credentials = self._repository.credentials(tenant_slug, email)
        if not self._passwords.verify(password, credentials.password_hash if credentials else None):
            raise Unauthenticated("Invalid tenant, email or password.")
        assert credentials is not None
        return self._start_session(credentials.user_id)

    def _start_session(self, user_id: UUID) -> str:
        token = secrets.token_urlsafe(32)
        self._repository.add_session(
            user_id, token, datetime.now(UTC) + timedelta(seconds=self._ttl)
        )
        return token

    def resolve(self, token: str) -> Principal:
        principal = self._repository.resolve(token)
        if principal is None:
            raise Unauthenticated("Authentication required.")
        return principal

    def logout(self, token: str) -> None:
        self._repository.revoke(token)

    def members(self, actor: Principal, offset: int = 0, limit: int = 20) -> list[Member]:
        actor.require_member_read()
        return self._repository.members(actor.tenant_id, offset, limit)

    def add_member(
        self, actor: Principal, name: str, email: str, password: str, role: Role
    ) -> Member:
        actor.require_member_write(role, role)
        return self._repository.add_member(
            actor.tenant_id, name, email, self._passwords.hash(password), role
        )

    def update_member(self, actor: Principal, user_id: UUID, role: Role, is_active: bool) -> Member:
        actor.require_member_read()
        member = self._repository.member(actor.tenant_id, user_id)
        if member is None:
            raise NotFound("Member not found.")
        actor.require_member_write(member.role, role)
        # Do not take an exclusive lock on a protected owner/admin before authorization.
        # Recheck after locking: another request may have promoted the target meanwhile.
        member = self._repository.member(actor.tenant_id, user_id, lock=True)
        if member is None:
            raise NotFound("Member not found.")
        actor.require_member_write(member.role, role)
        return self._repository.update_member(actor.tenant_id, user_id, role, is_active)
