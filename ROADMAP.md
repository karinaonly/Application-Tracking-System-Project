# ATS Resume Fixer: Fix & Improvement Tracker

Snapshot reviewed: full source tree (backend + frontend), 2026-10-23. Original snapshot was `setup_project_latest.py` (60 files, FastAPI + SQLModel backend, React/Vite frontend).

**How to use:** tick the box (`[x]`) when done, and add a line to the *Change Log* at the bottom with the date and what changed.

**Verification:** ✅ = implemented and unit-tested · 🟡 = implemented but not verified end-to-end · 🟢 = confirmed working in the running app with real data. An item is not truly done until it is 🟢.

**Priority:** `P0` = fix first (results are wrong or misleading) · `P1` = core features · `P2` = important polish · `P3` = nice to have

**Total items: 76** (61 original + 15 added 2026-10-23)

---

## Suggested Order

1. Section A (bugs) and Section B (scoring honesty). Everything else depends on these.
2. Section C (AI rewriter safety).
3. Section D items D1 to D3 (tailoring and before/after score).
4. Section F (hygiene) alongside the above.
5. The rest, as time allows.

---

## A. Confirmed Bugs

- [x] **A1 (P0): Weak-verb false positives** · `analyzer/bullet_analyzer.py`
  `any(w in bullet.lower()[:20] for w in WEAK_VERBS)` is a substring match. "Candidate…" is flagged weak (contains "did"), "Shadow mode…" (contains "had"), "Mademoiselle…" (contains "made").
  *Fix:* use word-boundary regex and only check the start of the bullet.
  ✅ *Done 2026-09-28: Word-boundary match, only at start of bullet.*

- [ ] **A2 (P1): Strong-verb list too small** · `common/constants.py`, `bullet_analyzer.py`
  "Wrote", "Maintained", and similar verbs return `missing`.
  *Fix:* expand the list, or lemmatize the first word with spaCy ("wrote" → "write").

- [ ] **A3 (P0): Missing keywords never reach the exported resume** · `export/docx_exporter.py`
  `export_tailored` accepts `missing_keywords`, but `_add_skills` ignores them and `_filter_keywords` is never called.
  *Fix:* call `_filter_keywords`, and append the results to the Skills section. Only add skills the user confirms they actually have.

- [ ] **A4 (P0 — raised from P1): Exporter silently overwrites your resume title with the job posting's title** · `export/docx_exporter.py` (`_add_header`, ~line 183)
  Found 2026-09-30 testing a real export: `clean_role = target_role.strip().upper() if target_role else "FULL STACK DEVELOPER"`. Every export replaces your actual professional title (e.g. "Full Stack Developer") with the attached job's title, uppercased, no confirmation. Confirmed in a real export: "FULL STACK DEVELOPER" became "FRONTEND APPRENTICE" for a job titled that way, even though the bullets underneath stayed backend/full-stack. The `"FULL STACK DEVELOPER"` fallback is also hardcoded to this one resume (see original A4 scope below) — a different user with no job attached would get the wrong title too.
  *Why it matters:* this isn't cosmetic — a resume claiming a title you didn't choose, especially one that doesn't match the content underneath it, can read as dishonest or simply confusing to a reviewer.
  *Fix options (needs a product decision, not just a patch):* (a) never auto-replace the title — always show the resume's own title; (b) only replace it if the user explicitly opts in per export (e.g. a checkbox "Match title to this job"); (c) show both, e.g. "Full Stack Developer — applying as Frontend Apprentice" so nothing is misrepresented. Also: `.replace("Aspiring ", "")` on the summary, and `LABEL_RE` targeting this resume's layout ("Senior High", "Capstone") are the original, narrower scope of this item and still need the generic fix below.
  *Fix (original, narrower scope):* remove the hardcoded replace, and make label filtering configurable or generic.

- [ ] **A5 (P2): Aggressive rewrite is never used** · `export/docx_exporter.py`
  `_apply_rewrites` only reads `ai_output` (the moderate version).
  *Fix:* let the user choose moderate or aggressive per bullet.

- [ ] **A6 (P1): Upload path traversal risk** · `resume/service.py`
  The raw client `filename` is used in the file path.
  *Fix:* sanitize the filename, or store as `{uuid}{ext}`.

- [ ] **A7 (P1): Upload limits not enforced** · `resume/service.py`, `config/settings.py`
  `max_file_size_mb` and `allowed_extensions` exist but are never checked.
  *Fix:* validate extension and size before processing, and return clear 400/413 errors.

