from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import Request
from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, JSONVariant, UUIDPrimaryKeyMixin
from app.core.enums import AuditAction
from app.core.rate_limit import get_client_ip
from app.core.timezone import utcnow


class AuditLog(UUIDPrimaryKeyMixin, Base):
    """
    Trilha de auditoria imutável (append-only) para conformidade LGPD e governança.
    `studio_id` é NULLABLE para permitir auditoria de eventos globais de SuperAdmin.
    `actor_user_id` é NULLABLE para suportar futuros fluxos de autoatendimento público.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_studio_created", "studio_id", "created_at"),
        Index("ix_audit_logs_entity", "studio_id", "entity_name", "entity_id"),
    )

    studio_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("studios.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    entity_name: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="audit_action_enum", native_enum=False),
        nullable=False,
    )
    metadata_diff: Mapped[dict[str, Any] | None] = mapped_column(JSONVariant, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


async def record_audit_log(
    session: AsyncSession,
    *,
    studio_id: uuid.UUID | None,
    actor_user_id: uuid.UUID | None,
    entity_name: str,
    entity_id: uuid.UUID | str,
    action: AuditAction,
    metadata_diff: dict[str, Any] | None = None,
    request: Request | None = None,
) -> AuditLog:
    ip_addr = get_client_ip(request) if request else None
    user_agent = request.headers.get("user-agent", "")[:512] if request else None
    entry = AuditLog(
        studio_id=studio_id,
        actor_user_id=actor_user_id,
        entity_name=entity_name,
        entity_id=str(entity_id),
        action=action,
        metadata_diff=metadata_diff,
        ip_address=ip_addr,
        user_agent=user_agent or None,
    )
    session.add(entry)
    await session.flush()
    return entry
