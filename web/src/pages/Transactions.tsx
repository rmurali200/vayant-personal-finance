import { useEffect, useRef, useState } from "react";
import { api, qs, useApi, type Account, type Category, type Transaction, type TransactionPage } from "../lib/api";
import { formatDay, monthEnd, monthStart, today } from "../lib/format";
import { Button, Card, Empty, ErrorNote, Segmented, TransactionRow, type Section } from "../ui/components";
import { Icon } from "../ui/Icon";

export const categorySection = (kind?: string | null): Section | undefined =>
  kind === "income" ? "income" : kind === "expense" ? "spend" : kind === "transfer" ? "net-worth" : undefined;

const PERIODS = [
  { value: "month", label: "This month" }, { value: "last", label: "Last month" },
  { value: "3m", label: "3 months" }, { value: "all", label: "All" },
] as const;
type Period = (typeof PERIODS)[number]["value"] | "custom";
const PAGE = 50;

function periodRange(p: Period): { start?: string; end?: string } {
  if (p === "month") return { start: monthStart(), end: today() };
  if (p === "last") return { start: monthStart(-1), end: monthEnd(-1) };
  if (p === "3m") return { start: monthStart(-2), end: today() };
  return {};
}

export function Transactions({ params }: { params: URLSearchParams }) {
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [account, setAccount] = useState("");
  const [category, setCategory] = useState(params.get("category") ?? "");
  const custom = params.get("start") ? { start: params.get("start")!, end: params.get("end") ?? undefined } : null;
  const [period, setPeriod] = useState<Period>(custom ? "custom" : "3m");
  const [pages, setPages] = useState(1);
  const [editing, setEditing] = useState<Transaction | null>(null);

  useEffect(() => { const t = setTimeout(() => setSearch(q), 250); return () => clearTimeout(t); }, [q]);
  useEffect(() => setPages(1), [search, account, category, period]);

  const range = period === "custom" && custom ? custom : periodRange(period);
  const list = useApi<TransactionPage>(`/transactions${qs({
    q: search, account_id: account, category_id: category, ...range, limit: PAGE * pages,
  })}`);
  const accounts = useApi<Account[]>("/accounts");
  const categories = useApi<Category[]>("/categories");

  const byDate = new Map<string, Transaction[]>();
  for (const t of list.data?.items ?? []) byDate.set(t.date, [...(byDate.get(t.date) ?? []), t]);

  return (
    <>
      <div className="filters">
        <label className="search">
          <Icon name="search" size={18} />
          <input type="search" placeholder="Search payees and notes" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search" />
        </label>
        <select value={account} onChange={(e) => setAccount(e.target.value)} aria-label="Account">
          <option value="">All accounts</option>
          {accounts.data?.map((a) => <option key={a.id} value={a.id}>{a.name}{a.institution ? ` (${a.institution})` : ""}</option>)}
        </select>
        <CategorySelect categories={categories.data} value={category} onChange={setCategory} emptyLabel="All categories" />
        <Segmented<Period> label="Period" value={period === "custom" ? ("" as Period) : period} onChange={setPeriod} options={PERIODS} />
      </div>
      {period === "custom" && custom && <p className="vy-muted small">Showing {formatDay(custom.start)} to {custom.end ? formatDay(custom.end) : "today"}</p>}
      <ErrorNote error={list.error} />
      <Card title={list.data ? `${list.data.total.toLocaleString()} transactions` : "Transactions"}>
        {list.data?.total === 0 && <Empty title="No transactions match">Try a different period or clear the search.</Empty>}
        {[...byDate].map(([date, items]) => (
          <div key={date} className="group">
            <div className="group-head"><span className="vy-eyebrow">{formatDay(date)}</span></div>
            {items.map((t) => (
              <TransactionRow key={t.id} merchant={t.payee} amount={t.amount} currency={t.currency}
                category={t.category_name ?? "Uncategorised"} section={categorySection(t.category_kind)}
                extra={<span className="small vy-muted hide-narrow">{t.account_name}</span>}
                onClick={() => setEditing(t)} />
            ))}
          </div>
        ))}
        {list.data && list.data.items.length < list.data.total && (
          <div className="more"><Button onClick={() => setPages((p) => p + 1)} disabled={list.loading}>Show more</Button></div>
        )}
      </Card>
      {editing && <EditTransaction txn={editing} categories={categories.data ?? []}
        onClose={(changed) => { setEditing(null); if (changed) list.reload(); }} />}
    </>
  );
}

export function CategorySelect({ categories = [], value, onChange, emptyLabel }: {
  categories?: Category[]; value: string; onChange: (v: string) => void; emptyLabel: string;
}) {
  const parents = categories.filter((c) => c.parent_id === null);
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} aria-label="Category">
      <option value="">{emptyLabel}</option>
      {parents.map((p) => (
        <optgroup key={p.id} label={p.name}>
          <option value={p.id}>All {p.name}</option>
          {categories.filter((c) => c.parent_id === p.id).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </optgroup>
      ))}
    </select>
  );
}

function EditTransaction({ txn, categories, onClose }: { txn: Transaction; categories: Category[]; onClose: (changed: boolean) => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [payee, setPayee] = useState(txn.payee);
  const [category, setCategory] = useState(txn.category_id ? String(txn.category_id) : "");
  const [notes, setNotes] = useState(txn.notes ?? "");
  const [error, setError] = useState("");
  useEffect(() => ref.current?.showModal(), []);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api(`/transactions/${txn.id}`, {
        method: "PATCH",
        body: JSON.stringify({ payee, category_id: category ? Number(category) : null, notes: notes || null }),
      });
      onClose(true);
    } catch (err) {
      setError(String(err));
    }
  };

  return (
    <dialog ref={ref} className="sheet" onClose={() => onClose(false)}>
      <form onSubmit={save} className="stack">
        <header className="card-head">
          <h2 className="title-3">Edit transaction</h2>
          <Button variant="quiet" size="sm" aria-label="Close" onClick={() => onClose(false)}><Icon name="close" size={18} /></Button>
        </header>
        <p className="small vy-muted">{formatDay(txn.date)} · {txn.account_name}</p>
        <label className="field">Payee<input value={payee} onChange={(e) => setPayee(e.target.value)} required /></label>
        <label className="field">Category<CategorySelect categories={categories} value={category} onChange={setCategory} emptyLabel="Uncategorised" /></label>
        <label className="field">Notes<textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} /></label>
        {error && <p className="error-note">{error}</p>}
        <div className="actions">
          <Button onClick={() => onClose(false)}>Cancel</Button>
          <Button variant="primary" type="submit">Save</Button>
        </div>
      </form>
    </dialog>
  );
}
