# LandIt (ATS Resume Fixer)

A local-first ATS resume inspection & optimization engine. Upload a resume, save a job
description, and get an honest analysis: ATS compatibility, bullet impact, keyword match —
plus AI rewrites that are stored, auditable, and never invent experience you don't have.

**Honesty is a feature, not a slogan:**

- Scores are computed, never faked. If a rewrite doesn't improve a bullet, the report says so
  (the "Projected After Tailoring" panel hides the delta chip at 0).
- The AI claim guard forbids inventing metrics, tools, or employers. Withheld rewrites are
  labeled as rejected, not silently swapped in.
- ATS compatibility is format-based; bullet rewrites never inflate it.
- Keyword scores are "N/A" without a job description — never a fake 100%.

## Features

- **Resume upload & parsing** — PDF/DOCX/TXT → contact, summary, skills, experience,
  projects, education, certifications (structured + raw).
- **Analysis against a saved job** — ATS compatibility checks, bullet impact (verbs,
  metrics), keyword match (curated skills taxonomy, weighted by required vs. preferred), grammar.
- **AI bullet rewrites** — batched, with per-rewrite provenance (`groq` / `guard_rejected`),
  retry variants, and a before/after improvement projection re-scored over the same
  bullet population.
- **AI summary & skills suggestions** — the professional summary is reworded under the
  same claim guard, and the skills section may only be reordered/regrouped from skills
  you already list. Reviewed separately from bullets; only accepted text reaches an export.
- **Per-job tailored resume versions** — one stored version per (resume, job): rewrites
  applied into the real text, re-saved (upserted) after better analyses, exportable as
  DOCX or PDF with a job-specific filename.
- **DOCX & PDF export** — tailored bullets, keyword suggestions, ATS-safe single-column
  formatting, glyph normalization (no tofu boxes).
- **Job descriptions** — paste manually or import from a URL (SSRF-guarded fetch;
  sites that block bots fail loudly with a "paste manually" message instead of saving
  junk). A deterministic parser extracts required/preferred skills, tools, seniority,
  and min years of experience on save.
- **Application tracker** — one status per saved job (saved → applied → interview →
  offer / rejected), an optional real applied date, and private notes. Filter by status;
  dates are never invented, and tracker notes never reach the AI provider.
- **Cover letters** — generated from the resume's real facts and the saved job, with a
  local preview of exactly what would be sent. Email, phone, location, and links are
  excluded; a guard rejects invented numbers, skills, and placeholders, retries once,
  and flags anything it cannot verify instead of silently calling it safe.
- **Auth** — JWT-based accounts; everything you store is scoped to your user.
  Login is rate-limited, and sign-ups can be closed on a local instance.
- **Privacy controls** — AI rewriting is opt-in per browser (and can be disabled
  server-wide); the UI states exactly what would be sent, and the rest of the
  analysis always runs locally.

## Tech stack

| Layer    | Tech                                                        |
|----------|-------------------------------------------------------------|
| Backend  | Python 3.10+, FastAPI, SQLModel, SQLite                     |
| AI       | Groq (default) via the OpenAI-compatible client; OpenAI/Gemini optional |
| Parsing  | pdfplumber, PyMuPDF, python-docx, spaCy (optional)          |
| Export   | python-docx (DOCX), ReportLab (PDF)                         |
| Frontend | React 19, Vite, Tailwind CSS v4, TypeScript, bun            |

## Project layout

