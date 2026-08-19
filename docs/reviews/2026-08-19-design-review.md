# Grill Me #1 — Design Review

**Reviewer**: critic agent
**Target**: SPEC v0.1.0 + PLAN v0.1.0
**Date**: 2026-08-19
**Verdict summary**: 14 findings — 1 BLOCKER, 5 CRITICAL, 7 MAJOR, 1 MINOR

**Pre-commitment predictions**: Before reading in detail I predicted issues in (a) score division-by-zero edge cases, (b) evidence substring fragility for Korean text, (c) LLM personal-info leak via free-tier training, (d) UNKNOWN vs MISSING gaming, (e) silent mock fallback, (f) SSRF via URL extractor, (g) race conditions on `is_current`, and (h) cascade behavior on deletes. All eight predictions surfaced real findings. Additional issues discovered during investigation: LLM silently omitting requirements from `matches`, unspecified datetime timezone, missing idempotency on `/fit/analyze`.

**Mode**: Started in THOROUGH mode. After the div-by-zero BLOCKER + 3 CRITICALs surfaced early, escalated to ADVERSARIAL mode — this surfaced Finding 2 (hallucination is rewarded) and Finding 3 (silent 100%), both under the same root cause: the score calculator over-trusts the LLM-returned shape.

---

## Finding 1: Score calculator throws ZeroDivisionError on empty requirement / preferred / tech list

**Severity**: BLOCKER
**Location**: SPEC §14 (formula), §11 (schema), PLAN Phase 7
**Claim**: The formula `sum(verdict_weight × importance_weight) / sum(importance_weight) × 100` divides by zero when the posting has no requirements, no preferred items, or no tech_stack — all three are permitted by §10.
**Failure scenario**: User pastes a wanted.co.kr posting that lists 주요업무 only with no explicit 자격요건 section (common for BM / 신입 roles). LLM returns `requirements: []`. Backend calls `requirement_dim(matches=[])` → `sum(importance_weight)` = 0 → `ZeroDivisionError` → 500 → user sees `"AI 분석이 실패했습니다"` on a valid input the SPEC promised to handle.
**Suggested fix**: SPEC §14 must state the empty-list rule: `if not matches: dim_score = None`, mark dimension `N/A`, and renormalize the overall weights over present dimensions only. Add PLAN Phase 7 tests: `test_requirement_dim_empty_list`, `test_preferred_dim_empty_list`, `test_tech_dim_empty_list`, `test_overall_when_a_dimension_is_absent`.

---

## Finding 2: LLM hallucination is REWARDED with +30% credit via the unknown fallback path

**Severity**: CRITICAL
**Location**: SPEC §13.3, §13.4, §14 verdict_weight table
**Claim**: §13.3 downgrades unverified evidence to `unknown`. §14 gives `unknown` verdict_weight **0.3**. The honest verdict for a genuinely missing skill is `missing` (weight 0.0). Net effect: an LLM that fabricates evidence scores **+30 percentage points** on that item compared to an LLM that honestly returns `missing`.
**Failure scenario**: Posting requires "Kubernetes 3년+". Resume has zero K8s mentions. Honest LLM: `{"verdict":"missing","evidence_ids":[]}` → weight 0.0. Hallucinating LLM: `{"verdict":"met","evidence_ids":["ev_99"]}` with `ev_99 = "쿠버네티스 클러스터 운영 3년"` (fabricated quote). Evidence matcher fails substring → §13.3 downgrades to `unknown` → weight 0.3. Hallucinator's `overall_score` > honest analyst's. The exact bug the evidence system is meant to prevent. Interview killer: *"So your system rewards lying?"*
**Suggested fix**: Downgrade path must go to `missing` (0.0), NOT `unknown` (0.3), when the ORIGINAL verdict was `met`/`partial`/`have` and verification failed. Reserve `unknown` for the case where the LLM itself returned `unknown` (admitted ignorance). Add SPEC §13.3 clarification + PLAN test `test_fabricated_evidence_downgrades_to_missing_not_unknown`.

---

## Finding 3: FitAnalysis matches do not have to cover every requirement — silent 100% on omitted items

