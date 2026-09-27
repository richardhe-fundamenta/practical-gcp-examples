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
import { randomUUID } from "node:crypto";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";
import { getIdentity } from "./src/identity.ts";
import { extractIndex, renderPage, type DocIndex } from "./src/pdf.ts";
import { locatePassage } from "./src/locate.ts";
import { findSection, summarize, indexToText } from "./src/llm.ts";
import {
  writeDoc,
  writeIndex,
  writeMeta,
  readDoc,
  readIndex,
  listDocs,
  getOrRenderPage,
  type DocMeta,
} from "./src/storage.ts";

const SERVER_FILE = fileURLToPath(import.meta.url);
const DIST_DIR = SERVER_FILE.endsWith(".ts")
  ? path.join(path.dirname(SERVER_FILE), "dist")
  : path.dirname(SERVER_FILE);

const MAX_UPLOAD_MB = Number(process.env.MAX_UPLOAD_MB ?? 20);
const PDF_MAGIC = Buffer.from("%PDF-");

const errorResult = (e: unknown): CallToolResult => ({
  isError: true,
  content: [{ type: "text", text: e instanceof Error ? e.message : String(e) }],
});

/** Run `fn` with the doc's PDF downloaded to a temp path; always clean up. */
async function withTempPdf<T>(
  sub: string,
  docId: string,
  fn: (pdfPath: string) => Promise<T>,
): Promise<T> {
  const pdf = await readDoc(sub, docId);
  const tmp = path.join(os.tmpdir(), `${randomUUID()}.pdf`);
  await fs.writeFile(tmp, pdf);
  try {
    return await fn(tmp);
  } finally {
    await fs.rm(tmp, { force: true });
  }
}

async function pageImage(
  sub: string,
  docId: string,
  index: DocIndex,
  page: number,
): Promise<{ page: number; widthPx: number; heightPx: number; imagePngBase64: string }> {
  const pg = index.pages.find((p) => p.page === page) ?? index.pages[0];
  const png = await getOrRenderPage(sub, docId, pg.page, () =>
    withTempPdf(sub, docId, (pdfPath) => renderPage(pdfPath, pg.page)),
  );
  return {
    page: pg.page,
    widthPx: pg.widthPx,
    heightPx: pg.heightPx,
    imagePngBase64: png.toString("base64"),
  };
}

