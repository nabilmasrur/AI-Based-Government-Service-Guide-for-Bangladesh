"""Deterministic phrase routing for Bangla, English and Banglish.

Why this exists
---------------
Embeddings alone are a poor judge of *which* passport service someone means:
"passport haray gese", "passport korte chai" and "passport koto din lage" all sit
very close together in vector space, because they share their subject and their
sentence shape. What separates them is a handful of decisive words — হারিয়ে, নতুন,
কত দিন — and those are worth matching outright.

So this table runs before the model. When it fires, the routing is exact,
auditable and free; when it does not, Gemini generalises to phrasing nobody
anticipated, and retrieval is the last resort. All three layers agree on the same
taxonomy, so they are interchangeable rather than competing.

Every pattern is written three ways because that is how Bangladeshis actually
type: Bangla script, English, and Banglish (Bangla words in Latin letters, spelt
however the writer feels that day — haray / harai / hariye / haraise).
"""
from __future__ import annotations

import re

# --------------------------------------------------------------------------- #
# domain
# --------------------------------------------------------------------------- #

DOMAIN = {
    "passport": r"পাসপোর্ট|পাসপোট|পাসর্পোট|passport|pasport|pashport|\bmrp\b|এমআরপি|ই-?পাসপোর্ট|e-?passport",
    "licence": (r"লাইসেন্স|লাইসেন্‌স|লাইসেন্স্|ড্রাইভিং|ড্রাইভার|গাড়ি\s*চালা|বাইক\s*চালা"
                r"|licen[cs]e?|driving|driver|\bbrta\b|বিআরটিএ|\bbsp\b"
                r"|শিক্ষানবিশ|sikkhanobish|shikkhanobish|learner|লার্নার|\bidp\b"
                r"|স্মার্ট\s*কার্ড|smart\s*card|smartcard"),
}

# --------------------------------------------------------------------------- #
# what the person is asking ABOUT — the field
# --------------------------------------------------------------------------- #

