/** DOM-free client-side data shaping: one fetch, many views. */
import type { ReportRow } from "./bigquery.ts";

export interface TrendPoint {
  period: string;
  revenue: number;
  orders: number;
}
export interface PoPPoint extends TrendPoint {
  delta: number;
  pct: number | null; // null when the previous period had zero revenue
}
export interface DimTotal {
  dimension: string;
  revenue: number;
  orders: number;
}

/** Revenue/orders summed across dimensions, one point per period (sorted). */
export function trend(rows: ReportRow[]): TrendPoint[] {
  const byPeriod = new Map<string, TrendPoint>();
  for (const r of rows) {
    const t = byPeriod.get(r.period) ?? { period: r.period, revenue: 0, orders: 0 };
    t.revenue += r.revenue;
    t.orders += r.orders;
    byPeriod.set(r.period, t);
  }
  return [...byPeriod.values()].sort((a, b) => a.period.localeCompare(b.period));
}

/** Totals per dimension value, top N by revenue; remainder folded into "Other". */
export function topN(rows: ReportRow[], n: number): DimTotal[] {
  const byDim = new Map<string, DimTotal>();
  for (const r of rows) {
    const d = byDim.get(r.dimension) ?? { dimension: r.dimension, revenue: 0, orders: 0 };
    d.revenue += r.revenue;
    d.orders += r.orders;
    byDim.set(r.dimension, d);
  }
  const sorted = [...byDim.values()].sort((a, b) => b.revenue - a.revenue);
  if (n <= 0 || sorted.length <= n) return sorted;
  const other = sorted.slice(n).reduce(
    (acc, d) => ({ dimension: "Other", revenue: acc.revenue + d.revenue, orders: acc.orders + d.orders }),
    { dimension: "Other", revenue: 0, orders: 0 },
  );
  return [...sorted.slice(0, n), other];
}

/** Period-over-period absolute + percentage change on a trend series. */
export function periodOverPeriod(series: TrendPoint[]): PoPPoint[] {
  return series.map((p, i) => {
    if (i === 0) return { ...p, delta: 0, pct: null };
    const prev = series[i - 1].revenue;
    const delta = p.revenue - prev;
    return { ...p, delta, pct: prev === 0 ? null : (delta / prev) * 100 };
  });
}

/** Raw rows -> CSV text (RFC-4180 quoting). */
export function toCsv(rows: ReportRow[]): string {
  const header = "period,dimension,revenue,orders";
  const body = rows
    .map((r) => `${r.period},${csvCell(r.dimension)},${r.revenue},${r.orders}`)
    .join("\n");
  return `${header}\n${body}`;
}

function csvCell(s: string): string {
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}
