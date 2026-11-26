import { Temporal as TemporalPolyfill } from "temporal-polyfill";

type TemporalNamespace = typeof TemporalPolyfill;

function getTemporal(): TemporalNamespace {
  const g = globalThis as unknown as { Temporal?: TemporalNamespace };
  if (!g.Temporal) {
    g.Temporal = TemporalPolyfill;
  }
  return g.Temporal;
}

/**
 * Formata uma data civil ISO (YYYY-MM-DD) sem conversão para Date/UTC,
 * evitando o deslocamento de -1 dia em fusos a oeste de UTC (ex.: Brasil).
 */
export function formatPlainCalendarDate(isoDate: string): string {
  try {
    const T = getTemporal();
    const plain = T.PlainDate.from(isoDate);
    return plain.toLocaleString("pt-BR");
  } catch {
    return isoDate;
  }
}

export function todayIsoInTimezone(studioTimezone = "America/Sao_Paulo"): string {
  const T = getTemporal();
  return T.Now.zonedDateTimeISO(studioTimezone).toPlainDate().toString();
}

export function shiftPlainDateIso(isoDate: string, days: number): string {
  const T = getTemporal();
  return T.PlainDate.from(isoDate).add({ days }).toString();
}

/**
 * Converte data civil + hora local do estúdio para instante UTC ISO 8601
 * usando `Temporal.ZonedDateTime.from` com `disambiguation: 'compatible'`.
 */
export function studioLocalDateTimeToUtcIso(
  isoDate: string,
  hhmm: string,
  studioTimezone = "America/Sao_Paulo"
): string {
  const T = getTemporal();
  const zdt = T.ZonedDateTime.from(`${isoDate}T${hhmm}[${studioTimezone}]`, {
    disambiguation: "compatible",
  });
  return zdt.toInstant().toString();
}

/**
 * Formata um timestamp UTC exatamente no fuso horário IANA do estúdio.
 */
export function formatUtcInStudioTimezone(
  utcIso: string,
  studioTimezone = "America/Sao_Paulo"
): { dateLabel: string; timeLabel: string; isoDate: string; hhmm: string } {
  const T = getTemporal();
  const zdt = T.Instant.from(utcIso).toZonedDateTimeISO(studioTimezone);
  const dateLabel = zdt.toPlainDate().toLocaleString("pt-BR");
  const timeLabel = zdt.toLocaleString("pt-BR", {
    hour: "numeric",
    minute: "2-digit",
  });
  const hh = String(zdt.hour).padStart(2, "0");
  const mm = String(zdt.minute).padStart(2, "0");
  return {
    dateLabel,
    timeLabel,
    isoDate: zdt.toPlainDate().toString(),
    hhmm: `${hh}:${mm}`,
  };
}

/**
 * Calcula idade civil exata e indicador de menoridade (< 18 anos) usando
 * o fuso horário IANA do estúdio (ex.: America/Sao_Paulo).
 */
export function computeAgeAndMinorInTimezone(
  isoBirthDate: string,
  studioTimezone = "America/Sao_Paulo"
): { age: number; isMinor: boolean } | null {
  if (!isoBirthDate || !/^\d{4}-\d{2}-\d{2}$/.test(isoBirthDate)) {
    return null;
  }
  try {
    const T = getTemporal();
    const birth = T.PlainDate.from(isoBirthDate);
    const today = T.Now.zonedDateTimeISO(studioTimezone).toPlainDate();
    if (T.PlainDate.compare(birth, today) > 0) {
      return null;
    }
    let age = today.year - birth.year;
    if (
      today.month < birth.month ||
      (today.month === birth.month && today.day < birth.day)
    ) {
      age -= 1;
    }
    return { age, isMinor: age < 18 };
  } catch {
    return null;
  }
}

export function formatCurrencyBRL(value: string | number): string {
  const num = typeof value === "string" ? Number(value) : value;
  if (Number.isNaN(num)) return "R$ 0,00";
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(num);
}

export function buildWhatsAppUrl(rawPhoneDigits: string, message: string): string {
  const clean = rawPhoneDigits.replace(/\D+/g, "");
  const e164 =
    clean.length === 10 || clean.length === 11 ? `55${clean}` : clean;
  return `https://wa.me/${e164}?text=${encodeURIComponent(message)}`;
}
