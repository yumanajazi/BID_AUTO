"""Quick safety net. Run with:   python -m pytest tests -q

These tests check the parts most likely to break when you change things:
numbering, date formats, buyer address rules, and the Word placeholder engine.
"""
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.docx_fill import fill_docx, list_marks, norm_key           # noqa: E402
from app.services.normalizer import build_context, buyer_lines, strip_ministry  # noqa: E402
from app.services.refnumbers import financial_year, make_letter_no           # noqa: E402
from app.services.companies import get_company                               # noqa: E402


def test_financial_year():
    from datetime import date
    assert financial_year(date(2026, 11, 9)) == "2026-27"
    assert financial_year(date(2027, 3, 31)) == "2026-27"
    assert financial_year(date(2027, 4, 1)) == "2027-28"


def test_letter_number():
    assert make_letter_no("SNTA", "2026-11-09", 1) == "SNTA/0911/2026-27/01"
    assert make_letter_no("SNTA", "2026-11-09", 12) == "SNTA/0911/2026-27/12"


def test_marks_are_case_and_space_insensitive():
    assert norm_key("Current  Date") == norm_key("currentdate")


def test_buyer_block_rules():
    f = {"buyer_designation": "PRINCIPAL", "department": "Dept X",
         "buyer_office": "KVS RO Patna, Department of Y, KVS, Ministry of Education", "buyer_line3": ""}
    assert buyer_lines(f) == ["PRINCIPAL", "KVS RO Patna, Department of Y, KVS"]       # ministry dropped, 2 lines
    f["buyer_line3"] = "Saran, Bihar - 841417"
    assert len(buyer_lines(f)) == 3
    f["buyer_designation"], f["buyer_office"] = "", ""
    assert buyer_lines(f) == ["Dept X", "Saran, Bihar - 841417"]                       # falls back to department


def test_strip_ministry():
    assert strip_ministry("A, B, Ministry of Education") == "A, B"
    assert strip_ministry("A, B") == "A, B"


def test_context_dates():
    ctx = build_context({"bid_opening": "2026-06-12", "filing_date": "2026-11-09", "bid_number": "GEM/2026/B/1",
                         "category": "x  y", "buyer_office": "o"})
    assert ctx["bid_date"] == "12-06-2026" and ctx["filing_date"] == "09.11.2026" and ctx["category"] == "x y"


def test_template_marks_all_known(tmp_path):
    c = get_company("snta")
    known = {norm_key(k) for k in c.placeholders}
    unknown = [m for m in list_marks(c.template) if norm_key(m) not in known]
    assert unknown == [], f"Template has marks missing from company.yaml: {unknown}"


def test_fill_leaves_no_marks_and_numbers_letters(tmp_path):
    c = get_company("snta")
    out = tmp_path / "filled.docx"
    ctx = build_context({"bid_opening": "2026-06-12", "filing_date": "2026-11-09", "bid_number": "GEM/2026/B/7575719",
                         "category": "Housekeeping", "buyer_designation": "PRINCIPAL", "buyer_office": "KVS RO Patna"})
    rep = fill_docx(c.template, out, ctx, c.placeholders, c.ref_prefix, "2026-11-09")
    assert rep["unknown"] == []
    assert rep["letters"] == [f"SNTA/0911/2026-27/{i:02d}" for i in range(1, len(rep["letters"]) + 1)]
    with zipfile.ZipFile(out) as z:
        assert b"{{" not in z.read("word/document.xml")