- [ ] **A8 (P2): Grammar checker skips most words** · `analyzer/grammar_checker.py`
  It filters with `w.isalpha()` *before* stripping punctuation, so words like "system," or "(API)" are skipped. It also caps output at 10 typos.
  *Fix:* strip punctuation first, ignore known tech terms, and raise or remove the cap.

- [ ] **A9 (P2): Metric regex misses common metrics** · `analyzer/bullet_analyzer.py`
  Single-digit numbers ("team of 5", "2 projects") aren't counted, and version numbers like "Python 3.11" count as metrics.
  *Fix:* refine the regex to distinguish real impact metrics from versions and dates.
  ✅ *Done 2026-09-29 (Copilot, verified by Claude): rewrote `_extract_metrics` with money/%/number regexes, tech-version and year exclusion, and a quantity-noun check for single digits ("5-member team"). Verified against GPAs, date ranges, Next.js/Node version numbers — all correctly excluded. New minor gap found: phone numbers inside a bullet are NOT excluded, logged as A11.*
  🔴 *Reopened 2026-10-23: decimals and unit-scaled metrics are still missed — "Cut latency by 2.5x", "Reduced build time to 3.5 hours", "Served 1.5 million users" all return no metric. Tracked as A16.*

- [x] **A10 (P0): False pronoun warning from PDF pipes read as "I"** · `analyzer/ats_checker.py`
  PDF extraction turns the "|" separators in contact lines (e.g. "Internship | Imus") into the letter "I", so a resume with zero real pronouns was flagged with a warning and lost 10 score points.
  *Fix:* ignore lines containing an email, URL, or phone number, and only count a capital "I" when followed by a lowercase word or as a contraction (I'm, I've, I'll, I'd).
  ✅ *Done 2026-09-29 (Copilot, verified by Claude): confirmed the fix reads the real `sections["contact"]["raw"]` key your parser produces. Verified against "Phase I", "Level I Support", "I.T. department" (correctly ignored) and real pronoun sentences (correctly counted, and the >2 threshold still works at exactly 2 and 3 occurrences).*

- [ ] **A11 (P3): Phone numbers inside a bullet count as metrics** · `analyzer/bullet_analyzer.py`
  Found during verification of A9. A bullet like "Reachable at +63 917 234 5678" produces 4 false "metrics" (63, 917, 234, 5678).
  *Fix:* exclude numbers matching a phone-like pattern from `_extract_metrics`, the same approach `ats_checker.py`'s `_CONTACT_LINE_RE` already uses.

- [x] **A12 (P0): AI rewriting is silently disabled by the key-prefix check** · `analyzer/ai_rewriter.py`, `auth/router.py`
  Found 2026-10-23. Groq keys start with `gsk_` (underscore), but `valid_key` requires `startswith("gsk-")` (hyphen). `AIRewriter().client` is `None`, so every bullet returns `source="fallback"` and no AI feature runs. `/auth/ai-status` still reports the AI as configured, so the UI can't tell either. The `OpenAI(...)` client is also built with no timeout.
  *Fix:* accept both prefixes (or validate by shape rather than prefix), have `/auth/ai-status` call the same check instead of duplicating it, set `timeout=` on the client, and add a live-key smoke test as the exit criterion for every C item.
  ✅ *Done 2026-10-26 (🟢 verified with real data): added a shared `resolve_ai_config` that validates the key by shape, wired both `AIRewriter` and `/auth/ai-status` to it, and passed a timeout to the client. A real resume + job analysis produced 6/6 Groq rewrites with zero fallbacks. Added `tests/test_ai_config.py` and `scripts/ai_smoke_test.py`.*

- [x] **A13 (P0): Exporter splits CamelCase and corrupts tech names** · `export/docx_exporter.py`
  Found 2026-10-23 in a real export: `JavaScript` → `"Java Script"`, `PostgreSQL` → `"Postgre SQL"`, `MongoDB` → `"Mongo DB"`, `GitHub` → `"Git Hub"`.
  *Fix:* replace the generic CamelCase splitter with an allowlist of canonical tech spellings; only split words that aren't known terms.
  ✅ *Done 2026-10-26: the splitter now protects canonical terms derived from `common/skills.py` (plus LinkedIn, DevOps, OpenAPI, WordPress, SharePoint) and only splits unknown joins such as `WordWord`. Added `tests/test_docx_exporter.py`. A real export of your parsed resume keeps GraphQL, JavaScript, TypeScript, PostgreSQL, Node.js and Next.js intact with no `"Graph QL"`-style splits.*

