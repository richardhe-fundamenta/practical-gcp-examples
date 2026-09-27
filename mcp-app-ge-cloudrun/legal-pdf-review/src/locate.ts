/**
 * Map an LLM-returned passage back to bounding boxes in the extraction index.
 * Pure + DOM-free so it can be unit-tested. Coordinates always come from the
 * index (never the model), so a highlight can never be at a hallucinated spot:
 * if the passage isn't found in the page words, we return no boxes.
 */
import type { DocIndex } from "./pdf.ts";

export interface Box {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}
export interface Located {
  page: number;
  boxes: Box[];
  snippet: string;
}

/** Lowercase, strip punctuation to spaces, collapse whitespace, split. */
function tokenize(s: string): string[] {
  return s
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
}

/**
 * Find the longest contiguous run of the passage's tokens within a single
 * page's word sequence. Returns the matched word boxes for the best page.
 * No match anywhere -> first page with empty boxes.
 */
export function locatePassage(index: DocIndex, passage: string): Located {
  const target = tokenize(passage);
  if (index.pageCount === 0) return { page: 1, boxes: [], snippet: "" };
  if (target.length === 0) return { page: index.pages[0].page, boxes: [], snippet: "" };

  let best: { page: number; start: number; len: number; words: DocIndex["pages"][0]["words"] } | null =
    null;

  for (const p of index.pages) {
    const wordTokens = p.words.map((w) => tokenize(w.text)[0] ?? "");
    // Slide a window: for each start position that matches target[0], extend.
    for (let i = 0; i < wordTokens.length; i++) {
      if (wordTokens[i] !== target[0]) continue;
      let len = 0;
      while (
        len < target.length &&
        i + len < wordTokens.length &&
        wordTokens[i + len] === target[len]
      ) {
        len++;
      }
      if (!best || len > best.len) {
        best = { page: p.page, start: i, len, words: p.words };
      }
    }
  }

  // Require at least one matched token; otherwise no confident location.
  if (!best || best.len === 0) {
    return { page: index.pages[0].page, boxes: [], snippet: "" };
  }

  const matched = best.words.slice(best.start, best.start + best.len);
  return {
    page: best.page,
    boxes: matched.map((w) => ({ x0: w.x0, y0: w.y0, x1: w.x1, y1: w.y1 })),
    snippet: matched.map((w) => w.text).join(" "),
  };
}