**Severity**: CRITICAL
**Location**: SPEC §11 (example), §13, §14 (formula operates on whatever `matches` contains)
**Claim**: Nothing in §11, §13, or §14 requires `requirement_fit.matches` to contain exactly one entry per `job_posting.requirements` item. `score_calculator` computes over whatever the LLM returned. If the LLM omits a hard requirement, that requirement is silently dropped from BOTH the numerator AND the denominator — omission → invisible.
**Failure scenario**: Posting has 5 must-have requirements. LLM returns matches for only the 2 the candidate obviously has (`met`, `met`) and silently skips the 3 they lack. `score = (1.0×1 + 1.0×1) / (1.0 + 1.0) × 100 = 100`. Backend reports "requirement_fit: 100" and overall verdict "Strong Fit" for a candidate who meets 2 of 5 must-haves. Directly contradicts §1's promise of "정량 · 근거 기반 적합도".
**Suggested fix**: SPEC §11 MUST state: `matches` contains exactly one entry per `job_id`. `score_calculator` MUST left-join LLM matches against the posting's requirement list — any missing `job_id` is materialized as `verdict=unknown` (or the request is retried once, else fail with `AnalysisFailedError`). Add PLAN test `test_fit_analysis_backfills_missing_requirement_ids`.

---

## Finding 4: SSRF via job posting URL extractor — no scheme / host / IP allow-list

**Severity**: CRITICAL
**Location**: SPEC §12 (URL extraction), §7 (`url_extractor.py`), §18 (Security omits SSRF)
**Claim**: `url_extractor.py` uses `requests + BeautifulSoup` on user-supplied URLs with no scheme restriction, no private-IP block, no port allow-list, no redirect cap, no timeout, no size cap. §18 does not mention SSRF at all.
**Failure scenario**: (a) `url: "http://127.0.0.1:8000/api/health"` → backend fetches its own health endpoint and stores the JSON as "job posting text". (b) `url: "http://169.254.169.254/latest/meta-data/"` on any cloud host reads instance metadata. (c) `url: "http://intranet.corp.local:8080/admin"` fingerprints the user's LAN. (d) Redirect chain: attacker-controlled URL 302s to `http://127.0.0.1:22` — first check passes, redirect target isn't re-checked. Portfolio red flag on first glance from any security-aware reviewer.
**Suggested fix**: SPEC §12 MUST state: (1) only `http`/`https` schemes; (2) resolve DNS and reject `10.0.0.0/8`, `127.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16`, `::1`, `fc00::/7`; (3) `allow_redirects=False`, follow manually with re-validation, max 3 hops; (4) 5-second timeout; (5) `MAX_URL_BYTES` (e.g., 2 MB). Add PLAN tests `test_url_extractor_rejects_localhost`, `test_url_extractor_rejects_private_ip`, `test_url_extractor_rechecks_redirects`.

---

## Finding 5: LIVE mode sends full resume text to Gemini free-tier — which uses prompts for training by default

**Severity**: CRITICAL
**Location**: SPEC §15 ("Gemini 우선 (무료 티어)"), §18 (masking covers logs only), §22 ("무료 티어 · 시연 유리")
**Claim**: §18 addresses local-side privacy (logs, `.env`, git). It says nothing about the fact that **Google AI Studio's free-tier API uses submitted prompts to improve models by default**. In LIVE mode the extracted resume — name, employer, dates, achievements — is sent verbatim. §18 masking is only for local logs, not for outbound prompt content.
**Failure scenario**: Interviewer clones the repo, obtains a free-tier `GEMINI_API_KEY` (the SPEC explicitly touts this path), uploads their own resume to try the app. Their PII is ingested into Google's training pipeline. If the interviewer notices during due diligence, this is a hard fail — the app being showcased leaks the reviewer's data on first use. Even if the current author only uses dummy data, the README/product surface must warn any downstream user.
**Suggested fix**: SPEC §18 add a "3rd-party data flow" subsection: (a) In LIVE mode with Gemini free-tier, prompt content is subject to Google's training policy — link to policy; (b) README + UI show a persistent banner in LIVE mode: `"업로드한 자료가 LLM 제공자에게 전송됩니다"`; (c) `.env.example` defaults `MOCK_MODE=true`; (d) document that OpenAI's paid API does NOT train on prompts (different guarantee). Add SPEC §5 acceptance criterion: LIVE badge is always accompanied by a data-flow disclosure link.

