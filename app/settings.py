"""Loads config/settings.yaml and knows where everything lives on disk."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "config" / "settings.yaml"
COMPANIES_DIR = ROOT / "companies"
DATA_DIR = ROOT / "data"
DB_FILE = DATA_DIR / "tenders.db"

_DEFAULTS = {
    "output_root": "outputs",
    "default_company": "snta",
    "converter": "auto",
    "host": "127.0.0.1",
    "port": 5000,
}


def load_settings() -> dict:
    s = dict(_DEFAULTS)
    if CONFIG_FILE.exists():
        s.update(yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {})
    return s


def output_root() -> Path:
    p = Path(str(load_settings()["output_root"])).expanduser()
    if not p.is_absolute():
        p = ROOT / p
    p.mkdir(parents=True, exist_ok=True)
    return p
