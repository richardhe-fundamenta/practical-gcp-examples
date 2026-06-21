---
name: data-analysis
description: Analyze data (e.g. an uploaded CSV/Excel) with pandas and produce a chart or report file, returned to the user as an attachment.
---

# data-analysis

Use this skill when the user wants to analyze data and/or get a chart or report — especially
when they uploaded a data file.

Steps:

1. **Load** the uploaded data by filename (it's in the working directory), e.g.
   `df = pandas.read_csv("data.csv")` (or `read_excel`). Inspect columns/dtypes as needed.
2. **Compute** the requested aggregation/analysis with pandas (group-by, resample, etc.).
3. **Produce output files** — they are returned to the user as attachments:
   - Chart → save an image: `matplotlib`/`seaborn` `fig.savefig("chart.png", dpi=150, bbox_inches="tight")`.
   - Tabular report → write `report.xlsx` (`df.to_excel`) or `report.csv`.
   - Do not print raw bytes or a giant table to stdout — write a file instead.
4. **Print a short text summary** (the headline finding) to stdout alongside the file(s).
5. Call `run_code` with the full script.

Displaying charts in the UI:
- After run_code returns, any image you saved is reported back as a short **placeholder token**,
  e.g. `chart.png -> {{chart:ab12}}`. To show it, make **ONE** `send_a2ui_json_to_client` call
  whose `a2ui_json` is a JSON **list with BOTH a `beginRendering` and a `surfaceUpdate`** —
  never `beginRendering` alone (that's an empty surface). Lay the surface out top-to-bottom:
  a `title` Text, a **`thinking`** Text (2–4 short sentences explaining how you approached the
  task and what the data shows — your reasoning, in plain language), then the chart in an
  `Image` whose `url` is the **token copied EXACTLY** (it resolves to the real image).
  `Column.children` uses `{"explicitList": [<ids>]}`:
  ```json
  [
    {"beginRendering": {"surfaceId": "report", "root": "root", "styles": {}}},
    {"surfaceUpdate": {"surfaceId": "report", "components": [
      {"id": "root", "component": {"Column": {"children": {"explicitList": ["title", "thinking", "chart"]}}}},
      {"id": "title", "component": {"Text": {"text": {"literalString": "<headline>"}, "usageHint": "h3"}}},
      {"id": "thinking", "component": {"Text": {"text": {"literalString": "<2-4 sentences: how you analyzed it + what the data shows>"}}}},
      {"id": "chart", "component": {"Image": {"url": {"literalString": "{{chart:ab12}}"}}}}
    ]}}
  ]
  ```

Guidance:
- Available packages include pandas, numpy, polars, pyarrow, duckdb, scipy, scikit-learn,
  statsmodels, matplotlib, seaborn, altair, plotly, openpyxl.
- Prefer matplotlib `savefig("chart.png", ...)` so the user gets a rendered image.
- One clear chart per request unless asked otherwise; label axes and give it a title.
- No network access; work only from the uploaded data.
- **Never hardcode, reconstruct, or invent the dataset.** Analyze only the actual file in the
  working directory (open it by name). If the file isn't there, do NOT recreate it from memory —
  ask the user to attach it and stop.
- If run_code returns an error, fix the script and retry.
