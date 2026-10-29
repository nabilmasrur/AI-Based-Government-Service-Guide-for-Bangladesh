"""Build the embedding index.

    python -m app.index

Run this once after editing data/*.json. The result is cached in
data/embeddings.npz so the server starts instantly and never re-embeds on boot.
"""
from __future__ import annotations

import sys

from . import config, kb, llm, retriever


def main() -> int:
    if not config.GEMINI_API_KEY:
        print("GEMINI_API_KEY is not set. Put it in .env first.")
        return 1

    entries = kb.load(force=True)
    stats = kb.stats()
    print(f"knowledge base: {stats['total']} entries "
          f"({stats['verified']} verified, {stats['unverified']} unverified)")
    if stats["unverified"]:
        print("  note: unverified entries are answered with a warning until you set "
              "verified_on in the JSON.")

    by_subtype: dict[str, int] = {}
    for entry in entries:
        key = f'{entry["domain"]}.{entry["subtype"]}'
        by_subtype[key] = by_subtype.get(key, 0) + 1
    missing = [
        f"{dom}.{sub}"
        for dom, meta in kb.TAXONOMY.items()
        for sub in meta["subtypes"]
        if f"{dom}.{sub}" not in by_subtype
    ]
    if missing:
        print("  sub-types with no entries yet: " + ", ".join(missing))

    try:
        retriever.build_index(verbose=True)
    except llm.LLMUnavailable as exc:
        print(f"embedding failed: {exc}")
        print("If the model name is rejected, try EMBED_MODEL=text-embedding-004 in .env")
        return 1

    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
