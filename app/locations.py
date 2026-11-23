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


CHALLAN_KEYWORDS = re.compile(
    r"চালান|চালান\s*কোড|এ-?চালান|কোন\s*ব্যাংক|ব্যাংক|ব্যাংকে|টাকা\s*জমা|ফি\s*জমা"
    r"|challan|a-?challan|which\s*bank|bank\s*e|\bbank\b",
    re.IGNORECASE
)


def is_challan_query(text: str) -> bool:
    """Returns True if user asks about a-challan code, authorized banks or where to pay."""
    norm = unicodedata.normalize("NFC", text or "")
    return bool(CHALLAN_KEYWORDS.search(norm))


def format_challan_lead(domain: str = "passport", lang: str = "bn") -> str:
    """Formats exact A-Challan code and authorized bank guide matching user specifications."""
    if lang == "bn":
        lines = [
            "🏦 পাসপোর্ট ও লাইসেন্স ফি জমাদান নির্দেশিকা",
            "📋 ই-পাসপোর্ট এ-চালান কোড: 1-2261-0000-2091",
            "🏛️ অনুমোদিত ব্যাংকসমূহ: সোনালী ব্যাংক, প্রিমিয়ার ব্যাংক, ওয়ান ব্যাংক, ট্রাস্ট ব্যাংক ও ঢাকা ব্যাংক।",
            "📱 মোবাইল ব্যাংকিং: বিকাশ, নগদ, রকেটের 'গভর্নমেন্ট ফি' অপশন থেকে সরাসরি পরিশোধযোগ্য।",
            "💡 পরামর্শ: সোনালী ব্যাংকের যেকোনো অনলাইন শাখায় চালান জমা দিয়ে মূল রসিদ সংগ্রহ করুন"
        ]
        return "\n".join(lines)
    else:
        lines = [
            "🏦 Passport & Driving Licence Fee Payment Guide",
            "📋 E-Passport A-Challan Code: 1-2261-0000-2091",
            "🏛️ Authorized Banks: Sonali Bank, Premier Bank, One Bank, Trust Bank & Dhaka Bank.",
            "📱 Mobile Banking: Pay directly via bKash, Nagad, Rocket under 'Government Fee' option.",
            "💡 Tip: Deposit challan at any Sonali Bank online branch and collect the original receipt."
        ]
        return "\n".join(lines)


def build_challan_card(domain: str = "passport", lang: str = "bn") -> dict:
    dom_key = "licence" if domain == "licence" else "passport"
    badge = "পাসপোর্ট ও লাইসেন্স · এ-চালান ও ব্যাংক" if lang == "bn" else "Passport & Licence · A-Challan & Bank"
    auth = "অর্থ মন্ত্রণালয় (Ministry of Finance) ও ইমিগ্রেশন ও পাসপোর্ট অধিদপ্তর" if lang == "bn" else "Ministry of Finance & Department of Immigration and Passports"
    source_url = "https://www.epassport.gov.bd/"

    field_label = "চালান ও অনলাইন পেমেন্ট নির্দেশিকা" if lang == "bn" else "Payment & Challan Instructions"
    field_content = (
        "অনলাইনে পাসপোর্ট আবেদন শেষে সরাসরি Ekpay / A-Challan গেটওয়ে ব্যবহার করে ফি জমা দেওয়া যায়। "
        "ব্যাংকে জমা দেওয়ার ক্ষেত্রে এ-চালান কপি ডাউনলোড ও প্রিন্ট করে নির্ধারিত ব্যাংকের শাখায় জমা দিয়ে চালানের মূল রসিদ পাসপোর্ট অফিসে জমা দিতে হবে।"
        if lang == "bn" else
        "You can pay online via Ekpay / A-Challan gateway or print the challan form and deposit at designated bank branches."
    )

    fields = [
        {
            "key": "payment",
            "label": field_label,
            "content": field_content
        }
    ]

    return {
        "domain": dom_key,
        "subtype": "new",
        "badge": badge,
        "title": "এ-চালান কোড ও অনুমোদিত ব্যাংক ডিরেক্টরি",
        "ref": "PAYMENT / A-CHALLAN / BANKS",
        "authority": auth,
        "office": "অনুমোদিত ব্যাংকসমূহ ও এ-চালান",
        "highlight_label": "পেমেন্ট পদ্ধতি" if lang == "bn" else "Payment Method",
        "highlight": "এ-চালান / ব্যাংক ও মোবাইল ব্যাংকিং" if lang == "bn" else "A-Challan / Bank & Mobile Banking",
        "fields": fields,
        "sources": [{"id": "payment.challan.banks", "url": source_url, "verified_on": "2026-11-15"}],
        "warn": None,
        "warn_text": None,
    }


