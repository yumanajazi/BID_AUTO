"""STEP 5: glue PDFs together (generated letter page + fixed certificates)."""
from pathlib import Path

from pypdf import PdfReader, PdfWriter


def page_count(pdf: Path) -> int:
    return len(PdfReader(str(pdf)).pages)


def merge_pdfs(parts: list[Path], out: Path) -> int:
    """Append every PDF in `parts` (in order) into `out`. Returns total pages."""
    w = PdfWriter()
    for p in parts:
        for page in PdfReader(str(p)).pages:
            w.add_page(page)
    with open(out, "wb") as f:
        w.write(f)
    return len(w.pages)
