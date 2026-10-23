import { useState } from "react";
import { LineChart } from "../charts/LineChart";
import { qs, useApi, type Account, type NetWorth } from "../lib/api";
import { formatDay, formatMoney, isoDate } from "../lib/format";
import { useSettings } from "../lib/settings";
import { Amount, Card, ErrorNote, MetricCard, Segmented } from "../ui/components";

const RANGES = [
  { value: "3", label: "3M" }, { value: "6", label: "6M" }, { value: "12", label: "1Y" }, { value: "24", label: "2Y" },
] as const;
type Range = (typeof RANGES)[number]["value"];

const GROUPS: Record<string, string> = {
  cash: "Cash", investment: "Investments", property: "Property", other_asset: "Other assets",
  credit: "Credit cards", loan: "Loans", other_liability: "Other liabilities",
};

export function Accounts() {
  const { currency } = useSettings();
  const [range, setRange] = useState<Range>("12");
  const start = new Date();
  start.setMonth(start.getMonth() - Number(range));
  const nw = useApi<NetWorth>(`/net-worth${qs({ currency, start: isoDate(start), interval: range === "3" ? "week" : "month" })}`);
  const accounts = useApi<Account[]>(`/accounts${qs({ currency })}`);
  const s = nw.data?.series ?? [];
  const first = s[0], now = s.at(-1);

  return (
    <>
      <ErrorNote error={nw.error ?? accounts.error} />
      <div className="metrics">
        {now && <MetricCard label="Net worth" value={now.net_worth} large currency={currency}
          delta={first && now.net_worth - first.net_worth} deltaLabel={`over ${RANGES.find((r) => r.value === range)!.label}`} />}
        {now && <MetricCard label="Assets" value={now.assets} section="assets" currency={currency} decimals={0} />}
        {now && <MetricCard label="Liabilities" value={now.liabilities} section="liabilities" currency={currency} decimals={0} />}
      </div>
      <Card title="Net worth over time" action={<Segmented<Range> label="Range" options={RANGES} value={range} onChange={setRange} />}>
        <LineChart label="Net worth over time" currency={currency} color="var(--net-worth)"
          points={s.map((p) => ({ date: p.date, value: p.net_worth, details: [{ label: "Assets", value: p.assets }, { label: "Liabilities", value: p.liabilities }] }))} />
      </Card>
      <div className="columns">
        <AccountList title="Assets" accounts={accounts.data?.filter((a) => a.classification === "asset")} currency={currency} />
        <AccountList title="Liabilities" accounts={accounts.data?.filter((a) => a.classification === "liability")} currency={currency} />
      </div>
    </>
  );
}

function AccountList({ title, accounts = [], currency }: { title: string; accounts?: Account[]; currency: string }) {
  const groups = Object.entries(GROUPS)
    .map(([type, label]) => ({ label, items: accounts.filter((a) => a.type === type) }))
    .filter((g) => g.items.length);
  const total = accounts.reduce((s, a) => s + (a.in_net_worth ? a.balance_converted ?? 0 : 0), 0);
  return (
    <Card title={title} action={<Amount value={total} currency={currency} decimals={0} size="md" />}>
      {groups.map((g) => (
        <div key={g.label} className="group">
          <div className="group-head">
            <span className="vy-eyebrow">{g.label}</span>
            <span className="vy-muted figure">{formatMoney(g.items.reduce((s, a) => s + (a.balance_converted ?? 0), 0), { currency, decimals: 0 })}</span>
          </div>
          {g.items.map((a) => (
            <div key={a.id} className="row">
              <div className="row-main">
                <span className="body-strong">{a.name}</span>
                <span className="small vy-muted">
                  {[a.institution, a.country, a.mask && `••${a.mask}`, a.balance_date && `Updated ${formatDay(a.balance_date)}`].filter(Boolean).join(" · ")}
                </span>
              </div>
              <div className="row-end">
                <Amount value={a.balance_converted ?? 0} currency={currency} />
                {a.currency !== currency && <span className="small vy-muted figure">{formatMoney(a.balance ?? 0, { currency: a.currency })}</span>}
              </div>
            </div>
          ))}
        </div>
      ))}
    </Card>
  );
}
