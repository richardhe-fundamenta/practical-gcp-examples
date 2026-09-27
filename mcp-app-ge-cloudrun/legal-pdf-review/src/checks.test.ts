/** Runnable self-check: `npm test`. Pure logic only — no network/GCP. */
import assert from "node:assert/strict";
import { locatePassage } from "./locate.ts";
import { scaleBoxes } from "./viewer.ts";
import { docPrefix, userPrefix } from "./storage.ts";
import { indexToText, buildFindPrompt, buildSummaryPrompt } from "./llm.ts";
import type { DocIndex } from "./pdf.ts";

const index: DocIndex = {
  renderDpi: 150,
  pageCount: 2,
  pages: [
    {
      page: 1,
      widthPx: 1000,
      heightPx: 1500,
      words: [
        { text: "The", x0: 10, y0: 10, x1: 40, y1: 30 },
        { text: "Indemnification", x0: 45, y0: 10, x1: 200, y1: 30 },
        { text: "Clause", x0: 205, y0: 10, x1: 280, y1: 30 },
        { text: "applies", x0: 285, y0: 10, x1: 360, y1: 30 },
      ],
    },
    {
      page: 2,
      widthPx: 1000,
      heightPx: 1500,
      words: [{ text: "Termination", x0: 10, y0: 10, x1: 150, y1: 30 }],
    },
  ],
};

// locatePassage: matched run returns the covering boxes on the right page
const found = locatePassage(index, "Indemnification Clause");
assert.equal(found.page, 1);
assert.equal(found.boxes.length, 2);
assert.deepEqual(found.boxes[0], { x0: 45, y0: 10, x1: 200, y1: 30 });
assert.equal(found.snippet, "Indemnification Clause");

// case/punctuation-insensitive
assert.equal(locatePassage(index, "  indemnification, clause!  ").boxes.length, 2);

// passage on page 2
assert.equal(locatePassage(index, "Termination").page, 2);

// not present -> first page, no boxes (never a wrong highlight)
const missing = locatePassage(index, "force majeure");
assert.equal(missing.boxes.length, 0);
assert.equal(missing.page, 1);

// scaleBoxes: half-size render scales boxes by 0.5
const rects = scaleBoxes(1000, 1500, 500, 750, [{ x0: 100, y0: 200, x1: 300, y1: 240 }]);
assert.deepEqual(rects[0], { left: 50, top: 100, width: 100, height: 20 });

// storage prefixes
assert.equal(userPrefix("sub-1"), "sub-1/");
assert.equal(docPrefix("sub-1", "abc123"), "sub-1/abc123/");
assert.throws(() => docPrefix("sub-1", "../other"), /invalid document id/);
assert.throws(() => docPrefix("sub-1", "a/b"), /invalid document id/);

// prompt builders
const text = indexToText(index);
assert.ok(text.includes("--- page 1 ---"));
assert.ok(text.includes("--- page 2 ---"));
assert.ok(text.includes("Indemnification"));
assert.ok(buildFindPrompt(text, "who indemnifies?").includes("who indemnifies?"));
assert.ok(buildSummaryPrompt("some passage").includes("some passage"));

console.log("checks.test.ts: all assertions passed");
