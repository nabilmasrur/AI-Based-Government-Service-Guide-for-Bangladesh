"""The goal-based agent.

Two entry points:
  handle_action()  — a chip was clicked. Intent is already structured, so NO Gemini
                     call happens at all and the answer comes back in ~0.2s.
  handle_message() — free text. One Gemini call to understand, and one short call to
                     write the opening sentence. Facts are never generated: the body
                     of every answer is copied verbatim from verified KB entries.
"""
from __future__ import annotations

import logging
import re
import time

from . import config, kb, llm, phrases, prompts, retriever, session, texts

# Services this version deliberately does not cover. Checked without the LLM so the
# scope boundary holds even when Gemini is slow, rate limited, or returns bad JSON.
OUT_OF_SCOPE = re.compile(
    r"জমি|খতিয়ান|নামজারি|ভূমি|খাজনা|দলিল|পর্চা|মিউটেশন"
    r"|জন্মনিবন্ধন|জন্ম নিবন্ধন|মৃত্যু নিবন্ধন|বিবাহ"
    r"|এনআইডি|ভোটার|ট্রেড লাইসেন্স|টিন|কর\b"
    r"|\bjomi\b|\bjami\b|khatian|khotian|namjari|mutation|porcha|land\b|khajna"
    r"|birth certificate|birth registration|death certificate|marriage"
    r"|\bnid\b|national id card|voter|trade licen|\btin\b|land tax|income tax",
    re.IGNORECASE)

# Social messages get a written answer, not a retrieval. Checked before the LLM
# so "assalamu alaikum" costs no quota and never reaches the knowledge base —
# and so the agent sounds like a person rather than a search box.
SMALLTALK = [
    ("chat_who", re.compile(
        r"(তুমি|আপনি|তুই)\s*(কে|কি)\b|তোমার\s*পরিচয়|কে\s*তুমি"
        r"|\b(tumi|apni|apne|tui)\s*(ke|k)\b|who\s+are\s+you|what\s+are\s+you"
        r"|তুমি\s*কি\s*(ai|এআই|রোবট)|are\s+you\s+(a\s+)?(bot|ai|human|robot)", re.IGNORECASE)),
    ("chat_help", re.compile(
        r"(কি|কী)\s*(কি\s*)?(করতে|সাহায্য)\s*(পারো|পারেন|পার)\b|কীভাবে\s*কাজ\s*কর"
        r"|তুমি\s*কি\s*কর|\bki\s*ki\s*(korte|parba|paro|paren)\b"
        r"|what\s+can\s+you\s+do|how\s+do\s+you\s+work|\bhelp\s*me\b|\bhelp\b\s*$", re.IGNORECASE)),
    ("chat_thanks", re.compile(
        r"ধন্যবাদ|শুকরিয়া|থ্যাংক|\bdhonnobad\b|\bdhonnobaad\b|\bthanks?\b|thank\s+you|\bthnx\b|\bty\b", re.IGNORECASE)),
    ("chat_bye", re.compile(
        r"আল্লাহ\s*হাফেজ|খোদা\s*হাফেজ|বিদায়|\ballah\s*hafez\b|\bkhoda\s*hafez\b"
        r"|\bbye\b|good\s*bye|see\s+you", re.IGNORECASE)),
    ("chat_howareyou", re.compile(
        r"কেমন\s*আছ|কেমন\s*আছেন|\bkemon\s*ac?h?o?\b|\bkemon\s*achen\b"
        r"|how\s+are\s+you|how\s+r\s+u", re.IGNORECASE)),
    ("chat_greet", re.compile(
        r"আসসালাম|আস-?সালাম|সালাম|নমস্কার|আদাব|শুভ\s*(সকাল|সন্ধ্যা|দুপুর|রাত)"
        r"|\bassalam|\bsalam\b|\bslm\b|\bhello\b|\bhi\b|\bhey\b|good\s*(morning|evening|afternoon)", re.IGNORECASE)),
    ("chat_name", re.compile(
        r"^\s*(আমি|আমার\s*নাম)\s+\S+\s*[।.!]?\s*$|^\s*(ami|amar\s*nam)\s+\w+\s*[.!]?\s*$"
        r"|^\s*(my\s+name\s+is|i\s*am|i'?m)\s+\w+\s*[.!]?\s*$", re.IGNORECASE)),
]