- [x] **A14 (P1): Exporter drops content it can't place** · `export/docx_exporter.py`
  Found 2026-10-23: GitHub is discarded whenever LinkedIn is also present, and certifications and languages are never emitted at all.
  *Fix:* give each contact channel its own slot, and add certifications/languages sections when the parsed resume has them.
  ✅ *Done 2026-10-26: LinkedIn and GitHub are now independent header slots, and `CERTIFICATIONS` / `LANGUAGES` render from `sections["certifications"]["raw"]` and `sections["languages"]["raw"]`. Covered by `tests/test_docx_exporter.py`. Your current resume only has GitHub and has no certifications/languages sections, so the new sections are fixture-tested until a real resume contains them.*

- [ ] **A15 (P0): Section parser mis-reads common resume layouts** · `parser/section_parser.py`
  Found 2026-10-23, verified against real inputs:
  - `"University of the Philippines"` → `"of the Philippines"`
  - A contact location can swallow the name and the following newline.
  - A full LinkedIn URL is duplicated into the portfolio field.
  - `"LinkedIn: linkedin.com/in/jane"` parses incorrectly.
  - An inline `"Skills: Python, JavaScript, React"` header is not detected.
  - A single-line contact containing an email becomes the whole line as `name`.
  *Fix:* anchor school extraction on the degree line, parse contact lines field-by-field, detect inline section headers, and never treat a line containing an email/phone as a name. Add fixtures (ties to F4/F12).

- [ ] **A16 (P1): Decimal and unit-scaled metrics are not counted** · `analyzer/bullet_analyzer.py`
  Found 2026-10-23 (extends A9/A11): `"Cut latency by 2.5x"`, `"Reduced build time to 3.5 hours"`, `"Served 1.5 million users"` all return no metric.
  *Fix:* allow decimals and magnitude words (million/thousand) in the metric regex, while keeping the version/year exclusions.

- [ ] **A17 (P1): Analyze accepts a `job_id` without an ownership check** · `resume/service.py`, `resume/router.py`
  Found 2026-10-23: a user can analyze against another user's job by guessing an id.
  *Fix:* verify `job.user_id == current_user.id` before use, and return 404 otherwise. (Depends on the E3 decision — moot if auth is removed.)

- [ ] **A18 (P1): Export uses the latest analysis, not the selected one** · `resume/service.py`, `frontend/src/pages/Upload.tsx`
  Found 2026-10-23: viewing analysis A and exporting can produce analysis B, because export resolves "most recent" server-side.
  *Fix:* accept an `analysis_id` on export, or export from a stored per-job version (ties to D3).

- [x] **A19 (P1): Upload page highlights a job but submits none** · `frontend/src/pages/Upload.tsx`
  Found 2026-10-23: the selected job card is visual only — `analyze` is called without `job_id`, so the highlighted job is not the one used.
  *Fix:* send the selected job id, and preselect it when arriving from a job (ties to D6).
  ✅ *Done 2026-10-26: `activeJobId` (the selected job, falling back to the first job) is sent to `analyzeResume`, used for the saved resume metadata, and drives the highlighted/checked job card. Also fixed the stale `ResumeSummary.file_type` reference that made `tsc` fail. `tsc --noEmit` and `bun run build` pass; a UI click-through is still needed to mark this 🟢.*

- [ ] **A20 (P2): `addToast` is recreated every render** · `frontend/src/App.tsx`
  Found 2026-10-23: it is passed into effect dependency arrays, so effects can re-run and re-fetch or re-toast.
  *Fix:* wrap in `useCallback`, or expose it through a stable ref/context.

- [ ] **A21 (P2): Settings saves are fake** · `frontend/src/pages/Settings.tsx`
  Found 2026-10-23: profile and password buttons report success without calling the API; plan and initials are hardcoded.
  *Fix:* wire them to real endpoints, or remove the controls. Also fix the Groq-incompatible provider message.

---

## B. Scoring Logic

- [x] **B1 (P0): No job description gives a fake 100 keyword score** · `resume/service.py`
  The default `{"score": 100.0}` is folded into the overall score.
  *Fix:* return `None` and rescale the overall weights (or show "N/A" in the UI).
  ✅ *Done 2026-09-28: New `analyzer/scoring.py`; unavailable parts are dropped and weights rescaled.*

- [x] **B2 (P0): Zero bullets gives a bullet score of 100** · `analyzer/bullet_analyzer.py`
  A resume where parsing failed looks perfect.
  *Fix:* return 0 or `None`, and add a warning "No bullets detected".
  ✅ *Done 2026-09-28: Returns `score: None` + warning when no bullets parsed.*

- [x] **B3 (P0): Keyword extraction quality** · `analyzer/keyword_engine.py`
  Returns `list(set)[:30]` (random order, drops terms) and includes junk noun chunks ("the team", "our company").
  *Fix:* deterministic ordering, stopword and pronoun filtering, and a ranked keyword list.
  ✅ *Done 2026-09-28: Deterministic ranking by JD frequency; noun-chunk junk moved to a separate, unscored list.*