---

## Finding 6: `is_current` has no unique constraint — concurrent build creates two "current" profiles

**Severity**: CRITICAL
**Location**: SPEC §8 (`career_profiles.is_current bool`), §19 (`POST /api/career/profile/build`), §22 (SQLite)
**Claim**: `is_current` is a plain boolean. §8 shows no partial-unique index (`UNIQUE(is_current) WHERE is_current=1`); no application-level locking is described. Two concurrent build_profile calls both flip prior rows to false and insert new rows with `is_current=true` — nothing enforces the "at most one" invariant.
**Failure scenario**: User double-clicks "Build Profile" on a flaky network. Two requests hit backend. Both execute `UPDATE career_profiles SET is_current=false` then `INSERT ... is_current=true`. `SELECT ... WHERE is_current=1` now returns two rows. `GET /api/career/profile` picks one arbitrarily. Subsequent fit analyses reference a `career_profile_id` different from what the UI displays. Silent divergence, no error.
**Suggested fix**: §8 add `UNIQUE INDEX idx_current_profile ON career_profiles(is_current) WHERE is_current=1` (SQLite supports partial indexes). Wrap the flip in `BEGIN IMMEDIATE`. Cleaner alternative: drop the boolean and derive "current" as `ORDER BY created_at DESC LIMIT 1` — no race, no invariant to violate. Add PLAN test `test_concurrent_build_profile_maintains_single_current`.

---

## Finding 7: Cascade rules unspecified — deleting a document / profile / posting leaves dangling references

**Severity**: MAJOR
**Location**: SPEC §8 (FKs declared without `ON DELETE`), §17 (delete covers filesystem, not row cascades), §19 (DELETE endpoints)
**Claim**: `fit_analyses.career_profile_id` and `fit_analyses.job_posting_id` are declared "int FK" with no `ON DELETE` clause — SQLite default is NO ACTION. `career_profiles.source_doc_ids` is a JSON blob (not even a FK). The delete interaction matrix is undefined.
**Failure scenario**: (a) User deletes a job posting via `DELETE /api/job/postings/9`. Existing `fit_analyses` rows with `job_posting_id=9` remain. Dashboard JOIN returns NULL for posting metadata → frontend shows "undefined - undefined" as title. (b) User deletes `career_document` id=3. Corresponding `career_profile.source_doc_ids = [1,2,3]` now references a dead row; `evidence_matcher` cannot re-verify because `extracted_text` is gone. All previously-verified evidence becomes "unverifiable on demand" and there is no plan for that state.
**Suggested fix**: §8 must specify `ON DELETE CASCADE` on `fit_analyses` FKs (or `ON DELETE RESTRICT` + 409). For `source_doc_ids`, either (a) block deletion of any document referenced by a career_profile, or (b) mark those profiles `stale=true` and disable further use. Add PLAN tests `test_delete_job_posting_cascades_analyses`, `test_delete_referenced_career_document_blocked`.

---

## Finding 8: LIVE fallback badge is a deception vector — `mode` vs `effective_mode` UX undefined

**Severity**: MAJOR
**Location**: SPEC §15 (health example only shows all-LIVE), §6 (`ModeBadge.tsx`), §22 (silent fallback rejected as a design choice — but effectively re-introduced by the .env fallback)
**Claim**: §15 states auto-fallback happens when `MOCK_MODE=false` + missing key. But the health-response example only shows the `mode=LIVE, effective_mode=LIVE` case. Badge behavior for `mode=LIVE, effective_mode=MOCK` is unspecified. §22's decision row explicitly rejects silent deception — yet the .env fallback IS silent deception unless the badge differentiates.
**Failure scenario**: Interviewer sets `MOCK_MODE=false, LLM_PROVIDER=gemini` but forgets to paste the key. App boots. If ModeBadge reads `mode` (not `effective_mode`) it shows "LIVE · Gemini" while the app actually serves hardcoded mock fixtures. Interviewer believes they see real Gemini output. Directly contradicts §22's own stated principle "silent fallback: 오해 유발".
**Suggested fix**: §15 add an explicit `effective_mode=MOCK` health example. §6 ModeBadge MUST render from `effective_mode`, not `mode`, and MUST show a distinct "MOCK (auto)" state with hover text explaining why. Add PLAN tests `test_health_reports_effective_mock_when_key_missing`, `test_ModeBadge_shows_auto_fallback_state`.

