import {
  registerAppResource,
  registerAppTool,
  RESOURCE_MIME_TYPE,
} from "@modelcontextprotocol/ext-apps/server";
import {
  McpServer,
  type CallToolResult,
  type ReadResourceResult,
} from "@modelcontextprotocol/server";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";
import { buildReportQuery } from "./src/query.ts";
import { runReportQuery } from "./src/bigquery.ts";

// Works both from source (server.ts) and compiled (dist/server.js).
const SERVER_FILE = fileURLToPath(import.meta.url);
const DIST_DIR = SERVER_FILE.endsWith(".ts")
  ? path.join(path.dirname(SERVER_FILE), "dist")
  : path.dirname(SERVER_FILE);

const PROJECT_ID = process.env.PROJECT_ID; // BigQuery billing project
const MAX_BYTES_BILLED = Number(process.env.MAX_BYTES_BILLED ?? 2_000_000_000);

const isoDate = (d: Date) => d.toISOString().slice(0, 10);
function defaultRange(): { start: string; end: string } {
  const end = new Date();
  const start = new Date(end);
  start.setFullYear(start.getFullYear() - 1);
  return { start: isoDate(start), end: isoDate(end) };
}

/**
 * Creates an MCP server exposing a read-only BigQuery financial-reports App.
 * `userToken` is the forwarded end-user OAuth token; queries run as that user.
 */
export function createServer(userToken?: string): McpServer {
  const server = new McpServer({
    name: "BigQuery Financial Reports MCP App",
    version: "1.0.0",
  });

  const resourceUri = "ui://financial-report/report.html";

  registerAppTool(server,
    "run-financial-report",
    {
      title: "Run Financial Report",
      description:
        "Runs a read-only revenue report over the thelook_ecommerce BigQuery " +
        "public dataset and loads an interactive dashboard (trend, top-N, " +
        "period-over-period, chart switching, CSV export). Set dryRun to only " +
        "estimate the bytes/cost without running the query.",
      inputSchema: z.object({
        startDate: z.string().optional().describe("Start date YYYY-MM-DD (default: 1 year ago)"),
        endDate: z.string().optional().describe("End date YYYY-MM-DD (default: today)"),
        grain: z.enum(["day", "month", "quarter"]).default("month"),
        dimension: z
          .enum(["category", "brand", "department", "traffic_source", "country"])
          .default("category")
          .describe("Column to group revenue by"),
        dryRun: z.boolean().optional().describe("Estimate cost only; do not run"),
      }),
      outputSchema: z.object({
        rows: z.array(
          z.object({
            period: z.string(),
            dimension: z.string(),
            revenue: z.number(),
            orders: z.number(),
          }),
        ),
        bytesProcessed: z.number(),
        dryRun: z.boolean(),
        params: z.object({
          startDate: z.string(),
          endDate: z.string(),
          grain: z.string(),
          dimension: z.string(),
        }),
      }),
      _meta: { ui: { resourceUri } },
    },
    async ({ startDate, endDate, grain, dimension, dryRun }): Promise<CallToolResult> => {
      const def = defaultRange();
      const start = startDate ?? def.start;
      const end = endDate ?? def.end;
      try {
        const query = buildReportQuery({ startDate: start, endDate: end, grain, dimension });
        const result = await runReportQuery({
          token: userToken,
          projectId: PROJECT_ID,
          query,
          dryRun,
          maxBytesBilled: MAX_BYTES_BILLED,
        });

        const gb = (result.bytesProcessed / 1e9).toFixed(2);
        const usd = ((result.bytesProcessed / 1e12) * 5).toFixed(2);
        const text = result.dryRun
          ? `Dry run: this report would process ~${gb} GB (est $${usd}).`
          : `Loaded revenue by ${dimension} (${grain}), ${start} to ${end}: ` +
            `${result.rows.length} rows, ${gb} GB processed.`;

        return {
          content: [{ type: "text", text }],
          structuredContent: {
            rows: result.rows,
            bytesProcessed: result.bytesProcessed,
            dryRun: result.dryRun,
            params: { startDate: start, endDate: end, grain, dimension },
          },
        };
      } catch (e) {
        return {
          isError: true,
          content: [{ type: "text", text: e instanceof Error ? e.message : String(e) }],
        };
      }
    },
  );

  registerAppResource(server,
    resourceUri,
    resourceUri,
    { mimeType: RESOURCE_MIME_TYPE },
    async (): Promise<ReadResourceResult> => {
      const html = await fs.readFile(path.join(DIST_DIR, "report.html"), "utf-8");
      return {
        contents: [{ uri: resourceUri, mimeType: RESOURCE_MIME_TYPE, text: html }],
      };
    },
  );

  return server;
}
