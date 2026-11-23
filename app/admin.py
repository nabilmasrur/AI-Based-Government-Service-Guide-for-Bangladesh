"""Admin: turn a plain-text extract into draft entries, then let a human approve them.

Nothing reaches the knowledge base without that approval step. That is what keeps
the project's "curated and verified" claim honest — auto-ingesting whatever a PDF
happens to contain would quietly break it.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import date

from . import config, kb, llm, prompts, retriever

log = logging.getLogger("admin")

ALLOWED_TOP_KEYS = {
    "id", "domain", "subtype", "field", "title_bn", "title_en", "content_bn",
    "content_en", "office_bn", "office_en", "online_possible", "applies_when",
    "source_url", "verified_on", "keywords",
}
ID_RE = re.compile(r"^[a-z_]+\.[a-z_]+\.[a-z_]+$")


# Taxonomy Aliases for robust extraction matching
FIELD_ALIASES: dict[str, str] = {
    "cost": "fee",
    "fees": "fee",
    "fee_amount": "fee",
    "price": "fee",
    "charges": "fee",
    "amount": "fee",
    "taka": "fee",
    "requirements": "documents",
    "required_documents": "documents",
    "docs": "documents",
    "papers": "documents",
    "document": "documents",
    "doc": "documents",
    "procedure": "online_steps",
    "process": "online_steps",
    "steps": "online_steps",
    "rules": "online_steps",
    "how_to_apply": "online_steps",
    "method": "online_steps",
    "instruction": "online_steps",
    "instructions": "online_steps",
    "location": "office",
    "place": "office",
    "address": "office",
    "center": "office",
    "dept": "office",
    "authority": "office",
    "where_to_go": "office",
    "time": "timeline",
    "duration": "timeline",
    "delivery_time": "timeline",
    "processing_time": "timeline",
    "period": "timeline",
    "payment_method": "payment",
    "how_to_pay": "payment",
    "bank": "payment",
    "police": "verification",
    "police_verification": "verification",
    "children": "minor",
    "child": "minor",
    "delivery": "collection",
    "collection_process": "collection",
    "criteria": "eligibility",
    "age": "eligibility",
    "qualification": "eligibility",
    "schedule": "appointment",
    "contact": "helpline",
    "phone": "helpline",
    "hotline": "helpline",
    "guidelines": "note",
    "general": "note",
    "notes": "note",
    "notice": "note",
}

SUBTYPE_ALIASES: dict[str, dict[str, str]] = {
    "renew": {"passport": "reissue", "licence": "renewal"},
    "renewal": {"passport": "reissue", "licence": "renewal"},
    "reissue": {"passport": "reissue", "licence": "renewal"},
    "re_issue": {"passport": "reissue", "licence": "renewal"},
    "re-issue": {"passport": "reissue", "licence": "renewal"},
    "new_application": {"passport": "new", "licence": "smartcard_new"},
    "new_apply": {"passport": "new", "licence": "smartcard_new"},
    "first_time": {"passport": "new", "licence": "learner"},
    "smart_card": {"passport": "new", "licence": "smartcard_new"},
    "smartcard": {"passport": "new", "licence": "smartcard_new"},
    "lost_passport": {"passport": "lost", "licence": "duplicate"},
    "lost_licence": {"passport": "lost", "licence": "duplicate"},
    "lost": {"passport": "lost", "licence": "duplicate"},
    "duplicate": {"passport": "lost", "licence": "duplicate"},
    "correction": {"passport": "correction", "licence": "renewal"},
    "info_correction": {"passport": "correction", "licence": "renewal"},
    "mrp": {"passport": "mrp_to_epp", "licence": "smartcard_new"},
    "mrp_epp": {"passport": "mrp_to_epp", "licence": "smartcard_new"},
    "mrp_to_epassport": {"passport": "mrp_to_epp", "licence": "smartcard_new"},
    "test": {"passport": "new", "licence": "exam"},
    "exam": {"passport": "new", "licence": "exam"},
    "driving_test": {"passport": "new", "licence": "exam"},
    "international": {"passport": "new", "licence": "idp"},
    "international_permit": {"passport": "new", "licence": "idp"},
}


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
    """Drop anything the model invented outside the schema, normalize fields/subtypes, and normalise ids."""
    out = {k: v for k, v in entry.items() if k in ALLOWED_TOP_KEYS}
    out.setdefault("applies_when", {})
    out.setdefault("keywords", [])
    out.setdefault("source_url", "")
    out["verified_on"] = None                 # a human sets this, never the model

    dom = out.get("domain") or ""
    if dom not in kb.TAXONOMY:
        raw_id = str(entry.get("id", "")).lower()
        content = (str(entry.get("content_bn", "")) + " " + str(entry.get("title_bn", ""))).lower()
        if "licence" in raw_id or "license" in raw_id or "brta" in raw_id or "ড্রাইভিং" in content:
            dom = "licence"
        else:
            dom = "passport"
    out["domain"] = dom

    field = str(out.get("field") or "").strip().lower()
    if field not in kb.FIELDS and field in FIELD_ALIASES:
        field = FIELD_ALIASES[field]
    elif field not in kb.FIELDS:
        field = "note"
    out["field"] = field

    sub = str(out.get("subtype") or "").strip().lower().replace("-", "_")
    if dom in kb.TAXONOMY and sub not in kb.TAXONOMY[dom]["subtypes"]:
        if sub in SUBTYPE_ALIASES:
            sub = SUBTYPE_ALIASES[sub].get(dom, sub)
        elif dom == "passport":
            sub = "new"
        else:
            sub = "smartcard_new"
    out["subtype"] = sub

    out["id"] = f"{dom}.{sub}.{field}"

    # Ensure title_bn is formulated as an informative citizen question
    if not out.get("title_bn"):
        sub_bn = kb.TAXONOMY[dom]["subtypes"].get(sub, {}).get("bn", sub)
        fld_bn = kb.FIELDS.get(field, {}).get("bn", field)
        out["title_bn"] = f"{sub_bn} — {fld_bn} সংক্রান্ত প্রশ্নোত্তর"
    if not out.get("title_en"):
        sub_en = kb.TAXONOMY[dom]["subtypes"].get(sub, {}).get("en", sub)
        fld_en = kb.FIELDS.get(field, {}).get("en", field)
        out["title_en"] = f"{sub_en} — {fld_en} Information"

    # Add useful keywords if missing
    kw = list(out.get("keywords") or [])
    sub_bn = kb.TAXONOMY[dom]["subtypes"].get(sub, {}).get("bn", "")
    fld_bn = kb.FIELDS.get(field, {}).get("bn", "")
    for k in [dom, sub, field, sub_bn, fld_bn]:
        if k and k not in kw:
            kw.append(k)
    out["keywords"] = kw[:15]

    return out


def _valid(entry: dict) -> tuple[bool, str]:
    for key in ("id", "domain", "subtype", "field", "title_bn", "title_en",
                "content_bn", "content_en"):
        if not entry.get(key):
            return False, f"missing {key}"
    if not ID_RE.match(entry["id"]):
        return False, f"bad id format: {entry['id']}"
    if entry["domain"] not in kb.TAXONOMY:
        return False, f"unknown domain: {entry['domain']}"
    if entry["subtype"] not in kb.TAXONOMY[entry["domain"]]["subtypes"]:
        return False, f"unknown subtype: {entry['subtype']}"
    if entry["field"] not in kb.FIELDS:
        return False, f"unknown field: {entry['field']}"
    return True, ""


def _fallback_extract(text: str) -> list[dict]:
    """Rule-based extractor that crafts multiple valid, high-quality citizen Q&A entries
    when Gemini LLM is unavailable (e.g. 429 quota or connection timeout)."""
    norm = unicodedata.normalize("NFC", text.lower())
    
    # 1. Determine domain
    dom = "passport"
    if any(k in norm for k in ["লাইসেন্স", "ড্রাইভিং", "বিআরটিএ", "যানবাহন", "মোটরযান", "licence", "license", "driving", "brta"]):
        dom = "licence"

    # 2. Determine primary subtype
    sub = "new" if dom == "passport" else "smartcard_new"
    if any(k in norm for k in ["রিনিউ", "নবায়ন", "নবায়ন", "renew", "reissue", "রি-ইস্যু", "রিইস্যু", "মেয়াদ শেষ", "মেয়াদোত্তীর্ণ"]):
        sub = "renewal" if dom == "licence" else "reissue"
    elif any(k in norm for k in ["হারা", "হারিয়ে", "হারিয়ে", "lost", "জিডি", "ডুপ্লিকেট"]):
        sub = "duplicate" if dom == "licence" else "lost"
    elif dom == "licence" and any(k in norm for k in ["লার্নার", "শিক্ষানবিশ", "learner"]):
        sub = "learner"
    elif dom == "licence" and any(k in norm for k in ["পরীক্ষা", "ফিল্ড টেস্ট", "লিখিত পরীক্ষা", "ড্রাইভিং টেস্ট", "exam"]):
        sub = "exam"
    elif dom == "passport" and any(k in norm for k in ["সংশোধন", "নাম সংশোধন", "বয়স সংশোধন", "correction"]):
        sub = "correction"
    elif dom == "passport" and any(k in norm for k in ["এমআরপি", "mrp"]):
        sub = "mrp_to_epp"

    sub_info = kb.TAXONOMY[dom]["subtypes"].get(sub, {"bn": sub, "en": sub})
    sub_label_bn = sub_info["bn"]
    sub_label_en = sub_info["en"]
    dom_label_bn = kb.TAXONOMY[dom]["label_bn"]
    dom_label_en = kb.TAXONOMY[dom]["label_en"]

    # Extract source url
    source_match = re.search(r"https?://\S+|www\.\S+", text)
    if source_match:
        source_url = source_match.group(0)
        if source_url.startswith("www."):
            source_url = "https://" + source_url
    else:
        source_url = "https://www.epassport.gov.bd/" if dom == "passport" else "https://brta.gov.bd/"

    # Split document into clean lines
    raw_lines = [l.strip() for l in text.splitlines() if l.strip()]
    entries = []

    # Topic A: Documents / প্রয়োজনীয় কাগজপত্র
    doc_keywords = ["কাগজ", "ডকুমেন্ট", "document", "সনদ", "ফটোকপি", "কপি", "জাতীয় পরিচয়পত্র", "nid", "ছবি", "সার্টিফিকেট", "দাখিল", "প্রয়োজনীয় কাগজপত্র", "কাগজপত্র"]
    doc_lines = [l for l in raw_lines if any(k in l.lower() for k in doc_keywords)]
    if doc_lines:
        content_bn_lines = []
        for i, l in enumerate(doc_lines[:8], 1):
            cleaned = re.sub(r"^[\d\.\-\*\•\s]+", "", l)
            content_bn_lines.append(f"{i}. {cleaned}")
        content_bn = "\n".join(content_bn_lines)
        entries.append({
            "id": f"{dom}.{sub}.documents",
            "domain": dom,
            "subtype": sub,
            "field": "documents",
            "title_bn": f"{dom_label_bn} ({sub_label_bn}) — কী কী কাগজপত্র প্রয়োজন?",
            "title_en": f"{dom_label_en} ({sub_label_en}) — What documents are required?",
            "content_bn": content_bn,
            "content_en": f"Required documents for {dom_label_en} ({sub_label_en}):\n" + "\n".join(f"- {l}" for l in doc_lines[:6]),
            "office_bn": "নিজ এলাকার আঞ্চলিক অফিস" if dom == "passport" else "বিআরটিএ সার্কেল অফিস",
            "office_en": "Regional Passport Office" if dom == "passport" else "BRTA Circle Office",
            "online_possible": True,
            "source_url": source_url,
            "verified_on": None,
            "applies_when": {},
            "keywords": [dom, sub, "documents", "কাগজপত্র", "কী কী লাগবে", "ডকুমেন্ট", "nid", "ফটোকপি"],
        })

    # Topic B: Fees / সরকারি ফি
    fee_keywords = ["ফি", "টাকা", "fee", "খরচ", "টাকার", "ভ্যাট", "চালান", "টেলিটক", "ব্যাংক", "tk", "bdt", "মূল্য"]
    fee_lines = [l for l in raw_lines if any(k in l.lower() for k in fee_keywords)]
    if fee_lines:
        content_bn = "\n".join(f"• {re.sub(r'^[•\-\*\s]+', '', l)}" for l in fee_lines[:6])
        entries.append({
            "id": f"{dom}.{sub}.fee",
            "domain": dom,
            "subtype": sub,
            "field": "fee",
            "title_bn": f"{dom_label_bn} ({sub_label_bn}) — সরকারি ফি কত এবং কীভাবে প্রদান করবেন?",
            "title_en": f"{dom_label_en} ({sub_label_en}) — What is the official fee and payment method?",
            "content_bn": content_bn,
            "content_en": f"Official fee structure for {dom_label_en} ({sub_label_en}):\n" + "\n".join(f"- {l}" for l in fee_lines[:6]),
            "office_bn": "অনলাইন পেমেন্ট গেটওয়ে / নির্ধারিত ব্যাংক শাখা",
            "office_en": "Online Payment Gateway / Designated Bank Branch",
            "online_possible": True,
            "source_url": source_url,
            "verified_on": None,
            "applies_when": {},
            "keywords": [dom, sub, "fee", "ফি কত", "টাকা কত", "খরচ", "ব্যাংক চালান", "পেমেন্ট"],
        })

    # Topic C: Online Steps / আবেদনের নিয়মাবলি
    step_keywords = ["অনলাইন", "আবেদন", "ধাপ", "পদ্ধতি", "নিয়ম", "website", "portal", "ওয়েবসাইট", "ফরম", "প্রক্রিয়া", "লগইন", "রেজিস্ট্রেশন"]
    step_lines = [l for l in raw_lines if any(k in l.lower() for k in step_keywords) and l not in doc_lines and l not in fee_lines]
    if step_lines or any(k in norm for k in ["online", "অনলাইন"]):
        lines_to_use = step_lines[:6] if step_lines else raw_lines[:4]
        content_bn_steps = []
        for i, l in enumerate(lines_to_use, 1):
            cleaned = re.sub(r"^[\d\.\-\*\•\s]+", "", l)
            content_bn_steps.append(f"{i}. {cleaned}")
        content_bn = "\n".join(content_bn_steps)
        entries.append({
            "id": f"{dom}.{sub}.online_steps",
            "domain": dom,
            "subtype": sub,
            "field": "online_steps",
            "title_bn": f"{dom_label_bn} ({sub_label_bn}) — কীভাবে অনলাইনে আবেদন করবেন? (আবেদন পদ্ধতি)",
            "title_en": f"{dom_label_en} ({sub_label_en}) — How to apply online? (Application Procedure)",
            "content_bn": content_bn,
            "content_en": f"Step-by-step online application process for {dom_label_en} ({sub_label_en}):\n" + "\n".join(f"- {l}" for l in lines_to_use),
            "office_bn": "অনলাইন পোর্টাল",
            "office_en": "Official Online Portal",
            "online_possible": True,
            "source_url": source_url,
            "verified_on": None,
            "applies_when": {},
            "keywords": [dom, sub, "online_steps", "আবেদন পদ্ধতি", "কীভাবে আবেদন করব", "online apply", "ধাপসমূহ"],
        })

    # Topic D: Office / কোথায় জমা দিবেন
    office_keywords = ["অফিস", "দপ্তর", "শাখা", "উপস্থিত", "বায়োমেট্রিক", "আঙুলের ছাপ", "ছবি", "স্থান", "ঠিকানা", "সার্কেল", "office"]
    office_lines = [l for l in raw_lines if any(k in l.lower() for k in office_keywords) and l not in doc_lines and l not in fee_lines]
    if office_lines:
        content_bn = "\n".join(f"• {re.sub(r'^[•\-\*\s]+', '', l)}" for l in office_lines[:4])
        entries.append({
            "id": f"{dom}.{sub}.office",
            "domain": dom,
            "subtype": sub,
            "field": "office",
            "title_bn": f"{dom_label_bn} ({sub_label_bn}) — আবেদন জমা ও বায়োমেট্রিকের জন্য কোথায় যেতে হবে?",
            "title_en": f"{dom_label_en} ({sub_label_en}) — Where to go for submission and biometrics?",
            "content_bn": content_bn,
            "content_en": f"Office and physical submission instructions for {dom_label_en} ({sub_label_en}):\n" + "\n".join(f"- {l}" for l in office_lines[:4]),
            "office_bn": "আঞ্চলিক পাসপোর্ট অফিস" if dom == "passport" else "বিআরটিএ সার্কেল অফিস",
            "office_en": "Regional Passport Office" if dom == "passport" else "BRTA Circle Office",
            "online_possible": False,
            "source_url": source_url,
            "verified_on": None,
            "applies_when": {},
            "keywords": [dom, sub, "office", "কোথায় যাব", "আঞ্চলিক অফিস", "বায়োমেট্রিক"],
        })

    # Topic E: Timeline / কত দিন লাগবে
    time_keywords = ["দিন", "কর্মদিবস", "মেয়াদ", "জরুরি", "সময়", "working days", "timeline", "বিতরণ", "ডেলিভারি"]
    time_lines = [l for l in raw_lines if any(k in l.lower() for k in time_keywords) and l not in doc_lines and l not in fee_lines]
    if time_lines:
        content_bn = "\n".join(f"• {re.sub(r'^[•\-\*\s]+', '', l)}" for l in time_lines[:4])
        entries.append({
            "id": f"{dom}.{sub}.timeline",
            "domain": dom,
            "subtype": sub,
            "field": "timeline",
            "title_bn": f"{dom_label_bn} ({sub_label_bn}) — সেবা পেতে কত দিন সময় লাগে?",
            "title_en": f"{dom_label_en} ({sub_label_en}) — How long does it take for processing and delivery?",
            "content_bn": content_bn,
            "content_en": f"Delivery and processing timeline for {dom_label_en} ({sub_label_en}):\n" + "\n".join(f"- {l}" for l in time_lines[:4]),
            "office_bn": "সংশ্লিষ্ট বিতরণ শাখা",
            "office_en": "Respective Delivery Branch",
            "online_possible": True,
            "source_url": source_url,
            "verified_on": None,
            "applies_when": {},
            "keywords": [dom, sub, "timeline", "কত দিন লাগে", "সময়", "জরুরি", "ডেলিভারি সময়"],
        })

    # If no specific section was triggered, or to ensure complete fallback:
    if not entries:
        clean_content = " ".join(text.split())
        if len(clean_content) > 500:
            clean_content = clean_content[:500] + "..."
        entries.append({
            "id": f"{dom}.{sub}.note",
            "domain": dom,
            "subtype": sub,
            "field": "note",
            "title_bn": f"{dom_label_bn} ({sub_label_bn}) — প্রয়োজনীয় সরকারি নির্দেশনা ও জ্ঞাতব্য",
            "title_en": f"{dom_label_en} ({sub_label_en}) — Official Guidelines and Notice",
            "content_bn": clean_content,
            "content_en": f"Official public notice extracted from document: {clean_content[:200]}...",
            "office_bn": "সংশ্লিষ্ট সরকারি কর্তৃপক্ষ",
            "office_en": "Relevant Government Authority",
            "online_possible": True,
            "source_url": source_url,
            "verified_on": None,
            "applies_when": {},
            "keywords": [dom, sub, "note", "নির্দেশনা", "নিয়মাবলি", "সরকারি নোটিশ"],
        })

    return entries


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

    # Merge with existing pending drafts so prior drafts are not lost
    current_pending = _read_pending()
    pending_index = {e["id"]: i for i, e in enumerate(current_pending)}
    for d in drafts:
        if d["id"] in pending_index:
            current_pending[pending_index[d["id"]]] = d
        else:
            current_pending.append(d)

    _write_pending(current_pending)
    return {
        "ok": True,
        "entries": drafts,
        "all_pending_count": len(current_pending),
        "rejected": rejected,
        "count": len(drafts),
        "fallback": fallback_used,
        "note": "AI কোটা পূর্ণ থাকায় নিয়মভিত্তিক বহু-প্রশ্নোত্তর খসড়া তৈরি হয়েছে — এডিট করে অনুমোদন দিন।" if fallback_used else None,
    }


def pending() -> list[dict]:
    return _read_pending()

def unverified() -> list[dict]:
    """Return all existing KB entries that are missing a verified_on date."""
    return [e for e in kb.load() if not e.get("verified_on")]


def list_entries(domain: str | None = None, query: str | None = None) -> list[dict]:
    """Retrieve existing KB entries with optional domain filter and search query."""
    rows = kb.load()
    if domain and domain != "all":
        rows = [e for e in rows if e.get("domain") == domain]
    if query:
        q = query.strip().lower()
        rows = [
            e for e in rows
            if q in (e.get("title_bn") or "").lower()
            or q in (e.get("title_en") or "").lower()
            or q in (e.get("content_bn") or "").lower()
            or q in (e.get("content_en") or "").lower()
            or q in (e.get("id") or "").lower()
            or any(q in str(k).lower() for k in e.get("keywords", []))
        ]
    return rows


def update_entry(entry: dict, verified_by_human: bool = True) -> dict:
    """Update or insert a single entry into the official knowledge base files."""
    raw_id = entry.get("id")
    if not raw_id:
        return {"ok": False, "error": "এন্ট্রি আইডি (id) অনুপস্থিত।"}

    domain = entry.get("domain") or raw_id.split(".")[0]
    path = config.KB_FILES.get(domain)
    if not path or not path.exists():
        return {"ok": False, "error": f"অজানা বা অনুপস্থিত ডোমেন: {domain}"}

    ok, why = _valid(entry)
    if not ok:
        return {"ok": False, "error": f"ভ্যালিডেশন ত্রুটি: {why}"}

    clean_entry = {k: v for k, v in entry.items() if k in ALLOWED_TOP_KEYS}
    if verified_by_human:
        clean_entry["verified_on"] = date.today().isoformat()
    elif "verified_on" in entry:
        clean_entry["verified_on"] = entry["verified_on"]

    current = json.loads(path.read_text(encoding="utf-8"))
    index = {e["id"]: i for i, e in enumerate(current)}
    if raw_id in index:
        current[index[raw_id]] = clean_entry
    else:
        current.append(clean_entry)

    path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    retriever.reset()
    return {"ok": True, "entry": clean_entry, "stats": kb.stats()}


def delete_entry(entry_id: str) -> dict:
    """Delete an entry from the knowledge base."""
    domain = entry_id.split(".")[0] if "." in entry_id else ""
    path = config.KB_FILES.get(domain)
    if not path or not path.exists():
        return {"ok": False, "error": f"অজানা ডোমেন বা ফাইল নেই: {domain}"}
    current = json.loads(path.read_text(encoding="utf-8"))
    filtered = [e for e in current if e.get("id") != entry_id]
    if len(filtered) == len(current):
        return {"ok": False, "error": "এন্ট্রি খুঁজে পাওয়া যায়নি"}
    path.write_text(json.dumps(filtered, ensure_ascii=False, indent=2), encoding="utf-8")
    retriever.reset()
    return {"ok": True, "id": entry_id, "stats": kb.stats()}


def save_pending(entry: dict) -> dict:
    """Save or update an unapproved draft in pending.json."""
    ok, why = _valid(entry)
    if not ok:
        return {"ok": False, "error": f"ভ্যালিডেশন ত্রুটি: {why}"}
    clean_entry = _clean(entry)
    clean_entry["verified_on"] = None

    rows = _read_pending()
    index = {e.get("id"): i for i, e in enumerate(rows)}
    if clean_entry["id"] in index:
        rows[index[clean_entry["id"]]] = clean_entry
    else:
        rows.append(clean_entry)
    _write_pending(rows)
    return {"ok": True, "entry": clean_entry, "count": len(rows)}


def delete_pending(entry_id: str) -> dict:
    """Delete an unapproved draft from pending.json."""
    rows = _read_pending()
    new_rows = [e for e in rows if e.get("id") != entry_id]
    _write_pending(new_rows)
    return {"ok": True, "count": len(new_rows)}


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