---

## Finding 9: Evidence substring matcher is brittle for Korean paraphrasing — false-negatives cascade into Finding 2

**Severity**: MAJOR
**Location**: SPEC §13.2 (substring + whitespace collapse + case fold), §22 (fuzzy rejected)
**Claim**: `case fold` is a no-op for Korean. LLMs paraphrase quotes routinely — swap Hangul/Latin (`파이프라인` ↔ `pipeline`), split spaced compound nouns (`실시간` ↔ `실 시간`), rewrite particles (`을/를`, `이/가`). Any of these breaks exact substring. Every false-negative feeds Finding 2 (unverified → unknown → +30% credit).
**Failure scenario**: Resume text: `"임베디드 파이프라인 성능 3배 개선"`. LLM extracts evidence quote: `"임베디드 pipeline 성능 3배 개선"` (Gemini routinely does this for Korean-English mixed content). `str.replace(whitespace).casefold()` still fails to match. Evidence → unverified → verdict downgraded to `unknown` → gets 30% instead of the true 100%. Real ability under-scored; per Finding 2, hallucinated ability over-scored. Both directions wrong.
**Suggested fix**: SPEC §13.2 must specify the exact normalization: (a) NFC-normalize both sides; (b) collapse ALL whitespace AND punctuation to nothing; (c) strip trailing Korean particles at token boundaries; (d) then substring. Also: minimum quote length 15 characters (§13 currently silent) to avoid trivial-substring false-positive. Add PLAN tests `test_evidence_matcher_survives_hangul_latin_swap`, `test_evidence_matcher_rejects_paraphrase`.

---

## Finding 10: Confidence penalty compounds silently — no floor, no explanation surfaced to user

**Severity**: MAJOR
**Location**: SPEC §14 (Confidence subsection)
**Claim**: §14 lists two independent multiplicative penalties: `unknown_ratio ≥ 40% → ×0.7` AND `verified_ratio < 60% → ×0.8`. Both can apply → ×0.56. No floor documented. LLM's own `confidence` is then multiplied on top. Compounding is not stated, not tested, and not surfaced.
**Failure scenario**: LLM returns `confidence: 0.8` (already conservative). Analysis has 45% unknown items and 55% verified evidence. Backend: `0.8 × 0.7 × 0.8 = 0.448`. User sees "confidence 44.8%" on a "Weak Fit" verdict. Was the LLM 80% or 45% confident? The displayed number is now a compound artifact, not a probability. If a third penalty is added later, this becomes meaningless without noticing.
**Suggested fix**: §14 add: (a) `final_confidence = max(0.1, min(1.0, llm_confidence × product_of_penalties))`; (b) Return `penalty_reasons: string[]` on the API response so UI can render `"×0.7 because 45% of requirements were unknown"`; (c) PLAN test `test_confidence_penalty_compounds_but_floors_and_reports_reasons`.

---

## Finding 11: Datetime columns have no timezone policy — created_at ordering & display become inconsistent

**Severity**: MAJOR
**Location**: SPEC §8 (all `datetime` columns), §11 (example uses `+09:00`), §19 (response echoes `created_at`)
**Claim**: §8 lists `uploaded_at`, `created_at` as `datetime` with no TZ annotation. SQLite has no native TZ enforcement — Python `datetime.utcnow()` vs `datetime.now()` produce different values and neither carries TZ info by default. §11 example shows `+09:00` (KST) but no SPEC clause pins the policy. Frontend sorting and display depend on this.
**Failure scenario**: Dev writes `datetime.now()` (naive local). A later maintainer switches one path to `datetime.utcnow()` (naive UTC). Rows now mix naive-local and naive-UTC in the same column. `ORDER BY created_at DESC` interleaves them wrong. Dashboard shows history in nonsensical order. Or: interviewer runs the app on a UTC/PT laptop and sees timestamps 9 hours off with no indication.
**Suggested fix**: §8 add: "모든 datetime 은 UTC-aware ISO8601 로 저장 (`datetime.now(timezone.utc)`); 프론트가 사용자 로컬 TZ 로 표시". Update §11 example to `Z` suffix. Enforce via SQLAlchemy `DateTime(timezone=True)` and a Pydantic serializer. Add PLAN test `test_created_at_is_utc_and_tz_aware`.

