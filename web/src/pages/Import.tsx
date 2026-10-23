import { useEffect, useMemo, useState } from "react";
import {
  api, post, useApi, type Account, type Category, type ImportMapping, type ImportPreview, type ImportRecord, type ImportResult,
} from "../lib/api";
import { currencyName, groupByCurrency } from "../lib/currency";
import { formatDay, formatMoney, today } from "../lib/format";
import { href } from "../lib/router";
import { Button, Card, ErrorNote, Segmented } from "../ui/components";
import { CategorySelect } from "./Transactions";

const MAX_BYTES = 10_000_000;
const FORMAT_LABELS: Record<string, string> = {
  "%Y-%m-%d": "YYYY-MM-DD", "%Y/%m/%d": "YYYY/MM/DD", "%m/%d/%Y": "MM/DD/YYYY", "%m/%d/%y": "MM/DD/YY",
  "%m-%d-%Y": "MM-DD-YYYY", "%d/%m/%Y": "DD/MM/YYYY", "%d/%m/%y": "DD/MM/YY", "%d-%m-%Y": "DD-MM-YYYY",
  "%d-%m-%y": "DD-MM-YY", "%d.%m.%Y": "DD.MM.YYYY", "%d %b %Y": "23 Oct 2026", "%d-%b-%Y": "23-Oct-2026",
  "%d-%b-%y": "23-Oct-26", "%d %B %Y": "23 October 2026", "%b %d, %Y": "Oct 23, 2026", "%B %d, %Y": "October 23, 2026",
  "%b %d %Y": "Oct 23 2026",
};
const STATUS: Record<ImportRow["status"], string> = { new: "New", duplicate: "Already imported", possible_duplicate: "Possible duplicate" };
type ImportRow = ImportPreview["rows"][number];
type Choice = { include: boolean; category_id: number | null };

/** Bank files are usually UTF-8; older exports are Windows-1252. */
async function readText(file: File) {
  const buf = await file.arrayBuffer();
  try { return new TextDecoder("utf-8", { fatal: true }).decode(buf); } catch { return new TextDecoder("windows-1252").decode(buf); }
}

