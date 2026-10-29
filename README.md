# সেবা সহায়ক — Government Service Assistant

An LLM-based conversational agent that answers citizens' questions about **passport**
and **driving licence** services in Bangladesh — which office, what documents, the fee,
how long it takes, and how much can be done online.

**CSE 3202 — Artificial Intelligence Sessional, BAUST.**
Unofficial academic project. It is not operated by any government authority.

---

## What makes it a goal-based agent, not a chatbot

The same word means different things at different points in a conversation. "পাসপোর্ট"
on the first turn is ambiguous — new, re-issue, correction, lost, MRP conversion — so the
agent asks. Once the sub-type is settled, the same word answers directly. The action
depends on how much of the goal ("give this citizen the correct, actionable procedure")
is already satisfied, not on the current input alone.

Three design decisions carry most of the project's weight:

**Facts are never generated.** Retrieval picks verified entries out of `data/*.json`;
the body of every answer is those entries copied verbatim. Gemini writes exactly one
connecting sentence and is explicitly forbidden from stating a fee, a deadline, a
document name or an office name. There is no path by which the model can invent a number.

**Below the confidence threshold the agent refuses.** If the best match scores under
`CONF_THRESHOLD` (0.62), it says it has no verified information instead of guessing.

**A clicked chip skips the LLM entirely.** The intent is already structured, so
`/api/action` goes straight to retrieval — roughly 10× faster than the free-text path.
`python -m eval.run_eval` prints both numbers side by side.

---

## Architecture

```
browser (static index.html)
   │  chip click  ─────────►  POST /api/action  ──►  retrieval  ──►  answer card   ~ 5 ms
   │  free text   ─────────►  POST /api/chat
   │                              │
   │                              ├─► Gemini · understand  (JSON: domain, subtype, slots)
   │                              ├─► slots missing?  ──►  clarifying question (no retrieval)
   │                              ├─► retrieval over the KB (cosine + keyword boost)
   │                              ├─► top score < 0.62?  ──►  refuse
   │                              └─► Gemini · one opening sentence  ──►  answer card
   └─ page load  ──────────►  GET /health   (wakes a sleeping free-tier server silently)
```

Retrieval is a cosine scan over a numpy matrix. With ~70 entries that takes well under a
millisecond, so an ANN index (Chroma, FAISS) would add a heavy dependency and a slower cold
start for no measurable gain. `app/retriever.py` is the only file that would change if you
ever swap it.

No database. The knowledge base is JSON in git, the vector index is a cached `.npz`, and
session state is an in-memory dict — the proposal scopes state to a single session and
there are no user accounts.

```
app/
  config.py     every tunable value
  kb.py         taxonomy (14 sub-types, 5 slots) + loading and validation
  llm.py        the only file that talks to Gemini
  retriever.py  filter → cosine → keyword boost
  agent.py      intent, slots, clarify-or-answer decision, card building
  texts.py      every user-facing string, bn + en
  prompts.py    the three prompts
  session.py    in-memory conversation state
  limits.py     per-IP rate limiting
  admin.py      draft entries → human approval → knowledge base
  main.py       FastAPI app
data/           passport.json · licence.json · sources.md
web/            index.html (the console UI) · admin.html · manifest.json
eval/           testset.json (40 queries) · run_eval.py
```

---

## Running it locally

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env                                   # then put your key in it
python -m app.index                                    # builds data/embeddings.npz
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>. API docs are at `/docs`, the admin panel at `/admin`.

Get a free Gemini key at <https://aistudio.google.com/apikey> — no card required.
If `gemini-embedding-001` is rejected, set `EMBED_MODEL=text-embedding-004` in `.env`.

Without a key the chip/sidebar path still works completely (it never calls Gemini), and
free-text questions fall back to keyword-only retrieval. Useful when the quota runs out
mid-demo.

---

## Evaluation

```bash
python -m eval.run_eval          # 40 queries, prints the metrics table
python -m eval.run_eval --fast   # fast-path timings only
python -m eval.run_eval --cat banglish
```

The test set covers clear Bangla, clear English, Banglish, bare ambiguous keywords,
multi-turn follow-ups, and deliberately out-of-scope questions (land records, NID) that
the agent should decline rather than answer. The printed table goes straight into the
report.

---

## Deploying

The frontend is a single static file and the backend is one FastAPI service. Hosting them
separately is what hides the free tier's cold start: the page loads instantly from a CDN
and fires a silent `/health` ping while the reader is still reading, so the server is
awake by the time they ask anything.

