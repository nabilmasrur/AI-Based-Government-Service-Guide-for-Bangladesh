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


def get_popular_district_chips(domain: str = "passport", lang: str = "bn") -> list[str]:
    """Returns top division/district chips for quick office selection."""
    if lang == "bn":
        return ["রংপুর", "ঢাকা", "চট্টগ্রাম", "রাজশাহী", "সিলেট", "খুলনা", "বরিশাল", "বগুড়া"]
    return ["Rangpur", "Dhaka", "Chattogram", "Rajshahi", "Sylhet", "Khulna", "Barishal", "Bogura"]
