import { useState } from "react";
import { ColumnChart } from "../charts/ColumnChart";
import { qs, useApi, type CashFlow as Flow } from "../lib/api";
import { formatMoney, formatMonth, formatPercent, monthEnd, monthStart } from "../lib/format";
import { href } from "../lib/router";
import { useSettings } from "../lib/settings";
import { Card, ErrorNote, MetricCard, Segmented } from "../ui/components";

const RANGES = [{ value: "3", label: "3M" }, { value: "6", label: "6M" }, { value: "12", label: "12M" }] as const;
type Range = (typeof RANGES)[number]["value"];
type Cat = Flow["categories"][number];

export function CashFlow() {
  const { currency } = useSettings();
  const [range, setRange] = useState<Range>("6");
  const [includeCurrent, setIncludeCurrent] = useState(false);
  // Whole months only by default, so a half-finished month doesn't skew averages.
  const start = monthStart(-Number(range) + (includeCurrent ? 1 : 0));
  const end = includeCurrent ? monthEnd() : monthEnd(-1);
  const flow = useApi<Flow>(`/cash-flow${qs({ currency, start, end })}`);
  const months = flow.data?.months ?? [];
  const income = months.reduce((s, m) => s + m.income, 0);
  const expenses = months.reduce((s, m) => s + m.expenses, 0);
  const cats = flow.data?.categories ?? [];

  return (
    <>
      <div className="filters">
        <Segmented<Range> label="Range" options={RANGES} value={range} onChange={setRange} />
        <label className="check"><input type="checkbox" checked={includeCurrent} onChange={(e) => setIncludeCurrent(e.target.checked)} />Include this month</label>
      </div>
      <ErrorNote error={flow.error} />
      <div className="metrics metrics-4">
        <MetricCard label="Income" value={income} section="income" currency={currency} decimals={0} />
        <MetricCard label="Spending" value={expenses} section="spend" currency={currency} decimals={0} />
        <MetricCard label="Saved" value={income - expenses} currency={currency} decimals={0} />
        <MetricCard label="Savings rate" value={income ? (income - expenses) / income : 0} format={(v) => formatPercent(v)} />
      </div>
      <Card title="Income and spending by month">
        <ColumnChart label="Income and spending by month" currency={currency}
          series={[{ name: "Income", color: "var(--income)" }, { name: "Spending", color: "var(--spend)" }]}
          groups={months.map((m) => ({ label: formatMonth(m.month), title: formatMonth(m.month, "long"), values: [m.income, m.expenses] }))} />
      </Card>
      <div className="columns">
        <Breakdown title="Income" kind="income" cats={cats} currency={currency} start={start} end={end} />
        <Breakdown title="Spending" kind="expense" cats={cats} currency={currency} start={start} end={end} />
      </div>
    </>
  );
}

/** Categories rolled up into their groups, with a share bar. Each row opens the matching transactions. */
function Breakdown({ title, kind, cats, currency, start, end }: {
  title: string; kind: "income" | "expense"; cats: Cat[]; currency: string; start: string; end: string;
}) {
  const [open, setOpen] = useState<string | null>(null);
  const mine = cats.filter((c) => c.kind === kind);
  const total = mine.reduce((s, c) => s + c.total, 0);
  const grouped = Map.groupBy(mine, (c) => c.group ?? c.name);
  const groups = [...(grouped.size > 1 ? grouped : Map.groupBy(mine, (c) => c.name))]
    .map(([name, items]) => ({ name, items, total: items.reduce((s, c) => s + c.total, 0) }))
    .sort((a, b) => b.total - a.total);
  const section = kind === "income" ? "income" : "spend";

  return (
    <Card title={title} action={<span className="figure body-strong">{formatMoney(total, { currency, decimals: 0 })}</span>}>
      {groups.map((g) => (
        <div key={g.name} className={`breakdown vy-sec-${section}`}>
          <button type="button" className="breakdown-row" aria-expanded={grouped.size > 1 ? open === g.name : undefined}
            onClick={() => grouped.size > 1 ? setOpen(open === g.name ? null : g.name) : g.items[0].category_id && (location.hash = href("/transactions", { category: g.items[0].category_id, start, end }))}>
            <span className="body-strong">{g.name}</span>
            <span className="figure">{formatMoney(g.total, { currency, decimals: 0 })}</span>
            <span className="share"><span style={{ width: `${(g.total / (total || 1)) * 100}%` }} /></span>
            <span className="small vy-muted figure">{formatPercent(g.total / (total || 1))}</span>
          </button>
          {grouped.size > 1 && open === g.name && g.items.map((c) => (
            <a key={c.category_id ?? c.name} className="breakdown-sub"
              href={c.category_id ? href("/transactions", { category: c.category_id, start, end }) : undefined}>
              <span>{c.name}</span>
              <span className="figure">{formatMoney(c.total, { currency, decimals: 0 })}</span>
            </a>
          ))}
        </div>
      ))}
    </Card>
  );
}
