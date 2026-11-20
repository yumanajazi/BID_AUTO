"""Make all documents from the command line, with no browser:

    python run_cli.py path/to/bid.pdf                 # default company, today's date
    python run_cli.py bid.pdf --company snta --date 2026-11-09 --docs atc,emd_exemption

Handy for testing and for batch work. Uses exactly the same code as the web app.
"""
import argparse
import shutil
from pathlib import Path

from app.services.companies import get_company
from app.services.extractor import extract_bid
from app.services.normalizer import safe_name, today_iso
from app.services.pipeline import generate
from app.services.storage import create_tender, make_folder, save_manifest, save_state, update_tender
from app.settings import load_settings

ap = argparse.ArgumentParser()
ap.add_argument("bid_pdf")
ap.add_argument("--company", default=load_settings()["default_company"])
ap.add_argument("--date", default=today_iso(), help="filing date, YYYY-MM-DD (default today)")
ap.add_argument("--docs", default="", help="comma separated keys (default: every document marked default)")
a = ap.parse_args()

company = get_company(a.company)
fields, warnings = extract_bid(Path(a.bid_pdf))
fields["filing_date"] = a.date
for level, msg in warnings:
    print(f"[{level}] {msg}")

selected = [k for k in a.docs.split(",") if k] or [d["key"] for d in company.documents if d.get("default")]
folder = make_folder(company.slug, a.date, safe_name(fields["bid_number"]))
shutil.copy(a.bid_pdf, folder / "source" / Path(a.bid_pdf).name)
state = {"company": company.slug, "fields": fields, "warnings": warnings, "selected_docs": selected,
         "part_order": {}, "uploads": {"extra": []}}
save_state(folder, state)
tid = create_tender(company.slug, fields["bid_number"], a.date, folder)

manifest = generate(company, folder, state)
save_manifest(folder, manifest)
update_tender(tid, status="generated")
print(f"\nSaved in: {folder / 'documents'}")
for o in manifest["outputs"]:
    print(f"  {o['file']}  ({o['pages']} pages)")
for w in manifest["warnings"]:
    print("  WARNING:", w)