def _smalltalk(message: str) -> str | None:
    """Only when the message names no service — "passport er jonno help lagbe"
    mentions help but is a real question, and must not be answered with chit-chat."""
    if phrases.domain_of(message):
        return None
    if len(message) > 90:
        return None
    for key, rx in SMALLTALK:
        if rx.search(message):
            return key
    return None


log = logging.getLogger(__name__)

# Which slots must be known before a given (domain, field) can be answered.
REQUIRED_SLOTS: dict[tuple[str, str | None, str], list[str]] = {
    ("passport", "new", "fee"): ["validity", "delivery"],
    ("passport", "reissue", "fee"): ["validity", "delivery"],
    ("licence", "smartcard_new", "fee"): ["professional"],
    ("licence", "renewal", "fee"): ["professional"],
}

# The domain's most common service, used only to break a tie when someone asks
# about a topic that several services share ("how many years is it valid?").
PRIMARY_SUBTYPE = {"passport": "new", "licence": "learner"}

# A few topics have a different natural default: an unqualified question about a
# licence's validity is about the licence itself, not the learner's permit.
FIELD_PRIMARY = {
    ("licence", "validity"): "smartcard_new",
    ("licence", "collection"): "smartcard_new",
    ("passport", "validity"): "new",
}

# Fields shown, in order, when the user has not asked about one field in particular.
# Only these make up an answer when no particular field was asked for. The rest
# (police verification, minors, collection …) appear when someone asks for them,
# which keeps the ordinary card short instead of burying the useful part.
DEFAULT_FIELDS = ["office", "documents", "fee", "timeline", "online_steps", "note"]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _subtype_for_field(domain: str, field: str | None) -> str | None:
    """Some questions name a topic that belongs to exactly one service — a delivery
    slip, a child's application, police verification. Asking "which service did you
    mean?" there is a worse answer than reading it off the knowledge base."""
    if not domain or not field:
        return None
    subs = {e["subtype"] for e in kb.load()
            if e["domain"] == domain and e["field"] == field}
    return subs.pop() if len(subs) == 1 else None


def _has_entry(domain: str, subtype: str | None, field: str | None) -> bool:
    return any(e["domain"] == domain and e["subtype"] == subtype and e["field"] == field
               for e in kb.load())


def _missing_slots(domain: str | None, subtype: str | None, field: str | None,
                   slots: dict, asked: list) -> list[str]:
    if not domain or not field:
        return []
    needed = REQUIRED_SLOTS.get((domain, subtype, field), [])
    return [s for s in needed if not slots.get(s) and s not in asked]


def _select(entries: list[dict], field: str | None) -> list[dict]:
    """One entry per field, best score wins, in a stable reading order."""
    best: dict[str, dict] = {}
    for entry in entries:
        key = entry["field"]
        if key not in best or entry.get("score", 0) > best[key].get("score", 0):
            best[key] = entry
    if field and field in best:
        ordered = [best[field]] + [best[f] for f in DEFAULT_FIELDS
                                   if f in best and f != field]
        return ordered[:4]
    return [best[f] for f in DEFAULT_FIELDS if f in best][:5]


def _highlight(domain: str, field: str | None, slots: dict, lang: str) -> str | None:
    """'Your case: 48 pages · 5 years · Regular' — answers the question while still
    showing the whole table, so the user sees the context of their own number."""
    if field not in ("fee", "timeline") or not slots:
        return None
    order = kb.TAXONOMY[domain]["fee_slots"] + ["delivery"]
    parts = [texts.slot_value_label(s, slots[s], lang)
             for s in order if s in slots and slots[s]]
    return " · ".join(dict.fromkeys(parts)) or None