TRACKING_KEYWORDS = re.compile(
    r"পাসপোর্ট\s*(হয়েছে|হয়েছে|হল|হলো)\s*কিনা|স্ট্যাটাস|ট্র্যাকিং|কখন\s*(পাব|পাওয়া|পাবো)|কবে\s*(পাব|পাওয়া|পাবো)|ডেলিভারি\s*স্ট্যাটাস"
    r"|status|tracking|check\s*status|delivery\s*status|passport\s*status",
    re.IGNORECASE
)


def is_tracking_query(text: str) -> bool:
    """Returns True if user asks about passport status tracking or SMS check."""
    norm = unicodedata.normalize("NFC", text or "")
    return bool(TRACKING_KEYWORDS.search(norm))


def format_tracking_lead(domain: str = "passport", lang: str = "bn") -> str:
    """Formats exact passport delivery SMS and online tracking guide matching user specifications."""
    if lang == "bn":
        lines = [
            "📲 পাসপোর্ট ডেলিভারি স্ট্যাটাস যাচাই",
            "📩 এসএমএস ফরম্যাট: Epass <Application ID> লিখে পাঠিয়ে দিন 16345 নম্বরে।",
            "🌐 অনলাইন পোর্টাল: [epassport.gov.bd/authorization/application-status](https://www.epassport.gov.bd/)",
            "📄 প্রয়োজনীয় তথ্য: ডেলিভারি স্লিপে থাকা ওআইডি (OID) বা অ্যাপ্লিকেশন আইডি।",
            "⏰ স্ট্যাটাস আপডেট সময়: বায়োমেট্রিক দেওয়ার সাধারণত ৩ থেকে ৭ কর্মদিবসের মধ্যে এসএমএস আসে।"
        ]
        return "\n".join(lines)
    else:
        lines = [
            "📲 Passport Delivery Status Tracking",
            "📩 SMS Format: Send 'Epass <Application ID>' to 16345.",
            "🌐 Online Portal: [epassport.gov.bd/authorization/application-status](https://www.epassport.gov.bd/)",
            "📄 Required Info: Online Registration ID (OID) or Application ID from delivery slip.",
            "⏰ Update Time: SMS is usually received within 3 to 7 working days after biometrics."
        ]
        return "\n".join(lines)


def build_tracking_card(domain: str = "passport", lang: str = "bn") -> dict:
    badge = "পাসপোর্ট · ডেলিভারি স্ট্যাটাস যাচাই" if lang == "bn" else "Passport · Delivery Status Tracking"
    auth = "ইমিগ্রেশন ও পাসপোর্ট অধিদপ্তর (DIP)" if lang == "bn" else "Department of Immigration and Passports"
    source_url = "https://www.epassport.gov.bd/authorization/application-status"
    field_label = "স্ট্যাটাস যাচাই ও নোটিফিকেশন নির্দেশিকা" if lang == "bn" else "Status Check Instructions"
    field_content = (
        "ই-পাসপোর্ট পোর্টালে অ্যাপ্লিকেশন আইডি ও জন্মতারিখ দিয়ে সরাসরি পাসপোর্ট কোন পর্যায়ে রয়েছে (আবেদন গৃহীত, পুলিশ ভেরিফিকেশন, পাসপোর্ট প্রিন্টিং বা ডেলিভারির জন্য প্রস্তুত) তা লাইভ দেখা যায়।"
        if lang == "bn" else
        "Check your e-passport progress live using your Application ID and Date of Birth on the official portal."
    )
    return {
        "domain": "passport",
        "subtype": "delivery",
        "badge": badge,
        "title": "পাসপোর্ট ডেলিভারি স্ট্যাটাস যাচাই",
        "ref": "PASSPORT / DELIVERY / STATUS",
        "authority": auth,
        "office": "অনলাইন পোর্টাল ও এসএমএস সেবা",
        "highlight_label": "ট্র্যাকিং মেথড" if lang == "bn" else "Tracking Method",
        "highlight": "এসএমএস (16345) ও অনলাইন পোর্টাল" if lang == "bn" else "SMS (16345) & Online Portal",
        "fields": [{"key": "timeline", "label": field_label, "content": field_content}],
        "sources": [{"id": "passport.status.tracking", "url": source_url, "verified_on": "2026-11-15"}],
        "warn": None,
        "warn_text": None,
    }