- [x] **B4 (P0): No skills taxonomy** · `common/constants.py`
  Hard skills (Python, React, PostgreSQL…) compete with generic phrases.
  *Fix:* add a curated skills list (or a skills dataset) and match against it first.
  ✅ *Done 2026-09-28: New `common/skills.py` (~120 skills).*

- [x] **B5 (P0): Substring matching creates false matches** · `analyzer/keyword_engine.py`
  `s.lower() in resume_lower` means "Java" matches "JavaScript".
  *Fix:* use word-boundary matching (careful with terms like `C++`, `.NET`, `CI/CD`).
  ✅ *Done 2026-09-28: Word-boundary regex; handles C++, C#, .NET, CI/CD, Node.js.*

- [x] **B6 (P1): No synonym or alias handling** · `analyzer/keyword_engine.py`
  "k8s" vs "Kubernetes", "CI/CD" vs "continuous integration", "JS" vs "JavaScript".
  *Fix:* add an alias map and normalize both sides before comparing.
  ✅ *Done 2026-09-28: Alias map added (k8s, postgres, js, ci/cd...). Extend over time.*

- [ ] **B7 (P1): TF-IDF over two documents is noisy** · `analyzer/keyword_engine.py`
  IDF carries almost no signal with only two documents.
  *Fix:* switch to local embeddings (e.g. a small sentence-transformers model) for the similarity score.

- [ ] **B8 (P2): Separate required vs. preferred skills** · `analyzer/keyword_engine.py`
  All JD keywords are weighted equally.
  *Fix:* weight "required / must have" higher than "nice to have".

- [ ] **B9 (P2): ATS checks are shallow** · `analyzer/ats_checker.py`, `parser/text_extractor.py`
  `has_headers` and `has_footers` are DOCX-only, so PDFs always pass. There are no checks for multi-column layouts, images or icons, unusual fonts, missing dates, or file naming.
  *Fix:* add PDF layout checks (column detection, image count) and more rules.

- [ ] **B10 (P3): Revisit the overall score weights** · `resume/service.py`
  The 35/35/30 split is arbitrary, and the grammar score is computed but not used in the overall score.
  *Fix:* decide on and document the weights, and include grammar if it's meaningful.

- [x] **B11 (P1): Soft-skill vocabulary for junior job postings** · `common/skills.py`, `analyzer/keyword_engine.py`
  A junior job description with no tech stack ("team player", "coordinate with clients", "teach classes") only matched 1 recognized skill, so the keyword score came back N/A.
  *Fix:* a `SOFT_SKILL_GROUPS` taxonomy (29 groups with aliases), wired into the same matcher as `HARD_SKILLS`.
  ✅ *Done 2026-09-29 (Copilot, verified by Claude): verified against the real Junior Software Engineer / NCR posting from this conversation — previously only "Communication" was recognized, now Teamwork, Continuous Learning, Client Coordination, and Knowledge Sharing are too. Confirmed no canonical name ever appears twice (e.g. "Team Player" never shows alongside "Teamwork") across all 39 tests.*

---

## C. AI Rewriter

> ✅ **2026-10-26: A12 is fixed and verified live.** `AIRewriter` now builds its client from the shared `resolve_ai_config`; a real resume + job analysis produced 6/6 Groq rewrites with no fallbacks, and C3 is re-verified. The remaining C items stay 🟡 until each is exercised end-to-end.

- [x] **C1 (P0): Prompt pushes the model to invent metrics** · `analyzer/ai_rewriter.py`
  "quantifiable metric" leads to fabricated numbers you can't defend in an interview.
  *Fix:* forbid adding figures, tools, claims, and placeholders not in the original; rewrite bullets without real metrics qualitatively.
  ✅ *Done 2026-10-03: AI now uses qualitative wording when a metric is missing. The backend rejects any model response containing bracketed placeholder text and preserves the original bullet, so `[X%]` cannot reach an export. Focused tests cover the prompt and fallback guard.*

- [x] **C2 (P1): Rewrites don't use JD keywords** · `analyzer/ai_rewriter.py`
  The prompt only gets the bullet and the role title.
  *Fix:* pass matched and missing JD keywords and instruct the model to use only ones that fit the real work.
  ✅ *Done 2026-09-30: `matched_keywords`/`missing_keywords` from `kw_engine.analyze()` are now passed into the rewrite prompt, with an explicit rule that a missing keyword may only be used if the bullet already reflects that skill. Verified with `test_missing_keywords_included_in_user_prompt`.*

