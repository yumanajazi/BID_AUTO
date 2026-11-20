"""The three step pages of one bid:  1 Details  ->  2 Documents  ->  3 Generate."""
from pathlib import Path

from flask import (Blueprint, abort, flash, jsonify, redirect, render_template,
                   request, send_from_directory, url_for)
from werkzeug.utils import secure_filename

from ..services.companies import get_company
from ..services.converter import ConversionError
from ..services.docx_fill import count_letters
from ..services.merger import page_count
from ..services.normalizer import build_context
from ..services.pipeline import generate
from ..services.refnumbers import make_letter_no
from ..services.storage import (get_tender, load_manifest, load_state, save_manifest,
                                save_state, update_tender)

bp = Blueprint("bid", __name__, url_prefix="/bid/<int:tid>")

EDITABLE_FIELDS = ["bid_number", "bid_opening", "bid_published", "category", "buyer_designation",
                   "buyer_office", "buyer_line3", "filing_date"]


def _load(tid: int):
    t = get_tender(tid)
    if not t:
        abort(404)
    folder = Path(t["folder"])
    return t, folder, get_company(t["company"]), load_state(folder)


def _is_pdf(fs) -> bool:
    head = fs.stream.read(5)
    fs.stream.seek(0)
    return head == b"%PDF-"


# --------------------------------------------------------------------------- 1
@bp.route("/details", methods=["GET", "POST"])
def details(tid):
    t, folder, company, state = _load(tid)
    f = state["fields"]
    if request.method == "POST":
        for k in EDITABLE_FIELDS:
            f[k] = request.form.get(k, "").strip()
        problems = [label for k, label in (("bid_number", "Bid number"), ("bid_opening", "Bid opening date"),
                                           ("category", "Bid category"), ("buyer_office", "Buyer address"),
                                           ("filing_date", "Date of filing")) if not f[k]]
        save_state(folder, state)
        update_tender(tid, bid_number=f["bid_number"], filing_date=f["filing_date"])
        if problems:
            flash("Still empty: " + ", ".join(problems), "error")
        elif request.form.get("action") == "next":
            return redirect(url_for("bid.documents", tid=tid))
        else:
            flash("Saved.", "ok")
    ctx = build_context(f)
    return render_template("details.html", t=t, f=f, ctx=ctx, warnings=state.get("warnings", []),
                           company=company, step="details", sample_letter=make_letter_no(
                               company.ref_prefix, f["filing_date"], 1) if f.get("filing_date") else "")


@bp.route("/preview-text", methods=["POST"])
def preview_text(tid):
    """Called by the page while you type, so you see the final text instantly."""
    t, folder, company, state = _load(tid)
    f = dict(state["fields"])
    f.update({k: (request.json or {}).get(k, f.get(k, "")) for k in EDITABLE_FIELDS})
    ctx = build_context(f)
    return jsonify({**ctx, "letter": make_letter_no(company.ref_prefix, f["filing_date"], 1) if f.get("filing_date") else ""})


# --------------------------------------------------------------------------- 2
@bp.route("/documents", methods=["GET", "POST"])
def documents(tid):
    t, folder, company, state = _load(tid)

    if request.method == "POST":
        state["selected_docs"] = [d["key"] for d in company.documents if request.form.get(f"sel_{d['key']}")]
        for d in company.documents:
            if d["kind"] != "slice":
                continue
            chosen = []
            for part in d["parts"]:
                if part == "letter" or request.form.get(f"use_{d['key']}_{part}"):
                    try:
                        order = int(request.form.get(f"order_{d['key']}_{part}", "0"))
                    except ValueError:
                        order = 0
                    chosen.append((order, part))
            state["part_order"][d["key"]] = [p for _, p in sorted(chosen, key=lambda x: x[0])]
        pb = request.files.get("price_breakup_pdf")
        if pb and pb.filename:
            if _is_pdf(pb):
                pb.save(folder / "uploads" / "price_breakup.pdf")
                state["uploads"]["price_breakup"] = "uploads/price_breakup.pdf"
            else:
                flash("Price breakup must be a PDF.", "error")
        for i, ex in enumerate(request.files.getlist("extra_pdfs")):
            if ex and ex.filename and _is_pdf(ex):
                name = f"extra_{len(state['uploads']['extra']) + 1}_{secure_filename(ex.filename)}"
                ex.save(folder / "uploads" / name)
                state["uploads"]["extra"].append(f"uploads/{name}")
        for rm in request.form.getlist("remove_extra"):
            if rm in state["uploads"]["extra"]:
                state["uploads"]["extra"].remove(rm)
        save_state(folder, state)
        if request.form.get("action") == "next":
            return redirect(url_for("bid.generate", tid=tid))
        flash("Saved.", "ok")

    cards = []
    for d in company.documents:
        card = {"key": d["key"], "title": d["title"], "kind": d["kind"], "note": d.get("note", ""),
                "selected": d["key"] in state["selected_docs"], "parts": []}
        if d["kind"] == "slice":
            current = state["part_order"].get(d["key"]) or d["parts"]
            ordered = current + [p for p in d["parts"] if p not in current]
            for i, part in enumerate(ordered, 1):
                att = company.attachments.get(part)
                card["parts"].append({
                    "key": part, "locked": part == "letter", "use": part in current, "order": i,
                    "label": "The letter (generated from your ATC, with the same letter number and dates)"
                             if part == "letter" else att["label"],
                    "pages": 1 if part == "letter" else page_count(att["path"])})
        if d["kind"] == "template":
            n = count_letters(company.template, company.ref_prefix)
            card["letters"] = [make_letter_no(company.ref_prefix, state["fields"]["filing_date"], i + 1)
                               for i in range(n)] if state["fields"].get("filing_date") else []
        if d["kind"] == "upload":
            card["uploaded"] = state["uploads"].get(d["key"])
        cards.append(card)
    return render_template("documents.html", t=t, cards=cards, extras=state["uploads"]["extra"],
                           company=company, step="documents")


# --------------------------------------------------------------------------- 3
@bp.route("/generate", methods=["GET", "POST"])
def generate_page(tid):
    t, folder, company, state = _load(tid)
    error = None
    if request.method == "POST":
        try:
            manifest = generate(company, folder, state)
            save_manifest(folder, manifest)
            update_tender(tid, status="generated")
            flash("All documents generated.", "ok")
        except (ValueError, ConversionError, KeyError) as e:
            error = str(e)
    manifest = load_manifest(folder)
    return render_template("generate.html", t=t, state=state, manifest=manifest, error=error,
                           folder=str(folder), company=company, step="generate")


bp.add_url_rule("/generate", endpoint="generate", view_func=generate_page, methods=["GET", "POST"])


@bp.route("/file/<sub>/<path:name>")
def file(tid, sub, name):
    t, folder, *_ = _load(tid)
    if sub not in ("documents", "preview", "editable", "source", "uploads"):
        abort(404)
    return send_from_directory(folder / sub, name, as_attachment=(sub in ("documents", "editable")))
