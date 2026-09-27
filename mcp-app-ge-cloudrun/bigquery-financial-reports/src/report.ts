/**
 * @file BigQuery Financial Reports UI (vanilla TS + Chart.js + MCP Apps SDK).
 * One tool call fetches aggregated rows; all filtering, chart-switching,
 * top-N, period-over-period and CSV export happen client-side. Re-queries the
 * server tool only when coarse params (dates/grain/dimension) change.
 */
import {
  App,
  applyDocumentTheme,
  applyHostFonts,
  applyHostStyleVariables,
  type McpUiHostContext,
} from "@modelcontextprotocol/ext-apps";
import type { CallToolResult } from "@modelcontextprotocol/client";
import { Chart, registerables, type ChartType, type TooltipItem } from "chart.js";
import { trend, topN, periodOverPeriod, toCsv, type PoPPoint } from "./analytics.ts";
import type { ReportRow } from "./bigquery.ts";
import "./global.css";
import "./report.css";

Chart.register(...registerables);

const TOOL = "run-financial-report";
type ChartKind = "line" | "bar" | "pie";

interface ReportParams {
  startDate: string;
  endDate: string;
  grain: string;
  dimension: string;
}
interface ReportResult {
  rows: ReportRow[];
  bytesProcessed: number;
  dryRun: boolean;
  params: ReportParams;
}

// --- DOM refs ---
const mainEl = document.querySelector(".main") as HTMLElement;
const form = document.getElementById("controls") as HTMLFormElement;
const startInput = document.getElementById("start-date") as HTMLInputElement;
const endInput = document.getElementById("end-date") as HTMLInputElement;
const grainSel = document.getElementById("grain") as HTMLSelectElement;
const dimSel = document.getElementById("dimension") as HTMLSelectElement;
const runBtn = document.getElementById("run-btn") as HTMLButtonElement;
const estimateBtn = document.getElementById("estimate-btn") as HTMLButtonElement;
const topnInput = document.getElementById("topn") as HTMLInputElement;
const csvBtn = document.getElementById("csv-btn") as HTMLButtonElement;
const statusEl = document.getElementById("status") as HTMLElement;
const canvas = document.getElementById("chart") as HTMLCanvasElement;
const popTable = document.getElementById("pop-table") as HTMLTableElement;
const popBody = popTable.querySelector("tbody") as HTMLTableSectionElement;

// --- state ---
let rows: ReportRow[] = [];
let chartKind: ChartKind = "line";
let chart: Chart | undefined;

// --- formatting ---
const usdFmt = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});
const usd = (v: number) => usdFmt.format(v);

function costLine(bytes: number): string {
  const gb = (bytes / 1e9).toFixed(2);
  const cost = ((bytes / 1e12) * 5).toFixed(2);
  return `${gb} GB processed (est $${cost})`;
}

function cssVar(name: string, fallback: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
}
const palette = (i: number) => `hsl(${(i * 57) % 360} 65% 55%)`;

function setStatus(msg: string): void {
  statusEl.textContent = msg;
}

// --- controls <-> params ---
function readControls(): ReportParams {
  return {
    startDate: startInput.value,
    endDate: endInput.value,
    grain: grainSel.value,
    dimension: dimSel.value,
  };
}
function applyParams(p: ReportParams): void {
  startInput.value = p.startDate;
  endInput.value = p.endDate;
  grainSel.value = p.grain;
  dimSel.value = p.dimension;
}
function clampTopN(): number {
  const n = parseInt(topnInput.value, 10);
  return Number.isFinite(n) ? Math.min(20, Math.max(1, n)) : 8;
}

// --- rendering ---
// Loose return type: options shape differs across line/bar/pie; Chart.js's
// generic ChartOptions<T> makes a shared builder painful to type precisely.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function baseOptions(moneyAxis: boolean): any {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: !moneyAxis },
      tooltip: {
        callbacks: {
          label: (item: TooltipItem<ChartType>) => ` ${usd(Number(item.raw ?? 0))}`,
        },
      },
    },
    scales: moneyAxis
      ? { y: { ticks: { callback: (v: string | number) => usd(Number(v)) } } }
      : undefined,
  };
}

function renderChart(kind: ChartKind): void {
  chartKind = kind;
  document.querySelectorAll<HTMLButtonElement>(".chip").forEach((b) =>
    b.classList.toggle("active", b.dataset.chart === kind),
  );
  chart?.destroy();
  const accent = cssVar("--color-accent", "#2563eb");
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  if (kind === "line") {
    const series = trend(rows);
    chart = new Chart(ctx, {
      type: "line",
      data: {
        labels: series.map((p) => p.period),
        datasets: [
          {
            label: "Revenue",
            data: series.map((p) => p.revenue),
            borderColor: accent,
            backgroundColor: accent,
            tension: 0.25,
          },
        ],
      },
      options: baseOptions(true),
    });
    renderPopTable(periodOverPeriod(series));
    popTable.hidden = series.length === 0;
    return;
  }

  const totals = topN(rows, clampTopN());
  const colors = totals.map((_, i) => palette(i));
  chart = new Chart(ctx, {
    type: kind as ChartType,
    data: {
      labels: totals.map((d) => d.dimension),
      datasets: [
        {
          label: "Revenue",
          data: totals.map((d) => d.revenue),
          backgroundColor: kind === "bar" ? accent : colors,
          borderColor: kind === "bar" ? accent : colors,
        },
      ],
    },
    options: baseOptions(kind === "bar"),
  });
  popTable.hidden = true;
}

