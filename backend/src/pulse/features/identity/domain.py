from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from pulse.platform.errors import Forbidden


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    tenant_id: UUID
    tenant_name: str
    tenant_slug: str
    email: str
    name: str
    role: Role

    def require_monitor_write(self) -> None:
        if self.role == Role.VIEWER:
            raise Forbidden("Your role cannot modify monitors.")

    def require_member_read(self) -> None:
        if self.role not in (Role.OWNER, Role.ADMIN):
            raise Forbidden("Your role cannot manage members.")

    def require_member_write(self, target_role: Role, new_role: Role) -> None:
        self.require_member_read()
        if Role.OWNER in (target_role, new_role):
            raise Forbidden("Ownership cannot be changed through member management.")
        if self.role == Role.ADMIN and Role.ADMIN in (target_role, new_role):
            raise Forbidden("Only the owner can manage administrators.")


@dataclass(frozen=True)
class Member:
    id: UUID
    email: str
    name: str
    role: Role
    is_active: bool


@dataclass(frozen=True)
class Credentials:
    user_id: UUID
    password_hash: str
