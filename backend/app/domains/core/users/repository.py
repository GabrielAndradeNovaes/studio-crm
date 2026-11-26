from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import StudioRole
from app.core.tenancy import BaseTenantRepository, bypass_tenant_filter
from app.domains.core.studios.models import Studio
from app.domains.core.users.models import StudioMembership, User


class StudioMembershipRepository(BaseTenantRepository[StudioMembership]):
    model = StudioMembership

    async def get_by_user_id(self, user_id: uuid.UUID) -> StudioMembership | None:
        stmt = self._base_select().where(StudioMembership.user_id == user_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_with_users(
        self, *, active_only: bool = False
    ) -> Sequence[tuple[StudioMembership, User]]:
        stmt = (
            sa.select(StudioMembership, User)
            .join(User, User.id == StudioMembership.user_id)
            .where(
                StudioMembership.studio_id == self.studio_id,
                User.deleted_at.is_(None),
            )
            .order_by(User.name.asc())
        )
        if active_only:
            stmt = stmt.where(StudioMembership.is_active.is_(True), User.is_active.is_(True))
        result = await self.session.execute(stmt)
        return result.all()

    async def count_active_owners(self, *, exclude_membership_id: uuid.UUID | None = None) -> int:
        stmt = sa.select(sa.func.count(StudioMembership.id)).where(
            StudioMembership.studio_id == self.studio_id,
            StudioMembership.role == StudioRole.OWNER,
            StudioMembership.is_active.is_(True),
        )
        if exclude_membership_id is not None:
            stmt = stmt.where(StudioMembership.id != exclude_membership_id)
        return int((await self.session.execute(stmt)).scalar_one())


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    normalized = email.strip().lower()
    with bypass_tenant_filter():
        stmt = sa.select(User).where(User.email == normalized, User.deleted_at.is_(None))
        return (await session.execute(stmt)).scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    with bypass_tenant_filter():
        stmt = sa.select(User).where(User.id == user_id, User.deleted_at.is_(None))
        return (await session.execute(stmt)).scalar_one_or_none()


async def list_user_active_memberships_with_studios(
    session: AsyncSession, user_id: uuid.UUID
) -> Sequence[tuple[StudioMembership, Studio]]:
    with bypass_tenant_filter():
        stmt = (
            sa.select(StudioMembership, Studio)
            .join(Studio, Studio.id == StudioMembership.studio_id)
            .where(
                StudioMembership.user_id == user_id,
                StudioMembership.is_active.is_(True),
            )
            .order_by(Studio.name.asc())
        )
        return (await session.execute(stmt)).all()
