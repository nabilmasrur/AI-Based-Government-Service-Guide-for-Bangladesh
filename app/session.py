"""In-memory conversation state. No database: the proposal scopes state to a
single session, and there are no user accounts to persist."""
from __future__ import annotations

import time
import uuid

from . import config

_sessions: dict[str, dict] = {}


def _blank(session_id: str) -> dict:
    return {
        "session_id": session_id,
        "domain": None,
        "subtype": None,
        "field": None,
        "slots": {},
        "asked": [],          # slots already asked about — stops repeat questions
        "history": [],
        "lang": "bn",
        "touched": time.time(),
    }


def _sweep() -> None:
    cutoff = time.time() - config.SESSION_TTL
    for sid in [s for s, v in _sessions.items() if v["touched"] < cutoff]:
        _sessions.pop(sid, None)


def get(session_id: str | None) -> dict:
    _sweep()
    if not session_id or session_id not in _sessions:
        session_id = session_id or uuid.uuid4().hex
        _sessions[session_id] = _blank(session_id)
    state = _sessions[session_id]
    state["touched"] = time.time()
    return state


def reset(session_id: str) -> dict:
    _sessions[session_id] = _blank(session_id)
    return _sessions[session_id]


def remember(state: dict, role: str, text: str) -> None:
    state["history"].append({"role": role, "text": text})
    del state["history"][: -config.HISTORY_TURNS * 2]


def public(state: dict) -> dict:
    """The slice of state the frontend's inspector panel shows."""
    return {
        "domain": state["domain"],
        "subtype": state["subtype"],
        "field": state["field"],
        "slots": state["slots"],
        "asked": state["asked"],
    }


def count() -> int:
    return len(_sessions)
