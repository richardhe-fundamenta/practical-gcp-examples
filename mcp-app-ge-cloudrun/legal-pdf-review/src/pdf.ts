/**
 * Bridge to the Python PyMuPDF helper (python/pdf_tool.py). Native/text PDFs
 * only. We keep PyMuPDF in Python because it does text-with-coordinates and
 * page rasterization in one clean library; everything else stays in TS.
 */
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

export interface Word {
  text: string;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}
export interface PageIndex {
  page: number;
  widthPx: number;
  heightPx: number;
  words: Word[];
}
export interface DocIndex {
  renderDpi: number;
  pageCount: number;
  pages: PageIndex[];
}

const HERE = path.dirname(fileURLToPath(import.meta.url));
// src/ at runtime (tsx) -> ../python ; dist build keeps python/ alongside.
const PDF_TOOL = path.resolve(HERE, "..", "python", "pdf_tool.py");

/** Run pdf_tool.py <args>, resolving with its stdout buffer. */
function runTool(args: string[]): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    // `uv run` uses the pyproject in the app root (cwd of the server process).
    const child = spawn("uv", ["run", "python", PDF_TOOL, ...args], {
      stdio: ["ignore", "pipe", "pipe"],
    });
    const out: Buffer[] = [];
    const err: Buffer[] = [];
    child.stdout.on("data", (d: Buffer) => out.push(d));
    child.stderr.on("data", (d: Buffer) => err.push(d));
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) resolve(Buffer.concat(out));
      else reject(new Error(`pdf_tool ${args[0]} failed (${code}): ${Buffer.concat(err)}`));
    });
  });
}

export async function extractIndex(pdfPath: string): Promise<DocIndex> {
  const out = await runTool(["extract", pdfPath]);
  return JSON.parse(out.toString("utf-8")) as DocIndex;
}

export async function renderPage(pdfPath: string, page: number): Promise<Buffer> {
  return runTool(["render", pdfPath, String(page)]);
}
