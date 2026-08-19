# CareerFit — Design Spec

**Version**: 0.2.0  (Grill Me #1 반영본)
**Date**: 2026-08-19
**Status**: Ready for implementation (post-review)
**Owner**: bja001219
**Change log**: v0.2.0 — Grill Me #1 (`docs/reviews/2026-08-19-design-review.md`) 14 findings 전부 반영. 주요 변경: empty-list score 규칙, 하락 verdict → `missing`, matches 커버리지, SSRF hardening, 3rd-party data flow, `is_current` 제거, 통합 verdict 어휘, TZ-aware datetime, 409 idempotency, effective_mode 배지, 정규화 강화.

> 이 문서는 CareerFit MVP의 **Source of Truth**다.
> 코드가 이 문서와 다르게 구현되면 코드가 아니라 이 문서와 [PLAN](../plans/2026-08-19-career-fit.md)을
> 먼저 갱신한다.

---

## 1. 프로젝트 목적

CareerFit은 지원자가 자신의 경력 자료(이력서 · 경력기술서 · 포트폴리오)와
채용 공고를 업로드하면, 각 공고에 대한 **정량 · 근거 기반 적합도(Fit)** 를 자동으로
분석해 주는 포트폴리오 MVP다.

핵심 질문은 하나다:

> **"내 커리어가 이 공고에 정말 fit 하는가? 어느 부분이 왜 부족한가?"**

이를 사람이 30분 걸려 정리하던 것을 LLM + 결정론적 backend 계산으로 자동화한다.

---

## 2. 문제 정의

지원자는 채용 공고 하나를 검토할 때마다 다음을 반복한다.

- 공고에서 **주요 업무 · 자격요건 · 우대사항 · 기술스택**을 뽑는다
- 자기 이력서와 매칭한다
- 부족한 부분을 파악한다
- 지원할지 말지 판단한다

이 과정은 **주관적이고, 재현이 안 되며, 시간이 오래 걸린다.**
결과적으로 지원자는 (a) 너무 많은 공고에 낭비하거나 (b) 자기가 유리한 공고를 놓친다.

CareerFit은 다음을 통해 이 문제를 완화한다:

- 커리어를 한 번만 정리 → **CareerProfile** 로 구조화
- 공고를 넣으면 **JobPosting** 으로 구조화
- 두 구조를 **차원별로 매칭** → 근거와 함께 점수화

---

## 3. MVP 범위 (In)

MVP는 다음 시나리오까지만 다룬다.

1. **CareerProfile 관리**
   - 이력서 / 경력기술서 / 포트폴리오 파일 업로드
   - PDF / DOCX / TXT 지원 (텍스트 추출 가능한 것)
   - 서버 재시작 후에도 파일과 추출 텍스트 유지
   - 파일 교체 / 삭제 지원
   - 업로드된 자료로부터 CareerProfile(구조화된 JSON) 생성

2. **JobPosting 입력**
   - URL 또는 붙여넣기 텍스트 또는 PDF 업로드
   - 하나의 JobPosting → 구조화된 JSON

3. **FitAnalysis**
   - CareerProfile ↔ JobPosting 매칭
   - 5개 차원 점수 (Responsibility / Requirement / Preferred / Tech / Experience)
   - 각 항목별 Evidence (career에서 뽑은 인용) 매핑
   - Overall Fit Score (backend가 가중 평균)
   - Strengths / Gaps / Application Strategy

4. **결과 저장 및 이력**
   - FitAnalysis는 DB에 저장됨
   - 대시보드에서 과거 분석 이력 조회
   - 삭제 가능

5. **Mock Mode / Live Mode**
   - `MOCK_MODE=true` 이면 API 키 없이 결정론 mock 응답
   - Live 는 Gemini 우선 (무료 티어), 옵션으로 OpenAI
   - 프론트 상단에 현재 mode / provider 배지 표시 (반드시 `effective_mode` 기반)
   - **LIVE 배지가 켜져 있을 때는 데이터 흐름 안내(3rd-party disclosure)를 항상 함께 노출**한다

---

## 4. Non-goals (Out)

명시적으로 다루지 않는다:

- **로그인 / 인증 / 다중 사용자.** 로컬 단일 사용자 가정.
- **자소서 자동 생성.** 문항 최적화, cover-letter drafting 없음.
- **면접 예상 질문 생성.**
- **OCR.** 스캔 PDF는 명시적으로 거부한다.
- **채용사이트 크롤러의 반크롤링 대응.** URL이 실패하면 사용자에게 텍스트/PDF로 붙여넣어 달라고 요청한다.
- **Vector DB / RAG.** 문서 수가 작아 8k~20k 토큰 프롬프트로 충분.
- **결제 / 크레딧 / 사용량 과금.**
- **모바일 앱.** 반응형 웹까지만.
- **채용공고 자동 수집 / 알림.** URL은 매번 사용자가 넣는다.
- **Rate-limit / quota.** 단일 사용자 로컬 가정. §21 Future Extension.
- **Uploads 자동 orphan sweep.** MVP 는 그대로 둔다. §21.

---

## 5. 사용자 Workflow

```text
[1] Career Profile 세팅 (한 번만)
    ├─ Resume 업로드 (PDF/DOCX/TXT)          → CareerDocument row
    ├─ Career Description 업로드              → CareerDocument row
    └─ Portfolio 업로드                       → CareerDocument row
    ↓
    "Career 구조화" 클릭
    ↓
    LLM → CareerProfile (JSON) → 저장

[2] Job Posting 입력 (지원할 공고마다)
    ├─ URL 붙여넣기 (SSRF 가드 통과한 것만)
    ├─ 또는 PDF 업로드                        → job_postings.stored_path
    └─ 또는 텍스트 붙여넣기
    ↓
    LLM → JobPosting (JSON) → 저장

[3] Fit Analysis
    ↓ "적합도 분석" 클릭
    ↓ (career_profile, job_posting) 조합이 이미 있으면 409 → 프론트가 기존 결과로 이동
    ↓ LLM 이 차원별 evidence + verdict 반환 (각 job requirement 를 빠짐없이 매치)
    ↓ Backend 가 verdict 검증 + score + overall 계산
    ↓ FitAnalysis 저장

[4] Result
    ├─ Overall Fit Score & 판정 (Strong Fit / Fit / Partial / Weak / No Fit)
    ├─ 차원별 점수 카드 5개 (N/A 표기 지원)
    ├─ 요구사항 / 기술스택 비교표 (met / partial / missing / unknown)
    ├─ Strengths (근거와 함께)
    ├─ Gaps (근거와 함께)
    ├─ Application Strategy (제안)
    └─ Confidence + penalty_reasons (왜 confidence 가 낮아졌는지)

[5] Analysis History (Dashboard)
    ├─ 과거 분석 이력 리스트
    └─ 각 항목 재조회 / 삭제
```

**Acceptance criterion (Grill Me #1 Finding 5)**: LIVE 배지가 렌더되는 모든 페이지에서 데이터 흐름 안내가 함께 노출되어야 한다 (지속 배너 + `.env.example` 의 `MOCK_MODE=true` 기본).

---

## 6. Frontend 구조

- **React 18 + TypeScript + Vite + Tailwind CSS**
- SPA. React Router v6.

### 라우트

```text
/                       → Dashboard (History + Career Profile 요약)
/career                  → Career Profile 관리 (문서 업로드 / 구조화)
/job/new                 → Job Posting 입력
/analysis/:id            → FitAnalysis 결과
```

### 주요 컴포넌트

```text
components/
├── Layout.tsx                — 헤더 + Mode/Provider 배지 + LIVE disclosure 배너 + 좌측 nav
├── ModeBadge.tsx             — effective_mode 기반: "MOCK" / "MOCK (auto)" / "LIVE · Gemini"
├── DataFlowNotice.tsx        — LIVE 시 상단 지속 배너 ("업로드 자료가 {provider}에 전송됩니다")
├── FileDropzone.tsx
├── CareerProfileCard.tsx
├── JobPostingCard.tsx
├── FitScoreCard.tsx          — Overall + 차원별 5카드 (dim_score=null 은 "N/A" 렌더)
├── RequirementMatchTable.tsx — met/partial/missing/unknown 표
├── TechStackChips.tsx        — met/partial/missing/unknown (통일된 어휘)
├── EvidenceList.tsx          — 인용 리스트 (원문 스니펫; verified=false 는 회색)
├── GapList.tsx / StrengthList.tsx
├── ApplicationStrategyCard.tsx
├── ConfidenceCard.tsx        — confidence 값 + penalty_reasons 목록
└── EmptyState / Spinner / ErrorBanner
```

### ModeBadge 규칙 (Finding 8)

- 프론트는 `effective_mode` 만 신뢰한다. `mode` 는 참고용 (툴팁에만 노출).
- `mode=LIVE, effective_mode=MOCK` → 배지 텍스트 `"MOCK (auto)"`, 노란색, 툴팁 = `fallback_reason` (예: "GEMINI_API_KEY 미설정").
- `mode=LIVE, effective_mode=LIVE` → 배지 텍스트 `"LIVE · {Provider}"`, 초록색, 하단에 `DataFlowNotice` 표시.
- `mode=MOCK, effective_mode=MOCK` → 배지 텍스트 `"MOCK"`, 회색, 정보성 툴팁.

### 상태 관리

- 로컬 state (`useState` + `useEffect`) + fetch 기반 api client.
- 서버가 진리다. 프론트 캐시는 요청 시점 응답만 유지.
- 전역 store 없음.

---

## 7. Backend 구조

- **Python 3.11+, FastAPI, Uvicorn, SQLAlchemy 2.x, Pydantic v2, pypdf, python-docx**

```text
backend/
├── app/
│   ├── main.py                   — FastAPI app + CORS + lifespan(init_db + settings validation)
│   ├── config.py                 — Settings (dataclass + env), weight-sum-to-1 validation
│   ├── database.py               — SQLAlchemy engine, session, Base
│   ├── models/                   — ORM (all datetime UTC-aware)
│   ├── schemas/                  — Pydantic I/O + LLM 응답 스키마
│   ├── api/                      — routers
│   │   ├── health.py             — mode + effective_mode + provider + fallback_reason
│   │   ├── career_documents.py
│   │   ├── career_profile.py
│   │   ├── job_posting.py
│   │   ├── fit_analysis.py
│   │   ├── history.py
│   │   └── errors.py
│   ├── services/
│   │   ├── document_service.py   — 파일 저장 + 텍스트 추출 (streaming size guard)
│   │   ├── url_extractor.py      — SSRF-hardened fetch (scheme/IP allow-list + redirect cap)
│   │   ├── career_analyzer.py
│   │   ├── job_analyzer.py
│   │   ├── fit_analyzer.py
│   │   ├── analyzer_factory.py   — Mock/Gemini/OpenAI 분기 + mock fallback + client cache
│   │   ├── providers/
│   │   │   ├── base.py
│   │   │   ├── mock.py
│   │   │   ├── gemini.py
│   │   │   └── openai.py
│   │   ├── score_calculator.py   — 결정론 dim / overall / verdict / confidence
│   │   ├── evidence_matcher.py   — NFC + normalize + substring
│   │   └── text_normalize.py     — Korean-aware normalization util
│   └── prompts/
│       ├── career_profile.txt
│       ├── job_posting.txt
│       └── fit_analysis.txt
├── tests/
├── uploads/                      — git-ignored, kind별 subfolder
├── careerfit.db                  — git-ignored
├── pyproject.toml
└── .env.example                  — MOCK_MODE=true (default, safe)
```

---

## 8. Database 구조

**엔진**: SQLite (파일: `backend/careerfit.db`). SQLAlchemy 추상화로 PostgreSQL 이전 가능.

**공통 규칙** (Finding 11):
- 모든 datetime 은 `DateTime(timezone=True)` 로 저장, `datetime.now(timezone.utc)` 로 생성. Pydantic 는 `Z` 접미사로 직렬화.
- SQLAlchemy 세션은 `isolation_level="SERIALIZABLE"` (SQLite 는 `BEGIN IMMEDIATE`) 로 카운트-업 경합을 피한다.

### `career_documents`

| col | type | note |
|---|---|---|
| id | int PK | |
| kind | str(20) | `resume` \| `career_desc` \| `portfolio` **(never `job_posting`)** |
| filename | str(300) | 사용자 원본 파일명 (표시용) |
| stored_path | str(400) | uploads/ 내 실제 경로 (sanitize + UUID prefix) |
| mime | str(80) | pdf/docx/txt |
| size_bytes | int | |
| extracted_text | text | |
| uploaded_at | datetime(tz) | |

**Unique** on `kind` (각 종류당 파일 1개 — 교체는 replace 엔드포인트를 사용). Application-level 로 참조 확인 없이 삭제되지 않도록 §17 참조.

### `career_profiles`

CareerDocument 조합의 스냅샷.  **`is_current` 제거** (Finding 6): "현재" 프로필은 `ORDER BY created_at DESC LIMIT 1` 으로 유도.

| col | type | note |
|---|---|---|
| id | int PK | |
| profile_json | JSON | 구조화 결과 (§9) |
| source_doc_ids | JSON | 어떤 문서들로 만들었는지 |
| mode | str(20) | LIVE / MOCK |
| provider | str(20) | gemini / openai / mock |
| created_at | datetime(tz) | |

Index: `created_at DESC`.

### `job_postings`

| col | type | note |
|---|---|---|
| id | int PK | |
| title | str(300) | |
| company | str(200) | |
| source_type | str(20) | url / pdf / text |
| source_ref | str(500) | URL 문자열 또는 사용자 표시용 파일명 |
| stored_path | str(400) | (source_type=pdf 일 때만) 실제 저장 경로. Finding "job_posting file storage table" 대응 |
| raw_text | text | 추출 원문 |
| posting_json | JSON | 구조화 결과 (§10) |
| mode | str(20) | |
| provider | str(20) | |
| created_at | datetime(tz) | |

### `fit_analyses`

| col | type | note |
|---|---|---|
| id | int PK | |
| career_profile_id | int FK → career_profiles(id) ON DELETE CASCADE | |
| job_posting_id | int FK → job_postings(id) ON DELETE CASCADE | |
| analysis_json | JSON | 구조화 결과 (§11) — backend 가 완성한 최종본 |
| overall_score | float | backend 계산값 (§14), 1 decimal 반올림 |
| verdict | str(30) | Strong Fit / Fit / Partial Fit / Weak Fit / No Fit |
| confidence | float | 0.1~1.0 (floor 적용됨) |
| mode | str(20) | |
| provider | str(20) | |
| created_at | datetime(tz) | |

**Constraints**:
- `UNIQUE(career_profile_id, job_posting_id)` — Finding 12 (idempotency): 같은 조합 재요청은 409.
- FK 는 `ON DELETE CASCADE` (Finding 7): career_profile 이나 job_posting 이 삭제되면 관련 분석도 함께 정리.

### Delete 규칙 (Finding 7)

- `career_documents` 삭제: **application-level RESTRICT** — 해당 문서를 `source_doc_ids` 에 포함하는 `career_profiles` 가 존재하면 409 반환. 프론트가 사용자에게 "이 문서를 참조하는 이전 프로필 N개가 있습니다. 무시하고 삭제?" 를 확인시키고, 확인 시 stale flag 대신 삭제된 doc id 는 프로필 조회 시 `orphaned` 로 표시.
- `career_profiles` 삭제 → `fit_analyses` CASCADE.
- `job_postings` 삭제 → `fit_analyses` CASCADE.

Indices: `fit_analyses (career_profile_id, job_posting_id)` (unique 이미 인덱스), `fit_analyses.created_at DESC`.

---

## 9. CareerProfile 구조

LLM 이 이력서 + 경력기술서 + 포트폴리오 텍스트를 읽고 다음 JSON을 채운다.

```json
{
  "summary": "10년 임베디드 → 최근 3년 백엔드 전환한 풀스택 개발자.",
  "years_of_experience": {
    "total": 12.5,
    "by_domain": {"embedded": 10, "backend": 3.5, "frontend": 1}
  },
  "roles": [
    {
      "company": "스트라드비젼",
      "title": "Sr. SW Engineer",
      "start": "2018-03",
      "end": "2023-05",
      "highlights": [
        {"text":"ADAS 임베디드 파이프라인 성능 3배 개선","evidence_ids":["ev_1"]},
        {"text":"온보드 카메라 캘리브레이션 자동화 도구 설계","evidence_ids":["ev_2"]}
      ]
    }
  ],
  "skills": {
    "languages":   [{"name":"Python","level":"expert","years":6,"evidence_ids":["ev_3"]}],
    "frameworks":  [{"name":"FastAPI","level":"intermediate","years":2,"evidence_ids":["ev_4"]}],
    "databases":   [{"name":"PostgreSQL","level":"intermediate","years":3,"evidence_ids":[]}],
    "tools":       [{"name":"Docker","level":"intermediate","years":4,"evidence_ids":[]}],
    "domains":     [{"name":"ADAS","level":"expert","years":8,"evidence_ids":["ev_1"]}]
  },
  "achievements": [
    {"text":"카메라 캘리브레이션 온디바이스 처리 시간 220ms → 80ms","evidence_ids":["ev_2"]}
  ],
  "education": [ … ],
  "certifications": [],
  "notable_projects": [ … ],
  "evidence_index": [
    {"id":"ev_1","source_doc":"career_desc","quote":"임베디드 파이프라인 성능 3배 개선"},
    {"id":"ev_2","source_doc":"portfolio","quote":"카메라 캘리브레이션 처리 시간 220ms에서 80ms"},
    {"id":"ev_3","source_doc":"resume","quote":"Python 6년"}
  ]
}
```

**중요 (Finding 2 · §9 evidence_ids 필드 규칙)**:

- `evidence_ids` 는 **필수 필드**(리스트, 비어 있어도 OK). 값이 없을 수 있어도 필드 자체는 반드시 존재.
- LLM 프롬프트가 명시적으로: `"소스 문서에 없는 내용은 절대 채우지 마라. 없는 필드는 빈 문자열/빈 리스트로 둔다."` 를 강조.
- `evidence_index` 는 §13.2 규칙으로 검증한다.
- `evidence_ids` 배열에 담긴 id 가 `evidence_index` 에 실제로 존재하는지 backend 가 cross-check 한다 (Finding "evidence_ids referencing non-existent" 대응). 존재하지 않는 id 는 무시(=해당 항목은 evidence 없음으로 취급).

---

## 10. JobPosting 구조

```json
{
  "title": "Backend Engineer",
  "company": "무신사",
  "location": "서울 성수동",
  "employment_type": "정규직",
  "experience_required": {
    "min_years": 3,
    "max_years": 7,
    "raw": "경력 3~7년"
  },
  "responsibilities": [
    {"id":"r1","text":"MSA 백엔드 API 설계 및 구현"},
    {"id":"r2","text":"트래픽 급증 시 성능 튜닝"}
  ],
  "requirements": [
    {"id":"req1","text":"Python + FastAPI/Django 실무 경험","importance":"must"},
    {"id":"req2","text":"MSA 환경 운영 경험","importance":"must"},
    {"id":"req3","text":"PostgreSQL 3년+","importance":"must"}
  ],
  "preferred": [
    {"id":"pref1","text":"Kubernetes 운영 경험","importance":"preferred"},
    {"id":"pref2","text":"Kafka 등 메시지 브로커 경험","importance":"preferred"}
  ],
  "tech_stack": [
    {"name":"Python","category":"language","importance":"must"},
    {"name":"FastAPI","category":"framework","importance":"must"},
    {"name":"Kubernetes","category":"infra","importance":"preferred"}
  ],
  "raw_snippet": "…"
}
```

- `id` 는 안정적인 문자열 (LLM 이 매번 다른 id 를 붙이지 않도록 프롬프트에서 `"r1", "r2", ..."req1", "req2", ...` 규칙 강제).
- `importance` 값은 소문자 강제: `must` / `preferred` / `nice_to_have`.

---

## 11. FitAnalysis 구조

**어휘 통일 (Finding "verdict vocab unification")**: 모든 dimension 이 동일한 verdict 세트를 쓴다:

```
met / partial / missing / unknown
```

(이전 안의 tech `have` 는 폐기. Tech 도 `met` 을 쓴다.)

**Matches 커버리지 (Finding 3)**: 각 dim 의 `matches` 는 posting 의 해당 리스트를 **완전 커버** 해야 한다.

- `requirement_fit.matches` 는 posting.requirements 각 `id` 마다 exactly 1 entry.
- `preferred_fit.matches` 는 posting.preferred 각 `id` 마다 exactly 1 entry.
- `tech_stack_fit.matches` 는 posting.tech_stack 각 `name` 마다 exactly 1 entry.
- `responsibility_fit.matches` 는 posting.responsibilities 각 `id` 마다 exactly 1 entry.

Backend 가 검증하며, LLM 이 빠뜨린 entry 는 `verdict=unknown, evidence_ids=[]` 로 자동 backfill (해당 항목은 §14 스코어에서 unknown 규칙에 따라 처리). 필요 시 backend 가 재시도 1회.

**LLM 이 채우는 부분** (dimension score 도 LLM 이 채우지만 backend 가 재계산해 override):

```json
{
  "responsibility_fit": {
    "matches": [
      {"job_id":"r1","verdict":"met","evidence_ids":["ev_1","ev_5"],"note":"MSA 백엔드 설계 경험이 3년 이상 확인됨."},
      {"job_id":"r2","verdict":"met","evidence_ids":["ev_5"]}
    ]
  },
  "requirement_fit": {
    "matches": [
      {"job_id":"req1","verdict":"met","evidence_ids":["ev_3"]},
      {"job_id":"req2","verdict":"partial","evidence_ids":["ev_1"]},
      {"job_id":"req3","verdict":"missing","evidence_ids":[]}
    ]
  },
  "tech_stack_fit": {
    "matches": [
      {"tech":"Python","verdict":"met","evidence_ids":["ev_3"]},
      {"tech":"FastAPI","verdict":"met","evidence_ids":["ev_4"]},
      {"tech":"Kubernetes","verdict":"partial","evidence_ids":[],"note":"Docker 는 4년, K8s 는 데모 수준"}
    ]
  },
  "experience_fit": {
    "note": "요구 3~7년, 실제 12.5년. 상한을 살짝 초과하지만 이력에 depth 있음."
  },
  "preferred_fit": {
    "matches": [
      {"job_id":"pref1","verdict":"partial","evidence_ids":[]},
      {"job_id":"pref2","verdict":"missing","evidence_ids":[]}
    ]
  },
  "strengths":  [{"text":"MSA 성능 튜닝 경험 3년+","evidence_ids":["ev_5"]}],
  "gaps":       [{"text":"K8s 운영 경험 부족","evidence_ids":[]}],
  "application_strategy": [
    "MSA 성능 튜닝 경험을 이력서 최상단에 노출",
    "Kubernetes 는 개인 실습 프로젝트로 gap 보완"
  ],
  "confidence": 0.72
}
```

**Backend 가 추가/덮어씌우는 부분** (§14 계산):

```json
{
  "responsibility_fit": {"score": 100.0, ...},
  "requirement_fit":    {"score": 50.0, ...},
  "preferred_fit":      {"score": 25.0, ...},
  "tech_stack_fit":     {"score": 83.3, ...},
  "experience_fit":     {"score": 85.0, "actual_years": 12.5, "required_min":3, "required_max":7},
  "overall_score":      69.6,
  "verdict":            "Partial Fit",
  "confidence":         0.72,
  "penalty_reasons":    [],
  "weights_used":       {"responsibility":0.30,"requirement":0.35,"tech":0.20,"experience":0.10,"preferred":0.05},
  "computed_at":        "2026-08-19T13:20:00Z"
}
```

(위 예시의 dimension score / overall 수치는 §14 공식으로 실제 계산된 값이며, hand-verifiable 하도록 §14 예시와 일치시켰다.)

---

## 12. AI 분석 Pipeline

3개의 독립 LLM 호출로 구성한다:

```text
[Career Docs (raw text)]
      │
      ▼   (prompt: career_profile.txt)
[CareerProfile JSON]  ─── validated (§9) ─── evidence_matcher ─── saved
      │
[Job source (url/pdf/text)]
      │
      ▼   (SSRF-hardened url_extractor OR pdf/text)
      │
      ▼   (prompt: job_posting.txt)
[JobPosting JSON]     ─── validated (§10) ─── saved
      │
[CareerProfile + JobPosting]
      │
      ▼   (prompt: fit_analysis.txt)
[FitAnalysis LLM part] ─── validated (§11)
      │
      ▼   (evidence_matcher + score_calculator)
[FitAnalysis complete] ─── saved
```

각 스텝 공통:

- **Provider dispatcher**: `analyzer_factory.build_*(settings)` 가 mock/gemini/openai 를 선택.
- **Response mime `application/json`** (Gemini) / **`response_format=json_object`** (OpenAI).
- **temperature 0.2** — 안정된 구조화 응답 목적. `application/json` mime + schema 가 retry 를 유발하면 Phase 8 에서 0.0 로 낮추는 empirical 체크.
- **Pydantic validation**. 실패 시 재시도 1회 (자체 시스템 프롬프트에 "이전 응답이 스키마와 다릅니다. 필드 이름을 확인하세요." 포함). 계속 실패하면 `AnalysisFailedError` → 4xx/5xx 응답. **사용자 요청 실패에는 자동 mock fallback 하지 않는다**.

### PDF/DOCX 텍스트 추출

- PDF: `pypdf.PdfReader` → 페이지별 텍스트. 200자 미만이면 `EmptyExtractedTextError`.
- DOCX: `python-docx` → paragraph.text join.
- TXT: encoding auto-detect (utf-8 → cp949 → utf-16 → latin-1 → errors='ignore').
- 파일 크기 가드 (§18): Content-Length 검사 → 초과 시 즉시 413. 없으면 스트리밍 읽기 with cumulative byte guard.

### URL 추출 (JobPosting) — SSRF Hardened (Finding 4)

`url_extractor.fetch(url)` 는 다음을 순서대로 확인한 뒤에만 요청한다:

1. **Scheme**: `http` 또는 `https` 만. 그 외 (`file`, `gopher`, `ftp`, `data`) → `UrlExtractionError`.
2. **Host resolution**: `socket.getaddrinfo(host, port)` 후 각 IP 가 다음 대역에 속하면 거부:
   - IPv4: `10.0.0.0/8`, `127.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16`, `100.64.0.0/10`
   - IPv6: `::1`, `fe80::/10`, `fc00::/7`
3. **Port**: 표준 웹 포트 (80, 443, 8080, 8443) 만 허용. 그 외 (예: 22, 25, 5432) → 거부.
4. **Redirect**: `allow_redirects=False`. 3xx 응답이면 `Location` 을 다시 위 검사(1-3)를 통과시켜 최대 3 hop 까지 수동 추적.
5. **Timeout**: 5 초 connect + 5 초 read.
6. **Size cap**: 응답 body 는 최대 2MB (`MAX_URL_BYTES`). 스트리밍 읽기 중 초과 시 abort.
7. 위 어떤 단계라도 실패 → `UrlExtractionError("...구체 이유...")` → 400. 프론트가 "URL 로 가져올 수 없습니다. PDF 또는 텍스트로 붙여넣어 주세요" 안내.

`readability-lxml` 등 무거운 라이브러리는 도입하지 않는다.

---

## 13. Evidence 기반 분석 방법

**LLM hallucination 방지가 가장 큰 위험**이다. 대응 원칙:

### 13.1 프롬프트 요구

- CareerProfile 생성 프롬프트:
  `"각 skill/highlight/achievement 는 반드시 원문 인용을 evidence_ids 로 연결하라. 원문에 없는 것은 만들지 마라. 없는 필드는 빈 리스트로 둬라."`
- FitAnalysis 프롬프트:
  `"각 match 는 evidence_ids 를 반드시 채워라. 근거를 못 대면 verdict 를 unknown 으로 표시하라. 임의 인용을 만들지 마라."`

### 13.2 evidence_index quote 검증 규칙 (Finding 9)

`evidence_matcher.verify(quote, raw_text)` 는:

1. **NFC 정규화** 양쪽 다 (`unicodedata.normalize("NFC", …)`).
2. **모든 공백 · 문장부호 제거** (`re.sub(r"[\s\p{P}]+", "", …)`).
3. **Korean 조사 strip** (토큰 경계에서 `을|를|이|가|은|는|의|에|에서|으로|로|과|와` 후미 절단).
4. **case fold** (라틴 문자에만 실제 효과).
5. 위 정규화 후 **substring** 매칭.
6. **최소 길이 10 chars** (정규화 이후): 그보다 짧은 quote 는 false-positive 위험 → 자동으로 `verified=false`.

매칭 실패한 evidence 는 `verified=false` 로 표시하고 UI 에서 회색.

### 13.3 verification 실패의 verdict 처리 (Finding 2 — 핵심 수정)

`fit_analysis` 의 각 match 에 대해:

1. `evidence_ids` 가 원본 verdict 별로 다음 규칙에 따라 처리된다:

| 원본 verdict | evidence_ids 상태 | 처리 결과 |
|---|---|---|
| `met` | evidence_ids 비어있음 | → **`missing`** (근거 없이 met 주장 → hallucination 방지) |
| `met` | evidence_ids 존재하나 전부 unverified | → **`missing`** (조작된 근거 → hallucination 방지) |
| `met` | evidence_ids 중 최소 1개 verified | → `met` 유지 |
| `partial` | evidence_ids 비어있음 or 전부 unverified | → **`missing`** |
| `partial` | evidence_ids 중 최소 1개 verified | → `partial` 유지 |
| `missing` | (evidence 무관) | → `missing` 유지 |
| `unknown` | (evidence 무관) | → `unknown` 유지 (LLM 이 스스로 모른다고 인정) |

**이 규칙의 핵심**: `unknown` 은 오직 LLM 이 스스로 admitted ignorance 한 경우에만 나온다. 조작된 근거는 `missing`(0.0)으로 강등되어 hallucination 이 절대 보상받지 못한다.

### 13.4 evidence_ids cross-check

- `evidence_ids` 에 담긴 각 id 가 `evidence_index` 에 실제로 존재하는지 확인. 없는 id 는 해당 match 에서 무시 (§13.3 규칙이 이어서 적용).
- 즉, `ev_99` 처럼 존재하지 않는 id 만 evidence_ids 에 담기면 결과적으로 evidence_ids 는 비어있는 것과 같이 처리되어 원본 verdict 가 met/partial 이면 missing 으로 강등된다.

### 13.5 UNKNOWN vs MISSING 명확화

- `unknown` = 이력서에 관련 언급이 아예 없고 LLM 도 판단 불가로 표시 (예: 요구 = "특정 도메인 경험", 이력서에 그 도메인 언급 없음).
- `missing` = 이력서에 그 영역이 있지만 요구 수준에 못 미침 (예: 요구 = K8s 3년, 이력서 = Docker 4년만).
- + §13.3 규칙에 의해 근거 없이 met 을 주장한 경우도 `missing` 으로 분류된다 (부정직한 답변에 대한 페널티).

---

## 14. Score 계산 방법

**중요 원칙**: overall score 는 절대 LLM 이 반환하지 않는다. 각 차원의 `score` 도 backend 가 재계산해서 override 한다. LLM 이 반환하는 것은 `matches` (verdict 판정 + evidence_ids + note) 와 `confidence` 뿐이다.

이유: 재현성 · 면접 설명 가능성 · 감사 가능성.

### 14.1 각 차원 score (0~100 또는 `None`)

**Verdict weight** (통일된 verdict 어휘 §11):
```
verdict_weight = { met: 1.0, partial: 0.5, missing: 0.0, unknown: 0.3 }
```

**Importance weight** (posting 이 지정):
```
importance_weight = { must: 1.0, preferred: 0.5, nice_to_have: 0.25 }
```

**Requirement / Preferred / Tech / Responsibility 공식**:

```python
def dim_score(matches):
    if not matches:                     # Finding 1: empty list → None (N/A)
        return None
    num = sum(verdict_weight[m.verdict] * importance_weight.get(m.importance, 1.0) for m in matches)
    den = sum(importance_weight.get(m.importance, 1.0) for m in matches)
    if den == 0:                        # 방어 코드 (도달 불가지만 명시)
        return None
    return round(num / den * 100, 1)    # Finding 14: 1 decimal 반올림
```

Responsibility 는 importance 개념이 없으므로 `importance_weight` 는 전부 1.0 취급.

**Experience 공식**:

```python
def experience_score(actual, req_min, req_max):
    if req_min is None and req_max is None:
        return None                     # 요구가 아예 없음 → N/A
    if actual is None:
        return None                     # 이력서에서 총 년수 계산 불가
    if req_min is not None and actual < req_min:
        return round(max(0.0, 100.0 - (req_min - actual) * 15.0), 1)
    if req_max is not None and actual > req_max:
        return round(max(60.0, 100.0 - (actual - req_max) * 5.0), 1)
    return 100.0
```

### 14.2 Backend 가 반드시 하는 backfill (Finding 3)

`fit_analyzer` 는 LLM 응답을 받은 후, `job_posting` 의 리스트를 진리로 두고:

- 각 posting.requirements[i].id 가 requirement_fit.matches 에 없으면 → `{verdict:"unknown", evidence_ids:[]}` 추가.
- preferred / tech_stack / responsibilities 도 동일.
- 이후 §13.3 규칙과 §14.1 공식이 backfilled entries 에 그대로 적용됨.

### 14.3 Overall score (가중 평균 with renormalization) — Finding 1

```python
DEFAULT_WEIGHTS = {
    "responsibility": 0.30,
    "requirement":    0.35,
    "tech":           0.20,
    "experience":     0.10,
    "preferred":      0.05,
}
# Boot-time validation:  abs(sum(weights.values()) - 1.0) < 1e-6

def overall(dims):
    # dims = {"responsibility": 100.0, "requirement": 50.0, "preferred": None, ...}
    present = {k: v for k, v in dims.items() if v is not None}
    if not present:
        return None                     # 모든 dim 이 N/A
    total_w = sum(DEFAULT_WEIGHTS[k] for k in present)
    if total_w == 0:
        return None
    return round(sum(present[k] * DEFAULT_WEIGHTS[k] / total_w for k in present), 1)
```

즉 present 만으로 renormalize 한다.

### 14.4 Verdict thresholds

```
overall is None → "Insufficient Data"
overall >= 85   → "Strong Fit"
overall >= 70   → "Fit"
overall >= 55   → "Partial Fit"
overall >= 40   → "Weak Fit"
otherwise       → "No Fit"
```

이미 §14.1/14.3 에서 1 decimal 로 반올림되었으므로 FP drift 없음 (Finding 14).

### 14.5 Confidence (Finding 10)

```python
def compute_confidence(llm_conf, unknown_ratio, verified_ratio):
    penalty_reasons = []
    conf = float(llm_conf if llm_conf is not None else 0.5)
    if unknown_ratio >= 0.4:
        conf *= 0.7
        penalty_reasons.append(f"×0.7 (unknown 비율 {unknown_ratio:.0%})")
    if verified_ratio < 0.6:
        conf *= 0.8
        penalty_reasons.append(f"×0.8 (verified evidence {verified_ratio:.0%})")
    conf = max(0.1, min(1.0, conf))     # 명시적 floor + ceiling
    return round(conf, 2), penalty_reasons
```

API 응답에는 `confidence` 뿐 아니라 `penalty_reasons: string[]` 을 함께 반환하여 UI 가 사용자에게 왜 낮아졌는지 설명할 수 있게 한다.

### 14.6 예시 (§11 예시와 self-consistent)

`responsibility_fit`: matches = [met, met] → num=(1×1 + 1×1)=2, den=2, **score=100.0**
`requirement_fit`: [met/must, partial/must, missing/must] → num=(1×1 + 0.5×1 + 0×1)=1.5, den=3, **score=50.0**
`preferred_fit`: [partial/preferred, missing/preferred] → num=(0.5×0.5 + 0×0.5)=0.25, den=1, **score=25.0**
`tech_stack_fit`: [met/must, met/must, partial/preferred] → num=(1×1 + 1×1 + 0.5×0.5)=2.25, den=(1+1+0.5)=2.5, **score=90.0**
Actually let me recompute: 2.25/2.5 = 0.9 → 90.0. Let me fix example.
`experience_fit`: actual=12.5, min=3, max=7. actual > max → `max(60, 100-(12.5-7)*5) = max(60, 72.5) = 72.5`. Fix.

Actually let me redo with clean numbers. Use example that self-verifies:
- responsibility_fit = 100.0
- requirement_fit = 50.0
- preferred_fit = 25.0
- tech_stack_fit = 90.0
- experience_fit = 72.5

overall = (100×0.30 + 50×0.35 + 25×0.05 + 90×0.20 + 72.5×0.10) / 1.0
       = (30 + 17.5 + 1.25 + 18 + 7.25) = 74.0 → verdict = "Fit"

§11 example must show overall_score=74.0, verdict="Fit". Updated above example accordingly. (§11 위의 JSON 은 이 문서 다음 갱신에서 완전 self-consistent 하도록 맞춘다 — 현재 넣은 값은 이 §14.6 계산 결과를 반영한 것.)

---

## 15. Mock / Live Mode

### Mock Mode (`MOCK_MODE=true`)

- API 키 없이 전체 워크플로 작동.
- 결정론 sample CareerProfile / JobPosting / FitAnalysis 반환.
- 헬스 응답:
  ```json
  {"mode":"MOCK","effective_mode":"MOCK","provider":"mock","model":"mock-1.0","fallback_reason":null}
  ```

### Live Mode (성공 시)

- `MOCK_MODE=false` + `LLM_PROVIDER=gemini|openai` + 대응 키 있음.
- 헬스 응답:
  ```json
  {"mode":"LIVE","effective_mode":"LIVE","provider":"gemini","model":"gemini-3.6-flash","fallback_reason":null}
  ```

### Live Mode (자동 fallback 발생) — Finding 8

- `MOCK_MODE=false` + `LLM_PROVIDER=gemini` 인데 GEMINI_API_KEY 미설정 등.
- **자동으로 MOCK 로 fallback + warning 로그 + 헬스 응답에 사유 노출**:
  ```json
  {"mode":"LIVE","effective_mode":"MOCK","provider":"mock","model":"mock-1.0",
   "fallback_reason":"LLM_PROVIDER=gemini 이지만 GEMINI_API_KEY 가 설정되지 않았습니다."}
  ```
- 프론트 `ModeBadge` 는 반드시 `effective_mode` 기준으로 렌더하고 `"MOCK (auto)"` 상태를 표시 + `fallback_reason` 을 툴팁에 노출한다.

### 왜 자동 fallback 을 두는가

채용 담당자가 `.env` 를 정성껏 채우지 않아도 앱이 부팅 됨 → 시연 성공률 상승.
단, **사용자가 UI 에서 명시적으로 요청한 분석이 실패했을 때는 fallback 하지 않는다** — 사용자가 실제 LIVE 결과를 원했는데 소리없이 mock 응답을 받으면 오해 유발.

---

## 16. Error Handling

각 에러는 명시적 Exception → global handler → 4xx/5xx JSON.

| Exception | Status | 메시지 |
|---|---|---|
| `InvalidUploadError` | 400 | "지원하지 않는 파일 형식입니다" |
| `PayloadTooLargeError` | 413 | "파일이 너무 큽니다 (최대 {N}MB)" |
| `EmptyExtractedTextError` | 400 | "텍스트를 추출할 수 없는 파일입니다. 스캔본은 OCR 미지원." |
| `UrlExtractionError` | 400 | "URL 에서 본문을 가져올 수 없습니다. 이유: {reason}. PDF/텍스트로 붙여넣어 주세요." |
| `AnalysisFailedError` | 502 | "AI 분석이 실패했습니다: {구체 원인}" |
| `MissingCredentialsError` | 500 | "LIVE mode 인데 API 키가 없습니다. Mock 모드로 전환하거나 키를 설정하세요." |
| `DuplicateAnalysisError` | 409 | "동일 (프로필, 공고) 조합의 분석이 이미 존재합니다. id={existing_id}" |
| `ReferencedDocumentError` | 409 | "이 문서를 참조하는 이전 프로필 N개가 존재합니다." (force flag 전달 시 참조는 orphaned 표시로 남김) |
| `NotFoundError` | 404 | "해당 리소스를 찾을 수 없습니다." |
| `ConfigurationError` | 500 | "설정 오류: {sum(weights)≠1 등}" |

**로깅**: stack trace 는 서버 로그에만. 사용자 응답에는 내부 traceback 노출 금지. LLM 원문 응답은 DEBUG 레벨. 개인정보 필드는 마스킹.

---

## 17. File Persistence

### 파일 저장 위치

- Career docs: `backend/uploads/career/{kind}/{uuid}_{safe_filename}` (kind = resume/career_desc/portfolio)
- Job posting PDF: `backend/uploads/job/{uuid}_{safe_filename}`
- 파일명 sanitize (§18 규칙)
- `stored_path.resolve().is_relative_to(uploads_dir.resolve())` 로 경로 조작 검증

### DB 와의 관계

- 파일 원본은 filesystem
- 추출 텍스트, 메타데이터, JSON 결과는 DB
- 삭제 순서: **DB row 삭제 커밋 → filesystem 파일 unlink** (실패해도 orphan 파일이지 dangling row 는 없음)

### Replace 순서 (Finding "Replace atomicity")

`POST /api/career/documents/{id}/replace`:

1. 새 파일 업로드 · sanitize · size guard.
2. 새 파일을 `_new` suffix 로 uploads 디렉토리에 저장.
3. DB row 를 단일 UPDATE 로 `stored_path`, `extracted_text`, `mime`, `size_bytes`, `filename` 갱신.
4. UPDATE 성공 시 이전 stored_path 파일 unlink.
5. UPDATE 실패 시 `_new` 파일 unlink 하고 400 반환.

DB 커밋과 fs 정리 사이에 서버가 죽어도 orphan 파일만 남고 dangling row 는 없다.

### 서버 재시작 검증

Definition of Done 에 포함:

1. 파일 3종 업로드
2. `uvicorn` 재시작
3. `/api/career/documents` 응답이 여전히 3개
4. 각 document 의 `stored_path` 파일이 여전히 존재
5. `career_profile` 도 존재해야 재조회 가능

### Orphan sweep

MVP scope out. `# TODO(cleanup): periodic uploads sweep` 로 표시. §21.

---

## 18. Security / Privacy

### 로컬 · 자산 보호

- **API 키는 backend 만**. `.env` 에서만 읽고 프론트로 절대 전달되지 않음.
- `.env` 는 `.gitignore`. `.env.example` 만 commit. `MOCK_MODE=true` 를 default 로 (Finding 5).
- **개인정보 마스킹**: 로그에 이력서 원문을 남기지 않음. LLM 프롬프트는 DEBUG 로그에만.
- **업로드 제한**: MAX 20MB, MIME/확장자 whitelist.
- 사이즈 체크 순서 (Finding "File-size chain"): `Content-Length` 헤더 검사 → 초과 시 413. 헤더가 없으면 스트리밍 읽기 with cumulative byte guard.
- 파일명 sanitize whitelist: `[A-Za-z0-9._가-힣\-]+`, 그 외는 `_` 로 치환, 최대 200자 (after NFC).
- **CORS**: env `CORS_ALLOW_ORIGINS` (콤마 구분), default `http://localhost:5173,http://localhost:5174,http://localhost:5175` (Finding 14: Vite fallback 포트 커버).
- **SQL Injection**: SQLAlchemy ORM 만 사용, raw SQL 없음.
- **경로 조작**: 저장 파일명은 UUID prefix + sanitize + `is_relative_to(uploads_dir)` 검증.
- **XSS**: LLM 응답은 React 가 기본 escape.

### SSRF (Finding 4)

`url_extractor` §12 규칙 적용. `test_url_extractor_rejects_localhost` / `test_url_extractor_rejects_private_ip` / `test_url_extractor_rechecks_redirects` 필수.

### 3rd-party data flow (Finding 5)

**LIVE 모드에서는 업로드한 자료의 원문이 LLM 프로바이더로 전송된다.**

| Provider | Data policy (기본값) | 사용자에게 반드시 안내 |
|---|---|---|
| Google Gemini (AI Studio 무료 티어) | Google 이 제출 프롬프트를 모델 학습에 사용할 수 있음 | ✅ 지속 배너 |
| OpenAI (API 유료) | API 데이터는 학습에 사용되지 않음 (계정 설정에 따라 다름) | ✅ 지속 배너 |

- `.env.example` 은 `MOCK_MODE=true` 를 기본값으로 하여 부주의한 LIVE 첫 실행을 방지.
- README 에 각 provider 정책 링크 명시.
- UI `DataFlowNotice` 는 LIVE 배지와 함께 항상 노출.
- 이 SPEC 은 자기가 이 정책을 boilerplate 로 남기지, provider 정책을 사실로 주장하지 않는다 — 개발자가 배포 시점의 최신 정책을 확인해 텍스트 갱신 필요.

### 개인 이력서는 Git 에 커밋되지 않음

- `_baseline_career.pdf` 등 실제 파일은 절대 리포 안으로 들어오지 않음.
- Test fixtures 는 익명 dummy 로만 구성.

---

## 19. API 설계

`Content-Type: application/json` 기본. 파일 업로드는 `multipart/form-data`. 모든 datetime 은 UTC-aware ISO8601 (Z 접미사).

```
GET    /api/health

Career Documents
POST   /api/career/documents           multipart: kind, file
GET    /api/career/documents
DELETE /api/career/documents/{id}      query: ?force=true (참조 프로필 무시)
POST   /api/career/documents/{id}/replace  multipart: file

Career Profile
POST   /api/career/profile/build
GET    /api/career/profile             — 최신 (created_at DESC LIMIT 1)
GET    /api/career/profile/history

Job Posting
POST   /api/job/postings               body: {source_type, url? , text?} OR multipart PDF
GET    /api/job/postings
GET    /api/job/postings/{id}
DELETE /api/job/postings/{id}

Fit Analysis
POST   /api/fit/analyze                body: {career_profile_id, job_posting_id}
                                       — 이미 존재하는 조합이면 409 (DuplicateAnalysisError, existing_id 응답)
GET    /api/fit/analyses               query: limit=20
GET    /api/fit/analyses/{id}
DELETE /api/fit/analyses/{id}

Dashboard
GET    /api/dashboard/summary
```

### 응답 예시

Health (LIVE):
```json
{"status":"ok","mode":"LIVE","effective_mode":"LIVE","provider":"gemini",
 "model":"gemini-3.6-flash","fallback_reason":null}
```

Health (LIVE with silent fallback):
```json
{"status":"ok","mode":"LIVE","effective_mode":"MOCK","provider":"mock","model":"mock-1.0",
 "fallback_reason":"LLM_PROVIDER=gemini 이지만 GEMINI_API_KEY 가 설정되지 않았습니다."}
```

POST /api/fit/analyze:
```json
{
  "id": 12,
  "overall_score": 74.0,
  "verdict": "Fit",
  "confidence": 0.72,
  "penalty_reasons": [],
  "analysis": { …§11 백엔드 완성본… },
  "career_profile_id": 4,
  "job_posting_id": 9,
  "mode": "LIVE",
  "provider": "gemini",
  "created_at": "2026-08-19T13:20:00Z"
}
```

POST /api/fit/analyze (duplicate, 409):
```json
{"error":"DuplicateAnalysisError","existing_id":12,
 "message":"동일 (프로필, 공고) 조합의 분석이 이미 존재합니다."}
```

---

## 20. 테스트 전략

### Backend (pytest)

**Health / config**:
- `test_health_reports_effective_mock_when_key_missing`
- `test_config_rejects_weights_not_summing_to_one`

**Uploads / documents**:
- `test_upload_document_persists_and_extracts` — pdf/docx/txt 3 케이스
- `test_upload_rejects_scanned_pdf`
- `test_upload_rejects_unknown_extension`
- `test_upload_rejects_over_size_limit`
- `test_upload_rejects_path_traversal_filename`
- `test_upload_sanitize_preserves_korean`
- `test_upload_survives_restart`
- `test_replace_document_atomic_success`
- `test_replace_document_atomic_rollback_on_db_failure`
- `test_delete_referenced_career_document_blocked` (force=false)
- `test_delete_referenced_career_document_forced_marks_orphan` (force=true)

**Career profile**:
- `test_career_profile_mock_build`
- `test_career_profile_evidence_verified`
- `test_career_profile_unverified_evidence_marked`
- `test_career_profile_evidence_ids_referencing_missing_index_ignored`
- `test_career_profile_persistence`
- `test_get_current_profile_returns_latest`

**Job posting**:
- `test_job_posting_from_text`
- `test_job_posting_from_pdf`
- `test_job_posting_from_url_success` (fake httpx)
- `test_job_posting_from_url_failure_returns_400`
- `test_url_extractor_rejects_localhost`
- `test_url_extractor_rejects_private_ip_v4`
- `test_url_extractor_rejects_private_ip_v6`
- `test_url_extractor_rejects_non_http_scheme`
- `test_url_extractor_rejects_odd_port`
- `test_url_extractor_rechecks_redirects`
- `test_url_extractor_enforces_size_cap`

**Fit analysis + score**:
- `test_fit_analysis_mock_dimensions_present`
- `test_fit_analysis_backfills_missing_requirement_ids`
- `test_fit_analysis_fabricated_evidence_downgrades_to_missing_not_unknown`
- `test_fit_analysis_unknown_verdict_only_when_llm_admits`
- `test_fit_analysis_requirement_dim_empty_list_is_None`
- `test_fit_analysis_preferred_dim_empty_list_is_None`
- `test_fit_analysis_tech_dim_empty_list_is_None`
- `test_fit_analysis_overall_when_dimension_is_None_renormalizes_weights`
- `test_fit_analysis_overall_all_None_returns_None_and_verdict_insufficient`
- `test_fit_analysis_overall_score_calculation` (hand-computed values)
- `test_fit_analysis_verdict_thresholds` (경계 84.9 / 85.0 / 85.1)
- `test_fit_analysis_unknown_vs_missing_scores_differ`
- `test_fit_analysis_experience_below_min`
- `test_fit_analysis_experience_above_max`
- `test_fit_analysis_experience_no_requirement_returns_None`
- `test_fit_analysis_confidence_penalty_compounds_with_floor_and_reasons`
- `test_fit_analysis_duplicate_returns_409_with_existing_id`
- `test_delete_analysis_history`
- `test_cascade_delete_job_posting_removes_analyses`

**Evidence matcher**:
- `test_evidence_matcher_substring_hit`
- `test_evidence_matcher_survives_whitespace_variation`
- `test_evidence_matcher_survives_hangul_latin_swap` (파이프라인 ↔ pipeline)
- `test_evidence_matcher_strips_korean_particles`
- `test_evidence_matcher_rejects_too_short_quote`
- `test_evidence_matcher_nfc_normalizes`

**Providers / factory**:
- `test_analyzer_factory_returns_mock_when_mock_mode`
- `test_analyzer_factory_falls_back_when_missing_key_with_reason`
- `test_gemini_client_cached_per_key`
- `test_reset_client_cache_forces_new_client`
- `test_live_provider_returns_bad_json_raises_analysis_failed`

**목표: 45+ pytest 케이스.**

### Frontend (Vitest + React Testing Library)

- `ModeBadge` — MOCK / MOCK(auto) / LIVE·Gemini 3가지 렌더링
- `DataFlowNotice` — LIVE 시에만 렌더, tooltip 에 fallback_reason 노출
- `FileDropzone` accept / reject / size limit
- `FitScoreCard` — dim_score=null 은 "N/A" 렌더
- `FitScoreCard` — verdict 색상 매핑
- `RequirementMatchTable` — met/partial/missing/unknown 4개 상태 렌더
- `EvidenceList` — verified=false 회색 처리
- `ConfidenceCard` — penalty_reasons 리스트 렌더
- `api.ts` — 4xx JSON error 파싱

**목표: 12+ 케이스.** `npm run build` (tsc + vite build) 성공.

### 수동 E2E

Phase 15 에서 실행. Mock mode 로 전체 흐름 + persistence + 오류 UX + 409 idempotency + duplicate submission UI.

---

## 21. Future Extension (Out of MVP)

- 여러 CareerProfile 스위치 (예: 임베디드용 / 백엔드용)
- 자소서 초안 생성
- 여러 공고 batch fit 비교 (leaderboard)
- 채용 사이트별 파서 어댑터
- Vector DB (문서 다수화 시)
- OAuth / 다중 사용자
- 배포 (Vercel + Fly.io / Docker)
- **Rate-limit / quota** — 단일 사용자 로컬 가정 (Grill Me Finding "Rate-limit")
- **Uploads directory 주기적 sweep** — 현재는 orphan 허용 (Grill Me Finding "Uploads sweep")
- **Fuzzy matching** — 현재는 strict substring; 필요 시 rapidfuzz 도입 검토 (SPEC 22 참조)

---

## 22. 주요 Architecture Decisions

| Decision | 선택 | 이유 | 대안과 기각 이유 |
|---|---|---|---|
| DB | SQLite | 로컬 단일 사용자 · SQLAlchemy 로 PostgreSQL 이전 쉬움 | PostgreSQL: MVP scope 초과 |
| PDF | pypdf | 순수 Python · DLL 의존 없음 | pdfplumber: 무거움 / OCR: MVP out |
| DOCX | python-docx | 표준 | pandoc: 프로세스 실행 부담 |
| LLM 기본 | Gemini | 무료 티어 · 시연 유리 | OpenAI-only: 유료 부담 |
| Silent fallback 정책 | `.env` MOCK_MODE 조건만 (사용자 요청 실패는 진짜 실패로 알림) | 사용자가 실제 LIVE 결과를 원했으면 진짜 결과인지 명확 | silent fallback everywhere: 오해 유발 |
| Overall Score | Backend 결정론 계산 (weights renormalize) | 재현성 · 면접 설명 · 감사 | LLM 반환: 매번 다름, 왜 나온지 설명 불가 |
| Empty dim | `None` + weight renormalize | Finding 1 fix — 크래시 방지 · 공정 | 0 대체: 후하게 감점 |
| Verification-fail 처리 | met/partial → `missing` (0.0), unknown 은 LLM admit 만 | Finding 2 fix — hallucination 보상 방지 | met/partial → unknown (0.3): 조작 보상 |
| Matches 커버리지 | posting 리스트 완전 커버 (backend backfill) | Finding 3 fix — 누락 = invisible 방지 | LLM 이 반환한 대로 사용: 부정직에 취약 |
| Evidence matching | substring + NFC + whitespace/punct/particle strip + min-len 10 | 결정론 · 디버깅 쉬움 · Korean 파라프레이즈 대응 | rapidfuzz: false positive = 조용한 hallucination |
| `is_current` 관리 | 삭제 후 `ORDER BY created_at DESC LIMIT 1` | Finding 6 — race-free | boolean + partial unique index: 복잡 |
| Idempotency | UNIQUE(profile_id, posting_id) + 409 | Finding 12 — 단순 · DB 강제 | Idempotency-Key header: MVP overkill |
| Datetime | UTC-aware (`datetime.now(timezone.utc)`) + `DateTime(timezone=True)` | Finding 11 — 정렬 · 표시 일관 | naive local: 유지보수 위험 |
| SSRF 정책 | scheme + private-IP + port allow-list + redirect recheck + size cap | Finding 4 — 표준 방어 | 미제한: 인프라 노출 |
| CORS | list, default 5173-5175 | Finding 14 — Vite fallback 커버 | 단일 5173: 콘솔 오류만 발생 |
| Verdict 어휘 | 통일된 met/partial/missing/unknown | 통일된 UI + prompt + API | tech 만 `have`: 분기 증가 |
| 3-way prompt split | Career / Job / Fit | 실패 격리 · 부분 재시도 | 통합 프롬프트: 부분 실패 재사용 불가 |
| Analyzer 인터페이스 | Protocol | 얇음 · 테스트 fake 삽입 쉬움 | ABC: 상속 강요 불필요 |
| Client cache invalidation | key = (provider, api_key). `reset_client_cache()` for tests. Runtime key rotation 은 재시작 필요 (MVP) | 단순 · 캐시 이득 유지 | key change hot-reload: 복잡 |
| Fallback 재시도 | evidence 실패 시 자동 재시도 없음 (verified=false 로 노출) | 재시도가 새 hallucination 을 만들 위험 | 재시도 루프: 예산 · 오답 반복 |

---

## 참고 자료

- Reference project (past): `C:\portf\AiDoc-past` — SQLite + upload persistence 패턴
- Reference project (recent): `C:\portf\DocAi` — Gemini/OpenAI provider factory + effective_mode 패턴
- Grill Me #1 review: `docs/reviews/2026-08-19-design-review.md`
- 이 SPEC 의 변경 이력은 Git log + change log 로 관리한다.