- [x] **C3 (P1): Fragile response parsing** · `analyzer/ai_rewriter.py`
  Parses "Moderate:/Aggressive:" with regex.
  *Fix:* request JSON output and validate it.
  ✅ *Done 2026-09-30: Switched from regex label-parsing (`Moderate:`/`Aggressive:`) to a validated JSON array response. Handles markdown-fenced JSON, `{"results": [...]}`-wrapped responses, short arrays, and malformed items, falling back to the original bullet per-entry rather than failing the whole batch. 8 tests cover this directly (`SuccessfulRewriteTests`, `RobustnessTests`).*
  🟢 *Verified 2026-10-26 with real data: JSON mode is sent only for the `openai` provider; `groq` and `gemini` rely on the prompt and the fence-stripping parser. Both provider tests pass, and a real resume + job analysis returned 6/6 Groq rewrites with zero fallbacks.*

- [x] **C4 (P1): Only 3 bullets are rewritten, sequentially** · `resume/service.py`
  The request blocks on up to 3 sequential LLM calls.
  *Fix:* rewrite all flagged bullets in one batched call or in parallel.
  ✅ *Done 2026-09-30: All flagged bullets go in ONE API call via `rewrite_bullets()` instead of one call per bullet (old code: up to 3 sequential calls). Cap raised from 3 to 8 bullets, enforced inside `AIRewriter` via `MAX_BULLETS_PER_CALL` so a huge resume can't blow up the prompt; bullets beyond the cap are left untouched with `source: "skipped_batch_limit"`, never silently dropped. Verified with `test_batched_single_call_for_multiple_bullets` and `test_bullets_beyond_cap_are_skipped_not_sent`.*

- [ ] **C5 (P2): Client recreated on every request** · `analyzer/ai_rewriter.py`, `resume/service.py`
  *Fix:* create the client once (singleton or cached dependency).
  ℹ️ *2026-09-30: same root cause as F6 (a new `ResumeService`, and therefore a new `AIRewriter` and `OpenAI` client, is built per request). Batching (C4) cut the number of calls per analysis from up to 3 to 1, but the client itself is still rebuilt each request until F6 is done.*

- [ ] **C6 (P1): No user review before applying AI rewrites** · frontend + backend
  Rewrites are applied straight into the export. Placeholder generation is now disabled and guarded server-side by C1, but users still cannot accept, reject, or edit individual suggestions before download.
  *Fix:* add accept, reject, or edit per suggestion, and store the decisions.

- [ ] **C7 (P3): Rewrite the professional summary and skills too** · `analyzer/ai_rewriter.py`
  Only experience bullets are rewritten today.

- [x] **C8 (P2): Mid-sentence keyword capitalization looks wrong** · `analyzer/ai_rewriter.py`
  Found 2026-09-30 testing a real export: a missing keyword like "Communication" (Title Case in the skills taxonomy for display) got used verbatim mid-sentence — "fostering clear Communication" — which reads as a typo.
  *Fix:* added rule 7 to the system prompt instructing natural sentence-case English, keeping capitals only for genuine proper nouns (React, Docker, Python, etc.).
  ✅ *Done 2026-09-30: covered by `test_system_prompt_instructs_natural_capitalization`. Can't verify the actual model output without a live API key — flag it if you still see this after the fix.*

- [x] **C9 (P0): AI rewrites can add unsupported claims** · `analyzer/ai_rewriter.py`, `analyzer/claim_guard.py`
  *Fix:* compare each rewrite with the original for placeholders, new numbers, skills, claim words, and inflated lead verbs; retry rejected bullets once and preserve the original when needed.
  ✅ *Done 2026-10-08: Added the tunable heuristic claim guard and selective batched retry flow.*

- [x] **C10 (P1): Guarded rewrite results are opaque in the UI** · `frontend/src/api.ts`, `frontend/src/pages/Analysis.tsx`
  *Fix:* expose guard status and show users when an unsupported AI suggestion was withheld.
  ✅ *Done 2026-10-08: Added guard metadata to the report and safe rejected/partial rewrite presentation.*
  ✅ *Still to confirm: `api.ts` type confirmed by the frontend build.*

- [x] **C11 (P0): Guard finalization skips zero-retry and failure paths** · `analyzer/ai_rewriter.py`
  ✅ *Done 2026-10-08: Every model result now receives explicit per-variant finalization, including zero-retry and AI-error paths.*

- [x] **C12 (P1): Claim guard misses implied skills and new tools** · `analyzer/claim_guard.py`
  ✅ *Done 2026-10-08: Added implied-skill handling and heuristic detection for newly introduced proper nouns.*

