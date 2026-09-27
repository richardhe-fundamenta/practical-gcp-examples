/**
 * Runs a report query against BigQuery's REST API using the *forwarded user
 * OAuth token* (so the query executes as the signed-in user, not the service).
 * Read-only: the tool only ever issues query jobs; enforcement rides on the
 * user's IAM roles (bigquery.dataViewer + bigquery.jobUser) and the
 * bigquery.readonly OAuth scope.
 */
import type { BuiltQuery } from "./query.ts";

export interface ReportRow {
  period: string;
  dimension: string;
  revenue: number;
  orders: number;
}

export interface QueryResult {
  rows: ReportRow[];
  bytesProcessed: number;
  dryRun: boolean;
}

export interface RunOptions {
  token?: string;
  projectId?: string; // billing project for the job
  query: BuiltQuery;
  dryRun?: boolean;
  maxBytesBilled: number;
}

const endpoint = (project: string) =>
  `https://bigquery.googleapis.com/bigquery/v2/projects/${encodeURIComponent(project)}/queries`;

export async function runReportQuery(opts: RunOptions): Promise<QueryResult> {
  if (!opts.token) {
    throw new Error(
      "No user credentials were forwarded. In Gemini Enterprise, complete the " +
        "OAuth login on the data store so your access token is passed through.",
    );
  }
  if (!opts.projectId) {
    throw new Error("PROJECT_ID env var is not set (BigQuery billing project).");
  }

  const body = {
    query: opts.query.sql,
    useLegacySql: false,
    parameterMode: "NAMED",
    queryParameters: [
      param("startDate", opts.query.params.startDate),
      param("endDate", opts.query.params.endDate),
    ],
    dryRun: opts.dryRun ?? false,
    maximumBytesBilled: String(opts.maxBytesBilled),
    timeoutMs: 30_000,
  };

  const res = await fetch(endpoint(opts.projectId), {
    method: "POST",
    headers: {
      Authorization: `Bearer ${opts.token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  const data = (await res.json()) as BqQueryResponse;
  if (!res.ok) {
    throw new Error(`BigQuery error (${res.status}): ${data?.error?.message ?? "unknown"}`);
  }

  const bytesProcessed = Number(data.totalBytesProcessed ?? 0);
  if (opts.dryRun) return { rows: [], bytesProcessed, dryRun: true };

  // ponytail: no getQueryResults polling — fail loud instead of returning
  // partial/empty results. Narrow the range if a query ever exceeds 30s.
  if (!data.jobComplete) {
    throw new Error(
      "Query did not finish within 30s. Narrow the date range or use a coarser grain.",
    );
  }

  const rows: ReportRow[] = (data.rows ?? []).map((r) => ({
    period: String(r.f[0].v),
    dimension: String(r.f[1].v ?? "(none)"),
    revenue: Number(r.f[2].v ?? 0),
    orders: Number(r.f[3].v ?? 0),
  }));
  return { rows, bytesProcessed, dryRun: false };
}

function param(name: string, value: string) {
  return {
    name,
    parameterType: { type: "STRING" },
    parameterValue: { value },
  };
}

interface BqQueryResponse {
  error?: { message?: string };
  totalBytesProcessed?: string;
  jobComplete?: boolean;
  rows?: { f: { v: unknown }[] }[];
}
