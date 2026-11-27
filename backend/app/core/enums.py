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


class AppointmentStatus(str, enum.Enum):
    AGENDADO = "AGENDADO"
    CONFIRMADO = "CONFIRMADO"
    EM_ATENDIMENTO = "EM_ATENDIMENTO"
    CONCLUIDO = "CONCLUIDO"
    CANCELADO = "CANCELADO"
    FALTOU = "FALTOU"


class DepositStatus(str, enum.Enum):
    NONE = "NONE"
    PAID = "PAID"
    APPLIED_TO_SALE = "APPLIED_TO_SALE"
    REFUNDED = "REFUNDED"
    FORFEITED = "FORFEITED"


class SaleStatus(str, enum.Enum):
    COMPLETED = "COMPLETED"
    REFUNDED = "REFUNDED"


class SaleItemKind(str, enum.Enum):
    PIERCING_SERVICE = "PIERCING_SERVICE"
    PIERCING_PRODUCT = "PIERCING_PRODUCT"
    TATTOO_SESSION = "TATTOO_SESSION"


class CommissionStatus(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    REVERSED = "REVERSED"


class FinancialTransactionType(str, enum.Enum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"
    REVERSAL = "REVERSAL"


class FinancialTransactionCategory(str, enum.Enum):
    SALE_PAYMENT = "SALE_PAYMENT"
    APPOINTMENT_DEPOSIT = "APPOINTMENT_DEPOSIT"
    FIXED_EXPENSE = "FIXED_EXPENSE"
    VARIABLE_EXPENSE = "VARIABLE_EXPENSE"
    INVENTORY_PURCHASE = "INVENTORY_PURCHASE"
    COMMISSION_PAYOUT = "COMMISSION_PAYOUT"
    REFUND_OUTFLOW = "REFUND_OUTFLOW"
    OTHER_INCOME = "OTHER_INCOME"


class CashFlowDirection(str, enum.Enum):
    INFLOW = "INFLOW"
    OUTFLOW = "OUTFLOW"


class AuditAction(str, enum.Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    SOFT_DELETE = "SOFT_DELETE"
    READ_SENSITIVE = "READ_SENSITIVE"
    LOGIN = "LOGIN"
    SWITCH_STUDIO = "SWITCH_STUDIO"
    REFUND = "REFUND"
    INVENTORY_MOVEMENT = "INVENTORY_MOVEMENT"
    DEPOSIT_RECEIVED = "DEPOSIT_RECEIVED"
    DEPOSIT_REFUNDED = "DEPOSIT_REFUNDED"
    COMMISSION_PAYOUT = "COMMISSION_PAYOUT"


SUPPORTED_MODULES: frozenset[str] = frozenset({"piercing", "tattoo"})
