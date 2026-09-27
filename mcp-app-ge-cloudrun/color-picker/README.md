# Color Picker MCP App

The simplest example in this repo: an [MCP App](https://modelcontextprotocol.io/extensions/apps/build)
that displays an interactive color picker inside an MCP-capable host (Claude,
Gemini Enterprise, etc.). It combines an MCP **tool** with a bundled HTML **UI
resource** — the host calls the tool, then renders the UI in a sandboxed iframe.

- **Tool** `pick-color` — optional `initialColor` (hex) → `{ color }` as `#rrggbb`.
- **UI** — native `<input type="color">`, a live swatch, a synced hex field, an
  RGB readout, and a "Use this color" button that reports the choice back to the
  model via `app.sendMessage`.

![Color picker MCP App demo](demo.gif)

## Project structure

```
color-picker/
├── main.ts            # transports: Streamable HTTP (default) + stdio
├── server.ts          # MCP server: pick-color tool + ui:// resource
├── mcp-app.html       # UI entry point
├── src/
│   ├── mcp-app.ts     # UI logic (App class, host communication)
│   ├── color.ts       # DOM-free hex validate/normalize + hexToRgb
│   ├── color.test.ts  # runnable self-check (npm test)
│   ├── global.css     # host style-variable fallbacks
│   └── mcp-app.css    # app styles
├── vite.config.ts     # bundles UI to a single self-contained HTML
├── Dockerfile         # deterministic build for Cloud Run
└── dist/mcp-app.html  # build output (git-ignored)
```

## Local development

```bash
npm install
npm test          # color-helper assertions
npm run build     # vite -> dist/mcp-app.html (single self-contained file)
npm run serve     # HTTP server on http://localhost:3001/mcp
# npm run start   # build + serve
# npm run dev     # watch build + watch server
# npm run serve:stdio   # stdio transport instead of HTTP
```

The server honors `$PORT` (default `3001`) and binds `0.0.0.0`.

See the [top-level README](../README.md#testing-a-server-locally) for how to
test the UI against a reference host or a tunnel.

## Deploying this example to Gemini Enterprise

Follow the generic recipe in the [top-level README](../README.md#deploying-to-gemini-enterprise-google-cloud-via-cloud-run)
(prerequisites, org-policy constraint, OAuth client, IAM). This example's
concrete values:

| Placeholder | Value for this example |
|-------------|------------------------|
| Cloud Run service name | `color-picker-mcp` |
| Deploy source | run `gcloud run deploy` from **this folder** (`color-picker/`) |
| Tool to enable (Step 5) | `pick-color` |

Deploy command (from `color-picker/`):

```bash
gcloud run deploy color-picker-mcp \
  --source . \
  --region us-central1 \
  --no-allow-unauthenticated
```

When creating the data store (Step 4), use:

**Description:**
> An interactive color picker. Returns a selected color as a hex value and loads
> an interactive HTML widget with a native color picker, a live swatch, and
> synced hex/RGB readouts.

**Instructions:**
> When the user wants to pick, choose, preview, or adjust a color, call the
> `pick-color` tool (optionally passing `initialColor` as a hex string to seed
> it). The tool returns a text summary and loads the interactive Color Picker
> widget in the chat. Tell the user the widget is available and that they can
> drag the picker or type a hex value, then click "Use this color" to confirm
> their choice.
