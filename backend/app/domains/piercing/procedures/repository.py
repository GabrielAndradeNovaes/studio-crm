from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date

from app.core.tenancy import BaseTenantRepository
from app.domains.piercing.procedures.models import PiercingProcedure


class PiercingProcedureRepository(BaseTenantRepository[PiercingProcedure]):
    model = PiercingProcedure

    async def list_filtered(
        self,
        *,
        client_id: uuid.UUID | None = None,
        professional_id: uuid.UUID | None = None,
        appointment_id: uuid.UUID | None = None,
        limit: int = 200,
    ) -> Sequence[PiercingProcedure]:
        stmt = self._base_select()
        if client_id is not None:
            stmt = stmt.where(PiercingProcedure.client_id == client_id)
        if professional_id is not None:
            stmt = stmt.where(PiercingProcedure.professional_id == professional_id)
        if appointment_id is not None:
            stmt = stmt.where(PiercingProcedure.appointment_id == appointment_id)
        stmt = stmt.order_by(PiercingProcedure.performed_at.desc()).limit(limit)
        return (await self.session.execute(stmt)).scalars().all()

    async def list_pending_downsizes(
        self,
        *,
        professional_id: uuid.UUID | None = None,
        due_before_or_on: date | None = None,
        due_from: date | None = None,
        strictly_before: date | None = None,
        limit: int = 200,
    ) -> Sequence[PiercingProcedure]:
        stmt = self._base_select().where(
            PiercingProcedure.downsize_completed_at.is_(None),
            PiercingProcedure.downsize_reminder_date.is_not(None),
        )
        if professional_id is not None:
            stmt = stmt.where(PiercingProcedure.professional_id == professional_id)
        if strictly_before is not None:
            stmt = stmt.where(PiercingProcedure.downsize_reminder_date < strictly_before)
        if due_from is not None:
            stmt = stmt.where(PiercingProcedure.downsize_reminder_date >= due_from)
        if due_before_or_on is not None:
            stmt = stmt.where(
                PiercingProcedure.downsize_reminder_date <= due_before_or_on
            )

        stmt = stmt.order_by(PiercingProcedure.downsize_reminder_date.asc()).limit(limit)
        return (await self.session.execute(stmt)).scalars().all()
