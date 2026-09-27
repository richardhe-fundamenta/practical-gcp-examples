/**
 * @file Legal PDF Review UI (vanilla TS + MCP Apps SDK).
 * Flow: upload PDF -> find relevant section (LLM) -> render page image with
 * highlight overlay -> validate -> summarize -> post summary to the conversation.
 * All server work goes through app.callServerTool; the summary is returned to
 * Gemini Enterprise via app.sendMessage.
 */
import {
  App,
  applyDocumentTheme,
  applyHostFonts,
  applyHostStyleVariables,
  type McpUiHostContext,
} from "@modelcontextprotocol/ext-apps";
import type { CallToolResult } from "@modelcontextprotocol/client";
import { scaleBoxes } from "./viewer.ts";
import type { Box } from "./locate.ts";
import "./global.css";
import "./app.css";

// --- DOM ---
const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const mainEl = document.querySelector(".main") as HTMLElement;
const fileInput = $<HTMLInputElement>("file");
const uploadBtn = $<HTMLButtonElement>("upload-btn");
const docSel = $<HTMLSelectElement>("doc");
const searchForm = $<HTMLFormElement>("search-form");
const queryInput = $<HTMLInputElement>("query");
const findBtn = $<HTMLButtonElement>("find-btn");
const statusEl = $<HTMLElement>("status");
const viewer = $<HTMLElement>("viewer");
const prevBtn = $<HTMLButtonElement>("prev");
const nextBtn = $<HTMLButtonElement>("next");
const pageLabel = $<HTMLElement>("page-label");
const validateBtn = $<HTMLButtonElement>("validate-btn");
const summarizeBtn = $<HTMLButtonElement>("summarize-btn");
const pageImg = $<HTMLImageElement>("page-img");
const overlay = $<HTMLElement>("overlay");
const summaryBox = $<HTMLElement>("summary-box");
const summaryText = $<HTMLElement>("summary-text");
const sendBtn = $<HTMLButtonElement>("send-btn");

// --- state ---
let docId = "";
let pageCount = 0;
let page = 1;
let natW = 0;
let natH = 0;
let boxes: Box[] = [];
let snippet = "";

const setStatus = (m: string) => (statusEl.textContent = m);
const errMsg = (e: unknown) => (e instanceof Error ? e.message : String(e));

/** Call a server tool; throws on isError with the tool's message. */
async function call<T>(name: string, args: Record<string, unknown>): Promise<T> {
  const res = (await app.callServerTool({ name, arguments: args })) as CallToolResult;
  if (res.isError) {
    const text = res.content
      .filter((c): c is { type: "text"; text: string } => c.type === "text")
      .map((c) => c.text)
      .join(" ");
    throw new Error(text || `${name} failed`);
  }
  return res.structuredContent as T;
}

// --- overlay rendering ---
function drawOverlay(): void {
  overlay.replaceChildren();
  if (!boxes.length || !natW || !natH) return;
  const rects = scaleBoxes(natW, natH, pageImg.clientWidth, pageImg.clientHeight, boxes);
  for (const r of rects) {
    const div = document.createElement("div");
    div.className = "hl";
    div.style.left = `${r.left}px`;
    div.style.top = `${r.top}px`;
    div.style.width = `${r.width}px`;
    div.style.height = `${r.height}px`;
    overlay.appendChild(div);
  }
}
pageImg.addEventListener("load", drawOverlay);
window.addEventListener("resize", drawOverlay);

interface PageResult {
  docId: string;
  page: number;
  pageCount: number;
  widthPx: number;
  heightPx: number;
  imagePngBase64: string;
  boxes?: Box[];
  snippet?: string;
}

function showPage(res: PageResult): void {
  docId = res.docId;
  page = res.page;
  pageCount = res.pageCount;
  natW = res.widthPx;
  natH = res.heightPx;
  boxes = res.boxes ?? [];
  snippet = res.snippet ?? snippet;
  viewer.hidden = false;
  pageLabel.textContent = `Page ${page} / ${pageCount}`;
  prevBtn.disabled = page <= 1;
  nextBtn.disabled = page >= pageCount;
  pageImg.src = `data:image/png;base64,${res.imagePngBase64}`;
  // reset validation for the new view
  summarizeBtn.disabled = true;
  summaryBox.hidden = true;
}

