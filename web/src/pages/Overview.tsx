import { useState } from "react";
import { LineChart } from "../charts/LineChart";
import { qs, useApi, type CashFlow, type Goal, type NetWorth, type TransactionPage } from "../lib/api";
import { formatDay, monthStart, today } from "../lib/format";
import { href } from "../lib/router";
import { useSettings } from "../lib/settings";
import { Card, CurrencyTabs, ErrorNote, MetricCard, Progress, TransactionRow } from "../ui/components";
import { categorySection } from "./Transactions";

export function Overview() {
  const { currency } = useSettings();
  const nw = useApi<NetWorth>(`/net-worth${qs({ currency })}`);
  const flow = useApi<CashFlow>(`/cash-flow${qs({ currency, start: monthStart(), end: today() })}`);
  const [txnCurrency, setTxnCurrency] = useState<string | null>(null);
  const recent = useApi<TransactionPage>(`/transactions${qs({ limit: 8, currency: txnCurrency ?? currency })}`);
  const goals = useApi<Goal[]>("/goals");

  const s = nw.data?.series ?? [];
  const now = s.at(-1), prev = s.at(-2);
  const thisMonth = flow.data?.months.find((m) => m.month === monthStart());

  return (
    <>
      <ErrorNote error={nw.error ?? flow.error} />
      <div className="metrics">
        {now && <MetricCard label="Net worth" value={now.net_worth} delta={prev && now.net_worth - prev.net_worth} large currency={currency} />}
        {now && <MetricCard label="Total assets" value={now.assets} delta={prev && now.assets - prev.assets} section="assets" currency={currency} decimals={0} />}
        {now && <MetricCard label="Total liabilities" value={now.liabilities} delta={prev && now.liabilities - prev.liabilities} lowerIsBetter section="liabilities" currency={currency} decimals={0} />}
      </div>

      <Card title="Net worth" action={<a className="link" href={href("/accounts")}>All accounts</a>}>
        <LineChart label="Net worth, last 12 months" currency={currency} color="var(--net-worth)"
          points={s.map((p) => ({ date: p.date, value: p.net_worth, details: [{ label: "Assets", value: p.assets }, { label: "Liabilities", value: p.liabilities }] }))} />
      </Card>

      <div className="metrics">
        <MetricCard label="Income this month" value={thisMonth?.income ?? 0} section="income" currency={currency} />
        <MetricCard label="Spending this month" value={thisMonth?.expenses ?? 0} section="spend" currency={currency} />
      </div>

      <div className="columns">
        <Card title="Recent transactions" action={
          <CurrencyTabs showCounts={false} counts={recent.data?.by_currency ?? {}} value={txnCurrency ?? currency} onChange={setTxnCurrency} />}>
          {recent.data?.items.map((t) => (
            <TransactionRow key={t.id} merchant={t.payee} amount={t.amount} currency={t.currency} date={formatDay(t.date)}
              category={t.category_name} section={categorySection(t.category_kind)} />
          ))}
          <div className="more"><a className="link" href={href("/transactions")}>View all transactions</a></div>
        </Card>
        <Card title="Goals" action={<a className="link" href={href("/goals")}>Details</a>}>
          <div className="stack">
            {goals.data?.map((g) => (
              <Progress key={g.id} kind="goal" section="goals" label={g.name} value={g.current} max={g.target} currency={g.currency} />
            ))}
          </div>
        </Card>
      </div>
    </>
  );
}
