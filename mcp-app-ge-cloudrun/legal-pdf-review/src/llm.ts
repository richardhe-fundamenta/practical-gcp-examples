/**
 * Vertex AI Gemini: find the relevant passage and summarize it. Prompt builders
 * are pure (unit-tested); the network calls are thin. `findSection` returns the
 * passage TEXT only — the caller re-locates it in the word index to get boxes,
 * so highlight coordinates never come from the model.
 */
import { GoogleGenAI } from "@google/genai";
import type { DocIndex } from "./pdf.ts";

const MODEL = process.env.GEMINI_MODEL ?? "gemini-3.5-flash";

/** Flatten the index to plain text with `--- page N ---` markers. */
export function indexToText(index: DocIndex): string {
  return index.pages
    .map((p) => `--- page ${p.page} ---\n${p.words.map((w) => w.text).join(" ")}`)
    .join("\n\n");
}

export function buildFindPrompt(indexText: string, query: string): string {
  return [
    "You are helping a legal professional locate a passage in a document.",
    "Return the EXACT verbatim passage from the document that best answers the",
    "request — copy the words as they appear, no paraphrasing, no quotes, no",
    "commentary. Keep it to the relevant sentence(s).",
    "",
    `Request: ${query}`,
    "",
    "Document:",
    indexText,
  ].join("\n");
}

export function buildSummaryPrompt(passage: string): string {
  return [
    "Summarize the following passage from a legal document for a lawyer.",
    "Be concise and precise; preserve defined terms and obligations. Do not add",
    "information that is not in the passage.",
    "",
    "Passage:",
    passage,
  ].join("\n");
}

let _ai: GoogleGenAI | undefined;
function ai(): GoogleGenAI {
  if (!_ai) {
    _ai = new GoogleGenAI({
      vertexai: true,
      project: process.env.PROJECT_ID,
      location: process.env.VERTEX_LOCATION ?? "europe-west2",
    });
  }
  return _ai;
}

async function generate(prompt: string): Promise<string> {
  const res = await ai().models.generateContent({ model: MODEL, contents: prompt });
  return (res.text ?? "").trim();
}

export async function findSection(indexText: string, query: string): Promise<string> {
  return generate(buildFindPrompt(indexText, query));
}

export async function summarize(passage: string): Promise<string> {
  return generate(buildSummaryPrompt(passage));
}