def format_police_lead(district_id: str, lang: str = "bn") -> str:
    """Formats exact DSB police verification office guide matching user specifications."""
    info = get_district_info(district_id)
    if not info:
        return ""
    pv = info.get("police_verification", {})
    if not pv:
        return ""

    if lang == "bn":
        name = pv.get("unit_name_bn", "")
        addr = pv.get("address_bn", "")
        docs = pv.get("documents_bn", "")
        phone = pv.get("phone_bn", "")
        alert = pv.get("alert_bn", "")
        lines = [
            f"👮 {name}",
            f"📍 ঠিকানা: {addr}",
            f"📑 পুলিশকে দেখাতে হবে: {docs}",
            f"📞 ভেরিফিকেশন হেল্পলাইন: {phone}",
            f"⚠️ জরুরি সতর্কতা: {alert}"
        ]
        return "\n".join(lines)
    else:
        name = pv.get("unit_name_en", "")
        addr = pv.get("address_en", "")
        docs = pv.get("documents_en", "")
        phone = pv.get("phone_en", "")
        alert = pv.get("alert_en", "")
        lines = [
            f"👮 {name}",
            f"📍 Address: {addr}",
            f"📑 Documents to show: {docs}",
            f"📞 Helpline: {phone}",
            f"⚠️ Important Note: {alert}"
        ]
        return "\n".join(lines)


def build_police_card(district_id: str, lang: str = "bn") -> dict:
    info = get_district_info(district_id)
    pv = (info or {}).get("police_verification", {})
    dist_name = (info or {}).get(f"name_{lang}", district_id.capitalize())

    badge = f"পাসপোর্ট · পুলিশ ভেরিফিকেশন ({dist_name})" if lang == "bn" else f"Passport · Police Verification ({dist_name})"
    auth = "বাংলাদেশ পুলিশ ও স্পেশাল ব্রাঞ্চ (SB)" if lang == "bn" else "Bangladesh Police & Special Branch (SB)"
    source_url = "https://www.police.gov.bd/"

    field_label = "ভেরিফিকেশন প্রক্রিয়া ও প্রয়োজনীয় কাগজপত্র" if lang == "bn" else "Verification Process & Documents"
    field_content = (
        f"{dist_name} জেলায় পাসপোর্ট আবেদনের পর স্পেশাল ব্রাঞ্চ (DSB) বা স্থানীয় থানা থেকে তদন্তকারী কর্মকর্তা নাগরিকের বর্তমান বা স্থায়ী ঠিকানা তদন্ত করবেন। "
        f"তদন্তের সময় মূল কাগজপত্র প্রদর্শন করতে হবে।"
        if lang == "bn" else
        f"Special Branch (DSB) or local police will verify citizen address and background in {dist_name}."
    )

    fields = [
        {
            "key": "verification",
            "label": field_label,
            "content": field_content
        }
    ]

    return {
        "domain": "passport",
        "subtype": "new",
        "badge": badge,
        "title": pv.get(f"unit_name_{lang}", ""),
        "ref": f"PASSPORT / POLICE / {district_id.upper()}",
        "authority": auth,
        "office": pv.get(f"unit_name_{lang}", ""),
        "highlight_label": "ভেরিফিকেশন এলাকা" if lang == "bn" else "Verification Area",
        "highlight": f"{dist_name} জেলা" if lang == "bn" else f"{dist_name} District",
        "fields": fields,
        "sources": [{"id": f"passport.police.{district_id}", "url": source_url, "verified_on": "2026-11-15"}],
        "warn": None,
        "warn_text": None,
    }


