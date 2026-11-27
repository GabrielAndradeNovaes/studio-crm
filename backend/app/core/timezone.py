from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.exceptions import DomainValidationError


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def validate_timezone_name(tz_name: str) -> str:
    cleaned = tz_name.strip()
    try:
        ZoneInfo(cleaned)
    except (ZoneInfoNotFoundError, KeyError, ValueError) as exc:
        raise DomainValidationError(
            detail=f"Fuso horário inválido: '{tz_name}'. Use um identificador IANA como 'America/Sao_Paulo'.",
            code="INVALID_TIMEZONE",
        ) from exc
    return cleaned


def today_in_studio_timezone(tz_name: str = "America/Sao_Paulo") -> date:
    tz = ZoneInfo(validate_timezone_name(tz_name))
    return datetime.now(tz).date()


def timestamp_to_studio_date(
    dt: datetime, tz_name: str = "America/Sao_Paulo"
) -> date:
    """Converte um instante UTC/aware para a data de competência civil no fuso do estúdio."""
    tz = ZoneInfo(validate_timezone_name(tz_name))
    aware = dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    return aware.astimezone(tz).date()


def calculate_age_in_timezone(
    birth_date: date, tz_name: str = "America/Sao_Paulo"
) -> tuple[int, bool]:
    """Retorna `(age, is_minor)` calculados na data civil atual do fuso do estúdio."""
    today_local = today_in_studio_timezone(tz_name)
    if birth_date > today_local:
        raise DomainValidationError(
            detail="A data de nascimento não pode ser uma data futura.",
            code="INVALID_BIRTH_DATE",
        )
    age = (
        today_local.year
        - birth_date.year
        - ((today_local.month, today_local.day) < (birth_date.month, birth_date.day))
    )
    return age, age < 18


def studio_date_range_to_utc(
    start_date: date, end_date: date, tz_name: str = "America/Sao_Paulo"
) -> tuple[datetime, datetime]:
    """Converte datas locais do estúdio (00:00:00 até 23:59:59.999999) para UTC."""
    tz = ZoneInfo(validate_timezone_name(tz_name))
    local_start = datetime.combine(start_date, time.min, tzinfo=tz)
    local_end = datetime.combine(end_date, time.max, tzinfo=tz)
    return local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc)
