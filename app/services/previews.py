"""Small PNG thumbnails of each PDF page, shown on the Generate page."""
from pathlib import Path

import pypdfium2 as pdfium


def render_previews(pdf: Path, out_dir: Path, stem: str, scale: float = 0.45, max_pages: int = 30) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    names = []
    doc = pdfium.PdfDocument(str(pdf))
    try:
        for i in range(min(len(doc), max_pages)):
            img = doc[i].render(scale=scale).to_pil().convert("RGB")
            name = f"{stem}_p{i + 1:02d}.png"
            img.save(out_dir / name, optimize=True)
            names.append(name)
    finally:
        doc.close()
    return names
