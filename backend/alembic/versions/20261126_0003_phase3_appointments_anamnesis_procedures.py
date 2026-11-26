"""Phase 3: appointments, versioned anamnesis (templates, records, public_links) and piercing_procedures

Revision ID: 20261126_0003
Revises: 20261126_0002
Create Date: 2026-11-26 11:55:00
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

from app.domains.core.anamnesis.defaults import (
    DEFAULT_PIERCING_CONSENT_TEXT,
    DEFAULT_PIERCING_FIELDS_SCHEMA,
    DEFAULT_PIERCING_TEMPLATE_TITLE,
)

revision: str = "20261126_0003"
down_revision: Union[str, None] = "20261126_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONVariant = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "appointments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("studio_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("professional_id", sa.Uuid(), nullable=False),
        sa.Column("module", sa.String(length=30), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=25), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("deposit_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("deposit_payment_method", sa.String(length=20), nullable=True),
        sa.Column("deposit_status", sa.String(length=25), nullable=False),
        sa.Column("deposit_paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "end_at > start_at", name=op.f("ck_appointments_end_after_start")
        ),
        sa.CheckConstraint(
            "deposit_amount >= 0",
            name=op.f("ck_appointments_deposit_amount_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["studio_id"],
            ["studios.id"],
            name=op.f("fk_appointments_studio_id_studios"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            name=op.f("fk_appointments_client_id_clients"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["professional_id"],
            ["users.id"],
            name=op.f("fk_appointments_professional_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["piercing_services.id"],
            name=op.f("fk_appointments_service_id_piercing_services"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_appointments_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name=op.f("fk_appointments_updated_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_appointments")),
    )
    op.create_index(
        op.f("ix_appointments_studio_id"), "appointments", ["studio_id"], unique=False
    )
    op.create_index(
        "ix_appointments_studio_prof_start",
        "appointments",
        ["studio_id", "professional_id", "start_at"],
        unique=False,
    )
    op.create_index(
        "ix_appointments_studio_client",
        "appointments",
        ["studio_id", "client_id"],
        unique=False,
    )

    op.create_table(
        "anamnesis_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("studio_id", sa.Uuid(), nullable=False),
        sa.Column("module", sa.String(length=30), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("fields_schema", JSONVariant, nullable=False),
        sa.Column("consent_text", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["studio_id"],
            ["studios.id"],
            name=op.f("fk_anamnesis_templates_studio_id_studios"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_anamnesis_templates_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name=op.f("fk_anamnesis_templates_updated_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_anamnesis_templates")),
        sa.UniqueConstraint(
            "studio_id",
            "module",
            "version",
            name="uq_anamnesis_templates_studio_module_version",
        ),
    )
    op.create_index(
        op.f("ix_anamnesis_templates_studio_id"),
        "anamnesis_templates",
        ["studio_id"],
        unique=False,
    )
    op.create_index(
        "ix_anamnesis_templates_studio_mod_active",
        "anamnesis_templates",
        ["studio_id", "module", "is_active"],
        unique=False,
    )

    op.create_table(
        "anamnesis_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("studio_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("appointment_id", sa.Uuid(), nullable=True),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("template_version", sa.Integer(), nullable=False),
        sa.Column("module", sa.String(length=30), nullable=False),
        sa.Column("answers", JSONVariant, nullable=False),
        sa.Column("guardian_signed_name", sa.String(length=160), nullable=True),
        sa.Column("consent_accepted", sa.Boolean(), nullable=False),
        sa.Column("consent_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_ip", sa.String(length=64), nullable=True),
        sa.Column("consent_user_agent", sa.String(length=512), nullable=True),
        sa.Column("signature_payload", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["studio_id"],
            ["studios.id"],
            name=op.f("fk_anamnesis_records_studio_id_studios"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            name=op.f("fk_anamnesis_records_client_id_clients"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["appointment_id"],
            ["appointments.id"],
            name=op.f("fk_anamnesis_records_appointment_id_appointments"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["anamnesis_templates.id"],
            name=op.f("fk_anamnesis_records_template_id_anamnesis_templates"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_anamnesis_records_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name=op.f("fk_anamnesis_records_updated_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_anamnesis_records")),
    )
    op.create_index(
        op.f("ix_anamnesis_records_studio_id"),
        "anamnesis_records",
        ["studio_id"],
        unique=False,
    )
    op.create_index(
        "ix_anamnesis_records_studio_client",
        "anamnesis_records",
        ["studio_id", "client_id"],
        unique=False,
    )
    op.create_index(
        "ix_anamnesis_records_studio_appt",
        "anamnesis_records",
        ["studio_id", "appointment_id"],
        unique=False,
    )

    op.create_table(
        "anamnesis_public_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("studio_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("appointment_id", sa.Uuid(), nullable=True),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resulting_record_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["studio_id"],
            ["studios.id"],
            name=op.f("fk_anamnesis_public_links_studio_id_studios"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            name=op.f("fk_anamnesis_public_links_client_id_clients"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["appointment_id"],
            ["appointments.id"],
            name=op.f("fk_anamnesis_public_links_appointment_id_appointments"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["anamnesis_templates.id"],
            name=op.f("fk_anamnesis_public_links_template_id_anamnesis_templates"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["resulting_record_id"],
            ["anamnesis_records.id"],
            name=op.f("fk_anamnesis_public_links_resulting_record_id_anamnesis_records"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_anamnesis_public_links_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_anamnesis_public_links")),
    )
    op.create_index(
        op.f("ix_anamnesis_public_links_studio_id"),
        "anamnesis_public_links",
        ["studio_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_anamnesis_public_links_token_hash"),
        "anamnesis_public_links",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_anamnesis_public_links_studio_client",
        "anamnesis_public_links",
        ["studio_id", "client_id"],
        unique=False,
    )

    op.create_table(
        "piercing_procedures",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("studio_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("appointment_id", sa.Uuid(), nullable=True),
        sa.Column("sale_id", sa.Uuid(), nullable=True),
        sa.Column("professional_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("jewelry_product_id", sa.Uuid(), nullable=True),
        sa.Column("anatomical_site_detail", sa.String(length=160), nullable=False),
        sa.Column("sterilization_lot", sa.String(length=80), nullable=True),
        sa.Column("healing_notes", sa.Text(), nullable=True),
        sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("downsize_reminder_date", sa.Date(), nullable=True),
        sa.Column("downsize_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["studio_id"],
            ["studios.id"],
            name=op.f("fk_piercing_procedures_studio_id_studios"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            name=op.f("fk_piercing_procedures_client_id_clients"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["appointment_id"],
            ["appointments.id"],
            name=op.f("fk_piercing_procedures_appointment_id_appointments"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["professional_id"],
            ["users.id"],
            name=op.f("fk_piercing_procedures_professional_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["piercing_services.id"],
            name=op.f("fk_piercing_procedures_service_id_piercing_services"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["jewelry_product_id"],
            ["piercing_products.id"],
            name=op.f("fk_piercing_procedures_jewelry_product_id_piercing_products"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_piercing_procedures_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name=op.f("fk_piercing_procedures_updated_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_piercing_procedures")),
    )
    op.create_index(
        op.f("ix_piercing_procedures_studio_id"),
        "piercing_procedures",
        ["studio_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_piercing_procedures_professional_id"),
        "piercing_procedures",
        ["professional_id"],
        unique=False,
    )
    op.create_index(
        "ix_piercing_procedures_studio_client",
        "piercing_procedures",
        ["studio_id", "client_id"],
        unique=False,
    )
    op.create_index(
        "ix_piercing_procedures_studio_downsize",
        "piercing_procedures",
        ["studio_id", "downsize_completed_at", "downsize_reminder_date"],
        unique=False,
    )

    # Backfill automático do template padrão de Body Piercing em estúdios já existentes
    if not context.is_offline_mode():
        bind = op.get_bind()
        studios_table = sa.table("studios", sa.column("id", sa.Uuid()))
        templates_table = sa.table(
            "anamnesis_templates",
            sa.column("id", sa.Uuid()),
            sa.column("studio_id", sa.Uuid()),
            sa.column("module", sa.String()),
            sa.column("version", sa.Integer()),
            sa.column("title", sa.String()),
            sa.column("fields_schema", JSONVariant),
            sa.column("consent_text", sa.Text()),
            sa.column("is_active", sa.Boolean()),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
        )
        now = datetime.now(timezone.utc)
        existing_studios = bind.execute(sa.select(studios_table.c.id)).fetchall()
        for (studio_id,) in existing_studios:
            already = bind.execute(
                sa.select(templates_table.c.id).where(
                    templates_table.c.studio_id == studio_id,
                    templates_table.c.module == "piercing",
                )
            ).first()
            if already is None:
                bind.execute(
                    templates_table.insert().values(
                        id=uuid.uuid4(),
                        studio_id=studio_id,
                        module="piercing",
                        version=1,
                        title=DEFAULT_PIERCING_TEMPLATE_TITLE,
                        fields_schema=DEFAULT_PIERCING_FIELDS_SCHEMA,
                        consent_text=DEFAULT_PIERCING_CONSENT_TEXT,
                        is_active=True,
                        created_at=now,
                        updated_at=now,
                    )
                )


def downgrade() -> None:
    op.drop_table("piercing_procedures")
    op.drop_table("anamnesis_public_links")
    op.drop_table("anamnesis_records")
    op.drop_table("anamnesis_templates")
    op.drop_table("appointments")