// --- documents ---
async function refreshDocs(selectId?: string): Promise<void> {
  const { documents } = await call<{ documents: { docId: string; filename: string; pageCount: number }[] }>(
    "list-documents",
    {},
  );
  docSel.replaceChildren();
  for (const d of documents) {
    const opt = document.createElement("option");
    opt.value = d.docId;
    opt.textContent = `${d.filename} (${d.pageCount}p)`;
    docSel.appendChild(opt);
  }
  if (selectId) docSel.value = selectId;
  docId = docSel.value;
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1] ?? "");
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

async function upload(): Promise<void> {
  const file = fileInput.files?.[0];
  if (!file) {
    setStatus("Choose a PDF first.");
    return;
  }
  uploadBtn.disabled = true;
  setStatus(`Uploading “${file.name}”…`);
  try {
    const b64 = await fileToBase64(file);
    const res = await call<{ docId: string; filename: string; pageCount: number }>("upload-document", {
      filename: file.name,
      contentBase64: b64,
    });
    await refreshDocs(res.docId);
    setStatus(`Uploaded “${res.filename}” (${res.pageCount} pages). Now search for a section.`);
  } catch (e) {
    setStatus(`Upload failed: ${errMsg(e)}`);
  } finally {
    uploadBtn.disabled = false;
  }
}

async function find(): Promise<void> {
  docId = docSel.value;
  if (!docId) {
    setStatus("Upload or pick a document first.");
    return;
  }
  const query = queryInput.value.trim();
  if (!query) {
    setStatus("Type what to look for.");
    return;
  }
  findBtn.disabled = true;
  setStatus("Searching…");
  try {
    const res = await call<PageResult & { note?: string }>("find-section", { docId, query });
    showPage(res);
    setStatus(
      res.boxes && res.boxes.length
        ? "Found a match — review the highlight, then Validate."
        : "Couldn't pinpoint exact words; showing the best page. Review and Validate if right.",
    );
  } catch (e) {
    setStatus(`Search failed: ${errMsg(e)}`);
  } finally {
    findBtn.disabled = false;
  }
}

async function gotoPage(target: number): Promise<void> {
  if (target < 1 || target > pageCount) return;
  setStatus("Loading page…");
  try {
    const res = await call<PageResult>("get-page", { docId, page: target });
    boxes = []; // highlights only apply to the found page
    showPage({ ...res, boxes: [] });
    setStatus(`Page ${res.page} / ${res.pageCount}`);
  } catch (e) {
    setStatus(`Couldn't load page: ${errMsg(e)}`);
  }
}

async function doSummarize(): Promise<void> {
  summarizeBtn.disabled = true;
  setStatus("Summarizing the validated section…");
  try {
    const { summary } = await call<{ summary: string }>("summarize-section", { docId, page, snippet });
    summaryText.textContent = summary;
    summaryBox.hidden = false;
    setStatus("Summary ready. Send it to the conversation when you're happy.");
  } catch (e) {
    setStatus(`Summarize failed: ${errMsg(e)}`);
  } finally {
    summarizeBtn.disabled = false;
  }
}

async function sendSummary(): Promise<void> {
  const text = summaryText.textContent ?? "";
  if (!text) return;
  try {
    await app.sendMessage({ role: "user", content: [{ type: "text", text: `Validated summary:\n\n${text}` }] });
    setStatus("Summary sent to the conversation.");
  } catch (e) {
    setStatus(`Couldn't send: ${errMsg(e)}`);
  }
}

// --- host theming ---
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

// --- events ---
uploadBtn.addEventListener("click", () => void upload());
searchForm.addEventListener("submit", (e) => {
  e.preventDefault();
  void find();
});
prevBtn.addEventListener("click", () => void gotoPage(page - 1));
nextBtn.addEventListener("click", () => void gotoPage(page + 1));
validateBtn.addEventListener("click", () => {
  summarizeBtn.disabled = false;
  setStatus("Validated. You can now Summarize this section.");
});
summarizeBtn.addEventListener("click", () => void doSummarize());
sendBtn.addEventListener("click", () => void sendSummary());
docSel.addEventListener("change", () => (docId = docSel.value));

const app = new App({ name: "Legal PDF Review", version: "1.0.0" });
app.onteardown = async () => ({});
app.onerror = console.error;
app.onhostcontextchanged = handleHostContextChanged;

app.connect().then(() => {
  const ctx = app.getHostContext();
  if (ctx) handleHostContextChanged(ctx);
  refreshDocs().catch((e) => setStatus(`Couldn't load your documents: ${errMsg(e)}`));
});
