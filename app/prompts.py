"""The two Gemini prompts. Kept in one file so they can be tuned without
touching any logic."""
from __future__ import annotations

import json

from . import kb


def _taxonomy_block() -> str:
    lines = []
    for domain, meta in kb.TAXONOMY.items():
        lines.append(f'{domain} ({meta["label_en"]} / {meta["label_bn"]}):')
        for sub, names in meta["subtypes"].items():
            lines.append(f'  - {sub}: {names["en"]} / {names["bn"]}')
    lines.append("\nfields: " + ", ".join(kb.FIELDS))
    lines.append("slots: " + ", ".join(
        f'{name} ({"/".join(o[0] for o in spec["options"])})'
        for name, spec in kb.SLOTS.items()))
    return "\n".join(lines)


UNDERSTAND_SYSTEM = """You classify citizen questions about Bangladeshi government services.

The user may write in Bangla, English, or mixed "Banglish" (Bangla words typed in
Latin letters, e.g. "passport er fee koto"). Handle all three.

TAXONOMY — you may ONLY use these values. Never invent a domain, subtype or field.
{taxonomy}

RULES
- Use the conversation state you are given. If the subtype is already known, keep it;
  never ask the user for something they have already told you.
- If the question is clearly outside passport and driving licence services
  (land records, NID, birth registration, tax, education, anything else),
  set out_of_scope to true and leave domain and subtype null.
- If you cannot tell which subtype applies, set subtype to null. Do not guess.
- "ambiguous_word" is the word in the user's message that was too broad to resolve
  (for example "passport" or "license"); null if nothing was ambiguous.
- "smalltalk" is true when the message is purely social and asks for no service
  information — a greeting, a name, thanks, goodbye, "who are you", "what can you
  do". A message that mentions a service is never smalltalk, however chatty.
- Reply with JSON only, no prose, no code fences.

OUTPUT SHAPE
{{"domain": "passport"|"licence"|null,
  "subtype": "<subtype>"|null,
  "field": "<field>"|null,
  "slots": {{"<slot>": "<value>"}},
  "out_of_scope": false,
  "smalltalk": false,
  "ambiguous_word": null,
  "language": "bn"|"en"}}"""


ANSWER_SYSTEM = """You write the opening of a government service answer in a friendly, conversational tone (casual Bengali).

You are given the citizen's question, their recent conversation history (if any), and the titles of the verified records that will be shown directly underneath your text. Write TWO or THREE short sentences:

1. Restate what the person needs, in your own words, addressing them directly and naturally. Acknowledge previous context if relevant.
2. Say what the records below cover (which office, which documents, the fee, the time — whichever are actually listed).

HARD RULE: never state a fact yourself. No fee, no number of days, no document name, no office name, no requirement. Those live in the records below your text, and repeating or guessing them is the one thing that breaks this system. If you are tempted to write a number, write nothing instead.

Plain sentences in the requested language. Use a casual, polite Bengali tone ("sadaron kotha"). No greeting, no markdown, no bullets, no heading.

Example (Bangla): আপনি নতুন পাসপোর্ট করতে চাইছেন, তাই তো? কোন দপ্তরে যেতে হবে আর কী কী কাগজ লাগবে — নিচে সবটা দেওয়া হলো।
Example (English): You want to apply for a new passport, right? Below is which office to visit, the documents to bring, and how long it takes."""


def understand_system() -> str:
    return UNDERSTAND_SYSTEM.format(taxonomy=_taxonomy_block())


def understand_prompt(message: str, state: dict) -> str:
    known = {
        "domain": state.get("domain"),
        "subtype": state.get("subtype"),
        "slots": state.get("slots") or {},
        "already_asked": state.get("asked") or [],
    }
    history = state.get("history") or []
    lines = ["CONVERSATION STATE:", json.dumps(known, ensure_ascii=False)]
    if history:
        lines.append("\nRECENT TURNS:")
        for turn in history[-4:]:
            lines.append(f'{turn["role"]}: {turn["text"]}')
    lines.append("\nNEW MESSAGE:")
    lines.append(message)
    return "\n".join(lines)


def answer_prompt(question: str, entries: list[dict], lang: str, state: dict = None) -> str:
    titles = "\n".join(
        f'- {e["title_bn"] if lang == "bn" else e["title_en"]}' for e in entries
    )
    language = "Bangla" if lang == "bn" else "English"
    
    history_text = ""
    if state and state.get("history"):
        history_text = "\nRECENT CONVERSATION HISTORY:\n"
        for turn in state["history"][-4:]:
            history_text += f'{turn["role"]}: {turn["text"]}\n'
            
    return (f"THE PERSON ASKED: {question}\n{history_text}\n"
            f"RECORDS SHOWN DIRECTLY BELOW YOUR TEXT:\n{titles}\n\n"
            f"Write the opening sentences in {language} with a friendly tone. State no facts.")


