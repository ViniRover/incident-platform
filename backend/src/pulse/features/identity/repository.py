from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from pulse.features.identity.domain import Credentials, Member, Principal, Role
from pulse.features.identity.models import SessionRow, TenantRow, UserRow
from pulse.features.identity.security import token_digest


def _member(row: UserRow) -> Member:
    return Member(row.id, row.email, row.name, Role(row.role), row.is_active)


class SqlIdentityRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def register(
        self, tenant_name: str, tenant_slug: str, name: str, email: str, password_hash: str
    ) -> UUID:
        tenant_id, user_id = uuid4(), uuid4()
        now = datetime.now(UTC)
        self._session.add(
            TenantRow(id=tenant_id, name=tenant_name, slug=tenant_slug, created_at=now)
        )
        self._session.flush()
        self._session.add(
            UserRow(
                id=user_id,
                tenant_id=tenant_id,
                email=email,
                name=name,
                password_hash=password_hash,
                role=Role.OWNER,
                is_active=True,
                created_at=now,
            )
        )
        self._session.flush()
        return user_id

    def credentials(self, tenant_slug: str, email: str) -> Credentials | None:
        row = self._session.scalar(
            select(UserRow)
            .join(TenantRow)
            .where(
                TenantRow.slug == tenant_slug, UserRow.email == email, UserRow.is_active.is_(True)
            )
        )
        return Credentials(row.id, row.password_hash) if row else None

    def add_session(self, user_id: UUID, token: str, expires_at: datetime) -> None:
        user = self._session.get(UserRow, user_id)
        assert user is not None
        self._session.add(
            SessionRow(
                token_hash=token_digest(token),
                tenant_id=user.tenant_id,
                user_id=user_id,
                expires_at=expires_at,
            )
        )
        self._session.flush()

    def resolve(self, token: str) -> Principal | None:
        result = self._session.execute(
            select(UserRow, TenantRow)
            .join(
                SessionRow,
                (SessionRow.user_id == UserRow.id) & (SessionRow.tenant_id == UserRow.tenant_id),
            )
            .join(TenantRow, TenantRow.id == UserRow.tenant_id)
            .where(
                SessionRow.token_hash == token_digest(token),
                SessionRow.expires_at > datetime.now(UTC),
                UserRow.is_active.is_(True),
            )
            .execution_options(populate_existing=True)
        ).first()
        if result is None:
            return None
        user, tenant = result
        return Principal(
            user.id, tenant.id, tenant.name, tenant.slug, user.email, user.name, Role(user.role)
        )

    def revoke(self, token: str) -> None:
        self._session.execute(
            delete(SessionRow).where(SessionRow.token_hash == token_digest(token))
        )

    def members(self, tenant_id: UUID, offset: int, limit: int) -> list[Member]:
        return [
            _member(row)
            for row in self._session.scalars(
                select(UserRow)
                .where(UserRow.tenant_id == tenant_id)
                .order_by(UserRow.created_at, UserRow.id)
                .offset(offset)
                .limit(limit)
            )
        ]

    def member(self, tenant_id: UUID, user_id: UUID, lock: bool = False) -> Member | None:
        statement = select(UserRow).where(UserRow.tenant_id == tenant_id, UserRow.id == user_id)
        row = self._session.scalar(
            statement.with_for_update().execution_options(populate_existing=True)
            if lock
            else statement
        )
        return _member(row) if row else None

    def add_member(
        self, tenant_id: UUID, name: str, email: str, password_hash: str, role: Role
    ) -> Member:
        row = UserRow(
            id=uuid4(),
            tenant_id=tenant_id,
            name=name,
            email=email,
            password_hash=password_hash,
            role=role,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        self._session.add(row)
        self._session.flush()
        return _member(row)

    def update_member(self, tenant_id: UUID, user_id: UUID, role: Role, is_active: bool) -> Member:
        row = self._session.scalar(
            select(UserRow)
            .where(UserRow.tenant_id == tenant_id, UserRow.id == user_id)
            .with_for_update()
        )
        assert row is not None
        row.role, row.is_active = role, is_active
        self._session.execute(
            delete(SessionRow).where(
                SessionRow.tenant_id == tenant_id, SessionRow.user_id == user_id
            )
        )
        self._session.flush()
        return _member(row)
