"""FastAPI application.

Run locally:   uvicorn app.main:app --reload
Docs:          http://127.0.0.1:8000/docs
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time

from fastapi import Body, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import admin as admin_mod
from . import agent, config, kb, limits, llm, session, texts, analytics

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")

BOOTED = time.time()

app = FastAPI(
    title="সেবা সহায়ক — Government Service Assistant",
    description="Passport and driving licence guidance for Bangladesh. "
                "Unofficial academic project (CSE 3202, BAUST).",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# models
# --------------------------------------------------------------------------- #

class ChatIn(BaseModel):
    session_id: str | None = None
    message: str = Field(min_length=1, max_length=500)
    lang: str = "bn"


class ActionIn(BaseModel):
    session_id: str | None = None
    action: dict = Field(default_factory=dict)
    lang: str = "bn"


class ResetIn(BaseModel):
    session_id: str | None = None

class FeedbackIn(BaseModel):
    session_id: str | None = None
    query_id: int
    is_positive: bool


class AdminLoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=100)


def _lang(value: str | None) -> str:
    return "en" if (value or "").lower().startswith("en") else "bn"


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# --------------------------------------------------------------------------- #
# health & meta
# --------------------------------------------------------------------------- #

@app.get("/health")
def health() -> dict:
    """Deliberately featherweight: no Gemini call, no index load, no KB read.

    The keep-alive cron hits this every few minutes; anything heavier here would
    quietly burn the API quota and slow the wake-up it is meant to speed.
    """
    return {"ok": True, "uptime_s": int(time.time() - BOOTED)}


@app.get("/api/meta")
def meta() -> dict:
    """Taxonomy, field labels, slot options and KB stats — the frontend builds its
    sidebar and chips from this, so the taxonomy lives in exactly one place."""
    return {
        **kb.meta(),
        "llm_ready": bool(config.GEMINI_API_KEY),
        "model": config.CHAT_MODEL,
        "threshold": config.CONF_THRESHOLD,
        "sessions": session.count(),
        "limits": limits.snapshot(),
    }


# --------------------------------------------------------------------------- #
# chat
# --------------------------------------------------------------------------- #

@app.post("/api/action")
def action(payload: ActionIn, request: Request) -> dict:
    """Fast path. A chip carries its own structured intent, so this never calls
    Gemini — and is therefore not rate limited."""
    state = session.get(payload.session_id)
    lang = _lang(payload.lang)
    state["lang"] = lang
    try:
        out = agent.handle_action(state, payload.action or {}, lang)
        
        # Log query
        trace = out.get("trace", {})
        query_id = analytics.log_query(
            payload.session_id, 
            str(payload.action), 
            trace.get("domain"), 
            trace.get("subtype"), 
            trace.get("field"), 
            trace.get("decision", "unknown")
        )
        out["query_id"] = query_id
        
        out["limit"] = limits.remaining(_client_ip(request))
        return out
    except Exception:                                    # noqa: BLE001
        log.exception("action failed")
        return JSONResponse(status_code=500,
                            content={"type": "error", "lead": texts.t("error", lang)})


@app.post("/api/chat")
def chat(payload: ChatIn, request: Request) -> dict:
    """Full path. Rate limited, because this one reaches Gemini."""
    lang = _lang(payload.lang)
    allowed, why = limits.check(_client_ip(request))
    if not allowed:
        log.info("rate limited (%s)", why)
        return JSONResponse(status_code=429,
                            content={"type": "error", "lead": texts.t("limit", lang),
                                     "chips": [], "trace": None,
                                     "limit": limits.remaining(_client_ip(request))})

    state = session.get(payload.session_id)
    state["lang"] = lang
    try:
        out = agent.handle_message(state, payload.message.strip(), lang)
        
        # Log query
        trace = out.get("trace", {})
        query_id = analytics.log_query(
            payload.session_id, 
            payload.message.strip(), 
            trace.get("domain"), 
            trace.get("subtype"), 
            trace.get("field"), 
            trace.get("decision", "unknown")
        )
        out["query_id"] = query_id
        
        out["limit"] = limits.remaining(_client_ip(request))
        return out
    except llm.LLMUnavailable as exc:
        log.warning("llm unavailable: %s", exc)
        return JSONResponse(status_code=503,
                            content={"type": "error", "lead": texts.t("error", lang)})
    except Exception:                                    # noqa: BLE001
        log.exception("chat failed")
        return JSONResponse(status_code=500,
                            content={"type": "error", "lead": texts.t("error", lang)})


@app.post("/api/reset")
def reset(payload: ResetIn) -> dict:
    if payload.session_id:
        session.reset(payload.session_id)
    return {"ok": True}

@app.post("/api/feedback")
def feedback(payload: FeedbackIn) -> dict:
    analytics.log_feedback(payload.session_id, payload.query_id, payload.is_positive)
    return {"ok": True}


# --------------------------------------------------------------------------- #
# admin authentication & helpers
# --------------------------------------------------------------------------- #

def _generate_admin_token(username: str) -> str:
    expiry = int(time.time()) + (24 * 3600)  # 24 hours
    secret = config.ADMIN_PASSWORD.encode("utf-8")
    payload = f"{username}:{expiry}".encode("utf-8")
    sig = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return f"{username}:{expiry}:{sig}"


def _verify_admin_token(token: str) -> bool:
    if not token or not config.ADMIN_PASSWORD:
        return False
    try:
        parts = token.split(":")
        if len(parts) != 3:
            return False
        username, expiry_str, sig = parts
        if not secrets.compare_digest(username, config.ADMIN_USERNAME):
            return False
        expiry = int(expiry_str)
        if time.time() > expiry:
            return False
        secret = config.ADMIN_PASSWORD.encode("utf-8")
        payload = f"{username}:{expiry}".encode("utf-8")
        expected_sig = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        return secrets.compare_digest(sig, expected_sig)
    except Exception:
        return False


def _require_admin(x_admin_key: str | None = None, authorization: str | None = None) -> None:
    token = ""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    elif x_admin_key:
        token = x_admin_key.strip()

    if not config.ADMIN_PASSWORD:
        raise HTTPException(status_code=503, detail="ADMIN_PASSWORD is not configured")

    if not token:
        raise HTTPException(status_code=401, detail="প্রশাসনিক অনুমোদন প্রয়োজন (Authentication required)")

    if _verify_admin_token(token):
        return

    if secrets.compare_digest(token, config.ADMIN_PASSWORD):
        return

    raise HTTPException(status_code=401, detail="ভুল ক্রেডেনশিয়াল বা সেশনের মেয়াদ শেষ (Invalid credentials or expired session)")


@app.post("/api/admin/login")
def admin_login(payload: AdminLoginIn) -> dict:
    if not config.ADMIN_PASSWORD:
        raise HTTPException(status_code=503, detail="ADMIN_PASSWORD is not configured")
    valid_user = secrets.compare_digest(payload.username, config.ADMIN_USERNAME)
    valid_pass = secrets.compare_digest(payload.password, config.ADMIN_PASSWORD)
    if not (valid_user and valid_pass):
        raise HTTPException(status_code=401, detail="ইউজারনেম বা পাসওয়ার্ড সঠিক নয়")

    token = _generate_admin_token(config.ADMIN_USERNAME)
    return {
        "ok": True,
        "token": token,
        "username": config.ADMIN_USERNAME,
        "expires_in": 86400,
    }


@app.get("/api/admin/verify")
def admin_verify(x_admin_key: str = Header(default=""),
                 authorization: str = Header(default="")) -> dict:
    _require_admin(x_admin_key, authorization)
    return {"ok": True, "username": config.ADMIN_USERNAME}


@app.post("/api/admin/propose")
def admin_propose(x_admin_key: str = Header(default=""),
                  authorization: str = Header(default=""),
                  body: dict = Body(default={})) -> dict:
    _require_admin(x_admin_key, authorization)
    return admin_mod.propose(body.get("text", ""))


@app.get("/api/admin/pending")
def admin_pending(x_admin_key: str = Header(default=""),
                  authorization: str = Header(default="")) -> dict:
    _require_admin(x_admin_key, authorization)
    return {"entries": admin_mod.pending(), "stats": kb.stats()}


@app.get("/api/admin/unverified")
def admin_unverified(x_admin_key: str = Header(default=""),
                     authorization: str = Header(default="")) -> dict:
    _require_admin(x_admin_key, authorization)
    return {"entries": admin_mod.unverified(), "stats": kb.stats()}


@app.get("/api/admin/stats")
def admin_stats(x_admin_key: str = Header(default=""),
                authorization: str = Header(default="")) -> dict:
    _require_admin(x_admin_key, authorization)
    return {"stats": analytics.get_stats()}


@app.post("/api/admin/approve")
def admin_approve(x_admin_key: str = Header(default=""),
                  authorization: str = Header(default=""),
                  body: dict = Body(default={})) -> dict:
    _require_admin(x_admin_key, authorization)
    return admin_mod.approve(body.get("entries", []), body.get("verified_on"))


# --------------------------------------------------------------------------- #
# static frontend (optional)
# --------------------------------------------------------------------------- #
# In the recommended setup the frontend is hosted separately (Cloudflare Pages,
# which never sleeps) and this server only answers the API. Serving web/ here too
# means a single-service deploy also works, with nothing else to configure.

if config.WEB_DIR.exists():
    @app.get("/admin")
    def admin_page() -> FileResponse:
        return FileResponse(config.WEB_DIR / "admin.html")

    app.mount("/", StaticFiles(directory=config.WEB_DIR, html=True), name="web")