- [x] **C13 (P1): Rewrite failure states are mislabeled** · `analyzer/ai_rewriter.py`, `frontend/src/pages/Analysis.tsx`
  ✅ *Done 2026-10-08: Added counted retries, accurate statuses, variant withholding metadata, and retry/service messages.*

---

## D. Missing Features (compared with FixResume)

- [ ] **D1 (P0): Before/after re-scoring**
  Analyze the tailored version and show the improvement (their headline "35% → 83%" feature).

- [ ] **D2 (P1): Real JD parser** · `jobs/models.py`, `jobs/router.py`
  `extracted_keywords` exists but is never filled.
  *Fix:* extract required skills, preferred skills, tools, and seniority once on save, then store them.

- [ ] **D3 (P1): Per-job tailored resume versions** · `resume/models.py`, `resume/service.py`
  Currently one export per resume.
  *Fix:* store a tailored version per (resume, job) pair.

- [ ] **D4 (P1): Reliable job import** · `jobs/scraper.py`
  Takes the first 200 lines, sets company to "Extracted from web", and fails silently on blocked or JS-rendered pages.
  *Fix:* detect empty results and show an error, extract the real company and title, and keep paste-text as the primary path.

- [ ] **D5 (P2): PDF export** · `export/`
  DOCX only today.

- [ ] **D6 (P2): Side-by-side original vs. tailored view** · frontend

- [ ] **D7 (P3): Application tracker**
  Status per job (saved, applied, interview, offer, rejected) with dates and notes.

- [ ] **D8 (P3): Cover letter generation from the resume and JD**

---

## E. Security & Config

- [ ] **E1 (P1): Default JWT secret** · `config/settings.py`
  `jwt_secret = "local-secret-key"`.
  *Fix:* require it from `.env`, and fail on startup if it's unset.

- [ ] **E2 (P1): CORS wide open** · `main.py`
  `allow_origins=["*"]` with `allow_credentials=True`.
  *Fix:* allow only the frontend origin (e.g. `http://localhost:5173`).

- [ ] **E3 (P2): Decide whether auth is needed at all**
  Single-user local app. Either remove auth to simplify, or keep it and harden it.

- [ ] **E4 (P2): Resume data privacy note**
  Resume text is sent to the Gemini/OpenAI API. Add a visible notice in the UI and an option to disable AI rewriting.

- [ ] **E5 (P1): SQL echo logs resume contents** · `.env`, `config/settings.py`
  Found 2026-10-23: `echo=True` in development prints every statement with bound values, so full resume text and user rows land in the console/logs.
  *Fix:* default echo to off and opt in per session via an env var, never in a committed `.env`.

- [ ] **E6 (P1): SSRF in the job-description fetch** · `jobs/router.py`, `jobs/scraper.py`
  Found 2026-10-23: an arbitrary user-supplied URL is fetched server-side.
  *Fix:* allowlist schemes and hosts, and block private/loopback IP ranges (including after redirects). This is separate from D4, which is about reliability.

---

## F. Engineering Hygiene

- [ ] **F1 (P0): No `requirements.txt`**
  Dependencies are undocumented: fastapi, sqlmodel, pydantic-settings, python-jose, passlib[bcrypt], pdfplumber, PyMuPDF, python-docx, spacy, scikit-learn, pyspellchecker, openai, httpx, beautifulsoup4, email-validator, python-multipart.

- [x] **F2 (P0): spaCy model fails silently** · `analyzer/keyword_engine.py`
  If `en_core_web_sm` is missing, `nlp = None` and noun chunks are silently skipped.
  *Fix:* log a clear warning or fail loudly, and document `python -m spacy download en_core_web_sm`.
  ✅ *Done 2026-09-28: Loud warning printed at startup if spaCy model is missing.*

- [ ] **F3 (P1): No README**
  Setup steps, `.env` example, how to run backend and frontend.

- [ ] **F4 (P1): No tests**
  Start with parser tests using 5 to 10 anonymized sample resumes as fixtures, then analyzer unit tests.
  🟡 *Updated 2026-10-08: `backend/tests/` now has 79 tests (bullets, keywords, scoring, ats_checker, claim guard, ai_rewriter). Parser tests still missing.*

- [ ] **F5 (P1): Fake fallback scores in the UI** · `frontend/src/pages/Analysis.tsx`
  `?? 68`, `?? 58`, `?? 71` show made-up numbers when data is missing.
  *Fix:* show an empty state or "N/A" instead.

- [ ] **F6 (P2): Analyzers constructed per request** · `resume/service.py`
  A new spellchecker and other analyzers are built each time.
  *Fix:* instantiate once at startup.

