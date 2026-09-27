# Legal PDF Review MCP App

An MCP App for **legal professionals**: upload a PDF, ask an LLM to find the
relevant passage, review it **highlighted on the rendered page**, validate it,
then send a summary back into the Gemini Enterprise conversation.

The review loop: **upload → find → validate → summarize → back to the chat.**

## How it works

- **Upload** a PDF from the app UI. It's stored in Cloud Storage under the
  signed-in user's own prefix, and a text + coordinate index is extracted.
- **Find** a section in natural language ("What are the indemnification
  obligations?"). Vertex AI Gemini locates the passage; the server maps it to
  bounding boxes and renders that page as an image.
- **Highlight** boxes are drawn over the page image in the browser. Coordinates
  come from the extraction index, never the model — so a highlight can't land
  on hallucinated text.
- **Validate** the highlight, then **Summarize** the passage. The summary is
  posted into the conversation via `sendMessage`.

## Design choices

- **Server-side rendering, not PDF.js.** Pages are rasterized to PNG on the
  server (PyMuPDF); the UI shows `<img>` + overlay boxes. This sidesteps the
  Gemini Enterprise iframe CSP, which forbids `unsafe-eval`, Web Workers, and
  `blob:` URLs.
- **TypeScript server + Python helper.** The MCP server is TypeScript (same
  pattern as the other examples); a small `python/pdf_tool.py` (PyMuPDF, run via
  `uv`) does text-extraction-with-coordinates and page rasterization.
- **Identity vs. access.** The forwarded user OAuth token is used *only* to
  identify the user (`userinfo` → `sub`, `email`). All Cloud Storage and Vertex
  access uses the Cloud Run runtime service account; per-user isolation is
  enforced in code with the `{sub}/` object prefix. The user's OAuth scopes stay
  minimal (`openid email`).
- **Native/text PDFs only** (MVP). Scanned/OCR documents are a future extension
  (Document AI).

## Read-only-ish by design

Users can only read/write **their own** prefix (`gs://<bucket>/{sub}/…`); the
`docId` is validated so it can't escape that prefix. The token never grants the
app direct data access — the service account does, gated by IAM.

## Try it: end-to-end walkthrough

A synthetic contract is included so you can exercise the full loop without
sourcing a real document: [`examples/sample-msa.pdf`](examples/sample-msa.pdf) —
a 3-page Master Services Agreement between *Altostrat Holdings, Inc.* and
*Cymbal Consulting LLC*, with numbered clauses for Indemnification (§4),
Limitation of Liability (§5), Termination for Convenience (§7), and Governing
Law and Venue (§8). It's a native/text PDF, so extraction and highlighting work
out of the box.

Once the app is attached to your Gemini Enterprise engine:

1. **Open the app.** Ask *"Open the legal PDF review app."* The UI launches.
2. **Upload.** Click the file picker, choose `examples/sample-msa.pdf`, and
   upload. The app stores it under your `{sub}/` prefix and builds the index.
3. **Find a clause.** Ask *"In my uploaded contract, what are the
   indemnification obligations?"* The app runs `find-section`, jumps to page 1,
   and highlights the §4 Indemnification paragraph on the rendered page.
4. **Validate.** Read the highlighted text against the model's answer. If it's
   the right passage, click **Validate**. (Highlights come from the extraction
   index, not the model, so the box always sits on real text.)
5. **Cross-check another clause.** Ask *"Where is the termination for
   convenience clause?"* — the app highlights §7 on page 2. Try *"What's the
   governing law and venue?"* to land on §8 (Delaware; Wilmington courts).
6. **Summarize back to the chat.** Click **Summarize**, review, then **Send**.
   `summarize-section` posts the validated summary into the Gemini Enterprise
   conversation via `sendMessage`.

Expected: indemnification and governing-law highlights on the pages noted above,
and a plain-language summary appearing back in the chat once you send it.

## Example questions to try

Ask Gemini Enterprise things like:

| You ask | What the app does |
|---------|-------------------|
| "Open the legal PDF review app." | Launches the UI to upload/select a document. |
| "In my uploaded contract, what are the indemnification obligations?" | `find-section` → highlights the clause on its page. |
| "Where is the termination for convenience clause?" | Finds + highlights that section. |
| "Summarize the highlighted section." | `summarize-section` → posts a summary back to the chat. |
| "What's the governing law and venue?" | Finds + highlights the governing-law clause. |

(Upload happens in the app UI via the file picker — PDFs aren't sent through the
chat.)

## Project structure

```
legal-pdf-review/
  pyproject.toml / uv.lock   # Python deps (PyMuPDF), managed by uv
  python/pdf_tool.py         # extract (text+boxes) | render (page PNG)
  main.ts                    # HTTP entry; extracts the forwarded token
  server.ts                  # 5 tools + UI resource; orchestration
  src/identity.ts            # userinfo(token) -> sub, email
  src/storage.ts             # GCS + per-user prefix enforcement
  src/pdf.ts                 # bridge to python/pdf_tool.py
  src/locate.ts              # passage -> bounding boxes (pure)
  src/llm.ts                 # Vertex Gemini find + summarize
  src/viewer.ts              # highlight overlay scaling (pure)
  src/app.ts                 # UI wiring
  app.html                   # UI markup (built to dist/app.html)
```

## Tools

| Tool | Purpose |
|------|---------|
| `upload-document` | Store a base64 PDF + build the index. |
| `list-documents` | List the user's uploaded PDFs. |
| `find-section` | LLM finds a passage; returns the page image + highlight boxes. |
| `get-page` | Return a page image for navigation. |
| `summarize-section` | Summarize the validated passage. |

## Testing locally

```bash
uv run python python/test_pdf_tool.py   # PyMuPDF extract/render self-check
npm install
npm test                                 # pure-logic self-check (locate, scaling, prompts)
npm run build                            # typecheck + build dist/app.html
```

See the [root README](../README.md#testing-a-server-locally) for running the
server over HTTP and calling it with an MCP client.

## Deploying to Gemini Enterprise

Follow the generic recipe in the
[root README](../README.md#deploying-to-gemini-enterprise-google-cloud-via-cloud-run).
Values specific to this app:

- **Service name:** `legal-pdf-review`
- **Env vars:** `PROJECT_ID`, `BUCKET`, `VERTEX_LOCATION` (e.g. `us-central1`),
  `MAX_UPLOAD_MB` (default `20`)
- **OAuth scopes:** `openid`, `email` (identity only)
- **One-time GCP setup:**
  ```bash
  # Bucket (SA-owned; app enforces per-user prefixes)
  gcloud storage buckets create gs://<PROJECT_ID>-legal-pdf-review \
    --location us-central1 --uniform-bucket-level-access

  # Runtime SA needs storage + Vertex
  gcloud storage buckets add-iam-policy-binding gs://<PROJECT_ID>-legal-pdf-review \
    --member "serviceAccount:<RUNTIME_SA>" --role roles/storage.objectAdmin
  gcloud projects add-iam-policy-binding <PROJECT_ID> \
    --member "serviceAccount:<RUNTIME_SA>" --role roles/aiplatform.user
  ```
- After deploy, grant the Discovery Engine SA `run.invoker` and **attach the
  resulting data store to your Gemini Enterprise engine** (creating the data
  store is not enough — it must be attached to the app).
