from __future__ import annotations

from app.core.audit import AuditLog
from app.core.database import Base
from app.domains.core.anamnesis.models import (
    AnamnesisPublicLink,
    AnamnesisRecord,
    AnamnesisTemplate,
)
from app.domains.core.appointments.models import Appointment
from app.domains.core.auth.models import RefreshToken
from app.domains.core.clients.models import Client
from app.domains.core.finance.models import (
    Commission,
    FinancialTransaction,
    Payment,
    Sale,
    SaleItem,
)
from app.domains.core.studios.models import PaymentMethodConfig, Studio
from app.domains.core.users.models import StudioMembership, User
from app.domains.piercing.inventory.models import InventoryMovement, PiercingProduct
from app.domains.piercing.procedures.models import PiercingProcedure
from app.domains.piercing.services.models import PiercingService

__all__ = [
    "Base",
    "Studio",
    "PaymentMethodConfig",
    "User",
    "StudioMembership",
    "RefreshToken",
    "AuditLog",
    "Client",
    "Appointment",
    "AnamnesisTemplate",
    "AnamnesisRecord",
    "AnamnesisPublicLink",
    "PiercingService",
    "PiercingProduct",
    "InventoryMovement",
    "PiercingProcedure",
    "Sale",
    "SaleItem",
    "Payment",
    "FinancialTransaction",
    "Commission",
]
