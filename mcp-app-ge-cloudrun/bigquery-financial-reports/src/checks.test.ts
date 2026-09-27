/** Runnable self-check: `npm test`. No framework — plain node:assert. */
import assert from "node:assert/strict";
import { buildReportQuery } from "./query.ts";
import { trend, topN, periodOverPeriod, toCsv } from "./analytics.ts";
import type { ReportRow } from "./bigquery.ts";

// --- query builder: allowlisting + parameterization ---
const q = buildReportQuery({
  startDate: "2023-01-01",
  endDate: "2023-12-31",
  grain: "month",
  dimension: "category",
});
assert.match(q.sql, /TIMESTAMP_TRUNC\(oi\.created_at, MONTH\)/);
assert.match(q.sql, /p\.category AS dimension/);
assert.match(q.sql, /@startDate/);
assert.match(q.sql, /@endDate/);
assert.deepEqual(q.params, { startDate: "2023-01-01", endDate: "2023-12-31" });

// invalid inputs are rejected (defense in depth behind the zod enum)
assert.throws(() => buildReportQuery({ startDate: "2023-01-01", endDate: "2023-12-31", grain: "week" as never, dimension: "category" }));
assert.throws(() => buildReportQuery({ startDate: "2023-01-01", endDate: "2023-12-31", grain: "month", dimension: "category; DROP TABLE x" as never }));
assert.throws(() => buildReportQuery({ startDate: "not-a-date", endDate: "2023-12-31", grain: "month", dimension: "category" }));
assert.throws(() => buildReportQuery({ startDate: "2023-12-31", endDate: "2023-01-01", grain: "month", dimension: "category" }));

// --- analytics ---
const rows: ReportRow[] = [
  { period: "2023-02", dimension: "A", revenue: 30, orders: 3 },
  { period: "2023-01", dimension: "A", revenue: 100, orders: 10 },
  { period: "2023-01", dimension: "B", revenue: 50, orders: 5 },
  { period: "2023-02", dimension: "B", revenue: 20, orders: 2 },
  { period: "2023-01", dimension: "C", revenue: 10, orders: 1 },
];

const t = trend(rows);
assert.deepEqual(t.map((p) => p.period), ["2023-01", "2023-02"]); // sorted
assert.equal(t[0].revenue, 160); // 100 + 50 + 10
assert.equal(t[1].revenue, 50); // 30 + 20

const top2 = topN(rows, 2);
assert.deepEqual(top2.map((d) => d.dimension), ["A", "B", "Other"]);
assert.equal(top2[0].revenue, 130); // A across periods
assert.equal(top2[2].revenue, 10); // C folded into Other

const pop = periodOverPeriod(t);
assert.equal(pop[0].pct, null);
assert.equal(pop[1].delta, -110); // 50 - 160
assert.equal(Math.round(pop[1].pct!), -69); // -110/160

// --- CSV quoting ---
const csv = toCsv([{ period: "2023-01", dimension: 'a,"b"', revenue: 1.5, orders: 2 }]);
assert.equal(csv, 'period,dimension,revenue,orders\n2023-01,"a,""b""",1.5,2');

console.log("checks.test.ts: all assertions passed");
