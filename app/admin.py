"""Admin: turn a plain-text extract into draft entries, then let a human approve them.

Nothing reaches the knowledge base without that approval step. That is what keeps
the project's "curated and verified" claim honest — auto-ingesting whatever a PDF
happens to contain would quietly break it.
"""
from __future__ import annotations

import json
import re
from datetime import date

from . import config, kb, llm, prompts, retriever

ALLOWED_TOP_KEYS = {
    "id", "domain", "subtype", "field", "title_bn", "title_en", "content_bn",
    "content_en", "office_bn", "office_en", "online_possible", "applies_when",
    "source_url", "verified_on", "keywords",
}
ID_RE = re.compile(r"^[a-z_]+\.[a-z_]+\.[a-z_]+$")


def _read_pending() -> list[dict]:
    if not config.PENDING_FILE.exists():
        return []
    try:
        return json.loads(config.PENDING_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def _write_pending(rows: list[dict]) -> None:
    config.PENDING_FILE.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def _clean(entry: dict) -> dict:
    """Drop anything the model invented outside the schema, and normalise ids."""
    out = {k: v for k, v in entry.items() if k in ALLOWED_TOP_KEYS}
    out.setdefault("applies_when", {})
    out.setdefault("keywords", [])
    out.setdefault("source_url", "")
    out["verified_on"] = None                 # a human sets this, never the model
    dom, sub, field = out.get("domain"), out.get("subtype"), out.get("field")
    if dom in kb.TAXONOMY and sub in kb.TAXONOMY[dom]["subtypes"] and field in kb.FIELDS:
        out["id"] = f"{dom}.{sub}.{field}"
    return out


def _valid(entry: dict) -> tuple[bool, str]:
    for key in ("id", "domain", "subtype", "field", "title_bn", "title_en",
                "content_bn", "content_en"):
        if not entry.get(key):
            return False, f"missing {key}"
    if not ID_RE.match(entry["id"]):
        return False, "bad id format"
    if entry["domain"] not in kb.TAXONOMY:
        return False, "unknown domain"
    if entry["subtype"] not in kb.TAXONOMY[entry["domain"]]["subtypes"]:
        return False, "unknown subtype"
    if entry["field"] not in kb.FIELDS:
        return False, "unknown field"
    return True, ""


def propose(text: str) -> dict:
    """Step 1 — the model drafts entries. They land in pending.json, not the KB."""
    text = (text or "").strip()
    if len(text) < 40:
        return {"ok": False, "error": "text too short", "entries": []}

    result = llm.generate_json(prompts.propose_system(), f"DOCUMENT TEXT:\n\n{text[:20000]}")
    drafts, rejected = [], []
    for raw in (result.get("entries") or [])[:20]:
        entry = _clean(raw)
        ok, why = _valid(entry)
        (drafts if ok else rejected).append(entry if ok else {"entry": entry, "why": why})

    existing = {e["id"] for e in kb.load()}
    for entry in drafts:
        entry["_replaces_existing"] = entry["id"] in existing

    _write_pending(drafts)
    return {"ok": True, "entries": drafts, "rejected": rejected, "count": len(drafts)}


def pending() -> list[dict]:
    return _read_pending()

def unverified() -> list[dict]:
    """Return all existing KB entries that are missing a verified_on date."""
    return [e for e in kb.load() if not e.get("verified_on")]


def approve(entries: list[dict], verified_on: str | None = None) -> dict:
    """Step 2 — a human has edited and approved these. Only now do they enter the KB."""
    stamp = verified_on or date.today().isoformat()
    written, skipped = [], []

    by_domain: dict[str, list[dict]] = {}
    for raw in entries:
        entry = {k: v for k, v in _clean(raw).items() if not k.startswith("_")}
        ok, why = _valid(entry)
        if not ok:
            skipped.append({"id": raw.get("id"), "why": why})
            continue
        entry["verified_on"] = stamp
        by_domain.setdefault(entry["domain"], []).append(entry)

    for domain, rows in by_domain.items():
        path = config.KB_FILES.get(domain)
        if not path:
            continue
        current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        index = {e["id"]: i for i, e in enumerate(current)}
        for entry in rows:
            if entry["id"] in index:
                current[index[entry["id"]]] = entry
            else:
                current.append(entry)
            written.append(entry["id"])
        path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")

    if written:
        retriever.reset()                      # re-validate and re-embed on next query
        _write_pending([e for e in _read_pending() if e.get("id") not in written])

    return {"ok": True, "written": written, "skipped": skipped,
            "verified_on": stamp, "stats": kb.stats(),
            "note": "Free hosting has an ephemeral filesystem — commit data/*.json to git "
                    "so these entries survive the next redeploy."}
