import { useState } from "react";
import { formatCompact, formatMonth, formatMoney } from "../lib/format";
import { niceTicks, useWidth } from "./scale";

export interface LinePoint {
  date: string;
  value: number;
  /** Extra figures listed in the tooltip, e.g. assets and liabilities behind a net worth point. */
  details?: { label: string; value: number }[];
}

const M = { l: 64, r: 12, t: 12, b: 28 };

/** Single-series trend line with a crosshair tooltip. The card title names the series, so no legend. */
export function LineChart({ points, currency, color, label, height = 240 }: {
  points: LinePoint[]; currency: string; color: string; label: string; height?: number;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  if (points.length < 2) return <div ref={ref} style={{ height }} />;

  const vals = points.map((p) => p.value);
  const { lo, hi, ticks } = niceTicks(Math.min(...vals), Math.max(...vals));
  const plotW = Math.max(width - M.l - M.r, 1);
  const x = (i: number) => M.l + (i * plotW) / (points.length - 1);
  const y = (v: number) => M.t + ((hi - v) / (hi - lo)) * (height - M.t - M.b);
  const line = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join("");
  const every = Math.max(1, Math.ceil(points.length / Math.max(2, Math.floor(plotW / 64))));
  const last = points.length - 1;
  const h = hover ?? null;

  const onMove = (e: React.PointerEvent) => {
    const r = e.currentTarget.getBoundingClientRect();
    const i = Math.round(((e.clientX - r.left - M.l) / plotW) * last);
    setHover(Math.max(0, Math.min(last, i)));
  };

  return (
    <div ref={ref} className="chart" style={{ height }}>
      {width > 0 && (
        <svg width={width} height={height} role="img" aria-label={label} onPointerMove={onMove} onPointerLeave={() => setHover(null)}>
          {ticks.map((t) => (
            <g key={t}>
              <line x1={M.l} x2={width - M.r} y1={y(t)} y2={y(t)} className="chart-grid" />
              <text x={M.l - 8} y={y(t)} dy="0.32em" textAnchor="end" className="chart-axis">{formatCompact(t, currency)}</text>
            </g>
          ))}
          {points.map((p, i) => (i % every === 0 || i === last) && (i === last || last - i >= every / 2) && (
            <text key={p.date} x={x(i)} y={height - 8} textAnchor={i === 0 ? "start" : i === last ? "end" : "middle"} className="chart-axis">
              {formatMonth(p.date)}
            </text>
          ))}
          <path d={line} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
          {h !== null && <line x1={x(h)} x2={x(h)} y1={M.t} y2={height - M.b} className="chart-crosshair" />}
          <circle cx={x(h ?? last)} cy={y(points[h ?? last].value)} r={4.5} fill={color} className="chart-dot" />
        </svg>
      )}
      {h !== null && (
        <div className="chart-tip" style={{ left: Math.min(Math.max(x(h), 90), width - 90), top: 0 }}>
          <div className="vy-muted">{formatMonth(points[h].date, "long")}</div>
          <strong>{formatMoney(points[h].value, { currency, decimals: 0 })}</strong>
          {points[h].details?.map((d) => (
            <div key={d.label} className="chart-tip-row"><span className="vy-muted">{d.label}</span>{formatMoney(d.value, { currency, decimals: 0 })}</div>
          ))}
        </div>
      )}
      <table className="sr-only">
        <caption>{label}</caption>
        <tbody>{points.map((p) => <tr key={p.date}><th>{p.date}</th><td>{formatMoney(p.value, { currency })}</td></tr>)}</tbody>
      </table>
    </div>
  );
}
