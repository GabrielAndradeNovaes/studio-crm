from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Generic, Sequence, TypeVar

import sqlalchemy as sa
from sqlalchemy import Select, event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria

from app.core.database import Base, SoftDeleteMixin, TenantModelMixin
from app.core.exceptions import NotFoundError
from app.core.timezone import utcnow

current_studio_id_ctx: ContextVar[uuid.UUID | None] = ContextVar(
    "current_studio_id_ctx", default=None
)
bypass_tenant_filter_ctx: ContextVar[bool] = ContextVar(
    "bypass_tenant_filter_ctx", default=False
)


@contextmanager
def tenant_scope(studio_id: uuid.UUID | None) -> Iterator[None]:
    token = current_studio_id_ctx.set(studio_id)
    try:
        yield
    finally:
        current_studio_id_ctx.reset(token)


@contextmanager
def bypass_tenant_filter() -> Iterator[None]:
    token = bypass_tenant_filter_ctx.set(True)
    try:
        yield
    finally:
        bypass_tenant_filter_ctx.reset(token)


@event.listens_for(Session, "do_orm_execute")
def _enforce_tenant_select_criteria(execute_state: ORMExecuteState) -> None:
    """
    Filtro global em profundidade para SELECTs ORM sobre modelos `TenantModelMixin`.
    Observação importante: `with_loader_criteria` aplica-se a SELECTs ORM; por isso,
    toda escrita/atualização/exclusão DEVE passar pelo `BaseTenantRepository`, que
    filtra explicitamente por `studio_id` em SELECT, INSERT, UPDATE e DELETE.
    """
    if bypass_tenant_filter_ctx.get():
        return
    studio_id = current_studio_id_ctx.get()
    if studio_id is None:
        return
    if (
        execute_state.is_select
        and not execute_state.is_column_load
        and not execute_state.is_relationship_load
    ):
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                TenantModelMixin,
                lambda cls: cls.studio_id == studio_id,
                include_aliases=True,
            )
        )


ModelT = TypeVar("ModelT", bound=Base)


class BaseTenantRepository(Generic[ModelT]):
    """
    Repositório Multi-Tenant estrito.
    Garante filtro explícito por `studio_id` em SELECT, INSERT, UPDATE, SOFT DELETE e DELETE,
    prevenindo qualquer vulnerabilidade IDOR mesmo em instruções SQLAlchemy Core diretas.
    """

    model: type[ModelT]

    def __init__(self, session: AsyncSession, studio_id: uuid.UUID) -> None:
        if not issubclass(self.model, TenantModelMixin):
            raise TypeError(
                f"{self.model.__name__} deve herdar de TenantModelMixin para usar BaseTenantRepository."
            )
        self.session = session
        self.studio_id = studio_id

    def _base_select(self, *, include_deleted: bool = False) -> Select[tuple[ModelT]]:
        stmt = sa.select(self.model).where(
            getattr(self.model, "studio_id") == self.studio_id
        )
        if not include_deleted and issubclass(self.model, SoftDeleteMixin):
            stmt = stmt.where(getattr(self.model, "deleted_at").is_(None))
        return stmt

    async def get_by_id(
        self, entity_id: uuid.UUID, *, include_deleted: bool = False
    ) -> ModelT | None:
        stmt = self._base_select(include_deleted=include_deleted).where(
            getattr(self.model, "id") == entity_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_or_404(
        self,
        entity_id: uuid.UUID,
        *,
        include_deleted: bool = False,
        detail: str = "Registro não encontrado.",
    ) -> ModelT:
        entity = await self.get_by_id(entity_id, include_deleted=include_deleted)
        if entity is None:
            raise NotFoundError(detail=detail)
        return entity

    async def list_all(
        self,
        *,
        include_deleted: bool = False,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[ModelT]:
        stmt = self._base_select(include_deleted=include_deleted).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def add(self, instance: ModelT) -> ModelT:
        # Força incondicionalmente o studio_id do contexto autenticado
        setattr(instance, "studio_id", self.studio_id)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def update_by_id(
        self,
        entity_id: uuid.UUID,
        values: dict[str, Any],
        *,
        include_deleted: bool = False,
    ) -> ModelT:
        safe_values = {k: v for k, v in values.items() if k not in {"id", "studio_id"}}
        if hasattr(self.model, "updated_at") and "updated_at" not in safe_values:
            safe_values["updated_at"] = utcnow()

        conditions = [
            getattr(self.model, "id") == entity_id,
            getattr(self.model, "studio_id") == self.studio_id,
        ]
        if not include_deleted and issubclass(self.model, SoftDeleteMixin):
            conditions.append(getattr(self.model, "deleted_at").is_(None))

        stmt = (
            sa.update(self.model)
            .where(*conditions)
            .values(**safe_values)
            .execution_options(synchronize_session="fetch")
        )
        result = await self.session.execute(stmt)
        if result.rowcount == 0:
            raise NotFoundError(detail="Registro não encontrado.")

        updated = await self.get_by_id(entity_id, include_deleted=True)
        if updated is None:
            raise NotFoundError(detail="Registro não encontrado.")
        return updated

    async def soft_delete_by_id(
        self,
        entity_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID | None = None,
    ) -> None:
        if not issubclass(self.model, SoftDeleteMixin):
            raise TypeError(f"{self.model.__name__} não suporta soft delete.")

        now = utcnow()
        values: dict[str, Any] = {"deleted_at": now}
        if hasattr(self.model, "updated_at"):
            values["updated_at"] = now
        if hasattr(self.model, "updated_by") and actor_user_id is not None:
            values["updated_by"] = actor_user_id

        stmt = (
            sa.update(self.model)
            .where(
                getattr(self.model, "id") == entity_id,
                getattr(self.model, "studio_id") == self.studio_id,
                getattr(self.model, "deleted_at").is_(None),
            )
            .values(**values)
            .execution_options(synchronize_session="fetch")
        )
        result = await self.session.execute(stmt)
        if result.rowcount == 0:
            raise NotFoundError(detail="Registro não encontrado.")

    async def hard_delete_by_id(self, entity_id: uuid.UUID) -> None:
        stmt = (
            sa.delete(self.model)
            .where(
                getattr(self.model, "id") == entity_id,
                getattr(self.model, "studio_id") == self.studio_id,
            )
            .execution_options(synchronize_session="fetch")
        )
        result = await self.session.execute(stmt)
        if result.rowcount == 0:
            raise NotFoundError(detail="Registro não encontrado.")
