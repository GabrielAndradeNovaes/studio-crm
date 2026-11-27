from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa

from app.core.enums import AppointmentStatus
from app.core.exceptions import NotFoundError
from app.core.tenancy import BaseTenantRepository
from app.domains.core.appointments.models import Appointment

NON_BLOCKING_STATUSES = (
    AppointmentStatus.CANCELADO,
    AppointmentStatus.FALTOU,
)


class AppointmentRepository(BaseTenantRepository[Appointment]):
    model = Appointment

    async def get_by_id_for_update_or_404(
        self, appointment_id: uuid.UUID
    ) -> Appointment:
        stmt = (
            self._base_select(include_deleted=False)
            .where(Appointment.id == appointment_id)
            .with_for_update()
        )
        appt = (await self.session.execute(stmt)).scalar_one_or_none()
        if appt is None:
            raise NotFoundError(detail="Agendamento não encontrado.")
        return appt

    async def has_overlapping_appointment(
        self,
        *,
        professional_id: uuid.UUID,
        start_at: datetime,
        end_at: datetime,
        exclude_appointment_id: uuid.UUID | None = None,
    ) -> bool:
        stmt = self._base_select(include_deleted=False).where(
            Appointment.professional_id == professional_id,
            Appointment.status.notin_(NON_BLOCKING_STATUSES),
            Appointment.start_at < end_at,
            Appointment.end_at > start_at,
        )
        if exclude_appointment_id is not None:
            stmt = stmt.where(Appointment.id != exclude_appointment_id)

        existing = (await self.session.execute(stmt.limit(1))).scalar_one_or_none()
        return existing is not None

    async def search(
        self,
        *,
        professional_id: uuid.UUID | None = None,
        client_id: uuid.UUID | None = None,
        status: AppointmentStatus | None = None,
        start_from: datetime | None = None,
        start_to: datetime | None = None,
        limit: int = 300,
    ) -> Sequence[Appointment]:
        stmt = self._base_select(include_deleted=False)

        if professional_id is not None:
            stmt = stmt.where(Appointment.professional_id == professional_id)
        if client_id is not None:
            stmt = stmt.where(Appointment.client_id == client_id)
        if status is not None:
            stmt = stmt.where(Appointment.status == status)
        if start_from is not None:
            stmt = stmt.where(Appointment.end_at >= start_from)
        if start_to is not None:
            stmt = stmt.where(Appointment.start_at <= start_to)

        stmt = stmt.order_by(Appointment.start_at.asc()).limit(limit)
        return (await self.session.execute(stmt)).scalars().all()