export function Import({ params }: { params: URLSearchParams }) {
  const accounts = useApi<Account[]>("/accounts");
  const categories = useApi<Category[]>("/categories");
  const history = useApi<ImportRecord[]>("/imports");
  const [accountId, setAccountId] = useState(params.get("account") ?? "");
  const [file, setFile] = useState<{ name: string; content: string } | null>(null);
  const [mapping, setMapping] = useState<ImportMapping | null>(null);  // null: let the server use the saved or guessed one
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [choices, setChoices] = useState<Record<string, Choice>>({});
  const [balance, setBalance] = useState({ amount: "", as_of: today() });
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const account = accounts.data?.find((a) => String(a.id) === accountId);

  useEffect(() => {
    if (!file || !accountId) return;
    let live = true;
    setError("");
    post<ImportPreview>("/imports/preview", { account_id: Number(accountId), filename: file.name, content: file.content, mapping })
      .then((p) => {
        if (!live) return;
        setPreview(p);
        setChoices(Object.fromEntries(p.rows.map((r) => [r.hash, { include: r.status === "new", category_id: r.category_id }])));
      })
      .catch((e) => live && setError(String(e)));
    return () => { live = false; };
  }, [file, accountId, mapping]);

  const pick = async (f: File | undefined) => {
    setResult(null); setPreview(null); setMapping(null);
    if (!f) return setFile(null);
    if (f.size > MAX_BYTES) return setError("That file is over 10 MB. Export a shorter date range.");
    setFile({ name: f.name, content: await readText(f) });
  };

  const counts = useMemo(() => {
    const c = { new: 0, duplicate: 0, possible_duplicate: 0, chosen: 0 };
    for (const r of preview?.rows ?? []) { c[r.status]++; if (choices[r.hash]?.include && r.status !== "duplicate") c.chosen++; }
    return c;
  }, [preview, choices]);

  const hasBalanceColumn = preview?.mapping?.balance != null;
  const run = async () => {
    if (!file || !preview) return;
    setBusy(true); setError("");
    try {
      const res = await post<ImportResult>("/imports", {
        account_id: Number(accountId), filename: file.name, content: file.content, mapping: preview.mapping,
        choices: Object.entries(choices).map(([hash, c]) => ({ hash, ...c })),
        balance: !hasBalanceColumn && !preview.ledger_balance && balance.amount ? { amount: Number(balance.amount.replace(/,/g, "")), as_of: balance.as_of } : null,
      });
      setResult(res); setPreview(null); setFile(null); history.reload();
    } catch (e) { setError(String(e)); } finally { setBusy(false); }
  };

  const currency = account?.currency ?? "USD";
  return (
    <>
      <Card title="Choose a file">
        <div className="import-pick">
          <label className="field">Account
            <select value={accountId} onChange={(e) => { setAccountId(e.target.value); setMapping(null); setResult(null); }}>
              <option value="">Select an account</option>
              {groupByCurrency(accounts.data ?? [], (a) => a.currency).map(([cur, list]) => (
                <optgroup key={cur} label={currencyName(cur)}>
                  {list.map((a) => <option key={a.id} value={a.id}>{a.name}{a.institution ? ` (${a.institution})` : ""}</option>)}
                </optgroup>
              ))}
            </select>
          </label>
          <label className="field">File
            <input type="file" accept=".csv,.ofx,.qfx,.txt" disabled={!accountId} onChange={(e) => pick(e.target.files?.[0])} />
          </label>
        </div>
        <p className="small vy-muted">CSV from any bank, or OFX/QFX (often labelled "Quicken" or "Money" on the bank's download page). The file is read on this computer; nothing leaves it.</p>
      </Card>

      <ErrorNote error={error ? new Error(error) : undefined} />

      {result && (
        <Card title="Import complete">
          <p>Added {result.inserted.toLocaleString()} transactions to {account?.name}.
            {result.duplicates_skipped > 0 && ` ${result.duplicates_skipped} were already imported and left out.`}
            {result.balances > 0 && ` Recorded ${result.balances} daily balances.`}</p>
          <div className="actions actions-start"><a className="link" href={href("/transactions")}>View transactions</a></div>
        </Card>
      )}

      {preview?.format === "csv" && (
        <ColumnSetup preview={preview} onChange={setMapping} />
      )}

      {preview && (
        <Card title="Review" action={
          <Button variant="primary" disabled={busy || counts.chosen === 0} onClick={run}>
            {busy ? "Importing…" : `Import ${counts.chosen.toLocaleString()} transactions`}
          </Button>}>
          <p className="small vy-muted review-summary">
            {[`${counts.new} new`, counts.duplicate && `${counts.duplicate} already imported`,
              counts.possible_duplicate && `${counts.possible_duplicate} possible duplicates (left out unless you tick them)`,
              preview.skipped.length && `${preview.skipped.length} lines skipped`].filter(Boolean).join(" · ")}
          </p>
          {preview.file_currency && preview.file_currency !== currency && (
            <p className="error-note">This file is in {preview.file_currency} but {account?.name} is a {currency} account.</p>
          )}
          <div className="table-wrap review-table">
            <table className="table">
              <thead><tr><th aria-label="Include" /><th>Date</th><th>Description</th><th className="num">Amount</th><th>Category</th><th className="hide-narrow">Status</th></tr></thead>
              <tbody>
                {preview.rows.map((r) => {
                  const c = choices[r.hash];
                  const set = (patch: Partial<Choice>) => setChoices((all) => ({ ...all, [r.hash]: { ...all[r.hash], ...patch } }));
                  return (
                    <tr key={r.hash} className={r.status === "duplicate" ? "row-muted" : undefined}>
                      <td><input type="checkbox" aria-label={`Include ${r.description}`} checked={!!c?.include && r.status !== "duplicate"}
                        disabled={r.status === "duplicate"} onChange={(e) => set({ include: e.target.checked })} /></td>
                      <td className="figure">{formatDay(r.date)}</td>
                      <td>{r.description}</td>
                      <td className={`num ${r.amount > 0 ? "vy-tone-positive" : ""}`}>{formatMoney(r.amount, { currency, signed: r.amount > 0 })}</td>
                      <td><CategorySelect categories={categories.data} value={c?.category_id ? String(c.category_id) : ""} emptyLabel="Uncategorised"
                        onChange={(v) => set({ category_id: v ? Number(v) : null })} /></td>
                      <td className={`hide-narrow small ${r.status === "possible_duplicate" ? "vy-tone-warning" : "vy-muted"}`}>{STATUS[r.status]}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {preview.skipped.length > 0 && (
            <details className="small vy-muted skipped">
              <summary>Skipped lines</summary>
              {preview.skipped.map((s) => <div key={s.line}>Line {s.line}: {s.reason}</div>)}
            </details>
          )}
          <div className="balance-note">
            {hasBalanceColumn ? <p className="small vy-muted">Daily balances will be taken from the file's balance column.</p>
              : preview.ledger_balance ? <p className="small vy-muted">
                  The file reports {account?.classification === "liability" ? "an amount owed" : "a balance"} of {formatMoney(account?.classification === "liability" ? Math.abs(preview.ledger_balance.amount) : preview.ledger_balance.amount, { currency })} on {formatDay(preview.ledger_balance.as_of)}. Earlier daily balances are worked out from the transactions.</p>
              : (
                <div className="import-pick">
                  <label className="field">Balance (optional)
                    <input inputMode="decimal" placeholder={formatMoney(0, { currency })} value={balance.amount} onChange={(e) => setBalance({ ...balance, amount: e.target.value })} />
                  </label>
                  <label className="field">On
                    <input type="date" value={balance.as_of} max={today()} onChange={(e) => setBalance({ ...balance, as_of: e.target.value })} />
                  </label>
                  <p className="small vy-muted">This file has no balances. Enter the account's balance on a date covered by the file (for a card, what you owed) and Vayant works out the daily balances from the transactions.</p>
                </div>
              )}
          </div>
        </Card>
      )}

      <ImportHistory records={history.data ?? []} onUndone={() => { history.reload(); setResult(null); }} />
    </>
  );
}

function ColumnSetup({ preview, onChange }: { preview: ImportPreview; onChange: (m: ImportMapping) => void }) {
  const m = preview.mapping;
  const cols = Array.from({ length: preview.columns }, (_, i) => ({
    value: String(i),
    label: preview.header?.[i] || `Column ${i + 1}${preview.sample[0]?.[i] ? ` (${preview.sample[0][i].slice(0, 24)})` : ""}`,
  }));
  if (!m) {
    return <Card title="Columns"><p className="vy-muted">Vayant couldn't find a date column in this file. Check that it is a transaction export, not a PDF statement saved as text.</p></Card>;
  }
  const split = m.amount == null;
  const set = (patch: Partial<ImportMapping>) => onChange({ ...m, ...patch });
  const col = (label: string, value: number | null | undefined, onPick: (v: number | null) => void, optional = false) => (
    <label className="field">{label}
      <select value={value ?? ""} onChange={(e) => onPick(e.target.value === "" ? null : Number(e.target.value))}>
        {optional && <option value="">None</option>}
        {cols.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
      </select>
    </label>
  );
  const roles = new Map<number, string>([[m.date, "Date"], [m.description, "Description"]]);
  if (m.amount != null) roles.set(m.amount, "Amount");
  if (m.debit != null) roles.set(m.debit, "Money out");
  if (m.credit != null) roles.set(m.credit, "Money in");
  if (m.balance != null) roles.set(m.balance, "Balance");

  return (
    <Card title="Columns">
      <p className="small vy-muted">
        {preview.profile_used ? "Using the column setup from your last import into this account." : "Vayant guessed these from the file. Check them against the sample below; your choices are remembered for this account."}
      </p>
      <div className="mapping">
        {col("Date", m.date, (v) => set({ date: v ?? 0 }))}
        <label className="field">Date format
          <select value={m.date_format} onChange={(e) => set({ date_format: e.target.value })}>
            {[...new Set([m.date_format, ...preview.date_formats])].map((f) => <option key={f} value={f}>{FORMAT_LABELS[f] ?? f}</option>)}
          </select>
        </label>
        {col("Description", m.description, (v) => set({ description: v ?? 0 }))}
        <div className="field">Amounts
          <Segmented label="Amount layout" value={split ? "split" : "one"} onChange={(v) => set(v === "one"
            ? { amount: m.debit ?? m.credit ?? 0, debit: null, credit: null }
            : { amount: null, debit: m.amount ?? 0, credit: null, negate: false })}
            options={[{ value: "one", label: "One column" }, { value: "split", label: "Out and in" }]} />
        </div>
        {split ? <>
          {col("Money out", m.debit, (v) => set({ debit: v }), true)}
          {col("Money in", m.credit, (v) => set({ credit: v }), true)}
        </> : col("Amount", m.amount, (v) => set({ amount: v ?? 0 }))}
        {col("Balance", m.balance, (v) => set({ balance: v }), true)}
      </div>
      {preview.date_formats.length > 1 && (
        <p className="small vy-tone-warning">Every date in this file fits more than one format (for example 03/04 could be 3 April or 4 March). Pick the one your bank uses.</p>
      )}
      {!split && (
        <label className="check"><input type="checkbox" checked={!!m.negate} onChange={(e) => set({ negate: e.target.checked })} />
          Money out is shown as a positive number in this file (common for credit cards)</label>
      )}
      <div className="table-wrap sample">
        <table className="table">
          <thead><tr>{cols.map((_, i) => <th key={i}>{roles.get(i) ? <span className="role">{roles.get(i)}</span> : null}{preview.header?.[i] ?? ""}</th>)}</tr></thead>
          <tbody>{preview.sample.map((r, i) => <tr key={i}>{cols.map((_, j) => <td key={j} className={roles.has(j) ? "" : "vy-muted"}>{r[j] ?? ""}</td>)}</tr>)}</tbody>
        </table>
      </div>
    </Card>
  );
}

function ImportHistory({ records, onUndone }: { records: ImportRecord[]; onUndone: () => void }) {
  const [confirming, setConfirming] = useState<number | null>(null);
  if (!records.length) return null;
  const undo = async (id: number) => { await api(`/imports/${id}`, { method: "DELETE" }).catch(() => undefined); setConfirming(null); onUndone(); };
  return (
    <Card title="Past imports">
      {records.map((r) => (
        <div key={r.id} className="row">
          <div className="row-main">
            <span className="body-strong">{r.filename}</span>
            <span className="small vy-muted">{r.account_name} · {r.row_count.toLocaleString()} transactions · {formatDay(r.created_at.slice(0, 10))}</span>
          </div>
          {confirming === r.id ? (
            <div className="actions">
              <Button size="sm" onClick={() => setConfirming(null)}>Keep</Button>
              <Button size="sm" variant="primary" onClick={() => undo(r.id)}>Remove {r.row_count.toLocaleString()} transactions</Button>
            </div>
          ) : <Button size="sm" variant="quiet" onClick={() => setConfirming(r.id)}>Undo</Button>}
        </div>
      ))}
    </Card>
  );
}
