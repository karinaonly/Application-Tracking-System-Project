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

- [x] **A3 (P0): Missing keywords never reach the exported resume** · `export/docx_exporter.py`
  `export_tailored` accepts `missing_keywords`, but `_add_skills` ignores them and `_filter_keywords` is never called.
  *Fix:* call `_filter_keywords`, and append the results to the Skills section. Only add skills the user confirms they actually have.
  ✅ *Done 2026-10-28: no blind keyword injection — the user confirms each keyword first. Backend: `confirm_keywords` service method + `POST /resumes/{resume_id}/analyses/{analysis_id}/confirm-keywords` validates every keyword against that analysis's `missing_keywords` (case-insensitive, canonical spelling stored, unknown keyword or empty selection → 400, foreign analysis/resume → 404) and stores them as `report["confirmed_keywords"]`. Both export paths (`export_docx`, `export_version_docx`) now pass ONLY the confirmed subset to the exporter — raw missing keywords never reach it. Exporter: `_add_skills` finally calls the previously dead `_filter_keywords` (drops fluff, duplicates, anything already in the skills text, length bounds) and appends a standard ATS "Additional Skills: X, Y, Z" line; the filter now preserves canonical taxonomy spelling ("postgresql" → "PostgreSQL") instead of the old lossy `.title()` casing ("Sql"). Frontend: the Keyword Gap card's missing keywords are checkable chips — tick the ones you actually have, hit "Add N skills to my resume", confirmed chips turn teal with a check, with honest copy ("Never confirm a skill you couldn't discuss in an interview"). Covered by 12 new tests (5 exporter, 5 confirm-validation, 2 export-passes-confirmed-only). Follow-up (caught in live verification): two silent bugs fixed — the JSON report update was a no-op because the service mutated the dict in place and reassigned the same object, so SQLAlchemy emitted no UPDATE (the API returned 200, the UI showed confirmed chips, but the export read `None`); and `_filter_keywords` treated "MySQL" as evidence that "SQL" was already listed (substring match), silently dropping confirmed SQL/Java-style keywords. Now whole-word matching, with a real-SQLite persistence regression test (188 total). Refinement: confirmed keywords are classified with the existing taxonomies — hard skills fold into the matching labeled skills line ("Databases: MySQL, PostgreSQL, SQL", "DevOps & Tools: …, Linux"), with "Additional Skills" only as a fallback when no label matches; soft skills (Communication, Innovative, …) are never added — the UI renders them as dashed advice-only chips, and the endpoint returns `soft_skipped` instead of storing them. Verified live on real analyses: a previous export's "Additional Skills: Innovative, Interpersonal, Decision Making, Communication" line is now gone, while SQL/Linux land in their categories. 197 tests.*

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

- [x] **A15 (P0): Section parser mis-reads common resume layouts** · `parser/section_parser.py`
  Found 2026-10-23, verified against real inputs:
  - `"University of the Philippines"` → `"of the Philippines"`
  - A contact location can swallow the name and the following newline.
  - A full LinkedIn URL is duplicated into the portfolio field.
  - `"LinkedIn: linkedin.com/in/jane"` parses incorrectly.
  - An inline `"Skills: Python, JavaScript, React"` header is not detected.
  - A single-line contact containing an email becomes the whole line as `name`.
  *Fix:* anchor school extraction on the degree line, parse contact lines field-by-field, detect inline section headers, and never treat a line containing an email/phone as a name. Add fixtures (ties to F4/F12).
  ✅ *Done 2026-10-28: all six reproduced and fixed. Contact is now parsed line-by-line with per-field rules (labeled fields win; a name line may never contain an email/phone/URL; LinkedIn/GitHub never leak into portfolio; bare usernames normalize to full paths). Inline headers ("Skills: …", "Summary: …") start a section and feed the remainder to the body — but only when the label is ALL-CAPS or the line starts a block, so "Languages: JavaScript" under a TECHNICAL SKILLS header stays content (caught by the real-resume click-through). `_clean_degree` strips label leakage without eating school names, dedupes "Senior High Senior High School, …", and keeps "Senior High School, ABM Strand …" intact. Experience merges wrapped company names from two-column PDFs, attaches trailing date-only lines to the pending title, restores "|" glyphs extracted as "I", and never dashes inside compounds ("486-Hour" survives). `_parse_skills` splits comma lists and drops category labels. Covered by `tests/test_section_parser.py` (25 tests) with two anonymized fixtures (`resume_classic.txt`, `resume_master_layout.txt`) — partial progress on F4/F12. Verified against the real resume: section order correct, no fake LANGUAGES section, experience subtitle "Synchores Information Technology Solutions | 486-Hour | Imus, Cavite", both education entries clean.*

