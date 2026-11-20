"""THE ORCHESTRA: runs the whole chain for one bid.

   fields -> context -> fill ATC template -> PDF
   then, from the filled ATC: cut the EMD / Turnover / Experience letter
        -> PDF -> + fixed certificates -> final PDF
   + your own uploads (price breakup, extras) copied in
   + package.zip of everything
"""
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from ..settings import load_settings
from .companies import Company
from .converter import docx_to_pdf
from .docx_fill import fill_docx
from .docx_slice import slice_docx
from .merger import merge_pdfs, page_count
from .normalizer import build_context, safe_name
from .previews import render_previews


def generate(company: Company, folder: Path, state: dict) -> dict:
    """Make every selected document. Returns the manifest (also saved to disk)."""
    folder = Path(folder)
    fields = state["fields"]
    selected = state["selected_docs"]
    mode = load_settings()["converter"]
    safe = safe_name(fields["bid_number"])
    docs_dir, edit_dir, prev_dir = folder / "documents", folder / "editable", folder / "preview"
    for d in (docs_dir, edit_dir, prev_dir):                  # start clean: no stale files
        for old in d.glob("*"):
            try:
                if old.is_dir():
                    shutil.rmtree(old, ignore_errors=True)
                else:
                    old.unlink()
            except PermissionError:
                raise ValueError(f"Cannot replace '{old.name}' because it is open in another program. "
                                 "Close it (PDF viewer / Word) and press Generate again.")

    warnings, outputs = [], []

    # ---- 1. fill the full ATC template -------------------------------------
    ctx = build_context(fields)
    missing = [k for k, v in ctx.items() if not v and k != "buyer_inline"]
    if missing:
        raise ValueError("These details are empty: " + ", ".join(missing) + ". Fill them on the Details page.")
    filled_docx = edit_dir / f"{safe}_ATC_filled.docx"
    report = fill_docx(company.template, filled_docx, ctx, company.placeholders,
                       company.ref_prefix, fields["filing_date"])
    if report["unknown"]:
        warnings.append("Template marks not recognised (left unchanged): " + ", ".join("{{" + m + "}}" for m in report["unknown"])
                        + " - add them in company.yaml.")

    engine = None
    work = folder / "editable" / "_work"
    work.mkdir(exist_ok=True)

    # ---- 2. go through the selected documents in recipe order --------------
    n = 0
    for doc in company.documents:
        key = doc["key"]
        if key not in selected:
            continue
        n += 1
        out_pdf = docs_dir / f"{safe}_{n:02d}_{doc['file_label']}.pdf"

        if doc["kind"] == "template":
            engine = docx_to_pdf(filled_docx, out_pdf, mode)
            pages = page_count(out_pdf)

        elif doc["kind"] == "slice":
            s = doc["slice"]
            part_docx = edit_dir / f"{safe}_{doc['file_label']}_letter.docx"
            slice_docx(filled_docx, part_docx, s["start_marker"], s["heading"], s["end_marker"])
            letter_pdf = work / f"{doc['key']}_letter.pdf"
            engine = docx_to_pdf(part_docx, letter_pdf, mode)
            if page_count(letter_pdf) != 1:
                warnings.append(f"{doc['title']}: the letter came out as {page_count(letter_pdf)} pages instead of 1 "
                                "(layout differs in this PDF converter). Check it carefully.")
            order = state.get("part_order", {}).get(key) or doc["parts"]
            parts = []
            for part in order:
                if part == "letter":
                    parts.append(letter_pdf)
                else:
                    parts.append(company.attachments[part]["path"])
            pages = merge_pdfs(parts, out_pdf)

        elif doc["kind"] == "upload":
            src = state.get("uploads", {}).get(key)
            if not src or not (folder / src).exists():
                warnings.append(f"{doc['title']} is ticked but no PDF was uploaded - skipped.")
                n -= 1
                continue
            shutil.copy(folder / src, out_pdf)
            pages = page_count(out_pdf)
        else:
            continue

        outputs.append({"key": key, "title": doc["title"], "file": out_pdf.name, "pages": pages,
                        "previews": render_previews(out_pdf, prev_dir, out_pdf.stem)})

    # ---- 3. extra uploads (e.g. EMD proof) -----------------------------------
    for extra in state.get("uploads", {}).get("extra", []):
        src = folder / extra
        if src.exists():
            n += 1
            out_pdf = docs_dir / f"{safe}_{n:02d}_Extra_{Path(extra).stem}.pdf"
            shutil.copy(src, out_pdf)
            outputs.append({"key": "extra", "title": f"Extra: {Path(extra).name}", "file": out_pdf.name,
                            "pages": page_count(out_pdf), "previews": render_previews(out_pdf, prev_dir, out_pdf.stem)})

    shutil.rmtree(work, ignore_errors=True)

    # ---- 4. one zip with everything ------------------------------------------
    zip_path = docs_dir / f"{safe}_package.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for o in outputs:
            z.write(docs_dir / o["file"], o["file"])

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "engine": engine, "letters": report["letters"], "outputs": outputs,
        "zip": zip_path.name, "warnings": warnings, "context": ctx,
    }