def _build_card(entries: list[dict], domain: str, subtype: str,
                field: str | None, slots: dict, lang: str) -> dict:
    chosen = _select(entries, field)
    dom_meta = kb.TAXONOMY[domain]
    sub_meta = dom_meta["subtypes"][subtype]

    fields, sources, warn = [], [], None
    for entry in chosen:
        fields.append({
            "key": entry["field"],
            "label": texts.label(kb.FIELDS[entry["field"]], lang),
            "content": entry[f"content_{lang}"],
        })
        if entry.get("source_url"):
            sources.append({
                "id": entry["id"],
                "url": entry["source_url"],
                "verified_on": entry.get("verified_on"),
                "score": entry.get("score"),
            })
        if kb.is_stale(entry):
            warn = "unverified" if not entry.get("verified_on") else "stale"

    office = next((e for e in chosen if e.get(f"office_{lang}")), None)

    return {
        "domain": domain,
        "subtype": subtype,
        "badge": f'{texts.label(dom_meta, lang) or dom_meta[f"label_{lang}"]} · {texts.label(sub_meta, lang)}',
        "title": texts.label(sub_meta, lang),
        "ref": f'{domain.upper()} / {subtype.upper()}',
        "authority": dom_meta[f"authority_{lang}"],
        "office": office.get(f"office_{lang}") if office else None,
        "highlight_label": texts.t("your_case", lang),
        "highlight": _highlight(domain, field, slots, lang),
        "fields": fields,
        "sources": sources,
        "warn": warn,
        "warn_text": texts.t(warn, lang) if warn else None,
    }


def _trace(state: dict, hits: list[dict], decision: str, note: str) -> dict:
    return {
        "domain": state.get("domain"),
        "subtype": state.get("subtype"),
        "field": state.get("field"),
        "slots": state.get("slots") or {},
        "conf": round(max((h.get("score", 0) for h in hits), default=0.0), 3),
        "threshold": config.CONF_THRESHOLD,
        "hits": [[h["id"], round(h.get("score", 0), 3)] for h in hits[:4]],
        "decision": decision,
        "note": note,
    }


def _reply(kind: str, lead: str, chips: list, trace: dict, state: dict,
           card: dict | None = None, started: float = 0.0) -> dict:
    return {
        "type": kind,
        "lead": lead,
        "card": card,
        "chips": chips,
        "trace": trace,
        "state": session.public(state),
        "session_id": state["session_id"],
        "ms": max(1, int((time.time() - started) * 1000)) if started else 0,
    }


# --------------------------------------------------------------------------- #
# the three outcomes
# --------------------------------------------------------------------------- #

def _clarify(state: dict, lang: str, started: float, word: str | None = None) -> dict:  # noqa: ARG001
    domain, subtype = state["domain"], state["subtype"]

    if not domain:
        note = "কোনো domain শনাক্ত হয়নি — দুটি সেবার মধ্যে বেছে নিতে বলা হয়েছে।"
        return _reply("clarify", texts.t("ask_domain", lang), texts.domain_chips(lang),
                      _trace(state, [], "clarify", note), state, started=started)

    if not subtype:
        hits = retriever.by_subtype(domain, next(iter(kb.TAXONOMY[domain]["subtypes"])))
        note = f"{len(kb.TAXONOMY[domain]['subtypes'])}টি sub-type সম্ভাব্য — অনুমান না করে প্রশ্ন করা হয়েছে।"
        question = texts.t("ask_subtype", lang,
                           dom=kb.TAXONOMY[domain][f"label_{lang}"])
        return _reply("clarify", question, texts.subtype_chips(domain, lang),
                      _trace(state, hits[:3], "clarify", note), state, started=started)

    missing = _missing_slots(domain, subtype, state["field"], state["slots"], state["asked"])
    slot = missing[0]
    state["asked"].append(slot)
    base = {"domain": domain, "subtype": subtype, "field": state["field"]}
    key = "ask_slot_more" if len(state["asked"]) > 1 else "ask_slot"
    question = texts.t(key, lang, label=texts.slot_label(slot, lang))
    note = f"field={state['field']} জানা, কিন্তু slot '{slot}' অপূর্ণ।"
    hits = retriever.by_subtype(domain, subtype, state["field"])
    return _reply("clarify", question, texts.slot_chips(slot, lang, base),
                  _trace(state, hits[:3], "clarify", note), state, started=started)


