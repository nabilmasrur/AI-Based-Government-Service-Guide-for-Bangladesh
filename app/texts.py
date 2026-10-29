"""Every user-facing string, in both languages. Nothing here needs the LLM,
so clarifying questions and refusals come back instantly."""
from __future__ import annotations

from . import kb

T = {
    "ask_domain": {
        "bn": "কোন সেবাটি নিয়ে জানতে চান?",
        "en": "Which service do you need help with?",
    },
    "ask_subtype": {
        "bn": "{dom} নিয়ে কয়েকটি আলাদা সেবা আছে। আপনার ঠিক কোনটি দরকার?",
        "en": "There are several different {dom} services. Which one do you need?",
    },

    # --- small talk: answered from here, never from the model, so a greeting
    # --- costs nothing and always sounds the same.
    "chat_greet": {
        "bn": "ওয়ালাইকুম আসসালাম! আমি পাসপোর্ট ও ড্রাইভিং লাইসেন্স সংক্রান্ত সরকারি সেবার তথ্য দিয়ে সাহায্য করি। কোনটি নিয়ে জানতে চান?",
        "en": "Hello! I help with passport and driving licence services in Bangladesh. Which one can I help you with?",
    },
    "chat_name": {
        "bn": "স্বাগতম! বলুন, পাসপোর্ট নাকি ড্রাইভিং লাইসেন্স — কোনটি নিয়ে জানতে চান?",
        "en": "Welcome! Tell me — passport or driving licence?",
    },
    "chat_who": {
        "bn": "আমি “সেবা সহায়ক” — বাংলাদেশের পাসপোর্ট ও ড্রাইভিং লাইসেন্স সেবার তথ্য দেওয়ার একটি সহায়ক। প্রতিটি উত্তর যাচাই করা তথ্যভাণ্ডার থেকে আসে, আর নিচে উৎসও দেখানো হয়।\n\nএটি একটি শিক্ষার্থী প্রকল্প (CSE 3202, BAUST) — কোনো সরকারি দপ্তর নয়।",
        "en": "I am “Seba Sohayok”, an assistant for passport and driving licence services in Bangladesh. Every answer comes from a verified knowledge base and shows its source.\n\nThis is a student project (CSE 3202, BAUST), not a government office.",
    },
    "chat_help": {
        "bn": "যা যা জিজ্ঞেস করতে পারেন —\n\n• কোন অফিসে যেতে হবে\n• কী কী কাগজ সঙ্গে নিতে হবে\n• কত ফি, কীভাবে দেবেন\n• কত দিন সময় লাগে\n• কতটুকু ঘরে বসে অনলাইনে হয়\n\nবাংলা, English বা মিশিয়ে — যেভাবে খুশি লিখুন।",
        "en": "You can ask me —\n\n• which office to visit\n• what documents to bring\n• the fee and how to pay it\n• how long it takes\n• how much can be done online\n\nWrite in Bangla, English, or a mix — whatever is easiest.",
    },
    "chat_thanks": {
        "bn": "স্বাগতম! আরও কিছু জানার থাকলে নির্দ্বিধায় জিজ্ঞেস করুন।",
        "en": "You are welcome. Ask me anything else you need.",
    },
    "chat_bye": {
        "bn": "আল্লাহ হাফেজ। কাজে লাগলে ভালো লাগবে — প্রয়োজনে আবার আসবেন।",
        "en": "Goodbye, and good luck. Come back any time.",
    },
    "chat_howareyou": {
        "bn": "ভালো আছি, ধন্যবাদ! আপনার কোন সেবাটি নিয়ে সাহায্য দরকার?",
        "en": "I am well, thank you. Which service can I help you with?",
    },
    "ask_slot": {
        "bn": "{label}?",
        "en": "{label}?",
    },
    "ask_slot_more": {
        "bn": "আর একটি তথ্য — {label}?",
        "en": "One more detail — {label}?",
    },
    "no_info": {
        "bn": "এই বিষয়ে জ্ঞানভাণ্ডারে যাচাইকৃত তথ্য পাওয়া যায়নি, তাই অনুমান করে উত্তর দিচ্ছি না।",
        "en": "I could not find verified information on this in the knowledge base, so I will not guess.",
    },
    "out_of_scope": {
        "bn": "এই সহায়ক এখন শুধু পাসপোর্ট ও ড্রাইভিং লাইসেন্স সেবা নিয়ে সাহায্য করতে পারে। জমি, এনআইডি বা অন্যান্য সেবা এখনো যুক্ত হয়নি।",
        "en": "This assistant currently covers only passport and driving licence services. Land, NID and other services are not included yet.",
    },
    "unverified": {
        "bn": "এই তথ্য এখনো দলের পক্ষ থেকে যাচাই করা হয়নি — সরকারি ওয়েবসাইট থেকে মিলিয়ে নিন।",
        "en": "This entry has not been verified by the team yet — please confirm it on the official website.",
    },
    "stale": {
        "bn": "এই তথ্য কিছুদিন হালনাগাদ হয়নি — সরকারি ওয়েবসাইট থেকে যাচাই করে নিন।",
        "en": "This information has not been updated for a while — please check the official website.",
    },
    "lead_fallback": {
        "bn": "আপনি {sub} নিয়ে জানতে চেয়েছেন। {fields} — সবটা নিচে দেওয়া হলো।",
        "en": "You asked about {sub}. Below you will find {fields}.",
    },
    "limit_left": {
        "bn": "আজ আর {n}টি প্রশ্ন করা যাবে",
        "en": "{n} questions left today",
    },
    "limit_min": {
        "bn": "এই মিনিটে আর {n}টি",
        "en": "{n} left this minute",
    },
    "your_case": {"bn": "আপনার ক্ষেত্রে", "en": "Your case"},
    "authority": {"bn": "কর্তৃপক্ষ", "en": "Authority"},
    "limit": {
        "bn": "একটু বেশি দ্রুত প্রশ্ন আসছে। কয়েক সেকেন্ড পরে আবার চেষ্টা করুন।",
        "en": "That is a lot of questions very quickly. Please try again in a few seconds.",
    },
    "error": {
        "bn": "দুঃখিত, একটি কারিগরি সমস্যা হয়েছে। আবার চেষ্টা করুন।",
        "en": "Sorry, something went wrong on our side. Please try again.",
    },
}