- [ ] **F7 (P2): Frontend still Figma Make boilerplate** · `frontend/`
  `package.json` name is `figma-make-app`, and `AGENTS.md`, `CLAUDE.md`, `.figma/`, and `.mise.toml` describe the Figma environment.
  *Fix:* rename the package and remove or replace the boilerplate files.

- [ ] **F8 (P2): Last analysis lives in `sessionStorage`** · `frontend/src/api.ts`
  A refresh loses context.
  *Fix:* fetch the analysis by ID from the API.

- [ ] **F9 (P2): Hardcoded absolute path** · `.vscode/settings.json`
  `d:\Projects\Application Tracking System - Personal\...` breaks on any other machine.
  *Fix:* use a relative path (`${workspaceFolder}/backend/venv/Scripts/python.exe`).

- [ ] **F10 (P2): No DB migrations**
  `create_all` won't alter existing tables when models change.
  *Fix:* add Alembic once the schema settles.

- [ ] **F11 (P3): Setup script is a full-code snapshot**
  Fine as a backup, but the source of truth should be a git repo.
  *Fix:* `git init`, add a `.gitignore` (`.env`, `*.db`, `uploads/`, `venv/`, `node_modules/`).

- [ ] **F12 (P3): Section parser is 716 lines with no structure tests**
  Split into smaller functions or classes and cover with tests (ties to F4).

- [ ] **F13 (P2): Dashboard shows hardcoded demo data** · `frontend/src/pages/Dashboard.tsx`
  `demoRecentFiles` ("Alex_Kim_Resume_v4.pdf"…) is the initial state, and the stat cards ("Average ATS Score 68", "Analyses Completed 9") are hardcoded.
  *Fix:* show real values or an empty state, and remove the demo arrays.

- [x] **F15 (P1): AI rewriter regression coverage** · `backend/tests/test_ai_rewriter.py`, `backend/tests/test_claim_guard.py`
  ✅ *Done 2026-10-08: Added mocked retry, failure-state, per-variant, implied-skill, and proper-noun coverage.*

- [ ] **F16 (P0): `build` never type-checks** · `frontend/package.json`, `frontend/src/pages/Upload.tsx`
  Found 2026-10-23: `build` is only `vite build`. `tsc --noEmit` fails with `Upload.tsx(196,44): Property 'type' does not exist on type 'ResumeSummary'`, yet the production build succeeds — so type errors ship.
  *Fix:* make `build` run `tsc --noEmit && vite build`, and fix the `FileTypeBadge` prop type (derive it from `filename`, or add `type` to `ResumeSummary`).

- [ ] **F17 (P3): Stray 0-byte database at the repo root** · `database.py`
  Found 2026-10-23: the relative SQLite path created `./ats_resume_fixer.db` (0 bytes) next to the real `backend/ats_resume_fixer.db`.
  *Fix:* resolve the DB path relative to the backend package, delete the stray file, and add `*.db` to `.gitignore` (F11).

- [ ] **F18 (P2): Setup script overwrites source unconditionally** · `backend/setup_project_latest.py`
  Found 2026-10-23: it is a stale full-code snapshot that rewrites files on every run and still references the old Gemini integration.
  *Fix:* delete it once git is in place (F11), and keep git as the source of truth.

---

## Progress Summary

Counts verified against the item list on 2026-10-23. (F14 is unused; numbering jumps from F13 to F15.)

| Section | Items | Done |
|---|---|---|
| A. Bugs | 21 | 6 |
| B. Scoring | 11 | 7 |
| C. AI Rewriter | 13 | 10 |
| D. Features | 8 | 0 |
| E. Security & Config | 6 | 0 |
| F. Hygiene | 17 | 2 |
| **Total** | **76** | **25** |

Re-verified end-to-end with real data on 2026-10-26: A12 and C3 (6/6 live rewrites from Groq, no fallbacks) and A13 (a real resume export keeps its tech spellings). A14's new certifications/languages sections are fixture-tested because the current real resume has neither; A19 is build-verified but still needs a UI click-through to become 🟢. The rest of the C section remains unit-tested only (🟡) until each item is exercised individually.

---

## Change Log