def _answer(state: dict, hits: list[dict], lang: str, started: float,
            question: str | None = None, use_llm: bool = True,
            degraded: bool = False) -> dict:
    domain, subtype, field = state["domain"], state["subtype"], state["field"]
    card = _build_card(hits, domain, subtype, field, state["slots"], lang)

    lead = texts.lead(domain, subtype, [f["key"] for f in card["fields"]], lang)
    if use_llm and question:
        try:
            written = llm.generate(prompts.ANSWER_SYSTEM,
                                   prompts.answer_prompt(question, hits, lang, state),
                                   temperature=0.3)
            if written:
                lead = written.split("\n")[0].strip()
        except llm.LLMUnavailable as exc:
            log.warning("lead generation failed (%s) — using template", exc)

    note = ("chip থেকে অভিপ্রায় জানা — কোনো LLM কল হয়নি।" if not use_llm
            else "সব slot পূর্ণ — উদ্ধৃত entry থেকে উত্তর তৈরি।")
    if degraded:
        note = "Gemini-তে পৌঁছানো যায়নি — subtype শুধু retrieval দিয়ে অনুমান করা হয়েছে।"
    shown = {f["key"] for f in card["fields"]}
    chips = texts.followup_chips(domain, subtype, lang, shown=shown)
    return _reply("answer", lead, chips, _trace(state, hits, "answer", note),
                  state, card=card, started=started)


def _no_info(state: dict, hits: list[dict], lang: str, started: float,
             out_of_scope: bool = False) -> dict:
    key = "out_of_scope" if out_of_scope else "no_info"
    note = ("প্রশ্নটি সমর্থিত দুটি সেবার বাইরে।" if out_of_scope
            else f"সর্বোচ্চ similarity {max((h.get('score', 0) for h in hits), default=0):.2f} "
                 f"— সীমা {config.CONF_THRESHOLD}-এর নিচে।")
    return _reply("no_info", texts.t(key, lang), texts.domain_chips(lang),
                  _trace(state, hits, "reject", note), state, started=started)


# --------------------------------------------------------------------------- #
# entry points
# --------------------------------------------------------------------------- #

def handle_action(state: dict, action: dict, lang: str) -> dict:
    """Fast path — a chip was clicked, so the intent is already structured."""
    started = time.time()
    if action.get("domain"):
        if action["domain"] != state["domain"]:
            state.update(subtype=None, field=None, slots={}, asked=[])
        state["domain"] = action["domain"]
    if action.get("subtype") and action["subtype"] != state["subtype"]:
        state.update(subtype=action["subtype"], field=None, slots={}, asked=[])
    if action.get("field"):
        state["field"] = action["field"]
    if action.get("slots"):
        state["slots"].update({k: str(v) for k, v in action["slots"].items()})

    if not state["domain"] or not state["subtype"]:
        return _clarify(state, lang, started)
    if _missing_slots(state["domain"], state["subtype"], state["field"],
                      state["slots"], state["asked"]):
        return _clarify(state, lang, started)

    hits = retriever.by_subtype(state["domain"], state["subtype"], state["field"])
    if not hits:
        hits = retriever.by_subtype(state["domain"], state["subtype"])
    if not hits:
        return _no_info(state, [], lang, started)
    return _answer(state, hits, lang, started, use_llm=False)


