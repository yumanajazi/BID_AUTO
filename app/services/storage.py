"""Where bids live.

On disk (traceable, plain files you can open any time):
   <output_root>/<company>/<YYYY-MM-DD>/<GEM_2026_B_1234567>/
        source/      the original bid PDF you uploaded
        uploads/     PDFs you uploaded yourself (price breakup, extras)
        editable/    the filled Word files (open and tweak in Word if needed)
        documents/   the FINAL PDFs to upload on GeM  (+ package.zip)
        preview/     thumbnails shown in the app
        bid.json     every field + every choice (the full state of this bid)
        manifest.json what was generated, when, with which converter

In a small SQLite database (data/tenders.db): one row per bid, so the Home
page can list your recent tenders.
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from ..settings import DATA_DIR, DB_FILE, output_root

SUBFOLDERS = ("source", "uploads", "editable", "documents", "preview")


def _db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_FILE)
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS tenders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company TEXT, bid_number TEXT, filing_date TEXT,
        folder TEXT, status TEXT, created_at TEXT, updated_at TEXT)""")
    return con


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def make_folder(company: str, filing_iso: str, safe_bid: str) -> Path:
    base = output_root() / company / filing_iso
    folder = base / safe_bid
    n = 2
    while folder.exists():                      # same bid twice on one day -> _2, _3 ...
        folder = base / f"{safe_bid}_{n}"
        n += 1
    for sub in SUBFOLDERS:
        (folder / sub).mkdir(parents=True, exist_ok=True)
    return folder


def create_tender(company: str, bid_number: str, filing_iso: str, folder: Path) -> int:
    with _db() as con:
        cur = con.execute(
            "INSERT INTO tenders (company,bid_number,filing_date,folder,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
            (company, bid_number, filing_iso, str(folder), "details", _now(), _now()))
        return cur.lastrowid


def get_tender(tid: int) -> dict | None:
    with _db() as con:
        row = con.execute("SELECT * FROM tenders WHERE id=?", (tid,)).fetchone()
    return dict(row) if row else None


def update_tender(tid: int, **cols) -> None:
    cols["updated_at"] = _now()
    sets = ", ".join(f"{k}=?" for k in cols)
    with _db() as con:
        con.execute(f"UPDATE tenders SET {sets} WHERE id=?", (*cols.values(), tid))


def recent_tenders(limit: int = 15) -> list[dict]:
    with _db() as con:
        rows = con.execute("SELECT * FROM tenders ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


# ---- the per-bid state file ----------------------------------------------------
def load_state(folder: Path) -> dict:
    return json.loads((Path(folder) / "bid.json").read_text(encoding="utf-8"))


def save_state(folder: Path, state: dict) -> None:
    (Path(folder) / "bid.json").write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def save_manifest(folder: Path, manifest: dict) -> None:
    (Path(folder) / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def load_manifest(folder: Path) -> dict | None:
    p = Path(folder) / "manifest.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
