"""STEP 1 of the pipeline: read the GeM bid PDF and pull out the fields we need.

How it works (in plain words):
  1. pdfplumber turns every page into text.
  2. The Hindi half of each label comes out as garbage, but the ENGLISH half
     (e.g. "Bid End Date/Time") is clean, so we search for the English labels
     with regular expressions ("regex").
  3. Anything we cannot find is left empty and a warning is added, so you
     can type it in on the Details page.

This works on a bid PDF alone, or on a merged PDF (bid document + buyer ATC).
"""
import re
from datetime import datetime
from pathlib import Path

import pdfplumber

CID = re.compile(r"\(cid:\d+\)")          # junk produced by Hindi fonts
DATE = r"(\d{2}-\d{2}-\d{4})"


def _iso(dmy: str) -> str:
    """'12-06-2026' -> '2026-06-12' (the format HTML date boxes use)."""
    try:
        return datetime.strptime(dmy, "%d-%m-%Y").strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return ""


def read_text(pdf_path: Path) -> tuple[str, list]:
    """Return (all text of the PDF, list of consignee-table rows if found)."""
    pages, rows = [], []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            pages.append(CID.sub("", t))
            if "Consignee" in t:           # the table with address + quantity
                try:
                    for table in page.extract_tables():
                        rows.extend(table)
                except Exception:          # table reading is best-effort only
                    pass
    return "\n".join(pages), rows


def _first(pattern: str, text: str, flags=0, group=1) -> str:
    m = re.search(pattern, text, flags)
    return re.sub(r"\s+", " ", m.group(group)).strip() if m else ""


def _english(line: str) -> bool:
    """True if the line is plain English (no Hindi letters)."""
    return bool(line.strip()) and re.fullmatch(r"[A-Za-z0-9 ;,.()\-/&:'+]+", line.strip()) is not None


def _item_category(lines: list[str]) -> str:
    for i, line in enumerate(lines):
        if "/Item Category" in line:
            same = line.split("/Item Category", 1)[1].strip()
            prev = lines[i - 1].strip() if i > 0 else ""
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if same:                                   # value on the same line
                parts = [same]
                if same.endswith("-") and _english(nxt):
                    parts.append(nxt)
            else:                                      # value wraps around the label
                parts = [p for p in (prev, nxt) if _english(p)]
            out = ""
            for p in parts:
                out = (out + ("" if out.endswith("-") else " ") + p) if out else p
            return out.strip()
    return ""


def _beneficiary(lines: list[str]) -> tuple[str, str, str]:
    """-> (designation, office text, officer name) from the 'Beneficiary :' block."""
    for i, line in enumerate(lines):
        if re.search(r"/Beneficiary\s*:", line):
            block = []
            for nxt in lines[i + 1:i + 9]:
                if nxt.strip().startswith("UIN Number") or not nxt.strip():
                    break
                block.append(nxt.strip())
            officer = ""
            if block and block[-1].startswith("(") and block[-1].endswith(")"):
                officer = block.pop()[1:-1].strip()
            if len(block) >= 2:
                return block[0], " ".join(block[1:]), officer
            return "", " ".join(block), officer
    return "", "", ""


def _consignee_hint(rows: list) -> str:
    """Best-effort: the consignee's address cell from the bid table."""
    for row in rows:
        cells = [re.sub(r"\s+", " ", (c or "")).strip() for c in row]
        for c in cells:
            if re.search(r"\b\d{6}\b", c) and len(c) > 12 and "wage" not in c.lower():
                return c
    return ""


def extract_bid(pdf_path: Path) -> tuple[dict, list]:
    """Return (fields, warnings). Dates come back as ISO 'YYYY-MM-DD'."""
    text, rows = read_text(pdf_path)
    warnings = []
    if len(text.strip()) < 200:
        warnings.append(("error", "Could not read text from this PDF (is it a scan?). Fill the details by hand."))
        return _empty(), warnings

    lines = text.split("\n")
    f = _empty()

    f["bid_number"] = _first(r"(GEM/\d{4}/[A-Z]/\d+)", text)
    f["bid_published"] = _iso(_first(r"Dated\s*:\s*" + DATE, text))
    f["bid_end"] = _iso(_first(r"Bid End Date/Time\s*" + DATE, text))
    f["bid_opening"] = _iso(_first(r"Bid Opening[\s\S]{0,60}?" + DATE, text))
    f["category"] = _item_category(lines)

    f["ministry"] = _first(r"Ministry/State Name\s+(.+)", text)
    f["department"] = _first(r"Department Name\s+(.+)", text)
    f["organisation"] = _first(r"Organisation Name\s+(.+)", text)
    f["office"] = _first(r"Office Name\s+(.+)", text)

    des, office, officer = _beneficiary(lines)
    f["buyer_designation"], f["buyer_office"], f["buyer_officer"] = des, office, officer
    f["consignee_hint"] = _consignee_hint(rows)

    f["contract_period"] = _first(r"Contract Period\s+(.+)", text)
    f["turnover_required"] = _first(r"Minimum Average Annual Turnover of the\s+([\d.,]+\s*\w+\s*\(s\))", text)
    f["experience_required"] = _first(r"Years of Past Experience Required for\s+(\d+\s*Year\s*\(s\))", text)
    f["emd_amount"] = _first(r"EMD Amount\s+(\d[\d,]*)", text)
    f["emd_exemption_clause"] = "EMD EXEMPTION" in text
    f["mse_relax_experience"] = _first(r"MSE Relaxation for Years Of[\s\S]{0,120}?\b(Yes|No)\b", text)
    f["startup_relax_experience"] = _first(r"Startup Relaxation for Years Of[\s\S]{0,120}?\b(Yes|No)\b", text)

    # ---- warnings the user should look at -----------------------------------
    for key, label in [("bid_number", "Bid number"), ("bid_opening", "Bid opening date"),
                       ("category", "Bid category"), ("buyer_office", "Buyer address")]:
        if not f[key]:
            warnings.append(("error", f"{label} was not found - please type it in."))
    if f["bid_number"] and f["category"] and "Housekeeping" not in f["category"] and "Facility" not in f["category"]:
        warnings.append(("info", "Category does not look like a manpower service bid - double check it."))
    if f["emd_amount"] and not f["emd_exemption_clause"]:
        warnings.append(("warn", f"This bid lists an EMD of Rs. {f['emd_amount']} but no EMD-exemption clause was found. "
                                 "Check that MSE exemption is allowed before filing."))
    if f["mse_relax_experience"] == "No":
        warnings.append(("warn", "The bid says MSE relaxation for experience/turnover is NOT given - "
                                 "the exemption letters may not be accepted."))
    if not f["buyer_designation"]:
        warnings.append(("info", "No designation (e.g. Principal) found in the buyer block - line 1 of the address will be skipped."))
    return f, warnings


def _empty() -> dict:
    return {
        "bid_number": "", "bid_published": "", "bid_end": "", "bid_opening": "", "category": "",
        "ministry": "", "department": "", "organisation": "", "office": "",
        "buyer_designation": "", "buyer_office": "", "buyer_officer": "", "buyer_line3": "",
        "consignee_hint": "", "contract_period": "", "turnover_required": "", "experience_required": "",
        "emd_amount": "", "emd_exemption_clause": False,
        "mse_relax_experience": "", "startup_relax_experience": "",
    }