def handle_message(state: dict, message: str, lang: str) -> dict:
    """Full path — free text in Bangla, English or Banglish."""
    started = time.time()
    session.remember(state, "user", message)

    social = _smalltalk(message)
    if social:
        chips = texts.domain_chips(lang) if social != "chat_bye" else []
        note = f"সামাজিক বার্তা ({social}) — retrieval বা LLM কিছুই লাগেনি।"
        return _reply("chat", texts.t(social, lang), chips,
                      _trace(state, [], "chat", note), state, started=started)

    rule = phrases.route(message)

    intent, degraded = {}, False
    try:
        intent = llm.generate_json(prompts.understand_system(),
                                   prompts.understand_prompt(message, state))
    except llm.LLMUnavailable as exc:
        log.warning("understand call failed (%s) — falling back to retrieval only", exc)
        degraded = True

    # An empty dict means the model answered but not with usable JSON. That is the
    # same situation as the call failing, so degrade instead of mistaking it for
    # "understood fine, just no domain".
    if not intent:
        log.warning("understand call returned nothing usable — retrieval only")
        degraded = True

    if intent.get("smalltalk") and not rule["domain"]:
        return _reply("chat", texts.t("chat_greet", lang), texts.domain_chips(lang),
                      _trace(state, [], "chat", "মডেল একে সামাজিক বার্তা হিসেবে চিহ্নিত করেছে।"),
                      state, started=started)

    if intent.get("out_of_scope"):
        return _no_info(state, [], lang, started, out_of_scope=True)

    # The hand-written rules take precedence over the model. They only fire on
    # decisive words, they are testable, and they behave the same every run —
    # all three matter more here than the extra coverage a guess would buy.
    new_domain = rule["domain"] or intent.get("domain")
    new_subtype = rule["subtype"] or intent.get("subtype")
    new_field = rule["field"] or intent.get("field")
    if rule["subtype"] and intent.get("subtype") and rule["subtype"] != intent["subtype"]:
        log.info("rule %r overrode model %r for %r",
                 rule["subtype"], intent["subtype"], message[:60])

    if new_domain:
        if new_domain != state["domain"]:
            state.update(subtype=None, slots={}, asked=[])
        state["domain"] = new_domain
    if new_subtype:
        if new_subtype != state["subtype"]:
            state.update(field=None)
        state["subtype"] = new_subtype
    if new_field:
        state["field"] = new_field

    # Resolve the service from the topic when the topic only belongs to one, and
    # correct a subtype guess that cannot answer the question that was asked.
    if state["domain"] and state["field"]:
        only = _subtype_for_field(state["domain"], state["field"])
        if only and (not state["subtype"]
                     or not _has_entry(state["domain"], state["subtype"], state["field"])):
            state["subtype"] = only
        elif not state["subtype"]:
            fallback = (FIELD_PRIMARY.get((state["domain"], state["field"]))
                        or PRIMARY_SUBTYPE.get(state["domain"]))
            if fallback and _has_entry(state["domain"], fallback, state["field"]):
                state["subtype"] = fallback
    for slot, value in {**(intent.get("slots") or {}), **rule["slots"]}.items():
        if slot in kb.SLOTS and value not in (None, ""):
            state["slots"][slot] = str(value)

    # Without the understanding call we can still search; retrieval tells us
    # which subtype the question is about. If embeddings are down too, keyword
    # scores alone never reach the normal threshold, so the bar drops to "at
    # least two keyword hits" — a degraded answer beats no service at all.
    # Retrieval may refine a service the person named; it may not invent one they
    # never mentioned — that is what the clarifying question is for.
    if degraded and not state["subtype"] and (state["domain"] or rule["domain"]):
        state["domain"] = state["domain"] or rule["domain"]
        probe = retriever.search(message, domain=state["domain"], top_k=12)
        bar = 2 * config.KEYWORD_BOOST if retriever.keyword_only() else config.CONF_THRESHOLD

        # Score the SUBTYPE, not one entry. Every passport record embeds close to
        # every other, so the single top hit picks the wrong service far too often
        # ("passport haray gese" landing on new.timeline). Summing each subtype's
        # evidence is much steadier, and the winning entry's field is ignored — a
        # guessed subtype should show the whole service, not one narrow slice.
        pool: dict[tuple, float] = {}
        for hit in probe:
            key = (hit["domain"], hit["subtype"])
            pool[key] = max(pool.get(key, 0.0), hit["score"])
        if pool:
            (dom, sub), best = max(pool.items(), key=lambda kv: kv[1])
            if best >= bar:
                state["domain"], state["subtype"] = dom, sub

    # Scope guard: a land or NID question must be turned away, not answered with
    # "which service did you mean?" — that invites the user to force a wrong answer.
    if not rule["named_domain"] and OUT_OF_SCOPE.search(message):
        return _no_info(state, [], lang, started, out_of_scope=True)

    if not state["domain"] or not state["subtype"]:
        return _clarify(state, lang, started, word=intent.get("ambiguous_word") or message.strip()[:24])

    if _missing_slots(state["domain"], state["subtype"], state["field"],
                      state["slots"], state["asked"]):
        return _clarify(state, lang, started)

    hits = retriever.search(message, domain=state["domain"], subtype=state["subtype"])
    if not hits or hits[0]["score"] < config.CONF_THRESHOLD:
        wider = retriever.by_subtype(state["domain"], state["subtype"], state["field"])
        if wider:
            hits = wider
        else:
            return _no_info(state, hits, lang, started)

    result = _answer(state, hits, lang, started, question=message,
                     use_llm=not degraded, degraded=degraded)
    session.remember(state, "assistant", result["lead"])
    return result