**Backend — Render (free).** Push to GitHub, then Render → New → Blueprint → pick the repo.
`render.yaml` already sets the build command, start command, health check path and the
Singapore region. Set `GEMINI_API_KEY` and `ADMIN_PASSWORD` in the dashboard, never in git.

Two things to know about the free plan: it spins down after 15 minutes idle and takes
about a minute to wake, and the filesystem is ephemeral, so entries added through the
admin panel must be committed to git or they vanish on the next redeploy. A cron ping
(cron-job.org → `/health`, every 10 minutes, **08:00–24:00 only**) keeps it awake for
about 480 hours a month, comfortably inside the 750-hour free allowance — pinging round
the clock would use 744 and leave no margin.

**Frontend — Cloudflare Pages or GitHub Pages (free, never sleeps).** Publish the `web/`
folder, then set `window.API_BASE` near the bottom of `index.html` to the Render URL
(no trailing slash) and set `ALLOWED_ORIGINS` on Render to the Pages origin.

**Single-service deploy** also works with nothing to configure: FastAPI serves `web/`
itself, so leave `API_BASE` as `""`.

**For the lab exam, run it on localhost.** No cold start, no hosting risk; the deployed
copy is the backup and the link for the report.

---

## The knowledge base

Every entry is one `(domain, subtype, field)` triple with both languages, its source URL
and a `verified_on` date:

```jsonc
{
  "id": "passport.new.documents",
  "domain": "passport", "subtype": "new", "field": "documents",
  "title_bn": "…", "title_en": "…",
  "content_bn": "…", "content_en": "…",
  "source_url": "https://www.epassport.gov.bd/",
  "verified_on": null,          // ← your job
  "keywords": ["কাগজ", "ki lagbe", "documents", …]
}
```

**All 35 seed entries ship with `verified_on: null`, and the UI marks them
"অযাচাইকৃত" with an amber warning.** That is deliberate. Open the official page, check
the entry against it, then set the date — the warning disappears on its own. Do not
skip this: the fee figures in the seed data came from a secondary source, and an
examiner who spots a wrong fee will spot it in the demo.

Splitting each service by `field` rather than storing one blob per sub-type is what makes
"fee koto" return only the fee, not the whole procedure. Keeping Bangla and English in the
same embedding text is what lets a Bangla question find an English entry and vice versa.

### Admin panel

Convert a PDF to `.txt` yourself, paste it into `/admin`, and Gemini proposes draft
entries. They land in `data/pending.json` — **not** in the knowledge base. You read them,
fix them, add the source URL and the verification date, and only then does approving write
them into `data/*.json` and re-embed. That human step is what keeps the "curated and
verified" claim true; auto-ingesting whatever a document happens to contain would quietly
break it.

---

## Publishing responsibly

If you put this online for real people:

- Keep the "অনানুষ্ঠানিক সহায়িকা" line and add that it is a student project. Do not use
  any government seal, emblem or logo, and keep `gov` and department names out of the domain.
- Fees and rules change. The `verified_on` field drives the staleness warning after
  `STALE_DAYS` (180) — leave it on.
- Leave `RATE_PER_MIN` and `RATE_PER_DAY` in place and do **not** enable billing on the
  Gemini key. Then a flood of traffic stops the service instead of sending you a bill.

---

## Notes for the viva

| Question | Answer |
|---|---|
| Goal-based, not simple reflex? | Same percept, different action depending on how much of the goal is satisfied — ask first, answer once the sub-type is known. |
| Why RAG? | Current Bangladeshi fees and document lists are not in the model's memory, or are stale. Grounding makes every fact traceable to one verified entry. |
| How is hallucination prevented? | Answer bodies are copied verbatim from KB entries; the model only writes one sentence and is forbidden from stating facts; below 0.62 the agent refuses. |
| Why no database? | 35 entries ≈ 200 KB held in RAM; the index is a cached matrix; session state is session-scoped. Firebase would add a network round-trip per read and nothing else. |
| Why not LangChain? | At this scale it adds dependencies and boot time without removing any real work, and every line here is explainable. |
| Why is a chip click so much faster? | Intent is already structured, so both Gemini calls are skipped. `run_eval --fast` shows the two means. |
| Environment properties | Partially observable, single-agent, sequential, static within a session, discrete, mostly deterministic (retrieval deterministic; the model's phrasing varies slightly). |

---

Sources: [epassport.gov.bd](https://www.epassport.gov.bd/) · [dip.gov.bd](https://dip.gov.bd/) ·
[brta.gov.bd](https://brta.gov.bd/). Seed fee figures are indicative and must be
re-checked against the official fee schedule before `verified_on` is set.