---

## Finding 12: `POST /api/fit/analyze` has no idempotency — double-click creates duplicates and duplicate LLM cost

**Severity**: MAJOR
**Location**: SPEC §19 (POST /api/fit/analyze), §8 (fit_analyses has no dedup key)
**Claim**: The endpoint creates a new row per call. No `Idempotency-Key` header, no unique constraint on `(career_profile_id, job_posting_id)`, no in-flight dedup, no client-side reasoning surfaced.
**Failure scenario**: User double-clicks "적합도 분석" on a slow spinner. Two POSTs fire. Two rows are created. Two LLM calls burn quota. History shows two nearly-identical analyses with slightly different `overall_score`s because LLM at temp=0.2 is not perfectly deterministic. User confused about which is "real"; dashboard inflated with dupes.
**Suggested fix**: §19 pick one of: (a) unique constraint `UNIQUE(career_profile_id, job_posting_id)` + 409 on repeat (simplest); (b) `Idempotency-Key` header (client UUID, server caches within a TTL); (c) frontend button-disable + backend in-flight tracker. Minimum: SPEC §19 must state the chosen approach. Add PLAN test `test_repeated_fit_analyze_is_idempotent_or_rejected`.

---

## Finding 13: Test plan (§20, PLAN Phase 3/6/7) misses path-traversal, SSRF, and score edge-case coverage

**Severity**: MAJOR
**Location**: SPEC §20, PLAN Phase 3 / 6 / 7
**Claim**: The 20+ pytest list enumerates only happy paths, mock wiring, and verdict thresholds. Missing: `test_upload_rejects_path_traversal_filename`, `test_upload_rejects_over_size_limit`, `test_url_extractor_rejects_localhost_and_private_ip`, `test_score_calculation_empty_requirements`, `test_score_calculation_all_unknown`, `test_confidence_penalty_formula`, `test_fit_analysis_cascade_delete`, `test_replace_document_atomic`, `test_gemini_client_cache_invalidates_on_key_change`.
**Failure scenario**: A senior reviewer opens `backend/tests/` looking for security tests. They find none. They ask: "You said path sanitize is done — how is it tested?" There is no answer. Definition of Done clause 3 ("관련 pytest 케이스 존재") passes vacuously because "관련" is subjective.
**Suggested fix**: PLAN Phase 3/6/7 add the named tests explicitly. Add a `Phase 7.5 — Security & Edge Cases` block enumerating them as first-class checkboxes. Update SPEC §20 test list. Tighten Definition of Done clause 3 to: "each SPEC-declared invariant has at least one covering test".

---

## Finding 14: Weights not validated to sum to 1.0; verdict boundary floating-point drift; fixed CORS port breaks on Vite fallback

**Severity**: MINOR
**Location**: SPEC §14 (weights `settings 로 조정 가능`), §14 (verdict thresholds), §18 (CORS `http://localhost:5173`)
**Claim**: (a) A maintainer edits weights via settings; if they don't sum to 1.0, `overall` is silently out of `[0, 100]`. (b) `overall = 84.9999...` → "Fit" not "Strong Fit" — FP drift near thresholds produces inconsistent verdicts across runs on the same input. (c) If Vite auto-selects 5174 because 5173 is busy, CORS blocks all XHRs and app appears silently broken.
**Failure scenario**: (a) Someone tweaks `weights = {responsibility: 0.35, requirement: 0.35, tech: 0.20, experience: 0.10, preferred: 0.05}` (sum 1.05) → overall_score = 105 → "Strong Fit" everywhere. (b) Two runs produce 84.9999 vs 85.0001 → different verdict label on identical input. (c) Colleague opens the app, Vite says "Port 5173 in use, using 5174" → browser console CORS errors only.
**Suggested fix**: (a) Settings loader validates `abs(sum(weights.values()) - 1.0) < 1e-6`; raise `ConfigurationError` on boot. (b) Round `overall` to 1 decimal before threshold compare, or state boundary policy (`>= 84.5`) explicitly. (c) §18 change CORS to `CORS_ORIGINS` env list, default `["http://localhost:5173","http://localhost:5174","http://localhost:5175"]`.

