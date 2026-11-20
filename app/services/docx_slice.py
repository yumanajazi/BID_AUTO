"""STEP 4b: cut ONE letter (one page) out of the already-filled ATC .docx.

Why: the Turnover, Experience and EMD letters must be IDENTICAL to the pages
inside the ATC (same letter number, same dates). So we never retype them -
we copy them out of the filled ATC and put them in their own Word file.

How we find the page without depending on page breaks (which differ between
Word and LibreOffice): we look for text markers in the body paragraphs,
see recipes.yaml  ->  slice: {start_marker, heading, end_marker}.
"""
import zipfile
from pathlib import Path

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W_T = f"{{{W}}}t"
W_DRAWING, W_PICT, W_SECTPR = f"{{{W}}}drawing", f"{{{W}}}pict", f"{{{W}}}sectPr"


def _text(el) -> str:
    return "".join(t.text or "" for t in el.iter(W_T))


def _has_drawing(el) -> bool:
    return el.find(f".//{W_DRAWING}") is not None or el.find(f".//{W_PICT}") is not None


def slice_docx(src: Path, dst: Path, start_marker: str, heading: str, end_marker: str) -> None:
    with zipfile.ZipFile(src) as zin:
        root = etree.fromstring(zin.read("word/document.xml"))
        body = root.find(f"{{{W}}}body")
        kids = list(body)
        sect = kids[-1] if kids and kids[-1].tag == W_SECTPR else None
        content = kids[:-1] if sect is not None else kids

        h = next((i for i, c in enumerate(content) if heading in _text(c)), None)
        if h is None:
            raise ValueError(f"Could not find the heading '{heading}' in the ATC. "
                             "Check recipes.yaml or the template text.")

        # start = closest paragraph above the heading that contains start_marker
        k = next((i for i in range(h, -1, -1) if start_marker in _text(content[i])), None)
        if k is None:
            raise ValueError(f"Could not find '{start_marker}' above '{heading}'.")
        start = k
        # include the empty lines + the page-background drawing just above the letter
        for j in range(k - 1, -1, -1):
            if _text(content[j]).strip():
                break                      # hit real text -> stop, nothing to add
            if _has_drawing(content[j]):
                start = j                  # the letterhead/background drawing paragraph
                break

        # end = just after the last real text line before the NEXT letter starts
        n = next((i for i in range(h + 1, len(content)) if end_marker in _text(content[i])), len(content))
        last_text = max(i for i in range(h, n) if _text(content[i]).strip())
        end = last_text + 1

        for el in kids:                    # build the new body
            body.remove(el)
        for el in content[start:end]:
            body.append(el)
        if sect is not None:
            body.append(sect)
        new_xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)

        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                zout.writestr(item, new_xml if item.filename == "word/document.xml" else zin.read(item.filename))
