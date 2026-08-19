# CareerFit — Implementation Plan

**Version**: 0.2.0  (Grill Me #1 반영본)
**Date**: 2026-08-19
**Related SPEC**: [`docs/superpowers/specs/2026-08-19-career-fit-design.md`](../specs/2026-08-19-career-fit-design.md) v0.2.0
**Related Review**: [`docs/reviews/2026-08-19-design-review.md`](../../reviews/2026-08-19-design-review.md)

> 이 문서는 진행 상태판(state board)이다.
> 항목 하나가 끝날 때마다 `[ ]` → `[x]` 로 즉시 갱신하고 commit 에 포함한다.
> 세션이 끊기면 다음 세션의 Claude 는 이 문서만 읽고 이어서 작업한다.

---

## Current Status

- **Current Phase**: Phase 4 진입 대기 (Analyzer Factory + Mock)
- **Last Completed**: Phase 3 Career Documents. **26/26 pytest green**. Persistence 검증됨.
- **Currently Working On**: (다음) `services/analyzer_factory.py` + `providers/mock.py`
- **Next**: Phase 4 (analyzer_factory + mock provider + client cache) → Phase 5 (Career Profile)
- **Known Issues**: 없음. Test infra 로 in-memory SQLite `StaticPool` 사용 (여러 connection 이 같은 DB 공유).

---

## Definition of Done (모든 항목 공통)

한 항목을 `[x]` 처리하려면 다음 중 해당되는 것을 모두 충족해야 한다.

1. 코드 구현
2. 기본 error handling
3. SPEC 이 선언한 invariant 하나당 최소 1개의 테스트 존재 (Finding 13)
4. 해당 테스트가 통과 (`pytest`, `npm run test:run`)
5. 실행 검증 (실제 uvicorn/npm run dev 로 손 확인 또는 통합 테스트)
6. SPEC 과 어긋난다면 SPEC 도 함께 갱신
7. 논리적 checkpoint 라면 Git commit + push (인증 가능한 경우)

---

## Phase 0 — Foundation & Design

- [x] AiDoc-past / DocAi 참고 프로젝트 분석 (models, services, factories, api client)
- [x] SPEC 초안 작성 (v0.1.0)
- [x] PLAN 초안 작성 (v0.1.0)
- [x] Grill Me #1 (design review) → `reviews/2026-08-19-design-review.md`
- [x] Grill Me findings 분류 (ACCEPT/PARTIAL/REJECT) → review 파일 하단
- [x] SPEC v0.2.0 반영 (14 findings + ambiguities + open questions)
- [x] PLAN v0.2.0 반영 (이 파일)

---

## Phase 1 — Repo Skeleton

- [x] `C:\portf\CareerFit` git init (branch=main, user.email/name 설정)
- [x] `.gitignore` (uploads/, *.db, .env, .venv, node_modules, dist, __pycache__, .pytest_cache, coverage 등)
- [x] `.env.example` (MOCK_MODE=**true**, LLM_PROVIDER=gemini, keys empty, MAX_UPLOAD_BYTES=20MB, MAX_URL_BYTES=2MB, CORS 5173-5175, weight override 주석)
- [x] Root `README.md` skeleton (Run / Mock / Live / Test / **3rd-party data flow disclosure** 섹션)
- [x] Backend 프로젝트 뼈대 (`backend/pyproject.toml`, `backend/app/__init__.py`, `backend/app/main.py` health endpoint 만)
- [x] Frontend 프로젝트 뼈대 (`frontend/package.json`, `vite.config.ts`, `tailwind.config.js`, `postcss.config.js`, `index.html`, `src/main.tsx`, `src/index.css`, tsconfig 2개, setup.ts, vite-env.d.ts)
- [x] `docs/` 링크 유효성 확인 (SPEC / PLAN / Review 상호 참조 OK)
- [x] Python 파일 syntax 검증 (`ast.parse` 전체 통과)
- [x] 첫 commit: `b716eac` — chore: bootstrap CareerFit skeleton (spec v0.2 + plan v0.2 + empty frontend/backend)
- [x] GitHub repo 생성: https://github.com/bja001219/CareerFit (public)
- [x] `git push -u origin main` 성공
- [x] Session Handoff 갱신

## Phase 2 — Backend Foundation

- [x] `app/config.py` (Settings dataclass + env, `mode`/`effective_mode`/`active_provider`/`active_model`/`fallback_reason` derivations)
- [x] `app/config.py` — weight-sum-to-1 boot validation (raises `ConfigurationError`)
- [x] `app/database.py` (SQLAlchemy engine + Base + `init_db`, PRAGMA foreign_keys=ON, uploads dir auto-create)
- [x] `app/models/career_document.py` (Unique kind, `DateTime(timezone=True)`)
- [x] `app/models/career_profile.py` (**is_current 없음** — created_at DESC 로 유도)
- [x] `app/models/job_posting.py` (source_type/stored_path 포함)
- [x] `app/models/fit_analysis.py` (UNIQUE(profile_id, posting_id), ON DELETE CASCADE FKs)
- [x] `app/models/errors.py` (10 typed errors with status codes)
- [x] `app/schemas/health.py` — Phase 2 만 health 응답. Career/Job/Fit 스키마는 각 Phase 에서 추가.
- [x] `app/api/health.py` (`/api/health` returns mode/effective_mode/provider/model/fallback_reason)
- [x] `app/api/errors.py` (global exception → JSON, no stack trace, DuplicateAnalysisError 는 existing_id 함께 반환)
- [x] `app/main.py` (`create_app()` factory + CORS from env list + include_router + lifespan)
- [x] pytest 세팅 (`conftest.py` — env 격리, in-memory DB 오버라이드, TestClient fixture)
- [x] `test_health_default_is_mock` 통과
- [x] `test_health_reports_effective_mock_when_key_missing` 통과
- [x] `test_health_reports_live_when_key_present` 통과
- [x] `test_default_settings_construct_without_error` 통과
- [x] `test_config_rejects_weights_not_summing_to_one` 통과
- [x] `test_config_accepts_explicit_weight_override_that_still_sums` 통과
- [x] `test_active_model_reflects_effective_mode` 통과
- [x] venv 생성 + `pip install -e ".[dev]"` 성공 (fastapi 0.141, pydantic 2.13, sqlalchemy 2.0.52, pytest 9.1.1 등)
- [x] `init_db()` 검증: 4 테이블 생성 확인, uploads/{career/{resume,career_desc,portfolio},job} 자동 생성 확인
- [x] `pyproject.toml` fix: `readme = "../README.md"` 제거 (setuptools 가 backend 밖 파일 접근 거부)
- [ ] commit: `feat(backend): scaffolding + health endpoint with effective_mode reporting`

## Phase 3 — Career Documents (Persistence + Security)

- [x] `services/document_service.py` — save + extract text (PDF / DOCX / TXT)
- [x] `services/document_service.py` — sanitize whitelist `[A-Za-z0-9._가-힣\-]+`, NFC, 200 chars max
- [x] `services/document_service.py` — cross-platform path-traversal 방지 (`/` + `\\` 분리 + `is_relative_to`)
- [x] `services/document_service.py` — size guard + MIN_EXTRACTED_CHARS 200 (scanned PDF 자동 거부)
- [x] `services/document_service.py` — `save_job_posting_pdf` (Phase 6 대비 helper 미리 배치)
- [x] `services/document_service.py` — `replace_document_atomic` helper (DB 커밋 후 old file unlink)
- [x] `api/career_documents.py` — POST /api/career/documents (unique(kind) enforced by delete+insert)
- [x] `api/career_documents.py` — GET /api/career/documents
- [x] `api/career_documents.py` — DELETE with `?force=true` (block if referenced by profile)
- [x] `api/career_documents.py` — POST /api/career/documents/{id}/replace (atomic §17)
- [x] Sample fixtures: in-memory `make_minimal_pdf` / `make_minimal_docx` / `make_minimal_txt` in conftest — no binary blobs committed
- [x] `test_upload_document_persists_and_extracts` PDF/DOCX/TXT (3 케이스)
- [x] `test_upload_rejects_scanned_pdf`
- [x] `test_upload_rejects_unknown_extension`
- [x] `test_upload_rejects_over_size_limit`
- [x] `test_upload_rejects_bad_kind`
- [x] `test_sanitize_filename_blocks_path_traversal` (3 케이스: `/`, `\\`, mixed)
- [x] `test_sanitize_filename_preserves_korean`
- [x] `test_sanitize_filename_caps_length` (200 chars)
- [x] `test_sanitize_filename_returns_default_for_empty`
- [x] `test_list_documents_returns_all_kinds`
- [x] `test_upload_replaces_previous_of_same_kind` (unique(kind) 검증)
- [x] `test_delete_removes_row_and_file`
- [x] `test_delete_missing_returns_404`
- [x] `test_delete_referenced_career_document_blocked` (Finding 7)
- [x] `test_delete_referenced_career_document_forced_marks_orphan` (Finding 7)
- [x] `test_replace_document_atomic_success`
- [x] `test_upload_survives_restart` — 별도 file-backed SQLite 로 process boundary 시뮬레이션
- [x] Fixture 인프라 fix: in-memory SQLite 는 `StaticPool` 사용해야 여러 connection 이 같은 DB 공유
- [x] Fixture 인프라 fix: `tmp_uploads_root` fixture 로 uploads 를 tmp_path 로 격리
- [ ] commit: `feat(backend): persistent career documents with pdf/docx/txt extraction + security`

## Phase 4 — Analyzer Factory + Mock

- [ ] `services/providers/base.py` — Analyzer Protocol (Career/Job/Fit) + json helpers
- [ ] `services/providers/mock.py` — 결정론 Career / Job / Fit mock (realistic dummy)
- [ ] `services/analyzer_factory.py` — build_career / build_job / build_fit
- [ ] `services/analyzer_factory.py` — mock fallback + client cache (key = (provider, api_key)) + `reset_client_cache()`
- [ ] `services/analyzer_factory.py` — fallback 시 `settings.compute_fallback_reason()` 로 사유 계산
- [ ] `test_analyzer_factory_returns_mock_when_mock_mode`
- [ ] `test_analyzer_factory_falls_back_when_missing_key_with_reason`
- [ ] `test_gemini_client_cached_per_key`
- [ ] `test_reset_client_cache_forces_new_client`
- [ ] commit: `feat(backend): analyzer factory with mock fallback and cache invalidation`

## Phase 5 — Career Profile

- [ ] `prompts/career_profile.txt` (§13.1 하드 규칙 명시: evidence_ids 필수, 없는 것 조작 금지)
- [ ] `services/text_normalize.py` (NFC + whitespace/punctuation strip + Korean particle strip)
- [ ] `services/evidence_matcher.py` (substring + normalize; min-length 10 chars post-normalize)
- [ ] `services/career_analyzer.py` (facade → provider)
- [ ] `api/career_profile.py` — POST /api/career/profile/build
- [ ] `api/career_profile.py` — GET /api/career/profile (latest via created_at DESC)
- [ ] `api/career_profile.py` — GET /api/career/profile/history
- [ ] `test_career_profile_mock_build`
- [ ] `test_career_profile_evidence_verified`
- [ ] `test_career_profile_unverified_evidence_marked`
- [ ] `test_career_profile_evidence_ids_referencing_missing_index_ignored`
- [ ] `test_career_profile_persistence`
- [ ] `test_get_current_profile_returns_latest`
- [ ] `test_evidence_matcher_substring_hit`
- [ ] `test_evidence_matcher_survives_whitespace_variation`
- [ ] `test_evidence_matcher_survives_hangul_latin_swap`
- [ ] `test_evidence_matcher_strips_korean_particles`
- [ ] `test_evidence_matcher_rejects_too_short_quote`
- [ ] `test_evidence_matcher_nfc_normalizes`
- [ ] commit: `feat(backend): career profile structuring + evidence verification (Korean-aware)`

## Phase 6 — Job Posting

- [ ] `services/url_extractor.py` (SSRF hardened per §12)
  - [ ] scheme allow-list (http/https)
  - [ ] IPv4 private-range block
  - [ ] IPv6 private-range block
  - [ ] port allow-list (80/443/8080/8443)
  - [ ] `allow_redirects=False` + manual re-check, max 3 hops
  - [ ] connect+read timeout 5s
  - [ ] MAX_URL_BYTES streaming cap
- [ ] `services/job_analyzer.py` (facade → provider)
- [ ] `prompts/job_posting.txt`
- [ ] `api/job_posting.py` — POST (text)
- [ ] `api/job_posting.py` — POST (url)
- [ ] `api/job_posting.py` — POST (pdf multipart, uses shared file/sanitize helpers)
- [ ] `api/job_posting.py` — GET (list, detail)
- [ ] `api/job_posting.py` — DELETE
- [ ] `test_job_posting_from_text`
- [ ] `test_job_posting_from_pdf`
- [ ] `test_job_posting_from_url_success` (fake requests session)
- [ ] `test_job_posting_from_url_failure_returns_400`
- [ ] `test_url_extractor_rejects_localhost`
- [ ] `test_url_extractor_rejects_private_ip_v4`
- [ ] `test_url_extractor_rejects_private_ip_v6`
- [ ] `test_url_extractor_rejects_non_http_scheme`
- [ ] `test_url_extractor_rejects_odd_port`
- [ ] `test_url_extractor_rechecks_redirects`
- [ ] `test_url_extractor_enforces_size_cap`
- [ ] `test_job_posting_persistence`
- [ ] commit: `feat(backend): job posting ingestion (text/pdf/url) with SSRF-hardened extractor`

## Phase 7 — Fit Analysis + Scoring

- [ ] `prompts/fit_analysis.txt` (matches 커버리지 강제 · evidence_ids 강제 · unknown 은 admit 만)
- [ ] `services/score_calculator.py`
  - [ ] `dim_score(matches)` — empty list → None
  - [ ] `experience_score(actual, req_min, req_max)` — None 가드
  - [ ] `overall(dims)` — present 만 renormalize
  - [ ] `verdict(overall)` — 반올림 1 decimal · thresholds
  - [ ] `compute_confidence(llm_conf, unknown_ratio, verified_ratio)` — floor 0.1 + penalty_reasons
- [ ] `services/fit_analyzer.py`
  - [ ] LLM 응답 수신 → §11 스키마 검증
  - [ ] backend backfill (posting 리스트 커버리지 강제)
  - [ ] evidence cross-check + §13.3 verdict downgrade 규칙
  - [ ] score_calculator 실행 → 완성된 analysis_json 저장
- [ ] `api/fit_analysis.py` — POST /api/fit/analyze
  - [ ] Duplicate 조합 → 409 DuplicateAnalysisError with existing_id
- [ ] `api/fit_analysis.py` — GET /api/fit/analyses (list, limit)
- [ ] `api/fit_analysis.py` — GET /api/fit/analyses/{id}
- [ ] `api/fit_analysis.py` — DELETE /api/fit/analyses/{id}
- [ ] `test_fit_analysis_mock_dimensions_present`
- [ ] `test_fit_analysis_backfills_missing_requirement_ids`
- [ ] `test_fit_analysis_fabricated_evidence_downgrades_to_missing_not_unknown`
- [ ] `test_fit_analysis_unknown_verdict_only_when_llm_admits`
- [ ] `test_fit_analysis_requirement_dim_empty_list_is_None`
- [ ] `test_fit_analysis_preferred_dim_empty_list_is_None`
- [ ] `test_fit_analysis_tech_dim_empty_list_is_None`
- [ ] `test_fit_analysis_overall_when_dimension_is_None_renormalizes_weights`
- [ ] `test_fit_analysis_overall_all_None_returns_None_and_verdict_insufficient`
- [ ] `test_fit_analysis_overall_score_calculation` (§14.6 예시 hand-verify)
- [ ] `test_fit_analysis_verdict_thresholds` (경계 84.9 / 85.0 / 85.1)
- [ ] `test_fit_analysis_unknown_vs_missing_scores_differ`
- [ ] `test_fit_analysis_experience_below_min`
- [ ] `test_fit_analysis_experience_above_max`
- [ ] `test_fit_analysis_experience_no_requirement_returns_None`
- [ ] `test_fit_analysis_confidence_penalty_compounds_with_floor_and_reasons`
- [ ] `test_fit_analysis_duplicate_returns_409_with_existing_id`
- [ ] `test_delete_analysis_history`
- [ ] `test_cascade_delete_job_posting_removes_analyses`
- [ ] commit: `feat(backend): fit analysis with backend-computed overall score and evidence-guarded verdicts`

## Phase 7.5 — Security & Edge Cases (Finding 13)

- [ ] `test_created_at_is_utc_and_tz_aware`
- [ ] `test_config_rejects_weights_not_summing_to_one`  (already Phase 2, verify)
- [ ] `test_url_extractor_all_ssrf_cases_covered` (integration coverage check)
- [ ] `test_upload_rejects_path_traversal_filename` (already Phase 3, verify)
- [ ] `test_replace_document_atomic_rollback_on_db_failure` (already Phase 3, verify)
- [ ] Manual: git-secrets scan on final commit
- [ ] Manual: no PII in tests fixtures (dummy names only)
- [ ] Manual: `.env` never staged
- [ ] commit: `test: security & edge-case gap coverage`

## Phase 8 — Live Providers (opt-in)

- [ ] Verify current Gemini model id (`gemini-3.6-flash` vs latest) against Google AI Studio catalog before implementation
- [ ] `services/providers/gemini.py` (google-genai, response_mime application/json, temperature=0.2 initial; test 0.0 if schema drift)
- [ ] `services/providers/openai.py` (openai SDK v1, response_format=json_object)
- [ ] `test_live_provider_returns_bad_json_raises_analysis_failed` (fake client)
- [ ] `test_live_provider_missing_key_falls_back_to_mock` (integration)
- [ ] Manual: at least one real Gemini call with dummy fixture (`.env.example` shows how)
- [ ] Empirical: if `application/json` mime causes schema-drift retries, lower to temperature=0.0 and update SPEC §12
- [ ] commit: `feat(backend): live providers (gemini/openai) with typed errors`

## Phase 9 — Frontend Foundation

- [ ] Tailwind + Vite 세팅 (indigo/violet 팔레트)
- [ ] `src/lib/types.ts` (Career / Job / Fit + Health 응답)
- [ ] `src/lib/api.ts` (typed fetch client, 4xx JSON error parsing)
- [ ] `src/components/Layout.tsx`
- [ ] `src/components/ModeBadge.tsx` — **`effective_mode` 기반**, "MOCK / MOCK (auto) / LIVE · Provider" 3상태
- [ ] `src/components/DataFlowNotice.tsx` — LIVE 시 상단 지속 배너 + provider별 정책 링크
- [ ] `src/components/ErrorBanner.tsx` / `Spinner.tsx` / `EmptyState.tsx`
- [ ] `App.tsx` — React Router (4 routes)
- [ ] Vitest 세팅 (`vitest.config.ts`, `src/setup.ts`)
- [ ] `test_ModeBadge_shows_mock_state`
- [ ] `test_ModeBadge_shows_auto_fallback_state_with_reason`
- [ ] `test_ModeBadge_shows_live_state_with_provider`
- [ ] `test_DataFlowNotice_only_renders_in_live`
- [ ] `test_api_ts_parses_4xx_json_error`
- [ ] commit: `feat(frontend): scaffolding + api client + effective_mode aware badge`

## Phase 10 — Career Profile UI

- [ ] `pages/CareerPage.tsx` — 3 dropzone (resume/career_desc/portfolio) + 목록
- [ ] `components/FileDropzone.tsx` (accept / reject / size limit)
- [ ] `components/CareerProfileCard.tsx` — evidence verified=false 회색
- [ ] "Build Profile" 버튼 → POST /career/profile/build → 결과 노출
- [ ] `test_CareerProfileCard_renders_skills`
- [ ] `test_CareerProfileCard_marks_unverified_evidence_gray`
- [ ] `test_FileDropzone_rejects_wrong_extension`
- [ ] commit: `feat(frontend): career profile management UI`

## Phase 11 — Job Posting UI

- [ ] `pages/JobNewPage.tsx` — 3-mode input (URL / text / PDF) 탭
- [ ] URL 실패 시 UX (에러 배너 + 텍스트/PDF 로 전환 유도 힌트)
- [ ] `components/JobPostingCard.tsx`
- [ ] `test_JobNewPage_submits_text_to_api`
- [ ] `test_JobNewPage_shows_url_extraction_error_hint`
- [ ] commit: `feat(frontend): job posting input`

## Phase 12 — Analysis Result UI

- [ ] `pages/AnalysisPage.tsx`
- [ ] `components/FitScoreCard.tsx` (overall + 5 dim; **N/A 렌더링 지원**)
- [ ] `components/RequirementMatchTable.tsx` (met/partial/missing/unknown 4상태)
- [ ] `components/TechStackChips.tsx` (통일된 vocab)
- [ ] `components/EvidenceList.tsx` (verified=false 회색)
- [ ] `components/StrengthList.tsx` / `GapList.tsx`
- [ ] `components/ApplicationStrategyCard.tsx`
- [ ] `components/ConfidenceCard.tsx` — confidence + penalty_reasons 리스트
- [ ] Duplicate 분석 요청 시 409 → 기존 결과 페이지로 redirect 처리
- [ ] `test_FitScoreCard_renders_fit_verdict_color`
- [ ] `test_FitScoreCard_renders_NA_for_null_dim`
- [ ] `test_RequirementMatchTable_renders_all_four_verdicts`
- [ ] `test_EvidenceList_marks_unverified_gray`
- [ ] `test_ConfidenceCard_renders_penalty_reasons`
- [ ] commit: `feat(frontend): fit analysis result UI (N/A dims + evidence + confidence reasons)`

## Phase 13 — Dashboard / History UI

- [ ] `pages/Dashboard.tsx` — career profile 상태 + 최근 분석 5개 + 통계
- [ ] `api/history` 연결
- [ ] 항목 클릭 → `/analysis/:id`
- [ ] 항목 삭제
- [ ] `test_Dashboard_renders_empty_state`
- [ ] commit: `feat(frontend): dashboard and history`

## Phase 14 — Grill Me #2 (Backend + Full-stack review)

- [ ] 리뷰 관점: 파일 영속성 / DB 트랜잭션 / 잘못된 파일 / URL 실패 / API 키 노출 / LLM 실패 / structured output parsing / retry / timeout / score 검증 / 중복 요청 / evidence verify robustness / 실제 UI 접근성
- [ ] `reviews/2026-08-19-backend-review.md` 작성
- [ ] Issue ACCEPT/PARTIAL/REJECT 분류
- [ ] 필요한 수정 반영 (SPEC / PLAN / 코드)
- [ ] 관련 테스트 통과
- [ ] commit: `fix: address backend review findings`

## Phase 15 — End-to-End Mock 검증

- [ ] Backend `pytest` 전부 green (45+)
- [ ] Frontend `npm run test:run` 전부 green (12+)
- [ ] `npm run build` 성공
- [ ] `uvicorn` 부팅 → `/api/health` 200
- [ ] `npm run dev` 로 브라우저 실제 흐름
  - [ ] 3개 문서 업로드
  - [ ] Career Build → CareerProfile 표시
  - [ ] Job (text) 입력 · 이어서 URL(로컬호스트) 실패 UX 확인
  - [ ] Fit → 결과 페이지 (overall_score 손 계산 값과 일치 확인)
  - [ ] 같은 조합 재요청 → 409 → 기존 결과로 redirect
  - [ ] Dashboard → 이력 표시 → 상세 재조회
  - [ ] `MOCK_MODE=false, LLM_PROVIDER=gemini, GEMINI_API_KEY=` → 배지 "MOCK (auto)" 확인
  - [ ] uvicorn 재시작 → 상태 유지
- [ ] commit: `test: verify end-to-end mock mode workflow`

## Phase 16 — Grill Me #3 (Final)

- [ ] 면접관 관점 최종 리뷰
- [ ] `reviews/2026-08-19-final-review.md` 작성
- [ ] BLOCKER / CRITICAL 수정
- [ ] README 최종본 (배지, 실행법, mock/live, test, security note, **data-flow disclosure**)
- [ ] 이 PLAN 최종 갱신
- [ ] commit: `docs: finalize CareerFit MVP`
- [ ] `git push`

---

## Decision Log

- **2026-08-19** SPEC v0.1.0 확정. Overall score = backend 결정론 계산.
- **2026-08-19** 사용자 결정: 위치=`C:\portf\CareerFit`, git remote=GitHub 생성 후 push, 검증=sample dummy Mock only.
- **2026-08-19** Grill Me #1: 14 findings 전부 ACCEPT (1 은 대안, 1 은 PARTIAL). SPEC v0.2.0, PLAN v0.2.0.
- **2026-08-19** REJECT: (a) MVP rate-limit — 단일 사용자. (b) Uploads periodic sweep — 개인 사용. (c) fuzzy match — false-positive 리스크 (hallucination 방어 훼손). 셋 모두 §21 Future Extension.

---

## Session Handoff

> 세션이 끊기면 다음 Claude 가 이 섹션만 봐도 이어서 작업할 수 있어야 한다.

### Last Updated

2026-08-19 (Phase 3 완료 직후)

### Current Phase

Phase 4 — Analyzer Factory + Mock.

### Last Completed Task

- [x] Phase 3 Career Documents 전체
- [x] 26/26 pytest green (health 3 + config 4 + career_docs 19)
- [x] Test infra 개선: `StaticPool` in-memory SQLite, `tmp_uploads_root`, in-memory PDF/DOCX/TXT 생성기

### Next Task

- [ ] `backend/app/services/providers/base.py` (Analyzer Protocol — Career/Job/Fit)
- [ ] `backend/app/services/providers/mock.py` (결정론 sample 응답)
- [ ] `backend/app/services/analyzer_factory.py` (build_career/build_job/build_fit + fallback + client cache)
- [ ] 4개 pytest:
  - `test_analyzer_factory_returns_mock_when_mock_mode`
  - `test_analyzer_factory_falls_back_when_missing_key_with_reason`
  - `test_gemini_client_cached_per_key`
  - `test_reset_client_cache_forces_new_client`
- [ ] commit: `feat(backend): analyzer factory with mock fallback and cache invalidation`

### Important Decisions (요약)

- SQLite + `backend/careerfit.db`
- 업로드는 filesystem `backend/uploads/{career|job}/…`
- 메타데이터·구조화 JSON 은 DB, datetime 은 UTC-aware
- Overall score = backend `score_calculator`, empty dim 은 `None` + renormalize
- Verification-fail 은 `missing` 으로 강등 (unknown 은 LLM admit 만)
- Analyzer 3분할 (Career / Job / Fit) — 실패 격리
- Mock 자동 fallback 은 `.env` 설정 조건만 (사용자 요청 실패에는 X)
- Provider: Gemini 우선, OpenAI 옵션. `.env.example` 기본은 `MOCK_MODE=true`
- URL extractor 는 SSRF hardened (scheme/private-IP/port/redirect/timeout/size)
- Fit analyze 는 UNIQUE(profile_id, posting_id) — 중복은 409
- `is_current` boolean 없음 (created_at DESC LIMIT 1)

### Known Issues

- 아직 코드가 없어 Known Issue 없음. Phase 진행 중 발견되는 것은 여기에 append.

### Files Recently Changed

- `docs/superpowers/specs/2026-08-19-career-fit-design.md` (v0.2.0)
- `docs/superpowers/plans/2026-08-19-career-fit.md` (v0.2.0 — 이 파일)
- `docs/reviews/2026-08-19-design-review.md` (Decision Log append)

### Git

- Local repo: `C:\portf\CareerFit` (branch `main`)
- Remote: https://github.com/bja001219/CareerFit (public)
- Latest commit: `b716eac` chore: bootstrap CareerFit skeleton
- GitHub CLI 인증 확인됨 (계정: bja001219, token scope: repo/workflow OK)

### Resume 명령어 (개발 재개용)

```powershell
# 현재 상태 확인
cd C:\portf\CareerFit
git status
git log --oneline -10

# 다음 PLAN 항목 확인
code docs/superpowers/plans/2026-08-19-career-fit.md

# Backend 개발
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000

# Frontend (새 창)
cd C:\portf\CareerFit\frontend
npm install
npm run dev

# 접속
# http://localhost:5173  (Frontend)
# http://localhost:8000/docs  (Swagger)
```