---

## What's Missing

- **kind = job_posting file storage table** — §17 says uploaded job-posting PDFs live under `uploads/job_posting/…`, but §8 has no table for them; `career_documents` is unique-per-kind for career kinds only. Where is `stored_path` recorded for job-posting PDFs? `job_postings.source_ref` is described as "url or filename" — is it storing an absolute path or the sanitized name? Undefined.
- **Replace-document atomicity** — §19 exposes `POST /api/career/documents/{id}/replace`, but §17 only covers delete order (DB→FS). For replace: is new file uploaded first, then DB updated, then old file deleted? What if the DB update fails after the new file is written? Not addressed.
- **Analyzer factory client-cache invalidation** — §22 test `test_gemini_client_cached_per_key` exists, but nothing states what happens when the key changes at runtime. If cache key is `(provider, api_key)`, missing entry triggers rebuild — fine, but SPEC doesn't say. If it's cached-by-process-lifetime, key rotation requires restart.
- **`evidence_ids` referencing non-existent `ev_x`** — §13 verifies quotes vs raw text but never verifies that `evidence_ids` referenced in `matches`/`strengths`/`gaps` correspond to actual entries in `evidence_index`. LLM can invent `ev_99` and it will silently pass the "has evidence_ids" check.
- **Rate-limit / quota surface** — no per-hour LLM call cap. Interviewer accidentally triggers "적합도 분석" 50 times → free tier throttled → user sees generic 500s. Even a simple in-process token bucket would be an easy talking point.
- **File-size limit enforcement chain** — §18 says MAX 20 MB but §7 `document_service.py` never states whether limit is enforced at multipart parse (streaming) or after full load into memory. 20 MB × 3 docs concurrently uploaded = 60 MB memory spike.
- **Uploads directory sweep** — orphan-file tolerance (§17) is fine short-term but there's no cleanup job. Directory grows unbounded across replace/delete cycles.

## Ambiguity Risks

- SPEC §9 says LLM "붙일 수 있다" (CAN attach) `evidence_ids`, but §13.4 downgrades matches without evidence_ids → the prompt must make evidence_ids REQUIRED. If left as "can", every fit match becomes `partial` after downgrade.
  - Interpretation A: `evidence_ids` optional in schema, required by prompt → LLM inconsistency will materialize as universal downgrade.
  - Interpretation B: `evidence_ids` required in schema → LLM omission = validation failure = retry loop.
  - Risk if A: silent quality collapse in the field.
- SPEC §15: "자동 fallback + warning 로그" — is the warning surfaced in the health-response body, only in stderr, or both? Finding 8's fix depends on it being consumable by the UI. Ambiguous today.
- SPEC §17 `kind` set — `"resume" | "career_desc" | "portfolio" | "job_posting"` — but §8 `career_documents.kind` uniqueness is scoped to career kinds. Is `job_posting` a valid value here or not?

## Multi-Perspective Notes

- **Executor**: PLAN Phase 3 asks for "sanitize filename" but SPEC §18 gives no explicit allowed-char whitelist. Executor will invent their own → later rework. Specify: `[A-Za-z0-9._가-힣-]+`, replace others with `_`, max 200 chars after NFC-normalize.
- **Stakeholder**: The stated purpose is "이 앱은 senior code review 를 통과해야 한다". Findings 2, 3, 4, 6 are the exact class a senior reviewer opens with. Fixing pre-implementation is 10x cheaper than post-implementation.
- **Skeptic**: §22's rejection of fuzzy matching (`rapidfuzz`) is defended by "false positive → hallucination defense 훼손". But Finding 9 shows the substring-only approach fails routinely on realistic Korean LLM output. The rejected alternative wasn't hand-waved, but the SPEC never states the acceptable false-negative rate. Without that budget, this is defense-by-assertion, not defense-by-measurement.

## Verdict Justification