```
backend/
  app/
    auth/          # JWT auth (E1: JWT_SECRET required at startup)
    resume/        # models, service (analyze / versions / export), router
    jobs/          # job descriptions, scraper (SSRF guard), JD parser
    cover_letter/  # D8: source selection, availability gate, guard, generation
    analyzer/      # ATS checker, bullet analyzer, keyword engine, AI rewriter, claim guard
    export/        # DOCX + PDF exporters (shared content rules)
    parser/        # text extraction + section parsing
    common/        # shared skills taxonomy, exceptions
    config/        # settings, database, Alembic runner
  migrations/      # versioned schema migrations (baseline + tracker)
  alembic.ini
  tests/           # 454 unittest tests
frontend/
  src/
    pages/         # Landing, Auth, Dashboard, Upload, Analysis, JobDescriptions, Settings
    api.ts         # typed API client
    components/
ROADMAP.md         # prioritized backlog with change log (77 items, tracked honestly)
```

## Setup

### Backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
# optional spaCy model (enables "extra terms" suggestions):
.\venv\Scripts\python.exe -m spacy download en_core_web_sm

copy .env.example .env   # then fill in the values
```

`.env` keys (see `.env.example` for all of them):

- `GROQ_API_KEY` — AI rewriting (get one at console.groq.com). Providers: `groq` (default),
  plus OpenAI/Gemini-compatible options via `AI_PROVIDER` / `AI_MODEL` / `AI_BASE_URL`.
- `JWT_SECRET` — **required**; the server refuses to start without it.
  Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- `CORS_ORIGINS` — frontend origins allowed to call the API.
- `DATABASE_URL` — SQLite path (defaults to `backend/ats_resume_fixer.db`).
- `AI_REWRITING_ENABLED` — set to `false` to keep every resume on this machine
  (no AI rewriting; the rest of the analysis still runs). Users can also switch
  AI rewriting off per browser on the Upload/Settings pages.
- `ALLOW_REGISTRATION` — set to `false` to close sign-ups after creating your account.

Never commit the real `.env`. The repo's secret scan checks staged diffs.

### Database migrations

The schema is versioned with Alembic. `app.main` runs `alembic upgrade head` on
startup, so a normal `uvicorn` launch is enough. An existing database created
before Alembic is adopted automatically: it is stamped at the baseline revision
(`0001_initial`, which matches that schema) and then upgraded. Data is preserved.

```powershell
# from backend/
.\venv\Scripts\python.exe -m alembic current   # show the applied revision
.\venv\Scripts\python.exe -m alembic check     # fail if models drifted from migrations
.\venv\Scripts\python.exe -m alembic revision --autogenerate -m "describe change"
.\venv\Scripts\python.exe -m alembic upgrade head
```

Review every autogenerated migration before committing it — Alembic cannot infer
data backfills or intent. Back up `ats_resume_fixer.db` before a schema change.

### Frontend

```powershell
cd frontend
bun install
```

The frontend talks to `VITE_API_URL` (default `http://127.0.0.1:8000`).

## Run

```powershell
# backend (from backend/)
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# frontend (from frontend/)
bun run dev -- --port 8443 --strictPort
```

- API: http://127.0.0.1:8000 · Swagger docs: http://127.0.0.1:8000/docs
- App: http://localhost:8443

## Tests

```powershell
# backend (from backend/) - 454 tests
$env:PYTHONUTF8="1"; .\venv\Scripts\python.exe -m unittest discover -s tests -t .

# frontend — type-check + production build
bun run build
```

## Typical flow

1. **Upload** a resume → it's parsed into sections.
2. **Job Descriptions** → paste a JD (or import from a URL) — skills/seniority are
   extracted on save.
3. **Analyze** the resume against that job → scores, flagged bullets, AI rewrites with
   provenance, and a projected after-tailoring score.
4. **Save as version** → the tailored text is stored per job; export it from the
   Dashboard as a DOCX or PDF whenever you need it.
5. **Track the application** → set saved/applied/interview/offer/rejected, record the
   real applied date, and keep private notes on the Jobs page.
6. **Write the cover letter** → on the Analysis page, preview the exact facts that would
   be sent, pick a tone, and generate. Edit the draft before copying or downloading it.

## Status

See `ROADMAP.md` for the full prioritized backlog (77/77 done at last count) with a
change log of every batch, what the tests caught, and what remains.
