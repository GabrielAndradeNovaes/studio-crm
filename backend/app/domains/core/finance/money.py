from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0.00")
HUNDRED = Decimal("100")


def money(value: Decimal | int | str) -> Decimal:
    """Arredondamento contábil padrão ROUND_HALF_UP para 2 casas decimais."""
    if isinstance(value, float):
        raise TypeError("Proibido usar float em cálculos monetários; utilize Decimal.")
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def compute_payment_fee_and_net(
    *,
    gross_amount: Decimal,
    fee_percentage: Decimal,
    fixed_fee: Decimal,
) -> tuple[Decimal, Decimal]:
    gross = money(gross_amount)
    if gross <= ZERO:
        return ZERO, ZERO
    pct_fee = (gross * Decimal(fee_percentage)) / HUNDRED
    fee = money(pct_fee + Decimal(fixed_fee))
    net = money(gross - fee)
    return fee, net