function renderPopTable(points: PoPPoint[]): void {
  popBody.replaceChildren();
  for (const p of points) {
    const tr = document.createElement("tr");
    const pct = p.pct === null ? "—" : `${p.pct >= 0 ? "+" : ""}${p.pct.toFixed(1)}%`;
    const delta = p.delta === 0 && p.pct === null ? "—" : usd(p.delta);
    for (const text of [p.period, usd(p.revenue), delta, pct]) {
      const td = document.createElement("td");
      td.textContent = text;
      tr.appendChild(td);
    }
    popBody.appendChild(tr);
  }
}

// --- server tool call ---
function textOf(result: CallToolResult): string {
  return result.content
    .filter((c): c is { type: "text"; text: string } => c.type === "text")
    .map((c) => c.text)
    .join(" ");
}

const errMsg = (e: unknown) => (e instanceof Error ? e.message : String(e));

/** Render a tool result (from a direct call or a model-triggered re-run). */
function applyResult(sc: ReportResult | undefined): void {
  if (!sc) {
    setStatus("No data returned.");
    return;
  }
  if (sc.dryRun) {
    setStatus(`${costLine(sc.bytesProcessed)} — press “Run report” to execute.`);
    return;
  }
  rows = sc.rows;
  setStatus(`${rows.length} rows · ${costLine(sc.bytesProcessed)}`);
  renderChart(chartKind);
}

/** Fallback when the host doesn't allow app->server tool calls: ask the model
 *  to re-run the tool. Note this usually renders a fresh widget rather than
 *  updating this one. */
async function requestViaModel(args: ReturnType<typeof readControls>, dryRun: boolean): Promise<void> {
  const range = `${args.startDate} to ${args.endDate}`;
  const text = dryRun
    ? `Estimate the cost (dryRun) of the financial report from ${range}, grain ${args.grain}, grouped by ${args.dimension}.`
    : `Run the financial report from ${range}, grain ${args.grain}, grouped by ${args.dimension}.`;
  await app.sendMessage({ role: "user", content: [{ type: "text", text }] });
  setStatus("Asked the assistant to re-run with these filters…");
}

async function runReport(dryRun = false): Promise<void> {
  const args = readControls();
  setStatus(dryRun ? "Estimating…" : "Running query…");
  runBtn.disabled = estimateBtn.disabled = true;
  try {
    // Prefer a direct server call so the widget updates in place. Not every
    // host advertises the serverTools capability, so we try regardless and
    // fall back to a model round-trip if the call is rejected.
    const res = await app.callServerTool({ name: TOOL, arguments: { ...args, dryRun } });
    if (res.isError) {
      setStatus(textOf(res) || "Query failed.");
      return;
    }
    applyResult(res.structuredContent as ReportResult | undefined);
  } catch (e) {
    try {
      await requestViaModel(args, dryRun);
    } catch (e2) {
      setStatus(`Couldn't re-run in-app (${errMsg(e)}); asking the model failed too (${errMsg(e2)}).`);
    }
  } finally {
    runBtn.disabled = estimateBtn.disabled = false;
  }
}

function downloadCsv(): void {
  if (rows.length === 0) {
    setStatus("Nothing to export — run a report first.");
    return;
  }
  // data: URL (not blob:) — GE's iframe CSP forbids blob: URLs.
  const a = document.createElement("a");
  a.href = "data:text/csv;charset=utf-8," + encodeURIComponent(toCsv(rows));
  a.download = "financial-report.csv";
  a.click();
}

// --- host theming (same pattern as the color-picker example) ---
function handleHostContextChanged(ctx: McpUiHostContext): void {
  if (ctx.theme) applyDocumentTheme(ctx.theme);
  if (ctx.styles?.variables) applyHostStyleVariables(ctx.styles.variables);
  if (ctx.styles?.css?.fonts) applyHostFonts(ctx.styles.css.fonts);
  if (ctx.safeAreaInsets) {
    mainEl.style.paddingTop = `${ctx.safeAreaInsets.top}px`;
    mainEl.style.paddingRight = `${ctx.safeAreaInsets.right}px`;
    mainEl.style.paddingBottom = `${ctx.safeAreaInsets.bottom}px`;
    mainEl.style.paddingLeft = `${ctx.safeAreaInsets.left}px`;
  }
}

// --- default date range so controls are populated before the first query ---
function seedDefaultDates(): void {
  if (endInput.value && startInput.value) return;
  const end = new Date();
  const start = new Date(end);
  start.setFullYear(start.getFullYear() - 1);
  endInput.value = end.toISOString().slice(0, 10);
  startInput.value = start.toISOString().slice(0, 10);
}

// --- events ---
form.addEventListener("submit", (e) => {
  e.preventDefault();
  void runReport(false);
});
estimateBtn.addEventListener("click", () => void runReport(true));
csvBtn.addEventListener("click", downloadCsv);
topnInput.addEventListener("change", () => {
  if (chartKind !== "line") renderChart(chartKind);
});
document.querySelectorAll<HTMLButtonElement>(".chip").forEach((b) =>
  b.addEventListener("click", () => renderChart(b.dataset.chart as ChartKind)),
);

const app = new App({ name: "Financial Reports", version: "1.0.0" });
app.onteardown = async () => ({});
app.onerror = console.error;
app.onhostcontextchanged = handleHostContextChanged;
app.ontoolresult = (result) => {
  const sc = result.structuredContent as ReportResult | undefined;
  if (!sc) return;
  applyParams(sc.params);
  applyResult(sc);
};

seedDefaultDates();

app.connect().then(() => {
  const ctx = app.getHostContext();
  if (ctx) handleHostContextChanged(ctx);
});
