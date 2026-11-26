from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenancy import BaseTenantRepository, bypass_tenant_filter
from app.domains.core.studios.models import PaymentMethodConfig, Studio


class PaymentMethodConfigRepository(BaseTenantRepository[PaymentMethodConfig]):
    model = PaymentMethodConfig

    async def list_ordered(self) -> Sequence[PaymentMethodConfig]:
        stmt = self._base_select().order_by(PaymentMethodConfig.method.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()


async def get_studio_by_id(session: AsyncSession, studio_id: uuid.UUID) -> Studio | None:
    with bypass_tenant_filter():
        stmt = sa.select(Studio).where(Studio.id == studio_id)
        return (await session.execute(stmt)).scalar_one_or_none()


async def get_studio_by_slug(session: AsyncSession, slug: str) -> Studio | None:
    with bypass_tenant_filter():
        stmt = sa.select(Studio).where(Studio.slug == slug.lower().strip())
        return (await session.execute(stmt)).scalar_one_or_none()


async def list_all_studios(session: AsyncSession) -> Sequence[Studio]:
    with bypass_tenant_filter():
        stmt = sa.select(Studio).order_by(Studio.created_at.desc())
        return (await session.execute(stmt)).scalars().all()
