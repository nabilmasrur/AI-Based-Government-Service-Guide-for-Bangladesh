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


PROPOSE_SYSTEM = """You turn a plain-text extract from an official Bangladeshi
government document into draft knowledge-base entries for review by a human editor.

TAXONOMY — use only these values:
{taxonomy}

RULES
- Produce one entry per (subtype, field) pair that the text actually supports.
- Copy facts from the text. Never add a fee, a deadline or a document that the text
  does not state. If the text is vague, write less rather than inventing.
- content_bn must be Bangla and content_en must be English; translate faithfully.
- keywords: 6-12 short search terms, mixing Bangla and English.
- Leave verified_on as null. A human sets it after checking the official source.
- Reply with JSON only: {{"entries": [ ... ]}}

ENTRY SHAPE
{{"id": "<domain>.<subtype>.<field>", "domain": "...", "subtype": "...",
  "field": "...", "title_bn": "...", "title_en": "...",
  "content_bn": "...", "content_en": "...",
  "office_bn": "...", "office_en": "...", "online_possible": true|false|null,
  "applies_when": {{}}, "source_url": "", "verified_on": null, "keywords": []}}"""


def propose_system() -> str:
    return PROPOSE_SYSTEM.format(taxonomy=_taxonomy_block())
