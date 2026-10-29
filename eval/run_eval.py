"""Run the 40-query test set and print the metrics table for the report.

    python -m eval.run_eval              # whole set
    python -m eval.run_eval --cat banglish
    python -m eval.run_eval --fast       # chip/fast-path timings only

The printed table goes straight into the report. Without numbers, the performance
measures in the proposal are just claims.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import agent, config, session  # noqa: E402

TESTSET = Path(__file__).parent / "testset.json"
CATS = ["clear_bn", "clear_en", "banglish", "ambiguous", "followup", "smalltalk", "out_scope"]


def run_case(case: dict) -> dict:
    state = session.get(f"eval-{case['id']}")
    lang = "en" if case["cat"] in ("clear_en",) or case["q"].isascii() else "bn"

    t0 = time.time()
    res = agent.handle_message(state, case["q"], lang)
    if case.get("then"):
        res = agent.handle_message(state, case["then"], lang)
    elapsed = (time.time() - t0) * 1000

    trace = res.get("trace") or {}
    got_type = res.get("type")
    want_type = case["expect"]

    subtype_ok = (trace.get("subtype") == case["subtype"]) if case["subtype"] else None
    session.reset(f"eval-{case['id']}")

    return {
        "id": case["id"], "cat": case["cat"], "q": case["q"],
        "want": want_type, "got": got_type, "type_ok": got_type == want_type,
        "subtype_want": case["subtype"], "subtype_got": trace.get("subtype"),
        "subtype_ok": subtype_ok,
        "conf": trace.get("conf", 0.0), "ms": round(elapsed),
    }


def run_fastpath() -> list[dict]:
    """Same answers reached by clicking chips — the comparison that justifies
    skipping the LLM when intent is already structured."""
    actions = [
        ("passport.new.documents", {"domain": "passport", "subtype": "new", "field": "documents"}),
        ("passport.new.timeline", {"domain": "passport", "subtype": "new", "field": "timeline"}),
        ("licence.learner.documents", {"domain": "licence", "subtype": "learner", "field": "documents"}),
        ("licence.exam.note", {"domain": "licence", "subtype": "exam", "field": "note"}),
        ("passport.lost.documents", {"domain": "passport", "subtype": "lost", "field": "documents"}),
    ]
    rows = []
    for name, action in actions:
        state = session.get(f"fast-{name}")
        t0 = time.time()
        res = agent.handle_action(state, action, "bn")
        rows.append({"name": name, "type": res["type"], "ms": round((time.time() - t0) * 1000)})
        session.reset(f"fast-{name}")
    return rows


def table(rows: list[list], headers: list[str]) -> str:
    widths = [max(len(str(r[i])) for r in [headers] + rows) for i in range(len(headers))]
    line = "  ".join("-" * w for w in widths)
    out = ["  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers)), line]
    out += ["  ".join(str(r[i]).ljust(widths[i]) for i in range(len(headers))) for r in rows]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cat", choices=CATS)
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    if args.fast:
        rows = run_fastpath()
        print("\nFAST PATH (chip click — no Gemini call)\n")
        print(table([[r["name"], r["type"], r["ms"]] for r in rows], ["case", "type", "ms"]))
        print(f"\nmean {statistics.mean(r['ms'] for r in rows):.0f} ms\n")
        return 0

    cases = json.loads(TESTSET.read_text(encoding="utf-8"))
    if args.cat:
        cases = [c for c in cases if c["cat"] == args.cat]

    print(f"running {len(cases)} cases · model={config.CHAT_MODEL} · threshold={config.CONF_THRESHOLD}\n")
    results = []
    for case in cases:
        row = run_case(case)
        results.append(row)
        mark = "ok " if row["type_ok"] else "MISS"
        print(f"  {mark} #{row['id']:>2} [{row['cat']:<9}] {row['ms']:>5}ms  "
              f"want={row['want']:<8} got={row['got']:<8} {row['q'][:42]}")
        if args.verbose and not row["type_ok"]:
            print(f"       subtype want={row['subtype_want']} got={row['subtype_got']} conf={row['conf']}")

    # ---- metrics -----------------------------------------------------------
    def pct(num, den):
        return f"{100 * num / den:.1f}%" if den else "—"

    subtype_rows = [r for r in results if r["subtype_ok"] is not None]
    subtype_acc = sum(1 for r in subtype_rows if r["subtype_ok"])

    amb = [r for r in results if r["want"] == "clarify"]
    amb_ok = sum(1 for r in amb if r["got"] == "clarify")
    clear = [r for r in results if r["want"] == "answer"]
    clear_ok = sum(1 for r in clear if r["got"] == "answer")

    scope = [r for r in results if r["want"] == "no_info"]
    scope_ok = sum(1 for r in scope if r["got"] == "no_info")

    print("\n" + "=" * 68)
    print("METRICS\n")
    metrics = [
        ["Sub-type accuracy", pct(subtype_acc, len(subtype_rows)), f"{subtype_acc}/{len(subtype_rows)}"],
        ["Clarification recall (ambiguous asked)", pct(amb_ok, len(amb)), f"{amb_ok}/{len(amb)}"],
        ["Clarification precision (clear not asked)", pct(clear_ok, len(clear)), f"{clear_ok}/{len(clear)}"],
        ["Out-of-scope refusal", pct(scope_ok, len(scope)), f"{scope_ok}/{len(scope)}"],
        ["Overall behaviour correct", pct(sum(1 for r in results if r["type_ok"]), len(results)),
         f"{sum(1 for r in results if r['type_ok'])}/{len(results)}"],
    ]
    print(table(metrics, ["metric", "score", "n"]))

    print("\nBY CATEGORY\n")
    cat_rows = []
    for cat in CATS:
        rows = [r for r in results if r["cat"] == cat]
        if not rows:
            continue
        cat_rows.append([cat, len(rows), pct(sum(1 for r in rows if r["type_ok"]), len(rows)),
                         f"{statistics.mean(r['ms'] for r in rows):.0f}"])
    print(table(cat_rows, ["category", "n", "correct", "mean ms"]))

    fast = run_fastpath()
    print("\nRESPONSE TIME BY PATH\n")
    print(table([
        ["full path (free text · 2 Gemini calls)", f"{statistics.mean(r['ms'] for r in results):.0f} ms"],
        ["fast path (chip click · no LLM)", f"{statistics.mean(r['ms'] for r in fast):.0f} ms"],
    ], ["path", "mean"]))
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