**REVISE**. Escalated to ADVERSARIAL mode after the BLOCKER (§14 div-by-zero) and 3 CRITICALs surfaced in Phase 2. Escalation surfaced Finding 3 (silent 100%) and Finding 2 (hallucination reward) — both directly attack the product's core thesis of "정량 · 근거 기반 적합도". Realist Check: no CRITICAL was downgraded — every one has a concrete failure scenario reachable through the public API with no exotic conditions. Finding 5 (Gemini training) was pressure-tested against the "dummy data only" scope note; it survives at CRITICAL because the SPEC's target audience is exactly the population (interviewers) that WILL run the app with real data. Finding 6 (`is_current` race) was pressure-tested against SQLite's single-writer property; it survives because SQLite serializes writes but does NOT serialize the read-modify-write pattern across two Python-level requests inside the same process — SQLAlchemy default isolation is `deferred`, not `immediate`.

**What would move this to ACCEPT**: Findings 1-6 MUST be addressed in SPEC text before ANY code is written. Findings 7-13 can be folded into their PLAN phases as new checkboxes. Finding 14 is polish and can wait.

## Open Questions (unscored)

- SPEC §12: LLM temperature=0.2 for stability — but Gemini's `application/json` mime with a `response_schema` may need `temperature=0.0` to avoid schema-drift retries. Worth an empirical bench before Phase 8.
- Is `gemini-3.6-flash` (§15) actually the current model id as of 2026-08-19, or a placeholder? Verify against Google's live model catalog in Phase 8.
- SPEC §11 mixes vocabulary: `verdict: met/partial/missing/unknown` for requirements, `verdict: have/partial/missing/unknown` for tech. Deliberate signal (met is subjective, have is objective) or oversight? Consider unifying — reduces prompt & UI branching.
- SPEC §17 delete order (DB then FS) accepts orphan files. If no periodic sweep is planned, upload dir grows monotonically. Not a bug for personal-use MVP, but earns a `TODO(cleanup)` in code.
- SPEC §11 `overall_score` example is 74.5 but weights would produce `78*0.30 + 70*0.35 + 82*0.20 + 90*0.10 + 40*0.05 = 76.3`, not 74.5. Illustrative only, but the example values don't self-consistency-check — worth aligning so a reader can hand-verify the formula from §14 against the §11 example.

---
*Not a ralplan output — this is a SPEC review. Ralplan gates not applicable.*

---

# Decision Log (author response, 2026-08-19)

