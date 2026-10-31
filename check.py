"""Diagnose the Gemini connection.

    python check.py

Prints exactly where the chain breaks: the key, the chat model, JSON mode, the
embedding model, and one real question through the agent.
"""
from __future__ import annotations

import sys
import traceback


def line(title):
    print("\n" + "-" * 62)
    print(title)
    print("-" * 62)


def main() -> int:
    from app import config

    line("1. .env")
    key = config.GEMINI_API_KEY
    if not key:
        print("  GEMINI_API_KEY is EMPTY. Open .env and put the key after the = sign.")
        return 1
    print(f"  key loaded: {key[:6]}…{key[-4:]}  (length {len(key)})")
    print(f"  chat model : {config.CHAT_MODEL}")
    print(f"  embed model: {config.EMBED_MODEL}")
    print(f"  admin credentials : user='{config.ADMIN_USERNAME}' password={'yes' if config.ADMIN_PASSWORD else 'NO — /admin will refuse'}")

    line("2. Which models does this key actually have?")
    try:
        from google import genai
        client = genai.Client(api_key=key)
        names = []
        for m in client.models.list():
            actions = getattr(m, "supported_actions", None) or []
            names.append((m.name.replace("models/", ""), list(actions)))
        chat = sorted(n for n, a in names if "generateContent" in a)
        emb = sorted(n for n, a in names if "embedContent" in a)
        print(f"  chat-capable   ({len(chat)}): " + ", ".join(chat[:12]) + (" …" if len(chat) > 12 else ""))
        print(f"  embed-capable  ({len(emb)}): " + ", ".join(emb[:8]))
        if chat and config.CHAT_MODEL not in chat:
            print(f"\n  !! '{config.CHAT_MODEL}' is NOT in the list above.")
            print(f"     Put one of these in .env as CHAT_MODEL, e.g. CHAT_MODEL={chat[0]}")
    except Exception:
        print("  could not list models:")
        traceback.print_exc(limit=2)

    line("3. Plain text generation")
    try:
        from app import llm
        out = llm.generate("You are terse.", "Reply with exactly: OK")
        print(f"  reply: {out[:80]!r}")
    except Exception:
        print("  FAILED:")
        traceback.print_exc(limit=3)
        return 1

    line("4. JSON mode (this is what the agent needs)")
    try:
        from app import llm
        data = llm.generate_json(
            'Reply with JSON only: {"domain": "passport", "ok": true}',
            "Give the JSON.")
        print(f"  parsed: {data}")
        if not data:
            print("  !! Empty — the model answered but not with valid JSON.")
    except Exception:
        print("  FAILED:")
        traceback.print_exc(limit=3)
        return 1

    line("5. Embedding a query")
    try:
        from app import llm
        vec = llm.embed(["notun passport korte ki lagbe"], task="RETRIEVAL_QUERY")[0]
        print(f"  vector length: {len(vec)}")
    except Exception:
        print("  FAILED:")
        traceback.print_exc(limit=3)
        return 1

    line("6. A real question through the agent")
    try:
        from app import agent, session
        state = session.get("diagnostic")
        res = agent.handle_message(state, "notun passport korte ki ki lagbe?", "bn")
        tr = res.get("trace") or {}
        print(f"  type      : {res['type']}   (expected: answer)")
        print(f"  subtype   : {tr.get('subtype')}   (expected: new)")
        print(f"  confidence: {tr.get('conf')}   threshold {tr.get('threshold')}")
        print(f"  top hits  : {tr.get('hits')}")
        print(f"  ms        : {res.get('ms')}")
        if res["type"] != "answer":
            print("\n  !! Not an answer. Look at the warnings printed above this block.")
    except Exception:
        print("  FAILED:")
        traceback.print_exc(limit=4)
        return 1

    print("\nAll checks finished.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