export function createServer(userToken?: string): McpServer {
  const server = new McpServer({
    name: "Legal PDF Review MCP App",
    version: "1.0.0",
  });
  const resourceUri = "ui://legal-pdf-review/app.html";
  const ui = { _meta: { ui: { resourceUri } } };

  registerAppTool(server,
    "upload-document",
    {
      title: "Upload PDF",
      description:
        "Upload a PDF (base64) for review. Stores it in the signed-in user's " +
        "private space and extracts a searchable text+coordinate index. Native " +
        "text PDFs only (no scanned/OCR).",
      inputSchema: z.object({
        filename: z.string().describe("Original file name"),
        contentBase64: z.string().describe("PDF file contents, base64-encoded"),
      }),
      outputSchema: z.object({
        docId: z.string(),
        filename: z.string(),
        pageCount: z.number(),
      }),
      ...ui,
    },
    async ({ filename, contentBase64 }): Promise<CallToolResult> => {
      try {
        const { sub, email } = await getIdentity(userToken);
        const pdf = Buffer.from(contentBase64, "base64");
        if (pdf.length > MAX_UPLOAD_MB * 1024 * 1024) {
          throw new Error(`File is too large (max ${MAX_UPLOAD_MB} MB).`);
        }
        if (!pdf.subarray(0, 5).equals(PDF_MAGIC)) {
          throw new Error("That file is not a PDF.");
        }
        const docId = randomUUID();
        const tmp = path.join(os.tmpdir(), `${docId}.pdf`);
        await fs.writeFile(tmp, pdf);
        let index: DocIndex;
        try {
          index = await extractIndex(tmp);
        } finally {
          await fs.rm(tmp, { force: true });
        }
        const meta: DocMeta = {
          docId,
          filename,
          pageCount: index.pageCount,
          uploadedAt: new Date().toISOString(),
        };
        await writeDoc(sub, docId, pdf, email);
        await writeIndex(sub, docId, index);
        await writeMeta(sub, docId, meta);
        return {
          content: [{ type: "text", text: `Uploaded “${filename}” (${index.pageCount} pages).` }],
          structuredContent: { docId, filename, pageCount: index.pageCount },
        };
      } catch (e) {
        return errorResult(e);
      }
    },
  );

  registerAppTool(server,
    "list-documents",
    {
      title: "List documents",
      description: "List the PDFs the signed-in user has uploaded.",
      inputSchema: z.object({}),
      outputSchema: z.object({
        documents: z.array(
          z.object({
            docId: z.string(),
            filename: z.string(),
            pageCount: z.number(),
            uploadedAt: z.string(),
          }),
        ),
      }),
      ...ui,
    },
    async (): Promise<CallToolResult> => {
      try {
        const { sub } = await getIdentity(userToken);
        const documents = await listDocs(sub);
        return {
          content: [{ type: "text", text: `${documents.length} document(s).` }],
          structuredContent: { documents },
        };
      } catch (e) {
        return errorResult(e);
      }
    },
  );

  registerAppTool(server,
    "find-section",
    {
      title: "Find relevant section",
      description:
        "Use the LLM to find the passage most relevant to a query in a document, " +
        "and return the page image with highlight boxes over the passage.",
      inputSchema: z.object({
        docId: z.string(),
        query: z.string().describe("What to look for, in natural language"),
      }),
      outputSchema: z.object({
        docId: z.string(),
        page: z.number(),
        pageCount: z.number(),
        snippet: z.string(),
        boxes: z.array(z.object({ x0: z.number(), y0: z.number(), x1: z.number(), y1: z.number() })),
        widthPx: z.number(),
        heightPx: z.number(),
        imagePngBase64: z.string(),
      }),
      ...ui,
    },
    async ({ docId, query }): Promise<CallToolResult> => {
      try {
        const { sub } = await getIdentity(userToken);
        const index = await readIndex<DocIndex>(sub, docId);
        const passage = await findSection(indexToText(index), query);
        const located = locatePassage(index, passage);
        const img = await pageImage(sub, docId, index, located.page);
        const note = located.boxes.length
          ? `Found on page ${img.page}.`
          : `Couldn't pinpoint the exact words — showing page ${img.page}.`;
        return {
          content: [{ type: "text", text: note }],
          structuredContent: {
            docId,
            page: img.page,
            pageCount: index.pageCount,
            snippet: located.boxes.length ? located.snippet : passage,
            boxes: located.boxes,
            widthPx: img.widthPx,
            heightPx: img.heightPx,
            imagePngBase64: img.imagePngBase64,
          },
        };
      } catch (e) {
        return errorResult(e);
      }
    },
  );

  registerAppTool(server,
    "get-page",
    {
      title: "Get page image",
      description: "Return a rendered page image for navigation.",
      inputSchema: z.object({ docId: z.string(), page: z.number() }),
      outputSchema: z.object({
        docId: z.string(),
        page: z.number(),
        pageCount: z.number(),
        widthPx: z.number(),
        heightPx: z.number(),
        imagePngBase64: z.string(),
      }),
      ...ui,
    },
    async ({ docId, page }): Promise<CallToolResult> => {
      try {
        const { sub } = await getIdentity(userToken);
        const index = await readIndex<DocIndex>(sub, docId);
        const img = await pageImage(sub, docId, index, page);
        return {
          content: [{ type: "text", text: `Page ${img.page} of ${index.pageCount}.` }],
          structuredContent: { docId, pageCount: index.pageCount, ...img },
        };
      } catch (e) {
        return errorResult(e);
      }
    },
  );

  registerAppTool(server,
    "summarize-section",
    {
      title: "Summarize section",
      description:
        "Summarize a validated passage for the lawyer. The UI posts the result " +
        "back into the conversation.",
      inputSchema: z.object({
        docId: z.string(),
        page: z.number(),
        snippet: z.string().describe("The validated passage text"),
      }),
      outputSchema: z.object({ summary: z.string() }),
      ...ui,
    },
    async ({ snippet }): Promise<CallToolResult> => {
      try {
        await getIdentity(userToken); // authorize
        const summary = await summarize(snippet);
        return {
          content: [{ type: "text", text: summary }],
          structuredContent: { summary },
        };
      } catch (e) {
        return errorResult(e);
      }
    },
  );

  registerAppResource(server,
    resourceUri,
    resourceUri,
    { mimeType: RESOURCE_MIME_TYPE },
    async (): Promise<ReadResourceResult> => {
      const html = await fs.readFile(path.join(DIST_DIR, "app.html"), "utf-8");
      return { contents: [{ uri: resourceUri, mimeType: RESOURCE_MIME_TYPE, text: html }] };
    },
  );

  return server;
}