- [x] **A16 (P1): Decimal and unit-scaled metrics are not counted** · `analyzer/bullet_analyzer.py`
  Found 2026-10-23 (extends A9/A11): `"Cut latency by 2.5x"`, `"Reduced build time to 3.5 hours"`, `"Served 1.5 million users"` all return no metric.
  *Fix:* allow decimals and magnitude words (million/thousand) in the metric regex, while keeping the version/year exclusions.
  ✅ *Done 2026-10-26: `_is_technology_version` no longer treats every decimal as a version. A decimal is a version only in a tech/version-word context; an explicit `k/m/b/x` suffix or a following quantity/magnitude word (`3.5 hours`, `1.5 million users`) makes it a metric. Covered by `tests/test_bullet_analyzer.py` (`test_decimal_and_unit_scaled_metrics_count` plus a new version-exclusion case).*

- [x] **A17 (P1): Analyze accepts a `job_id` without an ownership check** · `resume/service.py`, `resume/router.py`
  Found 2026-10-23: a user can analyze against another user's job by guessing an id.
  *Fix:* verify `job.user_id == current_user.id` before use, and return 404 otherwise. (Depends on the E3 decision — moot if auth is removed.)
  ✅ *Done 2026-10-26: `service.analyze` now raises the existing `JobNotFoundError` (404) when the job is missing or owned by someone else, instead of silently analyzing without keywords. Covered in `tests/test_resume_service.py`.*

- [x] **A18 (P1): Export uses the latest analysis, not the selected one** · `resume/service.py`, `frontend/src/pages/Upload.tsx`
  Found 2026-10-23: viewing analysis A and exporting can produce analysis B, because export resolves "most recent" server-side.
  *Fix:* accept an `analysis_id` on export, or export from a stored per-job version (ties to D3).
  ✅ *Done 2026-10-28: `GET /resumes/{id}/export` now accepts `analysis_id`; the service verifies the analysis belongs to that resume (`AnalysisNotFoundError` otherwise) and uses its keywords/rewrites/target role. Without the param it falls back to the latest (Upload-page exports keep that honest default). The frontend pins the export to the viewed analysis everywhere one is in view: Analysis page passes the open analysis's id, Dashboard passes the row's displayed `latest_analysis.id`. Covered by 3 new tests in `tests/test_resume_service.py`.*

- [x] **A19 (P1): Upload page highlights a job but submits none** · `frontend/src/pages/Upload.tsx`
  Found 2026-10-23: the selected job card is visual only — `analyze` is called without `job_id`, so the highlighted job is not the one used.
  *Fix:* send the selected job id, and preselect it when arriving from a job (ties to D6).
  ✅ *Done 2026-10-26: `activeJobId` (the selected job, falling back to the first job) is sent to `analyzeResume`, used for the saved resume metadata, and drives the highlighted/checked job card. Also fixed the stale `ResumeSummary.file_type` reference that made `tsc` fail. `tsc --noEmit` and `bun run build` pass. 🟢 Verified live 2026-10-28: the user's upload → analyze (with selected job) → export click-through produced a correct DOCX.*

- [x] **A20 (P2): `addToast` is recreated every render** · `frontend/src/App.tsx`
  Found 2026-10-23: it is passed into effect dependency arrays, so effects can re-run and re-fetch or re-toast.
  *Fix:* wrap in `useCallback`, or expose it through a stable ref/context.
  ✅ *Done 2026-10-26: `navigate`, `addToast`, and `dismissToast` are wrapped in `useCallback` with stable identity.*

- [x] **A21 (P2): Settings saves are fake** · `frontend/src/pages/Settings.tsx`
  Found 2026-10-23: profile and password buttons report success without calling the API; plan and initials are hardcoded.
  *Fix:* wire them to real endpoints, or remove the controls. Also fix the Groq-incompatible provider message.
  ✅ *Done 2026-10-26: real endpoints added — `PATCH /auth/me` (update full_name) and `POST /auth/change-password` (verifies the current password, min 8 chars, rehashes with passlib). Settings now saves the name and changes the password through them; the fake "Free Plan · 3 analyses/month" / "Upgrade to Pro" / hardcoded "AK" initials are gone (initials derive from the real name). The provider message is now provider-neutral. Covered in `tests/test_auth_service.py`; verified live: PATCH persists, wrong current password → 400, old password rejected after change (401), new password logs in.*

- [x] **A22 (P1): Tofu boxes (□) in exported DOCX bullets** · `export/docx_exporter.py`, `analyzer/ai_rewriter.py`
  Found 2026-10-28 (real-resume click-through): AI-rewritten bullets stored in the report contain U+2011 non-breaking hyphens from the model; several DOCX viewers render them as `□` (`end‑to‑□nd`, `real‑□me`, `problem‑□olving`). The same pass also split `NestJS` into `Nest JS`.
  *Fix:* normalize unrenderable dash glyphs (U+2010/U+2011/U+2012/U+2015/U+2212/U+FE58/U+FE63/U+00AD/U+FFFD) to ASCII hyphens at AI-output creation and defensively at every exporter consumption point; add `NestJS` to the canonical tech terms.
  ✅ *Done 2026-10-28: verified by generating the DOCX from the stored report — before: 6 U+2011 occurrences; after: none, `NestJS` intact, and the parser's " — " separators preserved. Covered by 5 new tests in `tests/test_docx_exporter.py` and `tests/test_ai_rewriter.py`.*

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