def is_medical_query(message: str) -> bool:
    """Checks if message is asking about driving licence medical test or certificate."""
    norm = unicodedata.normalize("NFC", message.lower())
    has_med = any(k in norm for k in ["মেডিকেল", "মেডিক্যাল", "ডাক্তার", "ডাক্তারি", "চিকিৎসক", "রক্তের গ্রুপ", "ডিএল-১", "medical", "doctor", "dl-1"])
    has_licence = any(k in norm for k in ["লাইসেন্স", "ড্রাইভিং", "বিআরটিএ", "লার্নার", "licence", "license", "driving", "brta", "সার্টিফিকেট", "ফরম", "টেস্ট"])
    return has_med and has_licence


def format_medical_lead(lang: str = "bn") -> str:
    """Formats exact driving licence medical test guide matching user specifications."""
    if lang == "bn":
        lines = [
            "🏥 ড্রাইভিং লাইসেন্স মেডিকেল টেস্ট গাইড",
            "🏢 অনুমোদিত স্থান: সরকারি সদর হাসপাতাল / সিভিল সার্জন কার্যালয় অথবা যেকোনো রেজিস্টার্ড এমবিবিএস ডাক্তার।",
            "📝 নির্ধারিত ফরম: বিআরটিএ মেডিকেল সার্টিফিকেট ফরম (ফর্ম ডিএল-১)।",
            "🩸 যাচাইকৃত টেস্ট: রক্তের গ্রুপ পরীক্ষা, কালার ব্লাইন্ডনেস (দৃষ্টিশক্তি) এবং শারীরিক সক্ষমতা।",
            "📌 ফি: সরকারি হাসপাতালে সাধারণত ৫০-১০০ টাকা সরকারি ফি প্রযোজ্য।"
        ]
        return "\n".join(lines)
    else:
        lines = [
            "🏥 Driving Licence Medical Test Guide",
            "🏢 Authorized Places: Government Sadar Hospital / Civil Surgeon Office or any registered MBBS doctor.",
            "📝 Designated Form: BRTA Medical Certificate Form (Form DL-1).",
            "🩸 Verified Tests: Blood group test, color blindness (vision), and physical fitness.",
            "📌 Fee: Usually 50-100 BDT government fee applies at government hospitals."
        ]
        return "\n".join(lines)


def build_medical_card(lang: str = "bn") -> dict:
    badge = "ড্রাইভিং লাইসেন্স · মেডিকেল সার্টিফিকেট" if lang == "bn" else "Driving Licence · Medical Certificate"
    title = "ড্রাইভিং লাইসেন্স মেডিকেল টেস্ট গাইড" if lang == "bn" else "Driving Licence Medical Test Guide"
    auth = "বাংলাদেশ সড়ক পরিবহন কর্তৃপক্ষ (বিআরটিএ)" if lang == "bn" else "Bangladesh Road Transport Authority (BRTA)"
    source_url = "http://www.brta.gov.bd/"

    fields = [
        {
            "key": "medical_info",
            "label": "মেডিকেল টেস্ট ও ফর্ম ডিএল-১ নির্দেশনা" if lang == "bn" else "Medical Test & Form DL-1 Guidelines",
            "content": (
                "বিআরটিএ শিক্ষানবিশ (লার্নার) ও মূল স্মার্টকার্ড ড্রাইভিং লাইসেন্সের জন্য রেজিস্টার্ড এমবিবিএস ডাক্তারের স্বাক্ষরিত "
                "ফর্ম ডিএল-১ জমা দেওয়া বাধ্যতামূলক। দৃষ্টিশক্তি ও রক্তের গ্রুপ সঠিক থাকতে হবে।"
                if lang == "bn" else
                "Form DL-1 certified by a registered MBBS doctor is mandatory for BRTA driving licence applications."
            )
        }
    ]

    return {
        "domain": "licence",
        "subtype": "new",
        "badge": badge,
        "title": title,
        "ref": "LICENCE / MEDICAL / DL-1",
        "authority": auth,
        "office": "বিআরটিএ ও অনুমোদিত স্বাস্থ্যকেন্দ্র" if lang == "bn" else "BRTA & Authorized Medical Centers",
        "highlight_label": "ফরম" if lang == "bn" else "Form",
        "highlight": "ফর্ম ডিএল-১ (মেডিকেল)" if lang == "bn" else "Form DL-1 (Medical)",
        "fields": fields,
        "sources": [{"id": "licence.medical", "url": source_url, "verified_on": "2026-11-15"}],
        "warn": None,
        "warn_text": None,
    }


