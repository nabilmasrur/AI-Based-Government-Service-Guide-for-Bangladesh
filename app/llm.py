"""Thin wrapper over the Gemini SDK. The only file that talks to Google."""
from __future__ import annotations

import json
import logging
import random
import re
import time

from . import config

log = logging.getLogger(__name__)
_client = None

# Google's free tier returns these when the model is momentarily overloaded or the
# per-minute quota is hit. They clear on their own, so retry instead of giving up —
# a 503 during the demo would otherwise look like a broken project.
RETRY_CODES = (429, 500, 502, 503, 504)
MAX_ATTEMPTS = 3
_CODE = re.compile(r"\b(4\d\d|5\d\d)\b")


class LLMUnavailable(RuntimeError):
    """Raised when Gemini cannot be reached — callers degrade instead of crashing."""


def _retryable(exc: Exception) -> bool:
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if code is None:
        found = _CODE.search(str(exc))
        code = int(found.group(1)) if found else None
    return code in RETRY_CODES


def _with_retry(what: str, call):
    """Run `call`, retrying transient overload with a short randomised backoff."""
    last = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return call()
        except Exception as exc:                         # noqa: BLE001
            last = exc
            if attempt == MAX_ATTEMPTS or not _retryable(exc):
                break
            wait = (2 ** (attempt - 1)) + random.uniform(0, 0.4)
            log.warning("%s: transient error, retry %d/%d in %.1fs (%s)",
                        what, attempt, MAX_ATTEMPTS - 1, wait, str(exc)[:120])
            time.sleep(wait)
    raise LLMUnavailable(str(last)) from last


def get_client():
    """Created on first use, not at import time, so the server boots instantly
    and /health answers before anything heavy has loaded."""
    global _client
    if _client is None:
        if not config.GEMINI_API_KEY:
            raise LLMUnavailable("GEMINI_API_KEY is not set")
        try:
            from google import genai
        except ImportError as exc:                       # pragma: no cover
            raise LLMUnavailable("google-genai is not installed") from exc
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def _types():
    try:
        from google.genai import types
    except ImportError as exc:                           # pragma: no cover
        raise LLMUnavailable("google-genai is not installed") from exc
    return types


def embed(texts: list[str], task: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """Embed a batch of strings. Falls back to one-at-a-time if the batch call
    is rejected, which some model versions do."""
    client = get_client()
    types = _types()
    cfg = types.EmbedContentConfig(task_type=task)
    try:
        resp = _with_retry("embed batch", lambda: client.models.embed_content(
            model=config.EMBED_MODEL, contents=texts, config=cfg))
        return [list(e.values) for e in resp.embeddings]
    except Exception as exc:                             # noqa: BLE001
        log.warning("batch embed failed (%s); retrying one by one", str(exc)[:150])
        out = []
        for text in texts:
            resp = _with_retry("embed one", lambda t=text: client.models.embed_content(
                model=config.EMBED_MODEL, contents=t, config=cfg))
            out.append(list(resp.embeddings[0].values))
        return out


def generate(system: str, prompt: str, as_json: bool = False, temperature: float = 0.2) -> str:
    client = get_client()
    types = _types()
    cfg = types.GenerateContentConfig(
        system_instruction=system,
        temperature=temperature,
        response_mime_type="application/json" if as_json else "text/plain",
    )
    resp = _with_retry("generate", lambda: client.models.generate_content(
        model=config.CHAT_MODEL, contents=prompt, config=cfg))
    return (resp.text or "").strip()


def generate_json(system: str, prompt: str) -> dict:
    """Ask for JSON and never let a stray fence or prose crash the request."""
    raw = generate(system, prompt, as_json=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                pass
        log.warning("model did not return JSON: %.200s", raw)
        return {}
