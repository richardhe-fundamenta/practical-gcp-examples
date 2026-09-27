/**
 * Pure highlight-overlay geometry. The page PNG is rendered at a fixed pixel
 * size (natural*); the UI shows it scaled to the container (rendered*). Boxes
 * are in the natural pixel space, so we scale them by the same factor to get
 * CSS-pixel rectangles that line up on top of the <img>.
 */
import type { Box } from "./locate.ts";

export interface Rect {
  left: number;
  top: number;
  width: number;
  height: number;
}

export function scaleBoxes(
  naturalW: number,
  naturalH: number,
  renderedW: number,
  renderedH: number,
  boxes: Box[],
): Rect[] {
  const sx = naturalW ? renderedW / naturalW : 1;
  const sy = naturalH ? renderedH / naturalH : 1;
  return boxes.map((b) => ({
    left: b.x0 * sx,
    top: b.y0 * sy,
    width: (b.x1 - b.x0) * sx,
    height: (b.y1 - b.y0) * sy,
  }));
}
