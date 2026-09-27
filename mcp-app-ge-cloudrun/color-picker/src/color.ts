/** Pure color helpers, kept DOM-free so they can be unit-tested. */

const HEX_RE = /^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;

export const DEFAULT_COLOR = "#3b82f6";

/**
 * Validate and canonicalize a hex color to `#rrggbb` (lowercase).
 * Accepts 3- or 6-digit hex, with or without a leading `#`.
 * Returns null for anything invalid.
 */
export function normalizeHex(input: string): string | null {
  const m = input.trim().match(HEX_RE);
  if (!m) return null;
  let hex = m[1].toLowerCase();
  if (hex.length === 3) {
    hex = hex[0] + hex[0] + hex[1] + hex[1] + hex[2] + hex[2];
  }
  return `#${hex}`;
}

/** Convert a canonical `#rrggbb` string to RGB components. */
export function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const n = normalizeHex(hex);
  if (!n) throw new Error(`invalid hex: ${hex}`);
  return {
    r: parseInt(n.slice(1, 3), 16),
    g: parseInt(n.slice(3, 5), 16),
    b: parseInt(n.slice(5, 7), 16),
  };
}