| # | Severity | Decision | Where Reflected |
|---|---|---|---|
| 1 | BLOCKER | **ACCEPT** | SPEC §14 (empty-list rule + weight renormalization) · PLAN Phase 7 tests |
| 2 | CRITICAL | **ACCEPT** | SPEC §13.3 (verification-fail → `missing`, not `unknown`) · PLAN Phase 5 tests |
| 3 | CRITICAL | **ACCEPT** | SPEC §11 (matches must cover every job_id) · SPEC §14 (backend backfill) · PLAN Phase 7 tests |
| 4 | CRITICAL | **ACCEPT** | SPEC §12 (SSRF hardening: scheme/private-IP/redirect/timeout/size caps) · SPEC §18 · PLAN Phase 6 tests |
| 5 | CRITICAL | **ACCEPT** | SPEC §18 (3rd-party data-flow section) · SPEC §5 acceptance criterion · README banner · `.env.example` MOCK_MODE=true default |
| 6 | CRITICAL | **ACCEPT (alternative)** | Drop `is_current` boolean; derive current profile via `ORDER BY created_at DESC LIMIT 1`. SPEC §8 updated |
| 7 | MAJOR | **ACCEPT** | SPEC §8 (ON DELETE CASCADE on fit_analyses; RESTRICT on referenced career_documents via app-level check) · PLAN tests |
| 8 | MAJOR | **ACCEPT** | SPEC §15 (add effective_mode=MOCK health example) · SPEC §6 (ModeBadge renders from effective_mode; distinct "MOCK (auto)" state) |
| 9 | MAJOR | **ACCEPT (PARTIAL)** | SPEC §13.2 (NFC + whitespace/punct strip + Korean particle strip) · min quote length 10 (looser than critic's 15 for short Korean quotes) · PLAN tests |
| 10 | MAJOR | **ACCEPT** | SPEC §14 (confidence floor 0.1, penalty_reasons in API response) · PLAN test |
| 11 | MAJOR | **ACCEPT** | SPEC §8 (DateTime(timezone=True), UTC-aware) · SPEC §11 example updated to `Z` · PLAN test |
| 12 | MAJOR | **ACCEPT** | SPEC §19 (UNIQUE(career_profile_id, job_posting_id) + 409) · PLAN test |
| 13 | MAJOR | **ACCEPT** | PLAN Phase 3/6/7 explicit new tests + new **Phase 7.5 — Security & Edge Cases** block |
| 14 | MINOR | **ACCEPT** | Weight sum validation + rounding to 1 decimal · CORS default list (5173-5175) · SPEC §14/§18 |

## Ambiguities / Missing (author response)

| Item | Decision |
|---|---|
| Job-posting file storage table | **ACCEPT**: `job_postings.stored_path` column added; sanitize path same as career_documents. §8 updated. |
| Replace-document atomicity | **ACCEPT**: write new file → update DB row (atomic single UPDATE) → delete old file. On DB failure the new file is garbage-collected on next request via orphan sweep helper. |
| Analyzer factory cache invalidation | **ACCEPT**: cache key = (provider, api_key). Key change ⇒ new entry. `reset_client_cache()` exposed for tests. Documented in §22. |
| evidence_ids referencing non-existent ev_x | **ACCEPT**: post-validation cross-check; unknown ids are treated as no evidence (per Finding 2 rules). SPEC §13.4 note. |
| Rate-limit / quota | **REJECT for MVP** (single-user local, keep as `TODO(quota)` in code + Future Extension note in §21). |
| File-size chain | **ACCEPT**: check Content-Length header first when present; then stream-limit reads. Reject before full memory load. §18 clarified. |
| Uploads sweep | **REJECT for MVP** (personal use; add `TODO(cleanup)` comment). §21 addition. |
| §17 kind set clarity | **ACCEPT**: `career_documents.kind` restricted to `resume/career_desc/portfolio`; job posting files stored via `job_postings.stored_path` (never in career_documents). §8 + §17 clarified. |
| §9 evidence_ids REQUIRED | **ACCEPT**: schema makes evidence_ids required list (may be empty). Prompt requires ≥1 evidence for any non-`unknown` verdict. |
| §15 fallback warning surfacing | **ACCEPT**: health response includes `effective_mode` + `fallback_reason` string when they differ. |
| §11 verdict vocab unification | **ACCEPT**: unify to `met / partial / missing / unknown` across all dimensions (drop tech's `have`). Cleaner API + UI. |
| §11 example number mismatch | **ACCEPT**: example numbers recomputed. |
| Gemini model id `gemini-3.6-flash` | **ACCEPT as verification checkpoint**: verify current model catalog before Phase 8 (Live provider phase). Placeholder OK for MVP; note in PLAN Phase 8. |
| Weight sum floating-point | **ACCEPT**: settings loader validates `abs(sum - 1) < 1e-6` at boot. |
| Verdict boundary FP drift | **ACCEPT**: round `overall_score` to 1 decimal before threshold compare. |
| CORS port | **ACCEPT**: `CORS_ALLOW_ORIGINS` default `["http://localhost:5173","http://localhost:5174","http://localhost:5175"]`. |

## Multi-Perspective response
- Executor sanitize whitelist: **ACCEPT** → SPEC §18 lists `[A-Za-z0-9._가-힣\-]+`, others → `_`, max 200 chars after NFC.
- Skeptic Fuzzy matching: **REJECT** (keep substring + strict normalization). Rationale: cross-language substring with NFC + particle strip covers realistic Gemini paraphrase (§13.2 tests will bench). Fuzzy is not free — it moves the failure mode from false-negative (visible: `verified=false`) to false-positive (invisible: hallucination passes). We keep visible failures.
- Stakeholder / Realist: acknowledged. Findings 1–6 are BLOCKERs for portfolio credibility.

## Open Questions (author response)
- LLM temperature: **ACCEPT** → PLAN Phase 8 adds an empirical check step: try temp 0.2 first, drop to 0.0 if `application/json` mime causes retries.
- Vocabulary unification (met/have): resolved above.
- SPEC §17 orphan sweep: `TODO(cleanup)` deferred to §21 Future Extension.
- SPEC §11 example numbers: fixed in this pass.