FIELD = {
    "documents": (r"কী\s*কী\s*লাগ|কি\s*কি\s*লাগ|কী\s*লাগ|কি\s*লাগ|কাগজ|ডকুমেন্ট|দলিলপত্র"
                  r"|প্রয়োজনীয়|সাথে\s*কী|সঙ্গে\s*কী|কী\s*নিতে\s*হবে|কি\s*নিয়ে\s*যাব|লাগবে"
                  r"|ki\s*ki\s*lag|ki\s*lag|ki\s*dorkar|kagoj|kagoz|document|papers?"
                  r"|what\s+(do\s+i\s+need|documents?|papers?)|required\s+documents?|checklist"
                  r"|need\s+to\s+(bring|submit)|requirements?"),

    "fee": (r"\bফি\b|ফি\s*কত|কত\s*টাকা|টাকা\s*লাগ|খরচ|মূল্য|চার্জ|দাম|কত\s*পড়বে"
            r"|koto\s*taka|koto\s*poisa|\bfee\b|fees\b|cost|charge|price|khoroch|khorcha|\bdam\b"
            r"|how\s+much|kt\s*taka"),

    "timeline": (r"কত\s*দিন|কতদিন|কত\s*সময়|সময়\s*লাগ|কবে\s*পাব|কবে\s*পাওয়া|কতক্ষণ|দেরি"
                 r"|koto\s*din|kotodin|kt\s*din|somoy\s*lag|kobe\s*pabo|kobe\s*pab"
                 r"|how\s+long|how\s+many\s+days|duration|when\s+will\s+i\s+(get|receive)"
                 r"|processing\s+time|koydin"),

    "office": (r"কোথায়\s*যা|কোথায়\s*গিয়ে|কোন\s*অফিস|কোথায়\s*করব|কোথায়\s*আবেদন|ঠিকানা|অফিস\s*কোথায়"
               r"|kothay|kothae|kon\s*office|kothai|\boffice\b|where\s+(do\s+i|should\s+i|to)"
               r"|which\s+office|address|location"),

    "online_steps": (r"অনলাইনে?\b|ঘরে\s*বসে|ওয়েবসাইট|ওয়েব\s*সাইট|অ্যাপ\s*দিয়ে|নিজে\s*করা"
                     r"|online|website|web\s*site|ghore\s*bo?she|portal|apply\s+online"
                     r"|internet\s*e|nijei\s*kor"),

    "payment": (r"কীভাবে\s*(টাকা|ফি)\s*দ|কোথায়\s*(টাকা|ফি)\s*দ|পেমেন্ট|বিকাশ|নগদ|রকেট|চালান"
                r"|ব্যাংকে\s*টাকা|কার্ড\s*দিয়ে"
                r"|payment|pay\s+the\s+fee|how\s+(do\s+i\s+|to\s+)?pay|bkash|nagad|rocket"
                r"|\bchallan\b|\bchalan\b|bank\s*e\s*taka|kivabe\s*(taka|fee)?\s*dib|কীভাবে\s*(টাকা|ফি)?\s*দেব|card\s*diye"),

    "verification": (r"পুলিশ\s*ভেরিফিকেশন|ভেরিফিকেশন|পুলিশ\s*আসবে|তদন্ত|থানা\s*থেকে|এসবি\b"
                     r"|police\s*verification|verification|police\s*report|\bsb\b\s*check"
                     r"|police\s*ashbe|thana\s*theke|verify\s+korbe"),

    "minor": (r"শিশু|বাচ্চা|বাচ্চার|ছেলের|মেয়ের|নাবালক|অপ্রাপ্তবয়স্ক|নবজাতক"
              r"|১৮\s*বছরের\s*কম|আঠারো\s*বছরের\s*কম|স্কুল\s*পড়ুয়া"
              r"|baccha|bacchar|bachchar|shishu|chotto|minor|child|kids?|newborn|baby"
              r"|under\s*18|below\s*18|son'?s|daughter'?s"),

    "collection": (r"সংগ্রহ|তুলতে|তুলব|হাতে\s*পাব|ডেলিভারি\s*স্লিপ|স্লিপ|নিতে\s*যাব|কে\s*তুলতে"
                   r"|collect|collection|delivery\s*slip|\bslip\b|pick\s*up|receive\s+the\s+passport"
                   r"|hate\s*pabo|tulbo|tulte|tulte\s*hobe|shongroho|deliver"),

    "eligibility": (r"কে\s*(আবেদন|করতে)\s*পার|বয়স\s*কত|কত\s*বছর\s*বয়স|যোগ্যতা|শর্ত"
                    r"|আমি\s*কি\s*পারব|কারা\s*পারবে"
                    r"|boyos|boyesh|\bage\b|age\s*limit|who\s+can\s+apply|eligib"
                    r"|am\s+i\s+eligible|minimum\s+age|koto\s*bosor\s*boyos"),

    "validity": (r"মেয়াদ|কত\s*বছর\s*(মেয়াদ|থাকবে|চলবে)|কতদিন\s*বৈধ|নবায়নের\s*সময়"
                 r"|meyad|meyaad|validity|valid\s+for|how\s+many\s+years|expire[sd]?\s*(kobe|when)"
                 r"|koto\s*bochor"),

    "appointment": (r"অ্যাপয়েন্টমেন্ট|এপয়েন্টমেন্ট|তারিখ\s*(নেব|নিতে)|সিরিয়াল|স্লট"
                    r"|appointment|booking|book\s+a\s+(slot|date)|slot|serial|tarikh\s*nibo"),

    "helpline": (r"হেল্পলাইন|হটলাইন|ফোন\s*নম্বর|যোগাযোগ|কল\s*করব|নম্বর\s*কত"
                 r"|helpline|hotline|contact|phone\s*number|call\s+them|customer\s*care"
                 r"|jogajog|number\s*koto"),
}

# --------------------------------------------------------------------------- #
# which service — the subtype, per domain
# --------------------------------------------------------------------------- #

