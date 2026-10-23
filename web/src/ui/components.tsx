// The Vayant design system's components (Button, Amount, SectionTag, Progress, MetricCard, TransactionRow),
// ported to typed React, plus the few layout pieces the app needs. Styles: styles/components.css.
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { formatMoney } from "../lib/format";

export type Section = "net-worth" | "income" | "spend" | "assets" | "liabilities" | "goals";
type Tone = "neutral" | "auto" | "positive" | "negative" | "warning" | Section;

const SECTIONS: Record<Section, string> = {
  "net-worth": "Net worth", income: "Income", spend: "Spending", assets: "Assets", liabilities: "Liabilities", goals: "Goals",
};
const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

export function Button({ variant = "secondary", size = "md", className, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "quiet"; size?: "md" | "sm" }) {
  return <button type="button" {...rest} className={cx("vy-btn", `vy-btn-${variant}`, `vy-btn-${size}`, className)} />;
}

export function Amount({ value, currency, decimals, signed, tone = "neutral", size = "sm", className }: {
  value: number; currency?: string; decimals?: number; signed?: boolean; tone?: Tone; size?: "sm" | "md" | "xl"; className?: string;
}) {
  const toneCls = tone === "auto" ? (value > 0 ? "vy-tone-positive" : value < 0 ? "vy-tone-negative" : "")
    : tone === "neutral" ? "" : `vy-tone-${tone}`;
  return <span className={cx("vy-amount", `vy-amount-${size}`, toneCls, className)}>
    {formatMoney(value, { currency, decimals, signed })}
  </span>;
}

export function SectionTag({ section, children }: { section: Section; children?: ReactNode }) {
  return <span className={`vy-tag vy-sec-${section}`}><span className="vy-tag-dot" aria-hidden="true" />{children ?? SECTIONS[section]}</span>;
}

export function Progress({ label, value, max, kind = "budget", section = "spend", warnAt, currency }: {
  label: ReactNode; value: number; max: number; kind?: "budget" | "goal"; section?: Section; warnAt?: number; currency?: string;
}) {
  const pct = Math.max(0, Math.min(1, value / (max || 1)));
  const over = value > max;
  const state = over ? "over" : warnAt != null && pct >= warnAt ? "near" : "ok";
  const remaining = max - value;
  const m = (v: number) => formatMoney(v, { currency, decimals: 0 });
  const note = kind === "goal"
    ? (value >= max ? "Reached" : `${m(remaining)} to go`)
    : (over ? `Over by ${m(-remaining)}` : `${m(remaining)} left`);
  return (
    <div className={cx("vy-progress", `vy-sec-${section}`, `vy-progress-${kind === "goal" ? "ok" : state}`)}>
      <div className="vy-progress-head">
        <span className="vy-progress-label">{label}</span>
        <span className="vy-progress-figures">{m(value)}<span className="vy-muted"> of {m(max)}</span></span>
      </div>
      <div className="vy-progress-track" role="progressbar" aria-valuemin={0} aria-valuemax={max} aria-valuenow={value}>
        <div className="vy-progress-fill" style={{ width: `${(pct * 100).toFixed(1)}%` }} />
      </div>
      <div className="vy-progress-note">{note}</div>
    </div>
  );
}

export function MetricCard({ label, value, delta, deltaLabel = "vs last month", lowerIsBetter, section, large, decimals, currency, format }: {
  label: string; value: number; delta?: number; deltaLabel?: string; lowerIsBetter?: boolean; section?: Section;
  large?: boolean; decimals?: number; currency?: string; format?: (v: number) => string;
}) {
  const good = delta != null && (lowerIsBetter ? delta < 0 : delta > 0);
  return (
    <div className={cx("vy-card vy-metric", section && `vy-sec-${section}`)}>
      <div className="vy-metric-top">
        <span className="vy-eyebrow">{label}</span>
        {section && <SectionTag section={section} />}
      </div>
      <div className={cx("vy-metric-value", large && "vy-metric-value-xl")}>
        {format ? format(value) : formatMoney(value, { currency, decimals: decimals ?? (large ? 0 : 2) })}
      </div>
      {delta != null && (
        <div className={cx("vy-metric-delta", Math.round(delta) !== 0 && (good ? "vy-tone-positive" : "vy-tone-negative"))}>
          {delta > 0 ? "↑ " : delta < 0 ? "↓ " : ""}{formatMoney(delta, { currency, decimals: 0, signed: true })}
          <span className="vy-muted"> {deltaLabel}</span>
        </div>
      )}
    </div>
  );
}

export function TransactionRow({ merchant, amount, date, category, section, currency, extra, onClick }: {
  merchant: string; amount: number; date?: string; category?: string | null; section?: Section; currency?: string;
  extra?: ReactNode; onClick?: () => void;
}) {
  const body = <>
    <span className={`vy-txn-icon vy-sec-${section ?? (amount > 0 ? "income" : "spend")}`} aria-hidden="true">{merchant.charAt(0)}</span>
    <span className="vy-txn-main">
      <span className="vy-txn-merchant">{merchant}</span>
      <span className="vy-txn-meta">{[date, category].filter(Boolean).join(" · ")}</span>
    </span>
    {extra}
    <Amount value={amount} signed={amount > 0} tone={amount > 0 ? "positive" : "neutral"} currency={currency} className="vy-txn-amount" />
  </>;
  return onClick
    ? <button type="button" className={cx("vy-txn vy-txn-button", extra != null && "vy-txn-extra")} onClick={onClick}>{body}</button>
    : <div className={cx("vy-txn", extra != null && "vy-txn-extra")}>{body}</div>;
}

// ---- Layout pieces built from the same tokens ----

export function Card({ title, action, children, className }: { title?: ReactNode; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cx("vy-card", className)}>
      {(title || action) && <header className="card-head">{title && <h2 className="title-3">{title}</h2>}{action}</header>}
      {children}
    </section>
  );
}

export function Segmented<T extends string>({ options, value, onChange, label }: {
  options: readonly T[] | readonly { value: T; label: string }[]; value: T; onChange: (v: T) => void; label: string;
}) {
  const opts = options.map((o) => (typeof o === "string" ? { value: o as T, label: o } : o as { value: T; label: string }));
  return (
    <div className="segmented" role="radiogroup" aria-label={label}>
      {opts.map((o) => (
        <button key={o.value} type="button" role="radio" aria-checked={o.value === value} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return <div className="empty"><p className="title-3">{title}</p>{children && <p className="vy-muted">{children}</p>}</div>;
}

export function ErrorNote({ error }: { error?: Error }) {
  return error ? <div className="error-note" role="alert">Could not load data. Is the server running? ({error.message})</div> : null;
}
