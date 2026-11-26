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
