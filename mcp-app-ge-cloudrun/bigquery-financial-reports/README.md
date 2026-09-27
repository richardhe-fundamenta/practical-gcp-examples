# BigQuery Financial Reports MCP App

A read-only MCP App that runs revenue reports over BigQuery and loads an
interactive dashboard in the chat — filters, chart switching, top-N,
period-over-period, and CSV export. Queries execute **as the signed-in user**
via forwarded OAuth, so people only ever see data their own IAM grants allow.

- **Tool** `run-financial-report(startDate?, endDate?, grain, dimension, dryRun?)`
  → runs one aggregated query and returns `{ rows, bytesProcessed, dryRun, params }`.
- **UI** — native date/select filters; line (trend), bar (top-N), pie (share)
  charts via Chart.js; a top-N control; a period-over-period table; a
  cost/bytes readout; and a "Download CSV" button. One fetch feeds every view;
  the UI re-invokes the tool (`app.callServerTool`) only when the dates, grain,
  or dimension change.

Data source: the public **`bigquery-public-data.thelook_ecommerce`** dataset
(`order_items` × `products` × `users`), revenue = `SUM(sale_price)` on
`status = 'Complete'`. Swap the dataset by editing the `TABLES`/`DIMENSIONS`
maps in [`src/query.ts`](src/query.ts).

## Example questions to try

Ask Gemini Enterprise any of these — the agent maps them to `run-financial-report`
and loads the dashboard, which you can then filter and re-chart yourself:

| Ask | Maps to |
|-----|---------|
| "Show me monthly revenue for the last year." | trend, `grain=month` (default range) |
| "Break down 2023 revenue by product category as a bar chart." | `dimension=category`, dates 2023 |
| "What were my top 10 brands by revenue in the last 6 months?" | `dimension=brand`, top-N |
| "Compare revenue by department quarter over quarter for 2022–2023." | `grain=quarter`, `dimension=department`, period-over-period |
| "Which traffic sources drove the most sales this year?" | `dimension=traffic_source` |
| "Show the daily revenue trend for December 2023." | `grain=day`, Dec 2023 |
| "Revenue share by country for the last quarter — as a pie chart." | `dimension=country`, pie view |
| "Before running it, estimate how much a daily 2023 report would cost." | `dryRun=true` (cost estimate only) |

Follow-ups work too, since the widget stays interactive: *"now switch to a pie
chart," "show the top 5 instead," "change the range to just Q4," "export this to
CSV."* Filter/chart tweaks happen in the widget; changing the dates, grain, or
group-by re-queries BigQuery.

## Read-only by design

- **OAuth scope** on the GE data store: `https://www.googleapis.com/auth/bigquery.readonly`.
- **IAM the user needs**: `roles/bigquery.dataViewer` + `roles/bigquery.jobUser`
  (jobUser lets them run the query job; **no** dataEditor/admin = no writes).
- **Injection-safe SQL**: the grain and group-by column come from allowlists
  ([`src/query.ts`](src/query.ts)); dates are passed as named query parameters.
- **Cost guard**: every job sets `maximumBytesBilled` (env `MAX_BYTES_BILLED`,
  default 2 GB) and `dryRun` returns only the byte/cost estimate.

The sample data is a public dataset, so there is **no import step** and nothing
to provision — which is what keeps this server strictly read-only.

## Project structure

```
bigquery-financial-reports/
├── main.ts            # transports + forwards the user's OAuth bearer token
├── server.ts          # run-financial-report tool + ui:// resource
├── report.html        # dashboard UI entry point
├── src/
│   ├── query.ts       # allowlisted, parameterized SQL builder (DOM-free)
│   ├── bigquery.ts    # BigQuery REST call using the forwarded user token
│   ├── analytics.ts   # trend / top-N / period-over-period / CSV (DOM-free)
│   ├── checks.test.ts # runnable self-check (npm test)
│   ├── report.ts      # UI logic (filters, Chart.js, re-query, export)
│   ├── global.css     # host style-variable fallbacks
│   └── report.css     # app styles
├── vite.config.ts     # bundles UI to a single self-contained HTML
└── Dockerfile         # deterministic build for Cloud Run
```

## Local development

```bash
npm install
npm test          # query-builder + analytics assertions
npm run build     # vite -> dist/report.html (single self-contained file)
npm run serve     # HTTP server on http://localhost:3001/mcp
```

Without a forwarded token the tool returns a friendly "complete the OAuth login"
error — the live query path is exercised inside Gemini Enterprise. See the
[top-level README](../README.md#testing-a-server-locally) for host/tunnel testing.

## Deploying this example to Gemini Enterprise

Follow the generic recipe in the [top-level README](../README.md#deploying-to-gemini-enterprise-google-cloud-via-cloud-run).
This example's concrete values:

| Placeholder | Value for this example |
|-------------|------------------------|
| Cloud Run service name | `bigquery-financial-reports` |
| Deploy source | run `gcloud run deploy` from **this folder** |
| Required env var | `PROJECT_ID` = your BigQuery billing project |
| Optional env var | `MAX_BYTES_BILLED` (bytes; default `2000000000`) |
| OAuth scopes (Step 4) | `openid email profile https://www.googleapis.com/auth/bigquery.readonly` |
| Tool to enable (Step 5) | `run-financial-report` |

Deploy command (from `bigquery-financial-reports/`), setting the billing project:

```bash
gcloud run deploy bigquery-financial-reports \
  --source . \
  --region us-central1 \
  --no-allow-unauthenticated \
  --set-env-vars PROJECT_ID=<YOUR_BILLING_PROJECT>
```

When creating the data store (Step 4), use these scopes and text:

**Scopes:** `openid email profile https://www.googleapis.com/auth/bigquery.readonly`

**Description:**
> Runs read-only financial reports on BigQuery and loads an interactive revenue
> dashboard (trend, top-N, period-over-period) with chart switching and CSV export.

**Instructions:**
> When the user asks to analyze, report on, chart, or break down revenue/sales,
> call the `run-financial-report` tool. Pass `startDate`/`endDate` (YYYY-MM-DD)
> when the user names a period, `grain` (day/month/quarter), and `dimension`
> (category, brand, department, traffic_source, country). The tool loads an
> interactive dashboard where the user can change filters, switch charts, and
> export CSV. Set `dryRun: true` first if the user wants a cost estimate.

> **Note:** each user must have `roles/bigquery.dataViewer` +
> `roles/bigquery.jobUser` on the billing project, and the OAuth scope must
> include `bigquery.readonly`. Queries run and bill as the signed-in user.
