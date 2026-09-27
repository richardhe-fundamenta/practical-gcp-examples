"""PyMuPDF helper for the legal-pdf-review MCP App.

Two subcommands, driven by the TypeScript server over a subprocess:

    extract <pdf>              -> prints a DocIndex JSON to stdout
    render  <pdf> <page> [dpi] -> writes a page PNG (bytes) to stdout

The word boxes in the index and the rendered page PNG share ONE pixel
coordinate space at RENDER_DPI, so the UI can overlay highlight rectangles
directly on the page image. PDF native units are points (72 dpi); we scale by
dpi/72 to pixels.

Native/text PDFs only (MVP): text comes from the PDF text layer, not OCR.
"""

import json
import sys

import pymupdf as fitz  # PyMuPDF

RENDER_DPI = 150


def _scale(dpi: int) -> float:
    return dpi / 72.0


def extract(pdf_path: str, dpi: int = RENDER_DPI) -> dict:
    """Build a DocIndex: per-page pixel dimensions + every word's box (px)."""
    s = _scale(dpi)
    pages = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc):
            rect = page.rect  # points
            words = []
            # get_text("words") -> (x0, y0, x1, y1, "word", block, line, word_no)
            for x0, y0, x1, y1, text, *_ in page.get_text("words"):
                if not text.strip():
                    continue
                words.append(
                    {
                        "text": text,
                        "x0": round(x0 * s, 1),
                        "y0": round(y0 * s, 1),
                        "x1": round(x1 * s, 1),
                        "y1": round(y1 * s, 1),
                    }
                )
            pages.append(
                {
                    "page": i + 1,
                    "widthPx": round(rect.width * s),
                    "heightPx": round(rect.height * s),
                    "words": words,
                }
            )
    return {"renderDpi": dpi, "pageCount": len(pages), "pages": pages}


def render(pdf_path: str, page: int, dpi: int = RENDER_DPI) -> bytes:
    """Rasterize a 1-based page number to PNG bytes at `dpi`."""
    with fitz.open(pdf_path) as doc:
        if page < 1 or page > doc.page_count:
            raise ValueError(f"page {page} out of range 1..{doc.page_count}")
        pix = doc[page - 1].get_pixmap(matrix=fitz.Matrix(_scale(dpi), _scale(dpi)))
        return pix.tobytes("png")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        sys.stderr.write("usage: pdf_tool.py extract|render ...\n")
        return 2
    cmd = argv[1]
    if cmd == "extract":
        index = extract(argv[2])
        json.dump(index, sys.stdout)
        return 0
    if cmd == "render":
        page = int(argv[3])
        dpi = int(argv[4]) if len(argv) > 4 else RENDER_DPI
        sys.stdout.buffer.write(render(argv[2], page, dpi))
        return 0
    sys.stderr.write(f"unknown command: {cmd}\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