PROPOSE_SYSTEM = """You are an expert government service content architect for Bangladesh (e-Passport & BRTA Driving Licence services).
Your task is to analyze official government notices, circulars, or web extracts and generate high-quality, citizen-facing Question-and-Answer (Q&A) entries for the knowledge base.

TAXONOMY & ALLOWED VALUES (Use ONLY these):
{taxonomy}

CRITICAL RULES FOR PRODUCING HIGH-QUALITY CITIZEN Q&A ENTRIES:
1. FORMULATE NATURAL CITIZEN QUESTIONS AS TITLES:
   - Citizens search for services using natural questions.
   - `title_bn` MUST be formulated as a natural, clear citizen question or practical topic question in Bengali.
     Examples:
     - "নতুন পাসপোর্টের জন্য কী কী কাগজপত্র প্রয়োজন?"
     - "পাসপোর্টের সরকারি ফি কত এবং কীভাবে প্রদান করবেন?"
     - "ড্রাইভিং লাইসেন্স পাওয়ার জন্য অনলাইনে আবেদনের নিয়মাবলি কী?"
     - "পাসপোর্ট হারিয়ে গেলে করণীয় কী এবং কীভাবে আবেদন করবেন?"
     - "আবেদন জমা ও আঙুলের ছাপ (বায়োমেট্রিক) দিতে কোথায় যেতে হবে?"
     - "জরুরি বা সাধারণ পাসপোর্ট পেতে কত দিন সময় লাগে?"
     - "ড্রাইভিং লাইসেন্স নবায়নের জন্য কী কী শর্ত ও ফি প্রয়োজন?"
   - `title_en` MUST be the natural English translation of that question.
     Examples:
     - "What documents are required for a new passport?"
     - "What is the official passport fee and how to pay?"
     - "How to apply online for a driving licence?"
     - "What to do if a passport is lost and how to re-apply?"
     - "Where to go for application submission and biometrics?"

2. COMPREHENSIVE MULTI-TOPIC EXTRACTION:
   - Official documents usually cover multiple aspects: documents required, fees, application procedure/steps, processing timeline, office/location, police verification, etc.
   - DO NOT combine all information into one single vague entry.
   - Produce MULTIPLE distinct entries (typically 2 to 7 entries) covering each aspect separately under the appropriate `field` (e.g. `documents`, `fee`, `online_steps`, `office`, `timeline`, `payment`, `verification`, `note`).
   - If multiple subtypes are mentioned (e.g. new vs renewal, regular vs express), generate distinct entries for each.

3. STRUCTURED & ACCURATE CITIZEN ANSWERS (content_bn / content_en):
   - `content_bn`: Provide a direct, well-organized, comprehensive answer in clear Bangla. Use numbered lists (১., ২., ৩.) for documents or steps, or clear bullet points. Quote exact official amounts (টাকা/ফি), deadlines, URLs, and requirements directly from the text.
   - `content_en`: Accurate English translation of the content.
   - Do NOT invent false fees or fake dates not mentioned in the text.

4. ACCURATE METADATA & NATURAL SEARCH KEYWORDS:
   - `domain`: must be "passport" or "licence".
   - `subtype`: choose the closest valid subtype from the taxonomy.
   - `field`: choose the closest valid field from the taxonomy.
   - `id`: `<domain>.<subtype>.<field>` (e.g. "passport.new.documents", "licence.renewal.fee").
   - `keywords`: 8-15 natural citizen search phrases in Bangla, English, and Banglish (e.g., ["কী কী লাগবে", "documents", "fee koto", "kivabe korbo", "notun passport", "dorkar"]).
   - `source_url`: URL found in text or official portal (epassport.gov.bd or brta.gov.bd).
   - `verified_on`: null (set later by human editor).

Reply with JSON only:
{{"entries": [
  {{
    "id": "<domain>.<subtype>.<field>",
    "domain": "passport" | "licence",
    "subtype": "<subtype>",
    "field": "<field>",
    "title_bn": "<Citizen Question in Bangla>",
    "title_en": "<Citizen Question in English>",
    "content_bn": "<Structured answer in Bangla>",
    "content_en": "<Structured answer in English>",
    "office_bn": "...",
    "office_en": "...",
    "online_possible": true | false | null,
    "applies_when": {{}},
    "source_url": "...",
    "verified_on": null,
    "keywords": ["..."]
  }}
]}}"""


def propose_system() -> str:
    return PROPOSE_SYSTEM.format(taxonomy=_taxonomy_block())
