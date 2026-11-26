from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from app.core.tenancy import BaseTenantRepository
from app.domains.piercing.services.models import PiercingService


class PiercingServiceRepository(BaseTenantRepository[PiercingService]):
    model = PiercingService

    async def search(
        self,
        *,
        q: str | None = None,
        anatomical_site: str | None = None,
        active_only: bool = False,
    ) -> Sequence[PiercingService]:
        stmt = self._base_select(include_deleted=False)
        if q and q.strip():
            term = q.strip()
            stmt = stmt.where(
                sa.or_(
                    PiercingService.name.ilike(f"%{term}%"),
                    PiercingService.anatomical_site.ilike(f"%{term}%"),
                )
            )
        if anatomical_site and anatomical_site.strip():
            stmt = stmt.where(
                PiercingService.anatomical_site.ilike(anatomical_site.strip())
            )
        if active_only:
            stmt = stmt.where(PiercingService.is_active.is_(True))

        stmt = stmt.order_by(PiercingService.name.asc())
        return (await self.session.execute(stmt)).scalars().all()
