# ResumeATS Pro (ATS Resume Fixer)

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
  metrics), keyword match (curated skills taxonomy + cosine similarity), grammar.
- **AI bullet rewrites** — batched, with per-rewrite provenance (`groq` / `guard_rejected`),
  retry variants, and a before/after improvement projection re-scored over the same
  bullet population.
- **Per-job tailored resume versions** — one stored version per (resume, job): rewrites
  applied into the real text, re-saved (upserted) after better analyses, exportable as
  DOCX with a job-specific filename.
- **DOCX export** — tailored bullets, keyword suggestions, ATS-safe formatting, glyph
  normalization (no tofu boxes).
- **Job descriptions** — paste manually or import from a URL (SSRF-guarded fetch;
  sites that block bots fail loudly with a "paste manually" message instead of saving
  junk). A deterministic parser extracts required/preferred skills, tools, seniority,
  and min years of experience on save.
- **Auth** — JWT-based accounts; everything you store is scoped to your user.

## Tech stack

| Layer    | Tech                                                        |
|----------|-------------------------------------------------------------|
| Backend  | Python 3.10+, FastAPI, SQLModel, SQLite                     |
| AI       | Groq (default) via the OpenAI-compatible client; OpenAI/Gemini optional |
| Parsing  | pdfplumber, PyMuPDF, python-docx, spaCy (optional), scikit-learn (optional) |
| Frontend | React 19, Vite, Tailwind CSS v4, TypeScript, bun            |

## Project layout

```
backend/
  app/
    auth/          # JWT auth (E1: JWT_SECRET required at startup)
    resume/        # models, service (analyze / versions / export), router
    jobs/          # job descriptions, scraper (SSRF guard), JD parser
    analyzer/      # ATS checker, bullet analyzer, keyword engine, AI rewriter, claim guard
    export/        # DOCX exporter
    parser/        # text extraction + section parsing
    common/        # shared skills taxonomy, exceptions
    config/        # settings, database
  tests/           # 168 unittest tests
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

Never commit the real `.env`. The repo's secret scan checks staged diffs.

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
# backend (from backend/) — 168 tests
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
   Dashboard as a DOCX whenever you need it.

## Status

See `ROADMAP.md` for the full prioritized backlog (46/77 done at last count) with a
change log of every batch, what the tests caught, and what remains.
