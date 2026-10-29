"""Knowledge base: the service taxonomy plus loading and validating the JSON entries."""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from . import config

# ---------------------------------------------------------------------------
# Taxonomy — the single source of truth. The prompts, the fast path and the
# frontend sidebar are all generated from this, so it is edited in ONE place.
# ---------------------------------------------------------------------------

SLOTS = {
    "pages": {"bn": "কত পৃষ্ঠা", "en": "Page count",
              "options": [("48", "৪৮ পৃষ্ঠা", "48 pages"), ("64", "৬৪ পৃষ্ঠা", "64 pages")]},
    "validity": {"bn": "কত বছরের মেয়াদ", "en": "Validity",
                 "options": [("5", "৫ বছর", "5 years"), ("10", "১০ বছর", "10 years")]},
    "delivery": {"bn": "কত দ্রুত দরকার", "en": "How urgent",
                 "options": [("regular", "নিয়মিত", "Regular"),
                             ("express", "জরুরি", "Express"),
                             ("super_express", "অতি জরুরি", "Super express")]},
    "vehicle_class": {"bn": "কোন শ্রেণির যানবাহন", "en": "Vehicle class",
                      "options": [("motorcycle", "মোটরসাইকেল", "Motorcycle"),
                                  ("light", "হালকা", "Light"),
                                  ("medium", "মাঝারি", "Medium"),
                                  ("heavy", "ভারী", "Heavy")]},
    "professional": {"bn": "পেশাদার নাকি অপেশাদার", "en": "Professional or not",
                     "options": [("true", "পেশাদার", "Professional"),
                                 ("false", "অপেশাদার", "Non-professional")]},
}

TAXONOMY: dict[str, dict[str, Any]] = {
    "passport": {
        "label_bn": "পাসপোর্ট", "label_en": "Passport",
        "authority_bn": "ইমিগ্রেশন ও পাসপোর্ট অধিদপ্তর",
        "authority_en": "Department of Immigration & Passports",
        "subtypes": {
            "new":         {"bn": "নতুন আবেদন", "en": "New application"},
            "reissue":     {"bn": "নবায়ন / রি-ইস্যু", "en": "Renewal / re-issue"},
            "correction":  {"bn": "তথ্য সংশোধন", "en": "Information correction"},
            "lost":        {"bn": "হারানো পাসপোর্ট", "en": "Lost passport"},
            "mrp_to_epp":  {"bn": "MRP → ই-পাসপোর্ট", "en": "MRP → e-passport"},
            "delivery":    {"bn": "বিতরণ ও ফি", "en": "Delivery & fee"},
            "status":      {"bn": "আবেদনের অবস্থা", "en": "Application status"},
        },
        "fee_slots": ["pages", "validity", "delivery"],
    },
    "licence": {
        "label_bn": "ড্রাইভিং লাইসেন্স", "label_en": "Driving licence",
        "authority_bn": "বাংলাদেশ সড়ক পরিবহন কর্তৃপক্ষ (BRTA)",
        "authority_en": "Bangladesh Road Transport Authority (BRTA)",
        "subtypes": {
            "learner":          {"bn": "শিক্ষানবিশ", "en": "Learner"},
            "smartcard_new":    {"bn": "স্মার্ট কার্ড", "en": "Smart card"},
            "renewal":          {"bn": "নবায়ন", "en": "Renewal"},
            "duplicate":        {"bn": "হারানো / ডুপ্লিকেট", "en": "Lost / duplicate"},
            "category_change":  {"bn": "শ্রেণি পরিবর্তন", "en": "Category change"},
            "exam":             {"bn": "পরীক্ষা পদ্ধতি", "en": "The driving test"},
            "idp":              {"bn": "আন্তর্জাতিক পারমিট", "en": "International permit"},
        },
        "fee_slots": ["vehicle_class", "professional"],
    },
}

