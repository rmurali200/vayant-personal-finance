// Money and date formatting per the design system: true minus before the symbol, tabular figures in CSS.
const MINUS = "−";
// en-US prints CAD as "CA$", keeping it distinct from USD; en-IN groups rupees in lakhs and crores.
const locale = (currency: string) => (currency === "INR" ? "en-IN" : "en-US");

export interface MoneyOpts {
  currency?: string;
  decimals?: number;
  signed?: boolean;
}

export function formatMoney(value: number, { currency = "USD", decimals = 2, signed = false }: MoneyOpts = {}) {
  const n = Number(value) || 0;
  const s = new Intl.NumberFormat(locale(currency), {
    style: "currency", currency, minimumFractionDigits: decimals, maximumFractionDigits: decimals,
  }).format(Math.abs(n));
  return (n < 0 && Math.abs(n) >= 0.5 * 10 ** -decimals ? MINUS : signed && n > 0 ? "+" : "") + s;
}

/** Axis ticks and tight spaces: $676K, ₹6.4Cr. */
export function formatCompact(value: number, currency = "USD") {
  const s = new Intl.NumberFormat(locale(currency), {
    style: "currency", currency, notation: "compact", maximumFractionDigits: 1,
  }).format(Math.abs(value));
  return (value < 0 ? MINUS : "") + s;
}

export const formatPercent = (v: number, digits = 0) => `${v < 0 ? MINUS : ""}${Math.abs(v * 100).toFixed(digits)}%`;

const parse = (iso: string) => new Date(iso + "T00:00:00");
export const formatDay = (iso: string) => parse(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
export const formatMonth = (iso: string, style: "short" | "long" = "short") =>
  parse(iso).toLocaleDateString("en-US", style === "long" ? { month: "long", year: "numeric" } : { month: "short" });

export function isoDate(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** First day of the month `offset` months from today (0 = this month). */
export function monthStart(offset = 0) {
  const d = new Date();
  return isoDate(new Date(d.getFullYear(), d.getMonth() + offset, 1));
}

export const today = () => isoDate(new Date());

export const sentence = (s: string) => (s.charAt(0).toUpperCase() + s.slice(1)).replace(/_/g, " ");

/** Last day of the month `offset` months from today. */
export function monthEnd(offset = 0) {
  const d = new Date();
  return isoDate(new Date(d.getFullYear(), d.getMonth() + offset + 1, 0));
}
