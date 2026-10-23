import { useState } from "react";
import { LineChart } from "../charts/LineChart";
import { qs, useApi, type Account, type NetWorth } from "../lib/api";
import { currencyName, groupByCurrency } from "../lib/currency";
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
      {groupByCurrency(accounts.data ?? [], (a) => a.currency).map(([cur, items]) => (
        <CurrencyAccounts key={cur} currency={cur} accounts={items} reporting={currency} />
      ))}
    </>
  );
}

/** All accounts held in one currency, in that currency only. */
function CurrencyAccounts({ currency, accounts, reporting }: { currency: string; accounts: Account[]; reporting: string }) {
  const counted = accounts.filter((a) => a.in_net_worth);
  const sum = (list: Account[], key: "balance" | "balance_converted") => list.reduce((s, a) => s + (a[key] ?? 0), 0);
  const signed = (key: "balance" | "balance_converted") =>
    sum(counted.filter((a) => a.classification === "asset"), key) - sum(counted.filter((a) => a.classification === "liability"), key);
  return (
    <Card
      title={<>{currencyName(currency)} <span className="vy-muted">{currency}</span></>}
      action={
        <div className="row-end">
          <span className="small vy-muted">Net</span>
          <Amount value={signed("balance")} currency={currency} decimals={0} size="md" />
          {currency !== reporting && <span className="small vy-muted figure">≈ {formatMoney(signed("balance_converted"), { currency: reporting, decimals: 0 })}</span>}
        </div>
      }>
      <div className="columns">
        <AccountList title="Assets" accounts={accounts.filter((a) => a.classification === "asset")} currency={currency} />
        <AccountList title="Liabilities" accounts={accounts.filter((a) => a.classification === "liability")} currency={currency} />
      </div>
    </Card>
  );
}

function AccountList({ title, accounts, currency }: { title: string; accounts: Account[]; currency: string }) {
  if (!accounts.length) return <div><div className="list-title"><h3 className="title-3">{title}</h3></div><p className="small vy-muted">None in {currency}</p></div>;
  const groups = Object.entries(GROUPS)
    .map(([type, label]) => ({ label, items: accounts.filter((a) => a.type === type) }))
    .filter((g) => g.items.length);
  const m = (v: number) => formatMoney(v, { currency, decimals: 0 });
  return (
    <div>
      <div className="list-title">
        <h3 className="title-3">{title}</h3>
        <span className="figure body-strong">{m(accounts.reduce((s, a) => s + (a.in_net_worth ? a.balance ?? 0 : 0), 0))}</span>
      </div>
      {groups.map((g) => (
        <div key={g.label} className="group">
          <div className="group-head">
            <span className="vy-eyebrow">{g.label}</span>
            <span className="vy-muted figure">{m(g.items.reduce((s, a) => s + (a.balance ?? 0), 0))}</span>
          </div>
          {g.items.map((a) => (
            <div key={a.id} className="row">
              <div className="row-main">
                <span className="body-strong">{a.name}</span>
                <span className="small vy-muted">
                  {[a.institution, a.mask && `••${a.mask}`, a.balance_date && `Updated ${formatDay(a.balance_date)}`].filter(Boolean).join(" · ")}
                </span>
              </div>
              <Amount value={a.balance ?? 0} currency={currency} />
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
