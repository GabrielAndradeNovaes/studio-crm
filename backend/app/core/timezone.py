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


def studio_date_range_to_utc(
    start_date: date, end_date: date, tz_name: str = "America/Sao_Paulo"
) -> tuple[datetime, datetime]:
    """Converte datas locais do estúdio (00:00:00 até 23:59:59.999999) para UTC."""
    tz = ZoneInfo(validate_timezone_name(tz_name))
    local_start = datetime.combine(start_date, time.min, tzinfo=tz)
    local_end = datetime.combine(end_date, time.max, tzinfo=tz)
    return local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc)