FIELDS = {
    # The five that make up a normal answer card, in reading order.
    "office":       {"bn": "দায়িত্বপ্রাপ্ত দপ্তর", "en": "Responsible office"},
    "documents":    {"bn": "প্রয়োজনীয় কাগজপত্র", "en": "Required documents"},
    "fee":          {"bn": "ফি", "en": "Fee"},
    "timeline":     {"bn": "সময়", "en": "Processing time"},
    "online_steps": {"bn": "অনলাইনে কতটুকু", "en": "Done online"},
    # Shown when asked about directly, so the common card stays short.
    "payment":      {"bn": "ফি পরিশোধের উপায়", "en": "How to pay"},
    "verification": {"bn": "পুলিশ ভেরিফিকেশন", "en": "Police verification"},
    "minor":        {"bn": "শিশু ও অপ্রাপ্তবয়স্ক", "en": "Children and minors"},
    "collection":   {"bn": "সংগ্রহ ও বিতরণ", "en": "Collection and delivery"},
    "eligibility":  {"bn": "যোগ্যতা ও বয়স", "en": "Eligibility and age"},
    "validity":     {"bn": "মেয়াদ", "en": "Validity"},
    "appointment":  {"bn": "অ্যাপয়েন্টমেন্ট", "en": "Appointment"},
    "helpline":     {"bn": "যোগাযোগ", "en": "Contact"},
    "note":         {"bn": "দ্রষ্টব্য", "en": "Note"},
}

REQUIRED_KEYS = ("id", "domain", "subtype", "field", "title_bn", "title_en",
                 "content_bn", "content_en", "source_url", "keywords")

# ---------------------------------------------------------------------------

_entries: list[dict] | None = None


def _validate(entry: dict, where: str) -> None:
    for key in REQUIRED_KEYS:
        if key not in entry:
            raise ValueError(f"{where}: entry {entry.get('id', '?')} is missing '{key}'")
    dom, sub = entry["domain"], entry["subtype"]
    if dom not in TAXONOMY:
        raise ValueError(f"{where}: unknown domain '{dom}' in {entry['id']}")
    if sub not in TAXONOMY[dom]["subtypes"]:
        raise ValueError(f"{where}: unknown subtype '{sub}' in {entry['id']}")
    if entry["field"] not in FIELDS:
        raise ValueError(f"{where}: unknown field '{entry['field']}' in {entry['id']}")


def load(force: bool = False) -> list[dict]:
    """Read every KB file, validate it, and cache the result in memory."""
    global _entries
    if _entries is not None and not force:
        return _entries

    out: list[dict] = []
    seen: set[str] = set()
    for domain, path in config.KB_FILES.items():
        if not path.exists():
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        for entry in raw:
            _validate(entry, path.name)
            if entry["id"] in seen:
                raise ValueError(f"duplicate entry id: {entry['id']}")
            seen.add(entry["id"])
            entry.setdefault("applies_when", {})
            entry.setdefault("verified_on", None)
            entry.setdefault("online_possible", None)
            out.append(entry)
    _entries = out
    return out


def embed_text(entry: dict) -> str:
    """The text that gets embedded — both languages together, so a Bangla query
    and an English query land near the same point in vector space."""
    return "\n".join([
        entry["title_bn"], entry["title_en"],
        entry["content_bn"], entry["content_en"],
        " ".join(entry.get("keywords", [])),
    ])


def is_stale(entry: dict) -> bool:
    """True when the entry has never been verified, or was verified long ago."""
    stamp = entry.get("verified_on")
    if not stamp:
        return True
    try:
        seen = datetime.strptime(stamp, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return True
    return (date.today() - seen).days > config.STALE_DAYS


def stats() -> dict:
    entries = load()
    verified = [e for e in entries if not is_stale(e)]
    dates = sorted(e["verified_on"] for e in verified) if verified else []
    return {
        "total": len(entries),
        "verified": len(verified),
        "unverified": len(entries) - len(verified),
        "last_verified": dates[-1] if dates else None,
    }


def meta() -> dict:
    """Everything the frontend needs to build its sidebar and chips."""
    return {"taxonomy": TAXONOMY, "fields": FIELDS, "slots": SLOTS, "stats": stats()}