def t(key: str, lang: str, **kw) -> str:
    text = T[key].get(lang, T[key]["en"])
    return text.format(**kw) if kw else text


def label(node: dict, lang: str) -> str:
    """Pull the right language out of any {bn, en} pair."""
    return node.get(lang) or node.get("en") or ""


def domain_chips(lang: str) -> list[dict]:
    return [
        {"label": kb.TAXONOMY[d][f"label_{lang}"], "action": {"domain": d}}
        for d in kb.TAXONOMY
    ]


def subtype_chips(domain: str, lang: str) -> list[dict]:
    return [
        {"label": label(meta, lang), "action": {"domain": domain, "subtype": sub}}
        for sub, meta in kb.TAXONOMY[domain]["subtypes"].items()
    ]


def slot_chips(slot: str, lang: str, base: dict) -> list[dict]:
    spec = kb.SLOTS[slot]
    out = []
    for value, bn, en in spec["options"]:
        out.append({
            "label": bn if lang == "bn" else en,
            "action": {**base, "slots": {slot: value}},
        })
    return out


def slot_label(slot: str, lang: str) -> str:
    return label(kb.SLOTS[slot], lang)


def join(items: list[str], lang: str) -> str:
    """Bangla joins the last pair with \u0993, English with 'and'."""
    items = [i for i in items if i]
    if len(items) <= 1:
        return items[0] if items else ""
    tail = "\u0993" if lang == "bn" else "and"
    return ", ".join(items[:-1]) + f" {tail} " + items[-1]


def lead(domain: str, subtype: str, fields: list[str], lang: str) -> str:
    """The opening line when no LLM wrote one — names the service and what follows,
    so a fast-path answer reads as deliberate rather than templated."""
    sub = label(kb.TAXONOMY[domain]["subtypes"][subtype], lang)
    names = join([label(kb.FIELDS[f], lang) for f in fields if f in kb.FIELDS], lang)
    return t("lead_fallback", lang, sub=sub, fields=names.lower() if lang == "en" else names)


def slot_value_label(slot: str, value: str, lang: str) -> str:
    for val, bn, en in kb.SLOTS[slot]["options"]:
        if val == str(value):
            return bn if lang == "bn" else en
    return str(value)


def followup_chips(domain: str, subtype: str, lang: str,
                   shown: set[str] | None = None) -> list[dict]:
    """The grey chips under an answer — what someone naturally asks next.

    Fields already on the card are skipped; when the card covered everything,
    the chips point at neighbouring services instead, so the conversation never
    dead-ends on an answer.
    """
    shown = shown or set()
    have = {e["field"] for e in kb.load()
            if e["domain"] == domain and e["subtype"] == subtype}
    out = [
        {"label": label(kb.FIELDS[f], lang), "grey": True,
         "action": {"domain": domain, "subtype": subtype, "field": f}}
        for f in ("fee", "timeline", "documents", "online_steps",
                  "payment", "verification", "minor", "collection",
                  "eligibility", "validity", "appointment", "helpline", "note")
        if f in have and f not in shown
    ]
    if out:
        return out[:3]

    return [
        {"label": label(meta, lang), "grey": True,
         "action": {"domain": domain, "subtype": sub}}
        for sub, meta in kb.TAXONOMY[domain]["subtypes"].items()
        if sub != subtype
    ][:3]