def is_gd_query(message: str) -> bool:
    """Checks if message is asking about lost passport police GD."""
    norm = unicodedata.normalize("NFC", message.lower())
    has_gd = any(k in norm for k in ["জিডি", "gd", "হারিয়ে", "হারিয়ে", "হারানো", "lost", "থানা"])
    has_passport = any(k in norm for k in ["পাসপোর্ট", "passport", "ডকুমেন্ট", "দলিল"])
    is_explicit_lost = "হারিয়ে" in norm or "হারিয়ে" in norm or "হারানো" in norm or "lost" in norm
    return (has_gd and has_passport) or (is_explicit_lost and "জিডি" in norm)


def format_gd_lead(lang: str = "bn") -> str:
    """Formats exact lost passport GD guide matching user specifications."""
    if lang == "bn":
        lines = [
            "📝 হারানো পাসপোর্টের সাধারণ ডায়েরি (GD) গাইড",
            "👮 কোথায় করবেন: যে থানা এলাকায় পাসপোর্ট হারিয়েছে সেই থানায় অথবা 'অনলাইন জিডি' অ্যাপে।",
            "🌐 অনলাইন লিংক: [gd.police.gov.bd](https://gd.police.gov.bd)",
            "📑 জিডিতে যা উল্লেখ করতে হবে: হারানো পাসপোর্টের নম্বর, মেয়াদ, ইস্যুর তারিখ এবং স্থান।",
            "⚠️ পরবর্তী ধাপ: জিডির মূল সার্টিফায়েড কপি ও ফটোকপি নিয়ে রি-ইস্যু আবেদন করতে হবে।"
        ]
        return "\n".join(lines)
    else:
        lines = [
            "📝 Lost Passport General Diary (GD) Guide",
            "👮 Where to lodge: At the local police station where it was lost or via the 'Online GD' portal/app.",
            "🌐 Online Portal: [gd.police.gov.bd](https://gd.police.gov.bd)",
            "📑 Information to mention in GD: Lost passport number, expiry date, issue date, and location of loss.",
            "⚠️ Next step: Submit the re-issue application with the original certified copy and photocopy of the GD."
        ]
        return "\n".join(lines)


def build_gd_card(lang: str = "bn") -> dict:
    badge = "পাসপোর্ট · হারানো জিডি গাইড" if lang == "bn" else "Passport · Lost GD Guide"
    title = "হারানো পাসপোর্টের সাধারণ ডায়েরি (GD) গাইড" if lang == "bn" else "Lost Passport General Diary (GD) Guide"
    auth = "বাংলাদেশ পুলিশ ও ইমিগ্রেশন ও পাসপোর্ট অধিদপ্তর" if lang == "bn" else "Bangladesh Police & Department of Immigration and Passports"
    source_url = "https://gd.police.gov.bd/"

    fields = [
        {
            "key": "gd_info",
            "label": "অনলাইন জিডি ও রি-ইস্যু আবেদন" if lang == "bn" else "Online GD & Re-issue Process",
            "content": (
                "পাসপোর্ট হারিয়ে গেলে দেরি না করে দ্রুত সংশ্লিষ্ট থানায় সাধারণ ডায়েরি (জিডি) অথবা অনলাইনে আবেদন করুন। "
                "জিডির কপি ছাড়া নতুন রি-ইস্যু আবেদন গ্রহণ করা হবে না।"
                if lang == "bn" else
                "Lodge a GD immediately at the local police station or online. A certified GD copy is mandatory for passport reissue."
            )
        }
    ]

    return {
        "domain": "passport",
        "subtype": "reissue",
        "badge": badge,
        "title": title,
        "ref": "PASSPORT / GD / LOST",
        "authority": auth,
        "office": "অনলাইন জিডি পোর্টাল ও সংশ্লিষ্ট থানা" if lang == "bn" else "Online GD Portal & Police Station",
        "highlight_label": "পোর্টাল" if lang == "bn" else "Portal",
        "highlight": "gd.police.gov.bd",
        "fields": fields,
        "sources": [{"id": "police.gd", "url": source_url, "verified_on": "2026-11-15"}],
        "warn": None,
        "warn_text": None,
    }