| Date | Item(s) | What changed | Notes |
|---|---|---|---|
| 2026-10-26 | A13, A14, A19 | Exporter now protects canonical tech spellings when splitting glued CamelCase, renders LinkedIn and GitHub as independent header slots, and writes `CERTIFICATIONS` / `LANGUAGES` sections when parsed. Upload page now sends the selected job id to `analyze`. Added 6 exporter regression tests. | 95 backend tests pass; `tsc --noEmit` is clean (fixed the stale `r.type` reference) and the Vite build passes. A13 confirmed with a real resume export; A14's certification/language path is fixture-tested only because the current resume has neither; A19 needs a UI click-through to be 🟢. |
| 2026-10-26 | A12, C3 verified; counts corrected | Set `AI_MODEL=openai/gpt-oss-120b` in `.env` and `settings.py`, restored the Gemini base URL, reduced the worst-case AI wait (`ai_timeout_seconds=20`, no SDK retries), added a logged and actionable cause for failed AI calls with the key redacted, and surfaced that cause in the Analysis panel. Ran a real resume + job analysis: 6/6 rewrites from Groq, no fallbacks. | Progress counts corrected to 22 done (A 3, B 7, C 10, F 2) from the checked boxes in this file; 24 would require ticking two more completed items. 89 tests pass. |
| 2026-10-26 | A12, C3 | Added a shared `resolve_ai_config` (shape-based key validation plus provider inference for `auto`), wired both `AIRewriter` and `/auth/ai-status` to it, added the client timeout/retry settings, and fixed JSON-mode polarity so only `openai` sends `response_format`. Added `tests/test_ai_config.py` and `scripts/ai_smoke_test.py`. | 86 tests pass. The smoke test exits 0 (`source=groq`, guard `passed`) with `AI_MODEL=openai/gpt-oss-120b`; the currently configured `llama-3.3-70b-versatile` returns `model_not_found` on Groq, so `AI_MODEL` needs updating. No key is logged. |
| 2026-10-23 | A9, C3 reopened; A12–A21, E5–E6, F16–F18 added; counts corrected | Full-code review. Added 15 items (10 bugs, 2 security, 3 hygiene), reopened 2 items marked done that fail verification, and fixed the totals (61 → 76 items, 22 → 20 done). Added a verification legend and a warning on Section C. | Reviewed every backend/frontend file; ran `pytest` (79 tests, 2 failing), `tsc --noEmit` (1 error), `vite build` (passes because it skips `tsc`), and probed parser/exporter/metric behaviour with real inputs. No source files changed. |
| 2026-10-08 | C11, C12, C13, F15 | Added explicit per-variant rewrite finalization with counted retries, implied-skill and new-proper-noun guard tuning, accurate frontend failure messaging, and mocked regression coverage. | Backend suite now has 79 tests; frontend build passes; no new dependencies or network calls. |
| 2026-10-08 | C9, C10 | Added a heuristic AI claim guard with one selective retry, per-variant rejection metadata, and frontend messaging for withheld suggestions. | Backend suite now has 66 tests; no new dependencies. |
| 2026-10-03 | C1 updated; C6 reprioritized | Removed AI-generated `[X]` metric placeholders. Missing metrics now produce qualitative rewrites, and the backend preserves the original bullet if a model still returns bracketed placeholder text. | Placeholder warning is no longer needed as the primary safeguard; user review remains a separate feature. |
| 2026-09-30 | C8 (new, done); A4, C6 raised to P0 | You tested a real export against a real job. Confirmed C1-C4 work correctly (placeholders used, not fabricated numbers). Found and fixed C8 (keyword capitalization bug in my own prompt). Found and logged two pre-existing, higher-priority issues: the exporter silently overwrites your resume title with the job's title (A4, raised to P0), and nothing warns you before download if a rewrite still has an unfilled `[X]` placeholder (C6, raised to P0) | Batch 2.1 |
| 2026-09-30 | C1, C2, C3, C4 | Rewrote `ai_rewriter.py`: fabrication-safe prompt with placeholder metrics, JD keyword awareness, structured JSON output, batched single-call rewriting (was up to 3 sequential calls, now 1 call for up to 8 bullets). Updated `resume/service.py` to call the new batched method. 18 new tests with a mocked client; verified the exporter still consumes the output correctly end-to-end | Batch 2 |
| 2026-09-29 | A9, A10, B11 | Copilot implemented metric detection, the pronoun-warning fix, and soft-skill groups, per a prompt I wrote for the issues found testing a real job posting. I verified by running all 39 tests plus extra edge-case probes (contractions, roman numerals, phone numbers, "I.T." abbreviations). Found and logged A11 (new, minor: phone numbers inside bullets miscounted as metrics) | Batch 1.1 (Copilot-implemented, Claude-verified) |
| 2026-09-28 | A1, B1, B2, B3, B4, B5, B6, F2 | Rewrote `bullet_analyzer.py` and `keyword_engine.py`; added `scoring.py`, `skills.py`, `service.py` patch; frontend shows N/A for unavailable scores; 31 unit tests | Batch 1. Existing DB is unchanged and compatible |
| | | | |