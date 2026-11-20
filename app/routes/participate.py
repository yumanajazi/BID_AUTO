"""The 'Participate' page: upload the bid PDF, pick the company, tick the documents."""
import shutil
import uuid

from flask import Blueprint, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from ..services.companies import get_company, list_companies
from ..services.extractor import extract_bid
from ..settings import DATA_DIR, load_settings
from ..services.normalizer import safe_name, today_iso
from ..services.storage import create_tender, make_folder, save_state

bp = Blueprint("participate", __name__)


def is_pdf(file_storage) -> bool:
    head = file_storage.stream.read(5)
    file_storage.stream.seek(0)
    return head == b"%PDF-"


@bp.route("/participate", methods=["GET", "POST"])
def participate():
    companies = list_companies()
    if request.method == "GET":
        docs_by_company = {
            c.slug: [{"key": d["key"], "title": d["title"], "default": d.get("default", False),
                      "kind": d["kind"], "note": d.get("note", "")} for d in c.documents]
            for c in companies}
        return render_template("participate.html", companies=companies, docs_by_company=docs_by_company,
                               default_company=load_settings()["default_company"])

    # ---------------- POST: a bid PDF was uploaded ----------------
    company = get_company(request.form.get("company", ""))
    bid_file = request.files.get("bid_pdf")
    if not bid_file or not bid_file.filename or not is_pdf(bid_file):
        flash("Please choose the bid document as a PDF file.", "error")
        return redirect(url_for("participate.participate"))

    incoming = DATA_DIR / "_incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    tmp = incoming / f"{uuid.uuid4().hex}.pdf"
    bid_file.save(tmp)

    fields, warnings = extract_bid(tmp)
    filing = today_iso()
    fields["filing_date"] = filing
    folder = make_folder(company.slug, filing, safe_name(fields["bid_number"]))
    shutil.move(str(tmp), folder / "source" / secure_filename(bid_file.filename))

    selected = [k for k in request.form.getlist("docs") if k in {d["key"] for d in company.documents}]
    state = {"company": company.slug, "source_file": secure_filename(bid_file.filename),
             "fields": fields, "warnings": warnings, "selected_docs": selected,
             "part_order": {}, "uploads": {"extra": []}}

    pb = request.files.get("price_breakup_pdf")
    if pb and pb.filename and is_pdf(pb):
        pb.save(folder / "uploads" / "price_breakup.pdf")
        state["uploads"]["price_breakup"] = "uploads/price_breakup.pdf"
    for i, ex in enumerate(request.files.getlist("extra_pdfs")):
        if ex and ex.filename and is_pdf(ex):
            name = f"extra_{i + 1}_{secure_filename(ex.filename)}"
            ex.save(folder / "uploads" / name)
            state["uploads"]["extra"].append(f"uploads/{name}")

    save_state(folder, state)
    tid = create_tender(company.slug, fields["bid_number"], filing, folder)
    flash("Bid document read. Please check the details below.", "ok")
    return redirect(url_for("bid.details", tid=tid))