- [x] **D1 (P0): Before/after re-scoring**
  Analyze the tailored version and show the improvement (their headline "35% → 83%" feature).
  ✅ *Done 2026-10-28: after the AI rewrites, `analyze()` re-runs the bullet analyzer and (when a job was scored) the keyword engine on the tailored text — same bullet population as the before-pass, with only applied rewrites substituted (raw-text replacement tolerates PDF line wraps). The report stores an `improvement` block (`before`/`after` overall + bullet/keyword scores, `applied_rewrites`/`flagged_bullets`); it is omitted when no rewrite changed a bullet. ATS compatibility carries over unchanged (format-based — rewrites don't touch it, and the claim guard forbids invented metrics, so the after number is never faked). The Analysis page shows a "Projected After Tailoring" panel: strikethrough before score → after score with a delta chip and per-component deltas. Covered by 3 tests in `tests/test_resume_service.py`.*

- [x] **D2 (P1): Real JD parser** · `jobs/models.py`, `jobs/router.py`
  `extracted_keywords` exists but is never filled.
  *Fix:* extract required skills, preferred skills, tools, and seniority once on save, then store them.
  ✅ *Done 2026-10-28: new deterministic `jobs/parser.py` (no AI) runs on both save paths (`POST /jobs/` and `/from-url`) and stores `extracted_keywords`: `required_skills` / `preferred_skills` / `other_skills` (bucketed by section headers — Requirements, Nice to have, Benefits resets — with anchored short-header detection so content lines like "…is a plus" never switch sections, and inline `Requirements: …` colons feed their remainder), `tools` (curated tool/cloud/DB subset of the taxonomy), `seniority` (title first, body fallback limited to intern/junior/mid/senior so a JD merely *mentioning* a manager isn't misread), and `min_years_experience`. Uses the same taxonomy as the keyword engine, so these are exactly the terms the keyword score can match. `JobResponse` now returns the block; all 25 existing jobs were backfilled in place; the Jobs page shows a seniority badge and required-skill chips on saved cards. Future: keyword scoring can weight required > preferred. Covered by 9 tests in `tests/test_job_parser.py`.*

- [x] **D3 (P1): Per-job tailored resume versions** · `resume/models.py`, `resume/service.py`
  Currently one export per resume.
  *Fix:* store a tailored version per (resume, job) pair.
  ✅ *Done 2026-10-28: new `resume_versions` table stores the tailored snapshot for real — `POST /resumes/{id}/versions` takes an `analysis_id` (validated to belong to that resume), applies only the rewrites that actually changed a bullet (same honesty rule as D1) into the raw text AND every section shape (`experience`/`projects` raw strings via the PDF line-wrap-tolerant replacer, `experience_parsed`/`projects_parsed` bullet lists), and stores the result with its `applied_rewrites` map. One version per (resume, job): re-saving after a better analysis upserts in place instead of piling up duplicates. An analysis with zero applied rewrites is rejected with a clear 400 — an identical copy is not a "tailored version". `GET .../versions` lists them, `GET .../versions/{id}/export` downloads the stored version as DOCX (bullets already tailored, so no rewrite map is passed; missing keywords and target role come from the version's analysis/job) with a job-specific filename, `DELETE` removes one. Frontend: "Save as version for this job" button in the Projected After Tailoring panel (job-tailored analyses only), and teal version chips on Dashboard resume cards ("Tailored for X · N rewrites") that download that version directly. `list_resumes` now includes the versions array. Covered by 8 tests in `tests/test_resume_service.py`.*

- [ ] **D4 (P1): Reliable job import** · `jobs/scraper.py`
  Takes the first 200 lines, sets company to "Extracted from web", and fails silently on blocked or JS-rendered pages.
  *Fix:* detect empty results and show an error, extract the real company and title, and keep paste-text as the primary path.
  🔶 *Partial 2026-10-28: silent failure is fixed — non-200 responses (Indeed/LinkedIn bot-blocking) and bot-wall pages (HTTP 200 but <100 chars of real text, e.g. "Enable JavaScript") now raise a clear ValueError that the router returns as a 400 and the UI toasts, telling the user to paste the JD manually; junk "Scraped Job" rows can no longer be created, and the 3 existing junk rows (empty "Scraped Job" ×2, 6-char "string") were deleted. Title comes from `<h1>` when present. Remaining: extract the real company (meta/JSON-LD) instead of the "Extracted from web" placeholder. Covered by 4 new mocked-HTTP tests in `tests/test_scraper.py`.*

- [ ] **D5 (P2): PDF export** · `export/`
  DOCX only today.

- [ ] **D6 (P2): Side-by-side original vs. tailored view** · frontend

- [ ] **D7 (P3): Application tracker**
  Status per job (saved, applied, interview, offer, rejected) with dates and notes.

- [ ] **D8 (P3): Cover letter generation from the resume and JD**

---

## E. Security & Config

- [x] **E1 (P1): Default JWT secret** · `config/settings.py`
  `jwt_secret = "local-secret-key"`.
  *Fix:* require it from `.env`, and fail on startup if it's unset.
  ✅ *Done 2026-10-26: the insecure default is gone; `validate_security_settings` runs in the app lifespan and rejects an empty or <32-char secret. Verified live: an empty `JWT_SECRET` makes uvicorn abort with "Application startup failed". `backend/.env.example` documents it.*

- [x] **E2 (P1): CORS wide open** · `main.py`
  `allow_origins=["*"]` with `allow_credentials=True`.
  *Fix:* allow only the frontend origin (e.g. `http://localhost:5173`).
  ✅ *Done 2026-10-26: CORS is now an explicit allowlist (`CORS_ORIGINS` env, defaults to localhost:8443/5173). Verified live: preflight from `localhost:8443` returns 200 with the origin echoed; `http://evil.example` is rejected with 400. If you preview the frontend from another origin, add it to `CORS_ORIGINS`.*

- [ ] **E3 (P2): Decide whether auth is needed at all**
  Single-user local app. Either remove auth to simplify, or keep it and harden it.

- [ ] **E4 (P2): Resume data privacy note**
  Resume text is sent to the Gemini/OpenAI API. Add a visible notice in the UI and an option to disable AI rewriting.

- [x] **E5 (P1): SQL echo logs resume contents** · `.env`, `config/settings.py`
  Found 2026-10-23: `echo=True` in development prints every statement with bound values, so full resume text and user rows land in the console/logs.
  *Fix:* default echo to off and opt in per session via an env var, never in a committed `.env`.
  ✅ *Done 2026-10-26: `db_echo` defaults to `False` (opt in with `DB_ECHO=true`). Verified live: after the change the backend log has zero `sqlalchemy.engine` lines, even across DB-touching requests.*

- [x] **E6 (P1): SSRF in the job-description fetch** · `jobs/router.py`, `jobs/scraper.py`
  Found 2026-10-23: an arbitrary user-supplied URL is fetched server-side.
  *Fix:* allowlist schemes and hosts, and block private/loopback IP ranges (including after redirects). This is separate from D4, which is about reliability.
  ✅ *Done 2026-10-26: `is_safe_public_url` enforces http(s), no credentials, and public resolved IPs only; redirects are followed manually so every hop is re-checked, and violations return 400. Covered in `tests/test_scraper.py` (loopback, private ranges, metadata IP, IPv6 loopback, public-IP allow).*

---

## F. Engineering Hygiene

- [x] **F1 (P0): No `requirements.txt`**
  Dependencies are undocumented: fastapi, sqlmodel, pydantic-settings, python-jose, passlib[bcrypt], pdfplumber, PyMuPDF, python-docx, spacy, scikit-learn, pyspellchecker, openai, httpx, beautifulsoup4, email-validator, python-multipart.
  ✅ *Done 2026-10-28 (with F3): `backend/requirements.txt` created with the direct dependencies pinned to the versions in the working venv (18 direct deps; spaCy + scikit-learn marked optional with the graceful-degradation note), plus the spaCy model install command documented in the README.*

- [x] **F2 (P0): spaCy model fails silently** · `analyzer/keyword_engine.py`
  If `en_core_web_sm` is missing, `nlp = None` and noun chunks are silently skipped.
  *Fix:* log a clear warning or fail loudly, and document `python -m spacy download en_core_web_sm`.
  ✅ *Done 2026-09-28: Loud warning printed at startup if spaCy model is missing.*

- [x] **F3 (P1): No README**
  Setup steps, `.env` example, how to run backend and frontend.
  ✅ *Done 2026-10-28: `README.md` at the repo root — what the app does with the honesty principles up front (no faked scores, claim guard, format-based ATS), features, tech stack, project layout, backend setup (`requirements.txt` — newly created with the direct dependencies pinned from the working venv, plus the optional spaCy model command), `.env` keys incl. the required `JWT_SECRET` and how to generate it, frontend setup (`bun install`, `VITE_API_URL`), run commands (uvicorn :8000, Vite :8443 strictPort), test commands, the typical upload → JD → analyze → save-version → export flow, and a pointer to `ROADMAP.md`.*

- [x] **F4 (P1): No tests**
  Start with parser tests using 5 to 10 anonymized sample resumes as fixture
  ✅ *Done 2026-10-28: 8 anonymized fixtures total in `tests/fixtures/` — the original 2 (`resume_classic`, `resume_master_layout`) plus 6 new layouts, each targeting a parsing hazard: ALL-CAPS alternate headers with em-dash dates (`resume_caps_headers`), skills-first order (`resume_skills_first`), experience with no dates (`resume_no_dates`), two-column PDF artifacts with glued labels and `|`→`I` glyph loss (`resume_two_column`), a projects-heavy student resume with "Expected 2026" graduation (`resume_student_projects`), and a career changer with `to`-separated dates and certifications/languages (`resume_career_changer`). The new fixtures caught and fixed 5 real parser bugs: (1) the URL regex's TLD alternation had no right boundary, so `carlos.mendoza@email.com` spawned a phantom portfolio "carlos.me"; (2) involvement-type headers (Leadership/Activities/Organizations) leaked their content into the preceding section as fake project entries — now skipped like REFERENCES, with orphan lines dropped instead of polluting contact; (3) "Expected 2026" became a bogus education entry instead of the graduation date; (4) a glued label prefix ("College Bachelor of Science…") made the whole line classify as school, swapping school and degree; (5) `_parse_projects` flushed on every bare date line, splitting every "Title / Dates / bullets" project in two (this also silently affected the original classic fixture). Also anonymized the master-layout fixture, which still contained a real employer name. Covered by 6 new fixture tests; arbitrary unrecognized org names (e.g. a society's proper name) remain a known limitation — only recognizable involvement headers are skipped.*
  🟡 *Updated 2026-10-08: `backend/tests/` now has 79 tests (bullets, keywords, scoring, ats_checker, claim guard, ai_rewriter). Parser tests still missing.*

- [x] **F5 (P1): Fake fallback scores in the UI** · `frontend/src/pages/Analysis.tsx`
  `?? 68`, `?? 58`, `?? 71` show made-up numbers when data is missing.
  *Fix:* show an empty state or "N/A" instead.
  ✅ *Done 2026-10-26: the numeric fallbacks are gone — missing scores render "N/A" (ATS/keyword/bullet cards), and the page shows a "No analysis to show" empty state with a link to Upload when there is no analysis at all, instead of a zeroed-out report.*

- [ ] **F6 (P2): Analyzers constructed per request** · `resume/service.py`
  A new spellchecker and other analyzers are built each time.
  *Fix:* instantiate once at startup.

- [ ] **F7 (P2): Frontend still Figma Make boilerplate** · `frontend/`
  `package.json` name is `figma-make-app`, and `AGENTS.md`, `CLAUDE.md`, `.figma/`, and `.mise.toml` describe the Figma environment.
  *Fix:* rename the package and remove or replace the boilerplate files.

- [ ] **F8 (P2): Last analysis lives in `sessionStorage`** · `frontend/src/api.ts`
  A refresh loses context.
  *Fix:* fetch the analysis by ID from the API.

- [x] **F9 (P2): Hardcoded absolute path** · `.vscode/settings.json`
  `d:\Projects\Application Tracking System - Personal\...` breaks on any other machine.
  *Fix:* use a relative path (`${workspaceFolder}/backend/venv/Scripts/python.exe`).
  ✅ *Done 2026-10-26: interpreter and `extraPaths` now use `${workspaceFolder}`.*

- [ ] **F10 (P2): No DB migrations**
  `create_all` won't alter existing tables when models change.
  *Fix:* add Alembic once the schema settles.

- [x] **F11 (P3): Setup script is a full-code snapshot**
  Fine as a backup, but the source of truth should be a git repo.
  *Fix:* `git init`, add a `.gitignore` (`.env`, `*.db`, `uploads/`, `venv/`, `node_modules/`).
  ✅ *Done 2026-10-26: git repo initialized on `main` with a root `.gitignore` covering `.env`, `*.db`, uploads, `venv/`, `node_modules/`, `dist/`; baseline commit `8890a61`. The snapshot itself was deleted (F18). The small `setup_project.py` copier remains, now redundant with `git clone` — safe to delete later.*

- [ ] **F12 (P3): Section parser is 716 lines with no structure tests**
  Split into smaller functions or classes and cover with tests (ties to F4).

- [x] **F13 (P2): Dashboard shows hardcoded demo data** · `frontend/src/pages/Dashboard.tsx`
  `demoRecentFiles` ("Alex_Kim_Resume_v4.pdf"…) is the initial state, and the stat cards ("Average ATS Score 68", "Analyses Completed 9") are hardcoded.
  *Fix:* show real values or an empty state, and remove the demo arrays.
  ✅ *Done 2026-10-26: demo arrays and "Welcome back, Alex" removed. Stat cards compute from `listResumes()`/`listJobs()` (resumes, jobs, average ATS across latest analyses, analyses count) with N/A when nothing is analyzed; empty states for the table and score progress; the welcome name comes from `getMe()`. The fake re-analyze/download toasts were replaced: export actually downloads the tailored DOCX, "view report" loads that resume's real analysis into the Analysis page, and re-analyze opens the Upload page.*

- [x] **F15 (P1): AI rewriter regression coverage** · `backend/tests/test_ai_rewriter.py`, `backend/tests/test_claim_guard.py`
  ✅ *Done 2026-10-08: Added mocked retry, failure-state, per-variant, implied-skill, and proper-noun coverage.*

- [x] **F16 (P0): `build` never type-checks** · `frontend/package.json`, `frontend/src/pages/Upload.tsx`
  Found 2026-10-23: `build` is only `vite build`. `tsc --noEmit` fails with `Upload.tsx(196,44): Property 'type' does not exist on type 'ResumeSummary'`, yet the production build succeeds — so type errors ship.
  *Fix:* make `build` run `tsc --noEmit && vite build`, and fix the `FileTypeBadge` prop type (derive it from `filename`, or add `type` to `ResumeSummary`).
  ✅ *Done 2026-10-26 (with A19): the stale `r.type` reference was fixed and `build` is now `tsc --noEmit && vite build`. Verified: `bun run build` runs the type check first and passes.*

- [x] **F17 (P3): Stray 0-byte database at the repo root** · `database.py`
  Found 2026-10-23: the relative SQLite path created `./ats_resume_fixer.db` (0 bytes) next to the real `backend/ats_resume_fixer.db`.
  *Fix:* resolve the DB path relative to the backend package, delete the stray file, and add `*.db` to `.gitignore` (F11).
  ✅ *Done 2026-10-26: the default `database_url` is now anchored to the backend package directory (still overridable via `DATABASE_URL`), the stray 0-byte root DB is deleted, and `*.db` is in the root `.gitignore`.*

- [x] **F18 (P2): Setup script overwrites source unconditionally** · `backend/setup_project_latest.py`
  Found 2026-10-23: it is a stale full-code snapshot that rewrites files on every run and still references the old Gemini integration.
  *Fix:* delete it once git is in place (F11), and keep git as the source of truth.
  ✅ *Done 2026-10-26: deleted via `git rm` (recoverable from history at commit `8890a61`).*

---

## Progress Summary

Counts verified against the item list on 2026-10-23. (F14 is unused; numbering jumps from F13 to F15.)

| Section | Items | Done |
|---|---|---|
| A. Bugs | 22 | 14 |
| B. Scoring | 11 | 7 |
| C. AI Rewriter | 13 | 10 |
| D. Features | 8 | 3 |
| E. Security & Config | 6 | 4 |
| F. Hygiene | 17 | 11 |
| **Total** | **77** | **49** |

Re-verified end-to-end with real data on 2026-10-26: A12 and C3 (6/6 live rewrites from Groq, no fallbacks), A13 (a real resume export keeps its tech spellings), E1 (empty `JWT_SECRET` aborts startup), E2 (allowed preflight 200 / foreign origin 400), and E5 (zero SQL-echo lines in the live log). A14's new certifications/languages sections are fixture-tested because the current real resume has neither; A19 is build-verified but still needs a UI click-through to become 🟢. The rest of the C section remains unit-tested only (🟡) until each item is exercised individually.

---

## Change Log

| Date | Item(s) | What changed | Notes |
|---|---|---|---|
| 2026-10-28 | A3 (refinement) | Confirmed keywords are now classified and placed properly: hard skills fold into the resume's existing labeled skills line (skill→category taxonomy over every HARD_SKILLS entry, with label matching for Languages/Frontend/Backend/APIs/Databases/DevOps/Tools/etc.), and "Additional Skills" is only a fallback; soft skills are never listed — the keyword engine flags `soft_missing_keywords`, the UI shows them as dashed advice-only chips with "show them in your bullets" copy, and the endpoint returns `soft_skipped` instead of storing them. Verified live: SQL → "Databases: MySQL, PostgreSQL, SQL", Linux → "DevOps & Tools: …, Linux", and the old soft-skill line disappeared. | 197 backend tests pass (9 new incl. taxonomy coverage + label matching). Counts unchanged: total 49. |
| 2026-10-28 | A3 (follow-up) | Live verification caught two silent bugs: (1) confirmed keywords were never persisted — the service mutated the report dict in place and reassigned the same object, invisible to SQLAlchemy change detection (API 200, UI chips teal, DB `None`, export empty); now a new dict is assigned, with a real-SQLite test proving a fresh session sees it. (2) `_filter_keywords` used substring matching, so confirmed "SQL" was dropped whenever the skills text had "MySQL", and "Java" whenever it had "JavaScript"; now whole-word matching. Verified on the real DB: analysis `b2e38c82…` exports `Additional Skills: SQL, Linux`. | 188 backend tests pass (2 new). Counts unchanged: total 49. |
| 2026-10-28 | A3 | Missing keywords now actually reach the exported resume — but only after explicit user confirmation (no blind injection). New `confirm-keywords` endpoint validates each keyword against the analysis's own `missing_keywords` and stores the canonical spellings as `report["confirmed_keywords"]`; both export paths pass only that subset. The exporter's dead `_filter_keywords` is finally called by `_add_skills`, which appends a standard "Additional Skills: …" line (fluff/dupes/already-present filtered; canonical spelling preserved instead of `.title()` mangling "SQL" → "Sql"). Frontend: checkable chips on the Keyword Gap card's missing keywords with an honesty-first confirm button. | 186 backend tests pass (12 new). Counts: A 14, total 49. |
| 2026-10-28 | F4 | Six new anonymized parser fixtures (8 total), each targeting a layout hazard — and they immediately caught 5 real parser bugs, all fixed: phantom portfolio fields from emails ("carlos.me" — URL regex TLD had no right boundary), involvement-header content leaking into projects as fake entries (now skipped like REFERENCES, orphan lines dropped), "Expected 2026" becoming a bogus education entry (now the graduation date), glued "College" labels swapping school/degree in degree-first layouts, and `_parse_projects` splitting every "Title / Dates / bullets" project in two on its date line (also silently affecting the original classic fixture). Also anonymized the master-layout fixture, which contained a real employer name. Known limitation recorded: arbitrary unrecognized org names still flow into the preceding section — only recognizable involvement headers are skipped. | 174 backend tests pass (6 new fixture tests in `test_section_parser.py`). Counts: F 11 → 48 done. |
| 2026-10-28 | F3 | README added at the repo root: honesty principles up front (no faked scores, claim guard, format-based ATS), features, tech stack, project layout, backend setup with a new `requirements.txt` (direct deps pinned from the working venv; spaCy model documented as optional with graceful degradation noted), `.env` keys incl. required `JWT_SECRET` + generation command, frontend setup (`bun install`, `VITE_API_URL`), run/test commands, the typical flow, and a pointer to the roadmap. | Docs only; no code changes. Counts: F 10 → 47 done. |
| 2026-10-28 | D3 | Per-job tailored resume versions are live: `POST /resumes/{id}/versions` stores a real tailored snapshot from an analysis — only rewrites that actually changed a bullet are applied (same honesty rule as D1) into the raw text and every section shape, one version per (resume, job) with upsert-on-re-save, and a 400 rejection when zero rewrites changed anything (an identical copy is not a tailored version). List / export (job-specific DOCX filename, no double-rewriting since bullets are already tailored) / delete endpoints round it out. Frontend: "Save as version for this job" in the improvement panel and teal version chips on Dashboard cards that download the version directly. | 168 backend tests pass (8 new); `tsc --noEmit` + `bun run build` pass; `resume_versions` table auto-created and verified live. Counts: D 3 → 46 done. |
| 2026-10-28 | D4 (partial) | URL import no longer fails silently: non-200 fetches (Indeed/LinkedIn bot-blocking — the user hit this live on an Indeed URL that saved as an empty "Scraped Job") and bot-wall pages (HTTP 200 but <100 chars of real text) now raise a clear error → 400 → UI toast telling the user to paste the JD manually. Junk "Scraped Job" rows can no longer be created; the 3 existing junk rows were deleted (23 jobs remain). Remaining for D4: extract the real company from meta/JSON-LD instead of the "Extracted from web" placeholder. | 161 backend tests pass (4 new mocked-HTTP tests in `tests/test_scraper.py`). No counts change (item stays open). |
| 2026-10-28 | D2 | Real JD parser is live: a deterministic `jobs/parser.py` (same taxonomy as the keyword engine) runs on both job-save paths and fills the previously-dead `extracted_keywords` column — required/preferred/other skills bucketed by section headers (anchored short-header detection; inline `Requirements: …` colons keep their content; Benefits/About-us headers reset the bucket), curated tools list (incl. cloud/DBs), seniority (title-first, body fallback restricted to intern/junior/mid/senior so "mentions a manager" isn't "is a manager"), and min years of experience. `JobResponse` exposes it; the Jobs page shows a seniority badge + required-skill chips; all 25 stored jobs backfilled in place. Notable catches while testing: "…is a plus" content lines were being mistaken for section headers, and cloud providers were missing from the tools list. Future: keyword scoring can weight required > preferred (noted in the roadmap item). | 157 backend tests pass (9 new in `tests/test_job_parser.py`); `tsc --noEmit` + `bun run build` pass. Counts: D 2 → 45 done. |
| 2026-10-28 | D1 | Before/after re-scoring is live: after AI rewrites, `analyze()` re-scores the tailored text (bullet analyzer over the same full bullet population with applied rewrites substituted; keyword engine re-run against the tailored raw text with PDF line-wrap-tolerant replacement) and stores a before/after `improvement` block in the report. The Analysis page shows a "Projected After Tailoring" panel (before → after overall with delta chip, per-component deltas, and an honest note: ATS unchanged — it is format-based, and no invented metrics are allowed). Verified against the real resume: 6/6 rewrites applied, before and after both 62.5 bullet impact (like-for-like swaps — honest neutral, not faked improvement). | 148 backend tests pass (3 new improvement tests); `tsc --noEmit` + `bun run build` pass; live run through the real Groq provider. Counts: D 1 → 44 done. |
| 2026-10-28 | A18 (also marks A19 🟢) | Export now uses the analysis the user is viewing instead of blindly "the latest": `GET /resumes/{id}/export` accepts `analysis_id` (validated to belong to that resume, `AnalysisNotFoundError` otherwise) and the frontend pins it everywhere an analysis is in view — Analysis page and Dashboard both pass the displayed analysis's id; Upload-page exports keep the latest-analysis default since no analysis is in view there. A19's upload → analyze (selected job) → export click-through was confirmed live by the user, closing the last undone bug in section A. | 145 backend tests pass (3 new export-selection tests); `tsc --noEmit` + `bun run build` pass. Counts: A 13 → 43 done. |
| 2026-10-28 | A22 | Export click-through found tofu boxes (□) in project bullets: Groq rewrites stored in the report contain U+2011 non-breaking hyphens, which several DOCX viewers cannot render; the same pass also split "NestJS" into "Nest JS". Unrenderable dash glyphs are now normalized to ASCII at AI-output creation (`ai_rewriter`) and defensively at every exporter consumption point (structured bullets, rewrites, raw lines); `NestJS` added to canonical tech terms. En/em dashes (" — " separators) intentionally preserved. Existing stored report now exports clean without re-analyzing. | 142 backend tests pass (5 new: exporter glyph + NestJS tests, rewriter glyph test). Verified by regenerating the DOCX from the stored report: 6 U+2011 occurrences before → 0 after. Counts: A 12 → 42 done. |
| 2026-10-28 | A15 (follow-up) | Real-resume click-through caught an A15 regression: "Languages: JavaScript…" under TECHNICAL SKILLS was mistaken for a LANGUAGES section header, eating the skills list. Inline headers now require an ALL-CAPS label or a preceding blank line. Also fixed pre-existing issues the click-through exposed: `_clean_company` no longer dashes inside compounds ("486-Hour", "Full-Stack"), restores "\|" glyphs extracted as "I", strips merged left-column labels from meta lines, and merges wrapped company names; `_clean_degree` dedupes "Senior High Senior High School…" and strips merged "College" prefixes; skills drop category labels. The stored resume was re-parsed in place. | 137 backend tests pass (8 new real-pattern tests). Real resume verified: correct section order, clean skills chips, "Synchores Information Technology Solutions \| 486-Hour \| Imus, Cavite", both education entries intact. Counts unchanged (41 done). |
| 2026-10-28 | A15 | Parser fixes: contact is parsed line-by-field (labeled fields win; email/phone/URL lines are never the name; LinkedIn/GitHub never leak into portfolio; bare handles normalize to full paths); inline section headers ("Skills: …", "Summary: …") are detected with the remainder kept as the body; `_clean_degree` only strips label prefixes followed by a separator; education merges dateless headers with their dated detail line and starts a new entry on a second school; experience attaches a trailing date-only line to the pending title; skills split on commas. Added `tests/test_section_parser.py` (17 tests) and 2 anonymized fixtures — partial F4/F12 progress. | 129 backend tests pass. All six documented failures reproduced before the fix and verified fixed after. Backend restarted with the new parser. Counts: A 11 → 41 done. |
| 2026-10-26 | A16, A20, A21, F5, F13 | Honesty batch: decimal/unit metrics (`2.5x`, `3.5 hours`, `1.5 million`) now count while version/year exclusions hold; `navigate`/`addToast` are stable `useCallback`s; Settings saves are real (`PATCH /auth/me` + `POST /auth/change-password` with current-password verification), fake plan/upgrade/hardcoded initials removed, provider message made provider-neutral; Analysis page shows N/A and a no-analysis empty state instead of fake fallback scores; Dashboard computes real stats from the API with empty states, and its export/report/re-analyze buttons do what they claim. | 112 backend tests pass (5 new: auth service profile/password + metric cases); `bun run build` (with `tsc`) passes. Verified live on the restarted server: PATCH `/auth/me` persists the name, wrong current password → 400, change-password → 204 with old password rejected (401) and new password logging in. Counts: A 10, F 9 → 40 done. |
| 2026-10-26 | A17, E1, E2, E5, E6, F9, F11, F16, F17, F18 | Analyze now 404s on missing/foreign `job_id`; JWT secret is required at startup (no insecure default); CORS is an explicit origin allowlist; SQL echo is off by default; the job-URL fetch has an SSRF guard (scheme/credentials/public-IP checks, redirects re-checked, 400 on violation). Frontend `build` runs `tsc` first, `.vscode` paths use `${workspaceFolder}`, the default DB path is anchored to `backend/`, the stray root DB and `setup_project_latest.py` are deleted, and `backend/.env.example` was added. | 107 tests pass; `bun run build` (with `tsc`) passes. Verified live on the restarted server: empty `JWT_SECRET` → startup abort; allowed preflight → 200 with ACAO, `http://evil.example` → 400; zero SQL-echo lines across DB-touching requests. Counts: A 7, E 4, F 7 → 35 done. |
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