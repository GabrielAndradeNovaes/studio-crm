from __future__ import annotations

import enum


class StudioRole(str, enum.Enum):
    OWNER = "OWNER"
    PROFESSIONAL = "PROFESSIONAL"
    RECEPTION = "RECEPTION"


class SubscriptionStatus(str, enum.Enum):
    TRIAL = "TRIAL"
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    SUSPENDED = "SUSPENDED"


class PaymentMethodCode(str, enum.Enum):
    PIX = "PIX"
    CREDIT_CARD = "CREDIT_CARD"
    DEBIT_CARD = "DEBIT_CARD"
    CASH = "CASH"


class LeadSource(str, enum.Enum):
    INSTAGRAM = "INSTAGRAM"
    INDICACAO = "INDICACAO"
    GOOGLE = "GOOGLE"
    PASSANTE = "PASSANTE"
    OUTRO = "OUTRO"


class PiercingItemType(str, enum.Enum):
    JEWELRY = "JEWELRY"
    AFTERCARE_PRODUCT = "AFTERCARE_PRODUCT"


class InventoryMovementType(str, enum.Enum):
    IN_PURCHASE = "IN_PURCHASE"
    OUT_SALE = "OUT_SALE"
    RETURN_REFUND = "RETURN_REFUND"
    ADJUSTMENT = "ADJUSTMENT"


class AuditAction(str, enum.Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    SOFT_DELETE = "SOFT_DELETE"
    READ_SENSITIVE = "READ_SENSITIVE"
    LOGIN = "LOGIN"
    SWITCH_STUDIO = "SWITCH_STUDIO"
    REFUND = "REFUND"
    INVENTORY_MOVEMENT = "INVENTORY_MOVEMENT"


SUPPORTED_MODULES: frozenset[str] = frozenset({"piercing", "tattoo"})
