/**
 * DOM-free BigQuery report query builder.
 *
 * Injection safety: SQL *identifiers* (the time grain and the group-by column)
 * are never taken from raw input — they are looked up in the allowlist maps
 * below, whose values are constants we control. User-supplied *values* (the
 * dates) are passed as named query parameters, never string-concatenated.
 */

const TABLES = {
  orderItems: "bigquery-public-data.thelook_ecommerce.order_items",
  products: "bigquery-public-data.thelook_ecommerce.products",
  users: "bigquery-public-data.thelook_ecommerce.users",
} as const;

/** Time grain -> BigQuery TIMESTAMP_TRUNC date part (allowlisted). */
export const GRAINS = { day: "DAY", month: "MONTH", quarter: "QUARTER" } as const;
export type Grain = keyof typeof GRAINS;

/** Group-by dimension -> fully-qualified column (allowlisted). */
export const DIMENSIONS = {
  category: "p.category",
  brand: "p.brand",
  department: "p.department",
  traffic_source: "u.traffic_source",
  country: "u.country",
} as const;
export type Dimension = keyof typeof DIMENSIONS;

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

export interface ReportParams {
  startDate: string; // YYYY-MM-DD (inclusive)
  endDate: string; // YYYY-MM-DD (inclusive)
  grain: Grain;
  dimension: Dimension;
}

export interface BuiltQuery {
  sql: string;
  params: { startDate: string; endDate: string };
}

export function buildReportQuery(p: ReportParams): BuiltQuery {
  if (!(p.grain in GRAINS)) throw new Error(`invalid grain: ${p.grain}`);
  if (!(p.dimension in DIMENSIONS)) {
    throw new Error(`invalid dimension: ${p.dimension}`);
  }
  if (!DATE_RE.test(p.startDate)) throw new Error(`invalid startDate: ${p.startDate}`);
  if (!DATE_RE.test(p.endDate)) throw new Error(`invalid endDate: ${p.endDate}`);
  if (p.startDate > p.endDate) throw new Error("startDate must be <= endDate");

  const grainPart = GRAINS[p.grain]; // constant, safe to inline
  const dimCol = DIMENSIONS[p.dimension]; // constant, safe to inline

  const sql = `
SELECT
  FORMAT_TIMESTAMP('%Y-%m-%d', TIMESTAMP_TRUNC(oi.created_at, ${grainPart})) AS period,
  ${dimCol} AS dimension,
  ROUND(SUM(oi.sale_price), 2) AS revenue,
  COUNT(DISTINCT oi.order_id) AS orders
FROM \`${TABLES.orderItems}\` AS oi
JOIN \`${TABLES.products}\` AS p ON oi.product_id = p.id
JOIN \`${TABLES.users}\` AS u ON oi.user_id = u.id
WHERE oi.status = 'Complete'
  AND oi.created_at >= TIMESTAMP(@startDate)
  AND oi.created_at < TIMESTAMP_ADD(TIMESTAMP(@endDate), INTERVAL 1 DAY)
  AND ${dimCol} IS NOT NULL
GROUP BY period, dimension
ORDER BY period, dimension`.trim();

  return { sql, params: { startDate: p.startDate, endDate: p.endDate } };
}
