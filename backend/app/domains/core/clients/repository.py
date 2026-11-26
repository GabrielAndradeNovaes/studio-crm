from __future__ import annotations

import re
import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from app.core.enums import LeadSource
from app.core.tenancy import BaseTenantRepository
from app.domains.core.clients.models import Client

NON_DIGITS_RE = re.compile(r"\D+")


class ClientRepository(BaseTenantRepository[Client]):
    model = Client

    async def get_active_by_whatsapp(
        self, whatsapp_digits: str, *, exclude_client_id: uuid.UUID | None = None
    ) -> Client | None:
        stmt = self._base_select(include_deleted=False).where(
            Client.whatsapp == whatsapp_digits
        )
        if exclude_client_id is not None:
            stmt = stmt.where(Client.id != exclude_client_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def search(
        self,
        *,
        q: str | None = None,
        lead_source: LeadSource | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[Client]:
        stmt = self._base_select(include_deleted=False)

        if q and q.strip():
            term = q.strip()
            digits = NON_DIGITS_RE.sub("", term)
            clauses = [
                Client.full_name.ilike(f"%{term}%"),
                Client.email.ilike(f"%{term}%"),
            ]
            if digits:
                clauses.append(Client.whatsapp.like(f"%{digits}%"))
            stmt = stmt.where(sa.or_(*clauses))

        if lead_source is not None:
            stmt = stmt.where(Client.lead_source == lead_source)

        stmt = stmt.order_by(Client.full_name.asc()).offset(offset).limit(limit)
        return (await self.session.execute(stmt)).scalars().all()
