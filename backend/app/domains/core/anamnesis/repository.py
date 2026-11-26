from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from app.core.tenancy import BaseTenantRepository
from app.domains.core.anamnesis.models import (
    AnamnesisPublicLink,
    AnamnesisRecord,
    AnamnesisTemplate,
)


class AnamnesisTemplateRepository(BaseTenantRepository[AnamnesisTemplate]):
    model = AnamnesisTemplate

    async def get_active_for_module(self, module: str) -> AnamnesisTemplate | None:
        stmt = (
            self._base_select()
            .where(
                AnamnesisTemplate.module == module,
                AnamnesisTemplate.is_active.is_(True),
            )
            .order_by(AnamnesisTemplate.version.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_by_module(
        self, module: str | None = None
    ) -> Sequence[AnamnesisTemplate]:
        stmt = self._base_select()
        if module:
            stmt = stmt.where(AnamnesisTemplate.module == module)
        stmt = stmt.order_by(
            AnamnesisTemplate.module.asc(), AnamnesisTemplate.version.desc()
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def get_max_version(self, module: str) -> int:
        stmt = sa.select(sa.func.coalesce(sa.func.max(AnamnesisTemplate.version), 0)).where(
            AnamnesisTemplate.studio_id == self.studio_id,
            AnamnesisTemplate.module == module,
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def is_used_by_records(self, template_id: uuid.UUID) -> bool:
        stmt = (
            sa.select(AnamnesisRecord.id)
            .where(
                AnamnesisRecord.studio_id == self.studio_id,
                AnamnesisRecord.template_id == template_id,
            )
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None


class AnamnesisRecordRepository(BaseTenantRepository[AnamnesisRecord]):
    model = AnamnesisRecord

    async def list_filtered(
        self,
        *,
        client_id: uuid.UUID | None = None,
        appointment_id: uuid.UUID | None = None,
        limit: int = 100,
    ) -> Sequence[AnamnesisRecord]:
        stmt = self._base_select()
        if client_id is not None:
            stmt = stmt.where(AnamnesisRecord.client_id == client_id)
        if appointment_id is not None:
            stmt = stmt.where(AnamnesisRecord.appointment_id == appointment_id)
        stmt = stmt.order_by(AnamnesisRecord.created_at.desc()).limit(limit)
        return (await self.session.execute(stmt)).scalars().all()


class AnamnesisPublicLinkRepository(BaseTenantRepository[AnamnesisPublicLink]):
    model = AnamnesisPublicLink
