"""Companies are folders under companies/. Each one is fully self-contained,
so work for one company never mixes with another."""
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..settings import COMPANIES_DIR


@dataclass
class Company:
    slug: str
    name: str
    ref_prefix: str
    folder: Path
    template: Path
    placeholders: dict
    attachments: dict = field(default_factory=dict)   # key -> {"path": Path, "label": str}
    documents: list = field(default_factory=list)     # list of recipe dicts

    def document(self, key: str) -> dict:
        for d in self.documents:
            if d["key"] == key:
                return d
        raise KeyError(key)


def _load(folder: Path) -> Company:
    cfg = yaml.safe_load((folder / "company.yaml").read_text(encoding="utf-8"))
    rec = yaml.safe_load((folder / "recipes.yaml").read_text(encoding="utf-8"))
    atts = {
        k: {"path": folder / v["file"], "label": v.get("label", k)}
        for k, v in (rec.get("attachments") or {}).items()
    }
    return Company(
        slug=cfg["slug"],
        name=cfg["name"],
        ref_prefix=cfg["ref_prefix"],
        folder=folder,
        template=folder / cfg["template"],
        placeholders=cfg.get("placeholders") or {},
        attachments=atts,
        documents=rec.get("documents") or [],
    )


def list_companies() -> list[Company]:
    out = []
    for f in sorted(COMPANIES_DIR.iterdir()):
        if f.is_dir() and (f / "company.yaml").exists() and (f / "recipes.yaml").exists():
            out.append(_load(f))
    return out


def get_company(slug: str) -> Company:
    for c in list_companies():
        if c.slug == slug:
            return c
    raise KeyError(f"Unknown company: {slug}")
