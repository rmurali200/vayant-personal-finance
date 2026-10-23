import { useApi, type Goal } from "../lib/api";
import { formatMoney, formatMonth } from "../lib/format";
import { Card, Empty, ErrorNote, Progress, SectionTag } from "../ui/components";

export function Goals() {
  const res = useApi<Goal[]>("/goals");
  if (res.data && !res.data.length) return <Empty title="No goals yet">Goals earmark part of one or more account balances toward a target.</Empty>;
  return (
    <>
      <ErrorNote error={res.error} />
      <div className="goal-grid">{res.data?.map((g) => <GoalCard key={g.id} goal={g} />)}</div>
    </>
  );
}

function GoalCard({ goal: g }: { goal: Goal }) {
  const m = (v: number) => formatMoney(v, { currency: g.currency, decimals: 0 });
  const remaining = Math.max(g.target - g.current, 0);
  const monthsLeft = g.target_date ? monthsUntil(g.target_date) : null;
  return (
    <Card title={g.name} action={<SectionTag section="goals">{g.kind === "reserve" ? "Reserve fund" : "Savings"}</SectionTag>}>
      <div className="stack">
        <Progress kind="goal" section="goals" label="Earmarked" value={g.current} max={g.target} currency={g.currency} />
        <p className="small vy-muted">
          {g.target_months != null && `Target: ${Number(g.target_months)} months of average spending (${m(g.target / Number(g.target_months))} a month). `}
          {g.target_date && `By ${formatMonth(g.target_date, "long")}`}
          {monthsLeft != null && remaining > 0 && (monthsLeft > 0 ? `: ${m(remaining / monthsLeft)} a month to stay on track.` : ": target date has passed.")}
        </p>
        <div>
          <div className="group-head"><span className="vy-eyebrow">Funded from</span></div>
          {g.allocations.map((a) => (
            <div key={a.account_id} className="row">
              <div className="row-main">
                <span className="body-strong">{a.account_name}</span>
                <span className="small vy-muted">
                  {a.percent != null ? `${Number(a.percent)}% of balance` : `Fixed ${formatMoney(a.amount ?? 0, { currency: a.account_currency, decimals: 0 })}`}
                </span>
              </div>
              <span className="figure">{m(a.contributed)}</span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

function monthsUntil(iso: string) {
  const d = new Date(iso + "T00:00:00"), now = new Date();
  return (d.getFullYear() - now.getFullYear()) * 12 + d.getMonth() - now.getMonth();
}
