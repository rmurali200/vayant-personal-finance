import { useState } from "react";
import { StackBar } from "../charts/StackBar";
import { qs, useApi, type Holding } from "../lib/api";
import { formatMoney, formatMonth, formatPercent, sentence } from "../lib/format";
import { useSettings } from "../lib/settings";
import { Card, Empty, ErrorNote, MetricCard } from "../ui/components";

// Validated categorical order (dataviz checks pass in both themes). Fixed per asset class, never by rank.
const CLASSES: Record<string, { label: string; color: string }> = {
  equity: { label: "Equity", color: "var(--viz-1)" },
  fixed_income: { label: "Fixed income", color: "var(--viz-2)" },
  cash: { label: "Cash", color: "var(--viz-3)" },
  real_estate: { label: "Real estate", color: "var(--viz-4)" },
  commodity: { label: "Commodities", color: "var(--viz-4)" },
  crypto: { label: "Crypto", color: "var(--viz-4)" },
  other: { label: "Other", color: "var(--viz-other)" },
};
const TYPES: Record<string, string> = {
  stock: "Stocks", etf: "ETFs", mutual_fund: "Mutual funds", bond: "Bonds", gic: "GICs",
  fixed_deposit: "Fixed deposits", money_market: "Money market", crypto: "Crypto", other: "Other",
};

const DEPOSITS = new Set(["gic", "fixed_deposit"]);

export function Investments() {
  const { currency } = useSettings();
  const res = useApi<Holding[]>(`/holdings${qs({ currency })}`);
  const holdings = res.data ?? [];
  const [open, setOpen] = useState<string | null>("equity");

  const value = holdings.reduce((s, h) => s + (h.value_converted ?? 0), 0);
  // Cost basis is in the security's currency; scale it by the same rate as its value.
  const cost = holdings.reduce((s, h) => s + (h.cost_basis != null && h.value ? h.cost_basis * (h.value_converted ?? 0) / h.value : h.value_converted ?? 0), 0);
  const byClass = Object.entries(CLASSES)
    .map(([key, c]) => {
      const items = holdings.filter((h) => h.asset_class === key);
      const types = [...Map.groupBy(items, (h) => h.security_type ?? "other")]
        .map(([t, hs]) => ({ t, value: hs.reduce((s, h) => s + (h.value_converted ?? 0), 0) }))
        .sort((a, b) => b.value - a.value);
      return { key, ...c, value: items.reduce((s, h) => s + (h.value_converted ?? 0), 0), types };
    })
    .filter((c) => c.value > 0);

  if (res.data && !holdings.length) return <Empty title="No holdings yet">Investment positions appear here once an account has them.</Empty>;

  return (
    <>
      <ErrorNote error={res.error} />
      <div className="metrics">
        <MetricCard label="Portfolio value" value={value} large currency={currency} />
        <MetricCard label="Gain since purchase" value={value - cost} currency={currency} decimals={0} section="assets"
          format={(v) => `${formatMoney(v, { currency, decimals: 0, signed: true })} (${formatPercent(cost ? v / cost : 0, 1)})`} />
      </div>
      <Card title="Allocation">
        <StackBar label="Allocation by asset class" currency={currency} slices={byClass.map((c) => ({ key: c.key, label: c.label, value: c.value, color: c.color }))} />
        <div className="allocation">
          {byClass.map((c) => (
            <div key={c.key}>
              <button type="button" className="breakdown-row" aria-expanded={open === c.key} onClick={() => setOpen(open === c.key ? null : c.key)}>
                <span className="body-strong"><i className="swatch" style={{ background: c.color }} />{c.label}</span>
                <span className="figure">{formatMoney(c.value, { currency, decimals: 0 })}</span>
                <span />
                <span className="small vy-muted figure">{formatPercent(c.value / (value || 1), 1)}</span>
              </button>
              {open === c.key && c.types.map((t) => (
                <div key={t.t} className="breakdown-sub">
                  <span>{TYPES[t.t] ?? sentence(t.t)}</span>
                  <span className="figure">{formatMoney(t.value, { currency, decimals: 0 })} <span className="vy-muted">· {formatPercent(t.value / c.value)}</span></span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </Card>
      <Card title="Holdings">
        <div className="table-wrap">
          <table className="table">
            <thead><tr>
              <th>Holding</th><th className="hide-narrow">Type</th><th className="hide-narrow">Account</th>
              <th className="num hide-narrow">Quantity</th><th className="num">Value</th><th className="num">Gain</th>
            </tr></thead>
            <tbody>
              {holdings.map((h) => {
                const gain = h.value != null && h.cost_basis ? (h.value - h.cost_basis) / h.cost_basis : null;
                return (
                  <tr key={`${h.account_id}-${h.security_id}`}>
                    <td>
                      <div className="body-strong">{h.symbol ?? h.name}</div>
                      <div className="small vy-muted">
                        {h.symbol ? h.name : [h.interest_rate && `${Number(h.interest_rate)}%`, h.maturity_date && `matures ${formatMonth(h.maturity_date, "long")}`].filter(Boolean).join(" · ")}
                      </div>
                    </td>
                    <td className="hide-narrow">{CLASSES[h.asset_class]?.label} · {TYPES[h.security_type ?? "other"]}</td>
                    <td className="hide-narrow">{h.account_name}</td>
                    <td className="num hide-narrow">{DEPOSITS.has(h.security_type ?? "") ? "—" : Number(h.quantity).toLocaleString()}</td>
                    <td className="num">
                      {formatMoney(h.value_converted ?? 0, { currency })}
                      {h.currency !== currency && <div className="small vy-muted">{formatMoney(h.value ?? 0, { currency: h.currency })}</div>}
                    </td>
                    <td className={`num ${gain && Math.abs(gain) >= 0.0005 ? (gain > 0 ? "vy-tone-positive" : "vy-tone-negative") : ""}`}>
                      {gain == null ? "—" : `${gain > 0 ? "+" : ""}${formatPercent(gain, 1)}`}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}
