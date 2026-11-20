"""STEP 2: turn the raw (and user-edited) fields into the exact text that
goes into the Word template.

build_context() is THE place that decides what each {{ }} mark becomes.
To support a new mark: add a key here, then add one line in company.yaml.
"""
import re
from datetime import date, datetime


def fmt_dash(iso: str) -> str:
    """2026-06-12 -> 12-06-2026  (used on the 'Bid Number ..., dated: ...' lines)."""
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%d-%m-%Y") if iso else ""


def fmt_dots(iso: str) -> str:
    """2026-11-09 -> 09.11.2026  (used for the signing / filing date)."""
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%d.%m.%Y") if iso else ""


def today_iso() -> str:
    return date.today().strftime("%Y-%m-%d")


def strip_ministry(office: str) -> str:
    """'KVS RO Patna, Department of X, Ministry of Education' -> without the ministry tail.
    The 'To,' block in your ATC leaves the ministry out; the flowing sentence keeps it."""
    return re.sub(r",?\s*Ministry of [^,]+$", "", office.strip(), flags=re.I).strip(" ,")


def buyer_lines(f: dict) -> list[str]:
    """The 'To,' block:
        line 1 - main person / position (e.g. PRINCIPAL)         [if given]
        line 2 - office / department address                      [if not, department]
        line 3 - district, state, pin code                        [if given]
    """
    line2 = strip_ministry(f.get("buyer_office", "")) or f.get("department", "").strip()
    lines = [f.get("buyer_designation", "").strip(), line2, f.get("buyer_line3", "").strip()]
    return [l for l in lines if l]


def buyer_inline(f: dict) -> str:
    """Same information as ONE flowing text, for sentences like '... at <here> and we decided'."""
    office = f.get("buyer_office", "").strip() or f.get("department", "").strip()
    text = " ".join(p for p in (f.get("buyer_designation", "").strip(), office) if p)
    if f.get("buyer_line3", "").strip():
        text += ", " + f["buyer_line3"].strip()
    return text


def build_context(f: dict) -> dict:
    """field name -> final text. (Keys here are what company.yaml points to.)"""
    return {
        "bid_number": f.get("bid_number", "").strip(),
        "bid_date": fmt_dash(f.get("bid_opening", "")),      # opening date, always
        "category": re.sub(r"\s+", " ", f.get("category", "")).strip(),
        "buyer_inline": buyer_inline(f),
        "buyer_block": "\n".join(buyer_lines(f)),
        "filing_date": fmt_dots(f.get("filing_date", "")),
    }


def safe_name(bid_number: str) -> str:
    """GEM/2026/B/7575719 -> GEM_2026_B_7575719 (safe for folder / file names)."""
    return re.sub(r"[^A-Za-z0-9]+", "_", bid_number).strip("_") or "UNKNOWN_BID"
