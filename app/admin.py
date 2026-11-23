"""Admin: turn a plain-text extract into draft entries, then let a human approve them.

Nothing reaches the knowledge base without that approval step. That is what keeps
the project's "curated and verified" claim honest — auto-ingesting whatever a PDF
happens to contain would quietly break it.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date

from . import config, kb, llm, prompts, retriever

log = logging.getLogger("admin")

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


def _fallback_extract(text: str) -> list[dict]:
    """Rule-based extractor that crafts valid draft entries when Gemini LLM is unavailable (e.g. 429 quota)."""
    norm = text.lower()
    dom = "passport"
    if any(k in norm for k in ["লাইসেন্স", "ড্রাইভিং", "বিআরটিএ", "যানবাহন", "মোটরযান", "licence", "license", "driving", "brta"]):
        dom = "licence"

    sub = "new"
    if any(k in norm for k in ["রিনিউ", "নবায়ন", "renew", "reissue", "রি-ইস্যু"]):
        sub = "renewal" if dom == "licence" else "reissue"
    elif any(k in norm for k in ["হারা", "হারিয়ে", "lost", "জিডি", "ডুপ্লিকেট"]):
        sub = "duplicate" if dom == "licence" else "lost"
    elif dom == "licence" and any(k in norm for k in ["লার্নার", "শিক্ষানবিশ", "learner"]):
        sub = "learner"

    field = "note"
    if any(k in norm for k in ["ফি", "টাকা", "খরচ", "মূল্য", "fee", "cost", "দাম"]):
        field = "fee"
    elif any(k in norm for k in ["কাগজ", "ডকুমেন্ট", "document", "সার্টিফিকেট", "দলিল"]):
        field = "documents"
    elif any(k in norm for k in ["অফিস", "ঠিকানা", "office", "স্থান", "ঠিকানায়"]):
        field = "office"
    elif any(k in norm for k in ["অনলাইন", "website", "portal", "ওয়েবসাইট"]):
        field = "online_steps"

    # Extract source url if present in text
    source_match = re.search(r"https?://\S+|www\.\S+", text)
    source_url = source_match.group(0) if source_match else ("https://www.bgpress.gov.bd" if "bgpress" in norm else "https://bangladesh.gov.bd/")
    if source_url.startswith("www."):
        source_url = "https://" + source_url

    title_bn = f"{kb.TAXONOMY[dom]['label_bn']} সংক্রান্ত সরকারি নির্দেশনা"
    title_en = f"Official Guidelines on {kb.TAXONOMY[dom]['label_en']}"

    clean_content = " ".join(text.split())
    if len(clean_content) > 500:
        clean_content = clean_content[:500] + "..."

    entry = {
        "id": f"{dom}.{sub}.{field}",
        "domain": dom,
        "subtype": sub,
        "field": field,
        "title_bn": title_bn,
        "title_en": title_en,
        "content_bn": clean_content,
        "content_en": f"Official public notice extracted from document: {clean_content[:150]}...",
        "source_url": source_url,
        "verified_on": None,
        "applies_when": {},
        "keywords": [w for w in re.findall(r"[\u0980-\u09ff\w]{3,}", text) if len(w) >= 3][:8],
    }
    return [entry]


def propose(text: str) -> dict:
    """Step 1 — the model drafts entries. They land in pending.json, not the KB."""
    text = (text or "").strip()
    if len(text) < 40:
        return {"ok": False, "error": "আরও টেক্সট দিন (অন্তত ৪০ অক্ষর)।", "entries": []}

    drafts, rejected = [], []
    fallback_used = False

    try:
        result = llm.generate_json(prompts.propose_system(), f"DOCUMENT TEXT:\n\n{text[:20000]}")
        raw_entries = result.get("entries") or []
        for raw in raw_entries[:20]:
            entry = _clean(raw)
            ok, why = _valid(entry)
            (drafts if ok else rejected).append(entry if ok else {"entry": entry, "why": why})
    except Exception as exc:
        log.warning("LLM extraction failed or quota exceeded (%s) — falling back to rule-based parser", exc)
        fallback_used = True

    if not drafts:
        # Fall back to heuristic rule-based extraction
        for raw in _fallback_extract(text):
            entry = _clean(raw)
            ok, why = _valid(entry)
            if ok:
                drafts.append(entry)

    existing = {e["id"] for e in kb.load()}
    for entry in drafts:
        entry["_replaces_existing"] = entry["id"] in existing

    _write_pending(drafts)
    return {
        "ok": True,
        "entries": drafts,
        "rejected": rejected,
        "count": len(drafts),
        "fallback": fallback_used,
        "note": "AI কোটা পূর্ণ থাকায় নিয়মভিত্তিক খসড়া তৈরি হয়েছে — এডিট করে অনুমোদন দিন।" if fallback_used else None,
    }


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
