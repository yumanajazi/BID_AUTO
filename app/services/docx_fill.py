"""STEP 4a: fill the Word template.

THE PROBLEM this solves: Word secretly chops one sentence into many small
pieces ("runs"), so "{{Current Date}}" is often stored as "{{Curre" + "nt Da" +
"te}}" and a simple find-and-replace never finds it.

THE SOLUTION: for every paragraph, glue the pieces into one string, find the
{{ }} marks in that string, then write the replacement back into the pieces.
All the formatting (font, bold, size) of the first piece is kept.

It also renumbers every "Letter No. SNTA/....../NN" in order: 01, 02, 03 ...
"""
import re
import zipfile
from collections import Counter
from pathlib import Path

from lxml import etree

from .refnumbers import letter_pattern, make_letter_no

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W_P, W_T, W_BR = f"{{{W}}}p", f"{{{W}}}t", f"{{{W}}}br"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
PLACEHOLDER = re.compile(r"\{\{(.*?)\}\}", re.S)

# Which parts of the .docx can contain text we must fill.
_FILLABLE = re.compile(r"^word/(document|header\d*|footer\d*)\.xml$")


def norm_key(s: str) -> str:
    """'Current Date' / 'current  date' / 'CurrentDate' all become 'currentdate'."""
    return re.sub(r"\s+", "", s).lower()


def _own_texts(p) -> list:
    """The <w:t> text nodes that belong to paragraph p itself (not to a
    paragraph nested inside a text box that sits inside p)."""
    out = []
    for t in p.iter(W_T):
        a = t.getparent()
        while a is not None and a.tag != W_P:
            a = a.getparent()
        if a is p:
            out.append(t)
    return out


def _replace_span(ts: list, start: int, end: int, value: str) -> None:
    """Replace characters [start, end) of the paragraph text with value.
    A value containing '\\n' becomes real line breaks inside the paragraph."""
    cum, pos = [], 0
    for t in ts:
        cum.append(pos)
        pos += len(t.text or "")

    def locate(p, is_end):
        for i, t in enumerate(ts):
            n = len(t.text or "")
            if (is_end and cum[i] < p <= cum[i] + n) or (not is_end and cum[i] <= p < cum[i] + n):
                return i, p - cum[i]
        raise ValueError("position outside paragraph")

    i, so = locate(start, False)
    j, eo = locate(end, True)
    head, tail = (ts[i].text or "")[:so], (ts[j].text or "")[eo:]
    lines = value.split("\n")

    for k in range(i + 1, j):                      # pieces fully swallowed by the mark
        ts[k].text = ""
    if i == j:
        ts[i].text = head + lines[0] + (tail if len(lines) == 1 else "")
        pending_tail = tail if len(lines) > 1 else ""
    else:
        ts[i].text = head + lines[0]
        ts[j].text = tail
        pending_tail = ""
    ts[i].set(XML_SPACE, "preserve")
    ts[j].set(XML_SPACE, "preserve")

    anchor = ts[i]
    for ln in lines[1:]:                           # extra lines: <w:br/> + new text piece
        br = etree.Element(W_BR)
        anchor.addnext(br)
        nt = etree.Element(W_T)
        nt.text = ln
        nt.set(XML_SPACE, "preserve")
        br.addnext(nt)
        anchor = nt
    if pending_tail:
        anchor.text = (anchor.text or "") + pending_tail


def fill_docx(src: Path, dst: Path, values: dict, placeholder_map: dict,
              ref_prefix: str, filing_iso: str) -> dict:
    """Fill src -> dst. Returns a report:
       {"replaced": {field: count}, "unknown": [marks we could not match], "letters": [numbers used]}"""
    keymap = {norm_key(k): v for k, v in placeholder_map.items()}
    letter_re = letter_pattern(ref_prefix)
    combined = re.compile(PLACEHOLDER.pattern + "|(?P<letter>" + letter_re.pattern + ")", re.S)

    replaced, unknown, letters = Counter(), [], []
    serial = 0

    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if _FILLABLE.match(item.filename):
                root = etree.fromstring(data)
                for p in list(root.iter(W_P)):
                    ts = _own_texts(p)
                    text = "".join(t.text or "" for t in ts)
                    if "{{" not in text and ref_prefix not in text:
                        continue
                    jobs = []                                    # forward pass: decide values
                    for m in combined.finditer(text):
                        if m.group("letter"):
                            serial += 1
                            num = make_letter_no(ref_prefix, filing_iso, serial)
                            letters.append(num)
                            jobs.append((m.start(), m.end(), num))
                        else:
                            mark = m.group(1)
                            field = keymap.get(norm_key(mark))
                            if field is None or field not in values:
                                unknown.append(mark.strip())
                                continue
                            replaced[field] += 1
                            jobs.append((m.start(), m.end(), values[field]))
                    for s, e, v in reversed(jobs):               # apply back-to-front
                        _replace_span(ts, s, e, v)
                data = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
            zout.writestr(item, data)
    return {"replaced": dict(replaced), "unknown": sorted(set(unknown)), "letters": letters}


def list_marks(docx: Path) -> list[str]:
    """Every distinct {{ }} mark in a template (used to check the template)."""
    marks = set()
    with zipfile.ZipFile(docx) as z:
        for name in z.namelist():
            if _FILLABLE.match(name):
                root = etree.fromstring(z.read(name))
                for p in root.iter(W_P):
                    text = "".join(t.text or "" for t in _own_texts(p))
                    marks.update(m.group(1).strip() for m in PLACEHOLDER.finditer(text))
    return sorted(marks)


def count_letters(docx: Path, ref_prefix: str) -> int:
    pat = letter_pattern(ref_prefix)
    n = 0
    with zipfile.ZipFile(docx) as z:
        root = etree.fromstring(z.read("word/document.xml"))
        for p in root.iter(W_P):
            n += len(pat.findall("".join(t.text or "" for t in _own_texts(p))))
    return n
