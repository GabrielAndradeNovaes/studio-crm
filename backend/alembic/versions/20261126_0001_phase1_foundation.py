"""Phase 1 foundation: studios, global users, studio_memberships, payment_method_configs, refresh_tokens, audit_logs

Revision ID: 20261126_0001
Revises: None
Create Date: 2026-11-26 09:40:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261126_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONVariant = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "studios",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("document", sa.String(length=32), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("plan_tier", sa.String(length=40), nullable=False),
        sa.Column("enabled_modules", JSONVariant, nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("subscription_status", sa.String(length=20), nullable=False),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("commission_deducts_payment_fee", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_studios")),
    )
    op.create_index(op.f("ix_studios_slug"), "studios", ["slug"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_superadmin", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "studio_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("studio_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("commission_service_pct", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("commission_product_pct", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["studio_id"],
            ["studios.id"],
            name=op.f("fk_studio_memberships_studio_id_studios"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_studio_memberships_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_studio_memberships")),
        sa.UniqueConstraint(
            "studio_id", "user_id", name="uq_studio_memberships_studio_user"
        ),
    )
    op.create_index(
        op.f("ix_studio_memberships_studio_id"),
        "studio_memberships",
        ["studio_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_studio_memberships_user_id"),
        "studio_memberships",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "payment_method_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("studio_id", sa.Uuid(), nullable=False),
        sa.Column("method", sa.String(length=20), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("fee_percentage", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("fixed_fee", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["studio_id"],
            ["studios.id"],
            name=op.f("fk_payment_method_configs_studio_id_studios"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_method_configs")),
        sa.UniqueConstraint(
            "studio_id", "method", name="uq_payment_method_configs_studio_method"
        ),
    )
    op.create_index(
        op.f("ix_payment_method_configs_studio_id"),
        "payment_method_configs",
        ["studio_id"],
        unique=False,
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("studio_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["studio_id"],
            ["studios.id"],
            name=op.f("fk_refresh_tokens_studio_id_studios"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_refresh_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
    )
    op.create_index(
        op.f("ix_refresh_tokens_family_id"), "refresh_tokens", ["family_id"], unique=False
    )
    op.create_index(
        op.f("ix_refresh_tokens_studio_id"), "refresh_tokens", ["studio_id"], unique=False
    )
    op.create_index(
        op.f("ix_refresh_tokens_token_hash"), "refresh_tokens", ["token_hash"], unique=True
    )
    op.create_index(
        op.f("ix_refresh_tokens_user_id"), "refresh_tokens", ["user_id"], unique=False
    )
    op.create_index(
        "ix_refresh_tokens_user_family",
        "refresh_tokens",
        ["user_id", "family_id"],
        unique=False,
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("studio_id", sa.Uuid(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("entity_name", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("metadata_diff", JSONVariant, nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_audit_logs_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["studio_id"],
            ["studios.id"],
            name=op.f("fk_audit_logs_studio_id_studios"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index(
        op.f("ix_audit_logs_actor_user_id"), "audit_logs", ["actor_user_id"], unique=False
    )
    op.create_index(
        op.f("ix_audit_logs_studio_id"), "audit_logs", ["studio_id"], unique=False
    )
    op.create_index(
        "ix_audit_logs_studio_created",
        "audit_logs",
        ["studio_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_audit_logs_entity",
        "audit_logs",
        ["studio_id", "entity_name", "entity_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("refresh_tokens")
    op.drop_table("payment_method_configs")
    op.drop_table("studio_memberships")
    op.drop_table("users")
    op.drop_table("studios")
