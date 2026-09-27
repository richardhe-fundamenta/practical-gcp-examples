/** Runnable self-check: `npm test`. */
import assert from "node:assert/strict";
import { normalizeHex, hexToRgb, DEFAULT_COLOR } from "./color.ts";

// normalizeHex canonicalizes to #rrggbb lowercase
assert.equal(normalizeHex("#3B82F6"), "#3b82f6");
assert.equal(normalizeHex("3b82f6"), "#3b82f6");
assert.equal(normalizeHex("#FFF"), "#ffffff"); // 3-digit expands
assert.equal(normalizeHex("  #abc  "), "#aabbcc"); // trims
assert.equal(normalizeHex("#ff"), null); // wrong length
assert.equal(normalizeHex("nope"), null);
assert.equal(normalizeHex("#12g456"), null); // non-hex char

// hexToRgb
assert.deepEqual(hexToRgb("#000000"), { r: 0, g: 0, b: 0 });
assert.deepEqual(hexToRgb("#ffffff"), { r: 255, g: 255, b: 255 });
assert.deepEqual(hexToRgb(DEFAULT_COLOR), { r: 59, g: 130, b: 246 });
assert.throws(() => hexToRgb("bogus"));

console.log("color.test.ts: all assertions passed");
