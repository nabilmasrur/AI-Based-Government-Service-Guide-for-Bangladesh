"""Retrieval over the knowledge base.

With ~70 entries a full cosine scan through a numpy matrix takes well under a
millisecond, so an approximate-nearest-neighbour index (Chroma, FAISS) would add
a heavy dependency and a slower cold start for no measurable gain. Swapping this
file for Chroma later touches nothing else.
"""
from __future__ import annotations

import logging
import re
import threading

import numpy as np

from . import config, kb, llm

log = logging.getLogger(__name__)

_lock = threading.Lock()
_matrix: np.ndarray | None = None
_ids: list[str] | None = None
_vector_ok = True          # flips to False if embeddings are unavailable


# --------------------------------------------------------------------------- #
# index
# --------------------------------------------------------------------------- #

def build_index(verbose: bool = False) -> None:
    """Embed every entry and write the matrix to disk. Run via `python -m app.index`."""
    entries = kb.load(force=True)
    texts = [kb.embed_text(e) for e in entries]
    if verbose:
        print(f"embedding {len(texts)} entries with {config.EMBED_MODEL} …")
    vectors = llm.embed(texts, task="RETRIEVAL_DOCUMENT")
    matrix = _normalise(np.asarray(vectors, dtype=np.float32))
    config.EMB_FILE.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(config.EMB_FILE, matrix=matrix,
                        ids=np.array([e["id"] for e in entries]))
    if verbose:
        print(f"wrote {config.EMB_FILE}  shape={matrix.shape}")


def _normalise(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=-1, keepdims=True)
    return mat / np.clip(norms, 1e-9, None)


def _load_index() -> bool:
    """Load the cached matrix. Returns False when vector search is unavailable —
    the caller then falls back to keyword scoring rather than failing."""
    global _matrix, _ids, _vector_ok
    if _matrix is not None:
        return True
    if not _vector_ok:
        return False
    with _lock:
        if _matrix is not None:
            return True
        try:
            if not config.EMB_FILE.exists():
                log.info("no embeddings file; building one now")
                build_index()
            data = np.load(config.EMB_FILE, allow_pickle=False)
            _matrix, _ids = data["matrix"], list(data["ids"])
            if len(_ids) != len(kb.load()):
                log.warning("index is stale (%d vectors vs %d entries); rebuilding",
                            len(_ids), len(kb.load()))
                build_index()
                data = np.load(config.EMB_FILE, allow_pickle=False)
                _matrix, _ids = data["matrix"], list(data["ids"])
            return True
        except Exception as exc:                          # noqa: BLE001
            log.warning("vector search unavailable (%s) — keyword only", exc)
            _vector_ok = False
            return False


# --------------------------------------------------------------------------- #
# search
# --------------------------------------------------------------------------- #

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def _tokens(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text or "") if len(w) > 1}


def _keyword_score(entry: dict, query: str) -> float:
    """Catches what the embedding misses — 'ফি', 'koto taka', 'GD' and friends."""
    q = query.lower()
    q_tokens = _tokens(query)
    hits = 0
    for word in entry.get("keywords", []):
        w = word.lower()
        if (" " in w and w in q) or (w in q_tokens) or (len(w) > 2 and w in q):
            hits += 1
    return min(hits * config.KEYWORD_BOOST, config.KEYWORD_BOOST_MAX)


def search(query: str, domain: str | None = None, subtype: str | None = None,
           field: str | None = None, top_k: int | None = None) -> list[dict]:
    """Filter → vector similarity → keyword boost. Returns entries with a `score`."""
    entries = kb.load()
    top_k = top_k or config.TOP_K

    # 1. filter — this is where multi-turn context earns its keep
    pool = [
        (i, e) for i, e in enumerate(entries)
        if (domain is None or e["domain"] == domain)
        and (subtype is None or e["subtype"] == subtype)
        and (field is None or e["field"] == field)
    ]
    if not pool:                                  # filter too tight — widen it
        pool = [
            (i, e) for i, e in enumerate(entries)
            if (domain is None or e["domain"] == domain)
            and (subtype is None or e["subtype"] == subtype)
        ]
    if not pool:
        pool = list(enumerate(entries))

    # 2. vector similarity, when we have an index
    sims = np.zeros(len(entries), dtype=np.float32)
    if _load_index():
        try:
            qvec = _normalise(np.asarray(llm.embed([query], task="RETRIEVAL_QUERY")[0],
                                         dtype=np.float32))
            sims = _matrix @ qvec
        except llm.LLMUnavailable as exc:
            log.warning("query embedding failed (%s) — keyword only", exc)

    # 3. keyword boost, then rank
    scored = []
    for idx, entry in pool:
        score = float(sims[idx]) + _keyword_score(entry, query)
        scored.append({**entry, "score": round(min(score, 1.0), 4)})
    scored.sort(key=lambda e: e["score"], reverse=True)
    return scored[:top_k]


def by_subtype(domain: str, subtype: str, field: str | None = None) -> list[dict]:
    """Exact lookup used by the fast path — no embedding call at all."""
    order = ["office", "documents", "fee", "timeline", "online_steps", "note"]
    found = [
        {**e, "score": 1.0} for e in kb.load()
        if e["domain"] == domain and e["subtype"] == subtype
        and (field is None or e["field"] == field)
    ]
    found.sort(key=lambda e: order.index(e["field"]) if e["field"] in order else 99)
    return found


def keyword_only() -> bool:
    """True when embeddings are unreachable and scores come from keywords alone.
    Callers then judge hits against a lower bar — a degraded answer beats none."""
    return not _vector_ok


def get(entry_id: str) -> dict | None:
    return next((e for e in kb.load() if e["id"] == entry_id), None)


def reset() -> None:
    """Called after the admin approves new entries."""
    global _matrix, _ids, _vector_ok
    with _lock:
        _matrix, _ids, _vector_ok = None, None, True
    kb.load(force=True)
