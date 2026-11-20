"""Letter reference numbers:  <PREFIX>/<DDMM>/<financial year>/<serial>

    SNTA/0911/2026-27/01     (filing date 9 Nov 2026 -> DDMM = 0911)

DDMM  = the day/month the documents are MADE (filing date).
FY    = Indian financial year (April-March) of that date.
serial= 01, 02, 03 ... in the order the letters appear. Never repeats.
"""
import re
from datetime import date, datetime


def parse_iso(iso: str) -> date:
    return datetime.strptime(iso, "%Y-%m-%d").date()


def financial_year(d: date) -> str:
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def letter_pattern(prefix: str) -> re.Pattern:
    """Matches the sample number that sits in the template, e.g. SNTA/0347/2026-27/01."""
    return re.compile(rf"{re.escape(prefix)}/\d{{4}}/\d{{4}}-\d{{2}}/\d{{2}}")


def make_letter_no(prefix: str, filing_iso: str, serial: int) -> str:
    d = parse_iso(filing_iso)
    return f"{prefix}/{d.strftime('%d%m')}/{financial_year(d)}/{serial:02d}"
