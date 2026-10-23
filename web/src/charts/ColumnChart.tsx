import { useState } from "react";
import { formatCompact, formatMoney } from "../lib/format";
import { columnPath, niceTicks, useWidth } from "./scale";

export interface Series { name: string; color: string }
export interface ColumnGroup { label: string; title: string; values: number[] }

const M = { l: 64, r: 8, t: 12, b: 28 };

/** Grouped columns from a zero baseline, e.g. income vs spending per month. Legend above, tooltip per group. */
export function ColumnChart({ groups, series, currency, label, height = 240 }: {
  groups: ColumnGroup[]; series: Series[]; currency: string; label: string; height?: number;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const max = Math.max(0, ...groups.flatMap((g) => g.values));
  const { hi, ticks } = niceTicks(0, max || 1);
  const plotW = Math.max(width - M.l - M.r, 1);
  const band = plotW / Math.max(groups.length, 1);
  const barW = Math.min(24, (band * 0.7 - 2 * (series.length - 1)) / series.length);
  const y = (v: number) => M.t + ((hi - Math.max(v, 0)) / hi) * (height - M.t - M.b);
  const every = Math.max(1, Math.ceil(groups.length / Math.floor(plotW / 44)));

  return (
    <div>
      <div className="legend">
        {series.map((s) => <span key={s.name}><i style={{ background: s.color }} />{s.name}</span>)}
      </div>
      <div ref={ref} className="chart" style={{ height }}>
        {width > 0 && (
          <svg width={width} height={height} role="img" aria-label={label} onPointerLeave={() => setHover(null)}>
            {ticks.map((t) => (
              <g key={t}>
                <line x1={M.l} x2={width - M.r} y1={y(t)} y2={y(t)} className="chart-grid" />
                <text x={M.l - 8} y={y(t)} dy="0.32em" textAnchor="end" className="chart-axis">{formatCompact(t, currency)}</text>
              </g>
            ))}
            {groups.map((g, gi) => {
              const groupW = series.length * barW + (series.length - 1) * 2;
              const x0 = M.l + gi * band + (band - groupW) / 2;
              return (
                <g key={g.title} onPointerEnter={() => setHover(gi)}>
                  <rect x={M.l + gi * band} y={M.t} width={band} height={height - M.t - M.b}
                    className={hover === gi ? "chart-band chart-band-on" : "chart-band"} />
                  {g.values.map((v, si) => (
                    <path key={si} d={columnPath(x0 + si * (barW + 2), y(v), barW, y(0) - y(v))} fill={series[si].color} />
                  ))}
                  {gi % every === 0 && (
                    <text x={M.l + gi * band + band / 2} y={height - 8} textAnchor="middle" className="chart-axis">{g.label}</text>
                  )}
                </g>
              );
            })}
          </svg>
        )}
        {hover !== null && groups[hover] && (
          <div className="chart-tip" style={{ left: Math.min(Math.max(M.l + hover * band + band / 2, 90), width - 90), top: 0 }}>
            <div className="vy-muted">{groups[hover].title}</div>
            {series.map((s, si) => (
              <div key={s.name} className="chart-tip-row">
                <span><i className="chart-key" style={{ background: s.color }} />{s.name}</span>
                <strong>{formatMoney(groups[hover].values[si], { currency, decimals: 0 })}</strong>
              </div>
            ))}
          </div>
        )}
        <table className="sr-only">
          <caption>{label}</caption>
          <thead><tr><th />{series.map((s) => <th key={s.name}>{s.name}</th>)}</tr></thead>
          <tbody>{groups.map((g) => <tr key={g.title}><th>{g.title}</th>{g.values.map((v, i) => <td key={i}>{formatMoney(v, { currency })}</td>)}</tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}
