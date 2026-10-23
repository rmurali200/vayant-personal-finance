import { useState } from "react";
import { CURRENCIES } from "./settings";

const NAMES: Record<string, string> = { USD: "US dollar", CAD: "Canadian dollar", INR: "Indian rupee" };
export const currencyName = (c: string) => NAMES[c] ?? c;

const rank = (c: string) => { const i = (CURRENCIES as readonly string[]).indexOf(c); return i < 0 ? CURRENCIES.length : i; };

/** Fixed order (USD, CAD, INR, then others A–Z) so sections never reshuffle by size. */
export const sortCurrencies = (list: Iterable<string>) =>
  [...new Set(list)].sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));

export function groupByCurrency<T>(items: T[], currency: (t: T) => string): [string, T[]][] {
  const groups = Map.groupBy(items, currency);
  return sortCurrencies(groups.keys()).map((c) => [c, groups.get(c)!]);
}

/** The selected currency tab: the user's pick while it has data, else `preferred`, else the first available. */
export function useCurrencyTab(available: string[], preferred: string) {
  const [chosen, setChosen] = useState<string | null>(null);
  const value = chosen && available.includes(chosen) ? chosen
    : available.length === 0 || available.includes(preferred) ? preferred : sortCurrencies(available)[0];
  return [value, setChosen] as const;
}
