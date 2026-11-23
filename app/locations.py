"""Office locations lookup for 64 districts in Bangladesh."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Optional

from . import config

_DATA: dict[str, dict] = {}

def _load() -> dict[str, dict]:
    global _DATA
    if not _DATA:
        p = config.DATA_DIR / "offices.json"
        if p.exists():
            _DATA = json.loads(p.read_text(encoding="utf-8"))
    return _DATA


OFFICE_KEYWORDS = re.compile(
    r"কোথায়|কোথায়|কোন\s*অফিস|অফিস|ঠিকানা|লোকেশন|শাখা|যেতে\s*হবে"
    r"|kothay|kothae|kothai|kon\s*office|\boffice\b|where|which\s+office|address|location",
    re.IGNORECASE
)


def is_office_query(text: str) -> bool:
    """Returns True if the text asks about an office or location."""
    norm = unicodedata.normalize("NFC", text or "")
    return bool(OFFICE_KEYWORDS.search(norm))


def find_district(text: str) -> Optional[str]:
    """Finds district id from text if any district alias is present."""
    data = _load()
    norm = unicodedata.normalize("NFC", text or "").lower()
    
    # Priority for longer aliases to prevent sub-string false positives
    matches: list[tuple[int, str]] = []
    for d_id, info in data.items():
        for alias in info.get("aliases", []):
            a_norm = unicodedata.normalize("NFC", alias).lower()
            if a_norm in norm:
                matches.append((len(a_norm), d_id))
    
    if matches:
        matches.sort(key=lambda m: m[0], reverse=True)
        return matches[0][1]
    return None


def get_district_info(district_id: str) -> Optional[dict]:
    data = _load()
    return data.get(district_id)


def format_office_lead(district_id: str, domain: str = "passport", lang: str = "bn") -> str:
    """Formats exact office details matching requested citizen assistant format."""
    info = get_district_info(district_id)
    if not info:
        return ""
    
    dom_key = "licence" if domain == "licence" else "passport"
    off = info.get(dom_key, info.get("passport", {}))
    
    if lang == "bn":
        name = off.get("office_name_bn", "")
        addr = off.get("address_bn", "")
        hours = off.get("hours_bn", "রবিবার - বৃহস্পতিবার, সকাল ৯:০০ - বিকাল ৪:০০")
        phone = off.get("phone_bn", "")
        
        lines = [
            f"{name}",
            f"📍 ঠিকানা: {addr}",
            f"⏰ অফিসের সময়সূচী: {hours}",
            f"📞 হেল্পলাইন: {phone}"
        ]
        return "\n".join(lines)
    else:
        name = off.get("office_name_en", "")
        addr = off.get("address_en", "")
        hours = off.get("hours_en", "Sunday - Thursday, 9:00 AM - 4:00 PM")
        phone = off.get("phone_en", "")
        
        lines = [
            f"{name}",
            f"📍 Address: {addr}",
            f"⏰ Hours: {hours}",
            f"📞 Helpline: {phone}"
        ]
        return "\n".join(lines)


def build_office_card(district_id: str, domain: str = "passport", lang: str = "bn") -> dict:
    info = get_district_info(district_id)
    dom_key = "licence" if domain == "licence" else "passport"
    off = (info or {}).get(dom_key, {})
    
    dist_name = (info or {}).get(f"name_{lang}", district_id.capitalize())
    badge = f"পাসপোর্ট · আঞ্চলিক অফিস ({dist_name})" if dom_key == "passport" else f"ড্রাইভিং লাইসেন্স · বিআরটিএ ({dist_name})"
    if lang == "en":
        badge = f"Passport · Regional Office ({dist_name})" if dom_key == "passport" else f"Driving Licence · BRTA ({dist_name})"
        
    auth = "ইমিগ্রেশন ও পাসপোর্ট অধিদপ্তর (DIP)" if dom_key == "passport" else "বাংলাদেশ সড়ক পরিবহন কর্তৃপক্ষ (BRTA)"
    source_url = "https://www.epassport.gov.bd/" if dom_key == "passport" else "http://www.brta.gov.bd/"
    
    field_label = "অফিস ও সেবা অঞ্চল" if lang == "bn" else "Office & Jurisdiction"
    field_content = (
        f"{dist_name} জেলার আওতাধীন সকল উপজেলার নাগরিকরা এই অফিসে প্রয়োজনীয় সেবা গ্রহণ করতে পারবেন। "
        f"আবেদন ও ফি পরিশোধ অনলাইনে সম্পন্ন করার পর অ্যাপয়েন্টমেন্টের তারিখে সশরীরে উপস্থিত হতে হবে।"
        if lang == "bn" else
        f"Citizens under {dist_name} district can receive service at this office. "
        f"Complete online application and payment before visiting on the appointment date."
    )
    
    fields = [
        {
            "key": "office",
            "label": field_label,
            "content": field_content
        }
    ]
    
    return {
        "domain": dom_key,
        "subtype": "new",
        "badge": badge,
        "title": off.get(f"office_name_{lang}", ""),
        "ref": f"{dom_key.upper()} / OFFICE / {district_id.upper()}",
        "authority": auth,
        "office": off.get(f"office_name_{lang}", ""),
        "highlight_label": "আপনার নির্বাচন" if lang == "bn" else "Selected Office",
        "highlight": f"{dist_name} জেলা" if lang == "bn" else f"{dist_name} District",
        "fields": fields,
        "sources": [{"id": f"{dom_key}.office.{district_id}", "url": off.get("maps_url", source_url), "verified_on": "2026-11-15"}],
        "warn": None,
        "warn_text": None,
    }


EXAM_KEYWORDS = re.compile(
    r"পরীক্ষা|টেস্ট|মাঠ|ভেন্যু|ফিল্ড\s*টেস্ট|ড্রাইভিং\s*টেস্ট|ব্যবহারিক|লিখিত|মৌখিক|রোড\s*টেস্ট"
    r"|porikkha|porikha|test|exam|venue|ground|field\s*test",
    re.IGNORECASE
)


def is_exam_query(text: str) -> bool:
    """Returns True if the text asks about driving test ground/venue/schedule."""
    norm = unicodedata.normalize("NFC", text or "")
    return bool(EXAM_KEYWORDS.search(norm))


def format_exam_lead(district_id: str, lang: str = "bn") -> str:
    """Formats exact driving exam venue details matching user specifications."""
    info = get_district_info(district_id)
    if not info:
        return ""
    dt = info.get("driving_test", {})
    if not dt:
        return ""

    if lang == "bn":
        name = dt.get("venue_name_bn", "")
        loc = dt.get("location_bn", "")
        sched = dt.get("schedule_bn", "")
        subj = dt.get("subjects_bn", "")
        reqs = dt.get("requirements_bn", "")
        lines = [
            f"🚗 {name}",
            f"📍 পরীক্ষার স্থান: {loc}",
            f"⏰ পরীক্ষার শিডিউল: {sched}",
            f"📋 পরীক্ষার বিষয়সমূহ: {subj}",
            f"⚠️ সাথে যা আনতে হবে: {reqs}"
        ]
        return "\n".join(lines)
    else:
        name = dt.get("venue_name_en", "")
        loc = dt.get("location_en", "")
        sched = dt.get("schedule_en", "")
        subj = dt.get("subjects_en", "")
        reqs = dt.get("requirements_en", "")
        lines = [
            f"🚗 {name}",
            f"📍 Exam Venue: {loc}",
            f"⏰ Schedule: {sched}",
            f"📋 Subjects: {subj}",
            f"⚠️ Requirements: {reqs}"
        ]
        return "\n".join(lines)


def build_exam_card(district_id: str, lang: str = "bn") -> dict:
    info = get_district_info(district_id)
    dt = (info or {}).get("driving_test", {})
    dist_name = (info or {}).get(f"name_{lang}", district_id.capitalize())

    badge = f"ড্রাইভিং লাইসেন্স · পরীক্ষা ভেন্যু ({dist_name})" if lang == "bn" else f"Driving Licence · Exam Venue ({dist_name})"
    auth = "বাংলাদেশ সড়ক পরিবহন কর্তৃপক্ষ (BRTA)" if lang == "bn" else "Bangladesh Road Transport Authority (BRTA)"
    source_url = "http://www.brta.gov.bd/"

    field_label = "পরীক্ষার নিয়মাবলী ও নির্দেশিকা" if lang == "bn" else "Rules & Guidelines"
    field_content = (
        f"{dist_name} জেলার লার্নার পারমিটধারী প্রার্থীদের নির্ধারিত তারিখে উপস্থিত হয়ে লিখিত (MCQ), "
        f"মৌখিক এবং ব্যবহারিক পরীক্ষায় উত্তীর্ণ হতে হবে। ব্যবহারিক পরীক্ষার জন্য গাড়ি/মোটরসাইকেল নিজে নিয়ে আসা যায় অথবা মাঠে নির্ধারিত ফি দিয়ে পাওয়া যায়।"
        if lang == "bn" else
        f"Learner permit holders of {dist_name} must attend written, oral and practical exams on the scheduled date."
    )

    fields = [
        {
            "key": "exam",
            "label": field_label,
            "content": field_content
        }
    ]

    return {
        "domain": "licence",
        "subtype": "exam",
        "badge": badge,
        "title": dt.get(f"venue_name_{lang}", ""),
        "ref": f"LICENCE / EXAM / {district_id.upper()}",
        "authority": auth,
        "office": dt.get(f"venue_name_{lang}", ""),
        "highlight_label": "পরীক্ষার জেলা" if lang == "bn" else "Exam District",
        "highlight": f"{dist_name} জেলা" if lang == "bn" else f"{dist_name} District",
        "fields": fields,
        "sources": [{"id": f"licence.exam.{district_id}", "url": dt.get("maps_url", source_url), "verified_on": "2026-11-15"}],
        "warn": None,
        "warn_text": None,
    }


def get_popular_district_chips(domain: str = "passport", lang: str = "bn") -> list[str]:
    """Returns top division/district chips for quick office selection."""
    if lang == "bn":
        return ["রংপুর", "ঢাকা", "চট্টগ্রাম", "রাজশাহী", "সিলেট", "খুলনা", "বরিশাল", "বগুড়া"]
    return ["Rangpur", "Dhaka", "Chattogram", "Rajshahi", "Sylhet", "Khulna", "Barishal", "Bogura"]