SUBTYPE = {
    "passport": {
        # Order matters: the first match wins, so the sharper signals come first.
        "lost": (r"হারা|হারিয়ে|হারাইছে|হারায়|খোয়া|চুরি|চোরি|নষ্ট\s*হয়ে\s*গে"
                 r"|haray|harai|hariye|haraise|hara\s*ges?e|harano|hariya"
                 r"|\blost\b|stolen|misplaced|missing|can'?t\s+find"),

        "correction": (r"সংশোধন|ভুল|বানান|নাম\s*পরিবর্তন|নাম\s*বদল|জন্ম\s*তারিখ\s*(ঠিক|ভুল|পরিবর্তন)"
                       r"|তথ্য\s*ঠিক|পিতার\s*নাম\s*ভুল|ঠিক\s*করতে"
                       r"|songshodhon|shongshodhon|\bvul\b|\bbhul\b|correction|correct\s+(my|the)"
                       r"|wrong\s+(name|spelling|date)|mistake|change\s+(my\s+)?name|spelling"),

        "mrp_to_epp": (r"\bmrp\b|এমআরপি|হাতে\s*লেখা|রূপান্তর|কনভার্ট|পুরনো\s*পাসপোর্ট\s*থেকে"
                       r"|machine\s*readable|convert|rupantor|old\s+passport\s+to"),

        "reissue": (r"নবায়ন|রি-?ইস্যু|রিইস্যু|মেয়াদ\s*(শেষ|উত্তীর্ণ|শেষের)|পাতা\s*শেষ|পৃষ্ঠা\s*শেষ"
                    r"|আবার\s*করতে|পুনরায়"
                    r"|nobayon|nobayan|reissue|re-?issue|renew|renewal|expired?|meyad\s*ses?h"
                    r"|page\s*ses?h|purono\s*passport"),

        "delivery": (r"জরুরি|অতি\s*জরুরি|দ্রুত|তাড়াতাড়ি|এক্সপ্রেস|সুপার\s*এক্সপ্রেস|কত\s*দ্রুত"
                     r"|joruri|oti\s*joruri|druto|taratari|express|urgent|super\s*express|fast"),

        "status": (r"অবস্থা|কতদূর|কত\s*দূর|চেক\s*কর|হয়েছে\s*কিনা|প্রস্তুত\s*হয়েছে|খোঁজ"
                   r"|obostha|koto\s*dur|kotodur|status|check\s+(my\s+)?(application|passport)"
                   r"|track|ready\s+(hoyeche|ki)"),

        "new": (r"নতুন|প্রথম\s*বার|প্রথমবার|প্রথম\s*পাসপোর্ট|করতে\s*চাই|করব|বানাব|নিতে\s*চাই"
                r"|আবেদন\s*করব|খুলব"
                r"|notun|natun|prothom|first\s*time|\bnew\b|korte\s*cha?i|korbo|banabo"
                r"|nite\s*cha?i|apply\s+for|want\s+(a|to\s+get)\s+.*passport|make\s+a\s+passport"),
    },

    "licence": {
        "duplicate": (r"হারা|হারিয়ে|হারাইছে|হারায়|খোয়া|চুরি|ডুপ্লিকেট|নষ্ট|ছিঁড়ে"
                      r"|haray|harai|hariye|haraise|harano|duplicate|\blost\b|stolen|damaged|torn|nosto"),

        "category_change": (r"পেশাদার|অপেশাদার|শ্রেণি\s*পরিবর্তন|ক্যাটাগরি|ভারী\s*যান|মাঝারি|আপগ্রেড"
                            r"|বাস\s*চালা|ট্রাক\s*চালা"
                            r"|peshadar|opeshadar|professional|non-?professional|category|class\s*change"
                            r"|heavy|medium|upgrade|bhari|truck|\bbus\b"),

        "exam": (r"পরীক্ষা|টেস্ট|লিখিত|মৌখিক|ব্যবহারিক|ভাইভা|ফিল্ড\s*টেস্ট|৮\s*আকৃতি"
                 r"|porikkha|porikha|\btest\b|exam|viva|practical|written|oral|field\s*test"),

        "idp": (r"আন্তর্জাতিক|ইন্টারন্যাশনাল|\bidp\b|বিদেশে\s*চালা|বাইরে\s*চালা"
                r"|international|abroad|overseas|foreign\s+country"),

        "renewal": (r"নবায়ন|মেয়াদ\s*(শেষ|উত্তীর্ণ)|রিনিউ|আবার\s*করতে"
                    r"|nobayon|nobayan|renew|renewal|expired?|meyad\s*ses?h"),

        "smartcard_new": (r"স্মার্ট\s*কার্ড|স্মার্টকার্ড|মূল\s*লাইসেন্স|আসল\s*লাইসেন্স|কার্ড\s*কবে"
                          r"|smart\s*card|smartcard|mul\s*licen|original\s+licen|permanent\s+licen"),

        "learner": (r"শিক্ষানবিশ|লার্নার|শিখব|শিখতে|নতুন\s*লাইসেন্স|প্রথম\s*বার|শুরু\s*করব"
                    r"|sikkhanobish|shikkhanobish|learner|learning|notun\s*licen|natun\s*licen"
                    r"|prothom|first\s*time|\bnew\b\s*licen|shikhbo|korte\s*cha?i|korbo|banabo"),
    },
}

# --------------------------------------------------------------------------- #

_DOMAIN_RX = {d: re.compile(p, re.IGNORECASE) for d, p in DOMAIN.items()}
_FIELD_RX = {f: re.compile(p, re.IGNORECASE) for f, p in FIELD.items()}
_SUBTYPE_RX = {
    dom: [(sub, re.compile(pat, re.IGNORECASE)) for sub, pat in subs.items()]
    for dom, subs in SUBTYPE.items()
}

# When two fields both match, the more specific question wins. "পাসপোর্ট হারালে কী
# কী কাগজ লাগে আর কত টাকা" is really a documents question with a fee aside.
FIELD_PRIORITY = [
    "verification", "minor", "collection", "appointment", "helpline",
    "payment", "eligibility", "validity",
    "fee", "timeline", "documents", "office", "online_steps",
]


