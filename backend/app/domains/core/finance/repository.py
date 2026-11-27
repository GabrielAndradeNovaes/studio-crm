from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date

import sqlalchemy as sa

from app.core.enums import (
    CommissionStatus,
    FinancialTransactionCategory,
    FinancialTransactionType,
    SaleStatus,
)
from app.core.exceptions import NotFoundError
from app.core.tenancy import BaseTenantRepository
from app.domains.core.finance.models import (
    Commission,
    FinancialTransaction,
    Payment,
    Sale,
    SaleItem,
)


class SaleRepository(BaseTenantRepository[Sale]):
    model = Sale

    async def get_by_id_for_update_or_404(self, sale_id: uuid.UUID) -> Sale:
        stmt = (
            self._base_select()
            .where(Sale.id == sale_id)
            .with_for_update()
        )
        sale = (await self.session.execute(stmt)).scalar_one_or_none()
        if sale is None:
            raise NotFoundError(detail="Venda não encontrada.")
        return sale

    async def list_filtered(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        status: SaleStatus | None = None,
        client_id: uuid.UUID | None = None,
        limit: int = 200,
    ) -> Sequence[Sale]:
        stmt = self._base_select()
        if date_from is not None:
            stmt = stmt.where(Sale.competence_date >= date_from)
        if date_to is not None:
            stmt = stmt.where(Sale.competence_date <= date_to)
        if status is not None:
            stmt = stmt.where(Sale.status == status)
        if client_id is not None:
            stmt = stmt.where(Sale.client_id == client_id)
        stmt = stmt.order_by(Sale.created_at.desc()).limit(limit)
        return (await self.session.execute(stmt)).scalars().all()


class SaleItemRepository(BaseTenantRepository[SaleItem]):
    model = SaleItem

    async def list_by_sale_ids(
        self, sale_ids: Sequence[uuid.UUID]
    ) -> Sequence[SaleItem]:
        if not sale_ids:
            return []
        stmt = self._base_select().where(SaleItem.sale_id.in_(sale_ids))
        return (await self.session.execute(stmt)).scalars().all()


class PaymentRepository(BaseTenantRepository[Payment]):
    model = Payment

    async def get_deposit_payment_for_appointment(
        self, appointment_id: uuid.UUID
    ) -> Payment | None:
        stmt = (
            self._base_select()
            .where(
                Payment.appointment_id == appointment_id,
                Payment.is_deposit.is_(True),
            )
            .order_by(Payment.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_by_sale_ids(
        self, sale_ids: Sequence[uuid.UUID]
    ) -> Sequence[Payment]:
        if not sale_ids:
            return []
        stmt = self._base_select().where(Payment.sale_id.in_(sale_ids))
        return (await self.session.execute(stmt)).scalars().all()


class FinancialTransactionRepository(BaseTenantRepository[FinancialTransaction]):
    model = FinancialTransaction

    async def get_by_id_for_update_or_404(
        self, tx_id: uuid.UUID
    ) -> FinancialTransaction:
        stmt = (
            self._base_select()
            .where(FinancialTransaction.id == tx_id)
            .with_for_update()
        )
        tx = (await self.session.execute(stmt)).scalar_one_or_none()
        if tx is None:
            raise NotFoundError(detail="Lançamento financeiro não encontrado.")
        return tx

    async def has_reversal(self, tx_id: uuid.UUID) -> bool:
        stmt = (
            sa.select(FinancialTransaction.id)
            .where(
                FinancialTransaction.studio_id == self.studio_id,
                FinancialTransaction.reversed_transaction_id == tx_id,
            )
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None

    async def list_filtered(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        tx_type: FinancialTransactionType | None = None,
        category: FinancialTransactionCategory | None = None,
        offset: int = 0,
        limit: int = 200,
    ) -> Sequence[FinancialTransaction]:
        stmt = self._base_select()
        if date_from is not None:
            stmt = stmt.where(FinancialTransaction.competence_date >= date_from)
        if date_to is not None:
            stmt = stmt.where(FinancialTransaction.competence_date <= date_to)
        if tx_type is not None:
            stmt = stmt.where(FinancialTransaction.type == tx_type)
        if category is not None:
            stmt = stmt.where(FinancialTransaction.category == category)
        stmt = (
            stmt.order_by(
                FinancialTransaction.competence_date.desc(),
                FinancialTransaction.created_at.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
        return (await self.session.execute(stmt)).scalars().all()


class CommissionRepository(BaseTenantRepository[Commission]):
    model = Commission

    async def list_by_sale_for_update(
        self, sale_id: uuid.UUID
    ) -> Sequence[Commission]:
        stmt = (
            self._base_select()
            .where(Commission.sale_id == sale_id)
            .with_for_update()
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def list_by_ids_for_update(
        self, commission_ids: Sequence[uuid.UUID]
    ) -> Sequence[Commission]:
        if not commission_ids:
            return []
        stmt = (
            self._base_select()
            .where(Commission.id.in_(commission_ids))
            .with_for_update()
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def list_filtered(
        self,
        *,
        professional_id: uuid.UUID | None = None,
        status: CommissionStatus | None = None,
        sale_ids: Sequence[uuid.UUID] | None = None,
        limit: int = 300,
    ) -> Sequence[Commission]:
        stmt = self._base_select()
        if professional_id is not None:
            stmt = stmt.where(Commission.professional_id == professional_id)
        if status is not None:
            stmt = stmt.where(Commission.status == status)
        if sale_ids is not None:
            if len(sale_ids) == 0:
                return []
            stmt = stmt.where(Commission.sale_id.in_(sale_ids))
        stmt = stmt.order_by(Commission.created_at.desc()).limit(limit)
        return (await self.session.execute(stmt)).scalars().all()
