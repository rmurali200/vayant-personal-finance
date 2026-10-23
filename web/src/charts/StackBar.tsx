import { formatMoney, formatPercent } from "../lib/format";

export interface Slice { key: string; label: string; value: number; color: string }

/** Part-to-whole as one horizontal bar; slices separated by a 2px surface gap. The caller lists the values. */
export function StackBar({ slices, currency, label }: { slices: Slice[]; currency: string; label: string }) {
  const total = slices.reduce((s, x) => s + x.value, 0) || 1;
  return (
    <div className="stackbar" role="img" aria-label={label}>
      {slices.filter((s) => s.value > 0).map((s) => (
        <span key={s.key} style={{ flexGrow: s.value, background: s.color }}
          title={`${s.label}: ${formatMoney(s.value, { currency, decimals: 0 })} (${formatPercent(s.value / total)})`} />
      ))}
    </div>
  );
}
