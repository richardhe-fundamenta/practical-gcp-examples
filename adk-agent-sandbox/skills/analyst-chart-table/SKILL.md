---
name: analyst-chart-table
description: >-
  Use when answering a business/analytics question over already-aggregated data
  and the deliverable is a visual. Produces ONE annotated chart plus a compact
  exact-numbers table, with the headline finding as the title. Defaults to a
  single secure PNG image (no live code in the artifact). Trigger on requests
  like "show me the trend", "chart this", "visualize X by segment",
  "build a report on the numbers". Do NOT use for multi-panel dashboards or for
  fetching/validating raw SQL (the harness owns data access and validation).
---

# Analyst chart + table

This skill turns a small set of **already-validated aggregates** into a single
secure visual: one chart with the finding stated in the title, and a compact
table of the exact numbers beneath it.

## Inputs you receive
- A JSON object of aggregated rows (small — already reduced by SQL upstream).
- The business question being answered.
- Optionally: a target/prior-period value for delta context.

Do not query data here. Data arrives pre-aggregated and pre-validated from the
harness. Your job is interpretation + rendering only.

## Procedure
1. **Pick the chart type from the question shape:**
   - trend over time -> line
   - comparison across categories -> bars
   - if neither fits cleanly, default to bars and say so in the title.
2. **Derive the headline finding** — the single most decision-relevant fact
   (biggest mover, threshold crossed, outlier segment). This becomes the title,
   phrased as a conclusion ("APAC churn doubled in Q1"), never a label
   ("Churn by region").
3. **Show change, not just level** — annotate the delta vs prior period or a
   reference line. Analysts think in deltas.
4. **Generate Python rendering code** (see Execution). Pass data as JSON; never
   build markup by string-concatenating data values.
5. **Attach the compact table** of exact numbers beneath the chart.
6. **Write one plain-English "so what"** line.

## Execution

You (the model) **generate Python rendering code**; the harness runs it in an
isolated sandbox (no network, no credentials) via the `render_chart` tool.

**Data source:** The harness writes the rows from the most recent successful
validated query to `data.json` in the working directory, as:

```json
{ "rows": [ { "col": value, ... }, ... ] }
```

`rows` is a list of record dicts straight from BigQuery — these are the ONLY data
you may chart. Your code reads `data.json`, shapes/aggregates `rows` (e.g. pivot a
month/category/value layout into series), and renders. Never hardcode values and
never invent labels or numbers not present in `rows`; you cannot pass data yourself,
which guarantees the chart reflects real queried data.

**Packages:** Use ONLY preinstalled packages listed in
`references/available-packages.md`. Never `pip install`; no network access is
available in the sandbox.

**Output:** Emit exactly ONE PNG written to `output.png`. Use matplotlib with
the `Agg` backend (`matplotlib.use("Agg")`). Save with
`fig.savefig("output.png", bbox_inches="tight")`.

**Style reference:** `references/example_render.py` shows the intended
look and shape — palette (`#b07a3c`, `#5f817b`, etc.), headline-as-title
(bold, left-aligned, conclusion phrased), compact table beneath with dark header
row, and a "so what" line in italic accent colour. Adapt it; do not assume it is
present in the sandbox or call it directly.

**Safety rules for generated code:**
- Do not build markup by string-concatenating data values; treat data as data.
- No `import subprocess`, `import os.system`, network calls, or file writes
  other than `output.png`.
- The PNG default is secure: no JavaScript in the artifact, portable to
  email/PDF/chat.
- Only generate the interactive-HTML variant when hover/zoom genuinely helps AND
  the harness confirms a trusted display surface. The harness — not this skill —
  applies iframe sandboxing and CSP to any HTML output.
  See `references/output-contract.md` and `references/security-notes.md`.

## Output rule
Exactly one takeaway, stated in words, on one visual. If the data supports
several findings, pick the most decision-relevant one; do not add panels.
