"""Self-check for pdf_tool: `uv run python python/test_pdf_tool.py`.

Generates a tiny one-page PDF in memory (no fixtures on disk), then asserts the
extraction index and the PNG render behave. No network, no GCP.
"""

import os
import tempfile

import pymupdf as fitz

import pdf_tool


def _make_pdf(path: str, text: str) -> None:
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)  # US Letter, points
    page.insert_text((72, 72), text, fontsize=18)
    doc.save(path)
    doc.close()


def test_extract_and_render() -> None:
    with tempfile.TemporaryDirectory() as d:
        pdf = os.path.join(d, "doc.pdf")
        _make_pdf(pdf, "Indemnification Clause")

        idx = pdf_tool.extract(pdf, dpi=150)
        assert idx["pageCount"] == 1, idx["pageCount"]
        assert idx["renderDpi"] == 150
        page = idx["pages"][0]
        # 612 pt * 150/72 = 1275 px
        assert page["widthPx"] == 1275, page["widthPx"]
        assert page["heightPx"] == 1650, page["heightPx"]

        texts = [w["text"] for w in page["words"]]
        assert "Indemnification" in texts, texts
        w = next(w for w in page["words"] if w["text"] == "Indemnification")
        assert w["x1"] > w["x0"] and w["y1"] > w["y0"], w

        png = pdf_tool.render(pdf, 1, dpi=150)
        assert png[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
        assert len(png) > 100


def test_blank_page() -> None:
    """A page with no text layer yields the page but zero words (no crash)."""
    with tempfile.TemporaryDirectory() as d:
        pdf = os.path.join(d, "blank.pdf")
        doc = fitz.open()
        doc.new_page(width=612, height=792)  # blank, no text
        doc.save(pdf)
        doc.close()
        idx = pdf_tool.extract(pdf)
        assert idx["pageCount"] == 1, idx
        assert idx["pages"][0]["words"] == [], idx["pages"][0]["words"]


if __name__ == "__main__":
    test_extract_and_render()
    test_blank_page()
    print("test_pdf_tool.py: all assertions passed")