def domain_of(message: str) -> str | None:
    """Only when exactly one domain is named — a message mentioning both is
    genuinely ambiguous and should be asked about, not guessed."""
    hits = [d for d, rx in _DOMAIN_RX.items() if rx.search(message)]
    return hits[0] if len(hits) == 1 else None


def field_of(message: str) -> str | None:
    hits = {f for f, rx in _FIELD_RX.items() if rx.search(message)}
    for field in FIELD_PRIORITY:
        if field in hits:
            return field
    return None


def subtype_of(message: str, domain: str | None) -> str | None:
    if not domain or domain not in _SUBTYPE_RX:
        return None
    for sub, rx in _SUBTYPE_RX[domain]:
        if rx.search(message):
            return sub
    return None


# A few questions name no service because in Bangladesh they only belong to one:
# police verification, a child's application, a delivery slip and appointments are
# passport matters; nobody asks them about a driving licence.
FIELD_IMPLIES_DOMAIN = {
    "verification": "passport",
    "minor": "passport",
    "collection": "passport",
    "appointment": "passport",
}


# Values people state outright, so the agent never asks for something already said.
# "super express passport koto din lage" must not be answered with "how urgent?".
SLOT_VALUES = {
    "delivery": [
        ("super_express", r"অতি\s*জরুরি|সুপার\s*এক্সপ্রেস|oti\s*joruri|super\s*express|superexpress"),
        ("express", r"জরুরি|এক্সপ্রেস|joruri|express|urgent"),
        ("regular", r"নিয়মিত|সাধারণ|regular|normal|niyomito"),
    ],
    "validity": [
        ("10", r"১০\s*বছর|10\s*(bochor|bosor|years?|yr)"),
        ("5", r"৫\s*বছর|\b5\s*(bochor|bosor|years?|yr)"),
    ],
    "pages": [
        ("64", r"৬৪\s*(পৃষ্ঠা|পাতা)?|\b64\s*(page|prishta)?"),
        ("48", r"৪৮\s*(পৃষ্ঠা|পাতা)?|\b48\s*(page|prishta)?"),
    ],
    "professional": [
        ("false", r"অপেশাদার|opeshadar|non-?professional|nonprofessional"),
        ("true", r"পেশাদার|peshadar|professional"),
    ],
    "vehicle_class": [
        ("heavy", r"ভারী|bhari|bhari\s*gari|heavy|truck|\bbus\b|ট্রাক|বাস"),
        ("medium", r"মাঝারি|majhari|medium"),
        ("motorcycle", r"মোটর\s*সাইকেল|মোটরসাইকেল|বাইক|motorcycle|motor\s*cycle|bike|scooter"),
        ("light", r"হালকা|halka|light|প্রাইভেট\s*কার|private\s*car|\bcar\b"),
    ],
}
_SLOT_RX = {name: [(val, re.compile(pat, re.IGNORECASE)) for val, pat in opts]
            for name, opts in SLOT_VALUES.items()}


def slots_of(message: str) -> dict:
    """First match wins per slot, and the more specific value is listed first —
    "অতি জরুরি" must not be read as plain "জরুরি"."""
    found = {}
    for name, opts in _SLOT_RX.items():
        for value, rx in opts:
            if rx.search(message):
                found[name] = value
                break
    return found


def _domain_from_subtype(message: str) -> str | None:
    """"পরীক্ষার দিন কী নিতে হবে" names no service, but only driving licences have
    an exam here — so a subtype word that belongs to exactly one domain settles it.
    A word both domains share (হারিয়ে) stays ambiguous, as it should."""
    # A single bare word ("সংশোধন") is a topic, not a request — it deserves a
    # question back, not a guess about which service was meant.
    if len(message.split()) < 2:
        return None
    hits = {dom for dom, rules in _SUBTYPE_RX.items()
            if any(rx.search(message) for _, rx in rules)}
    return hits.pop() if len(hits) == 1 else None


def route(message: str) -> dict:
    """Best-effort reading of one message. Any key may be None; the caller layers
    the model and retrieval on top of whatever is missing."""
    message = message or ""
    domain = domain_of(message)
    field = field_of(message)
    if not domain:
        domain = _domain_from_subtype(message)
    if not domain and field in FIELD_IMPLIES_DOMAIN:
        domain = FIELD_IMPLIES_DOMAIN[field]
    return {
        "domain": domain,
        "subtype": subtype_of(message, domain),
        "field": field,
        "slots": slots_of(message),
        "named_domain": domain_of(message),   # stated outright, not inferred
    }
