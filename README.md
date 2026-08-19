# CareerFit

**AI-powered Career × Job Posting Fit Analysis.**

> 이력서 · 경력기술서 · 포트폴리오를 한 번 정리해 두고, 채용 공고를 넣으면
> 5개 차원(주요업무 / 자격요건 / 우대사항 / 기술스택 / 경력년수)에서
> **근거 기반의 정량 적합도(Fit Score)** 를 자동으로 계산해 주는 포트폴리오 MVP.

핵심 질문은 언제나 하나다: **"내 커리어가 이 공고에 정말 fit 하는가? 어느 부분이 왜 부족한가?"**

---

## Why

지원자는 채용 공고 하나를 검토할 때마다 요구사항을 뽑고, 자기 이력과 매칭하고,
부족한 부분을 파악하고, 지원 여부를 판단하는 과정을 매번 반복한다.
CareerFit 은 이 반복 작업을 LLM + 결정론 backend 계산으로 자동화한다.

## Features

- **Career Profile 관리** — Resume / Career Description / Portfolio 를 PDF / DOCX / TXT 로 업로드하고, 서버 재시작 후에도 유지되는 CareerProfile JSON 으로 구조화한다.
- **Job Posting 입력** — URL(SSRF 가드) · PDF · 붙여넣기 텍스트 3가지 방식.
- **Fit Analysis** — 5차원(Responsibility / Requirement / Preferred / Tech / Experience) 별 verdict + Evidence + backend 계산 overall score.
- **Evidence 기반** — LLM 이 주장하는 각 매치는 원문 인용에 substring 매칭으로 검증. 조작된 근거는 자동으로 `missing` 으로 강등되어 hallucination 이 절대 점수를 얻지 못한다.
- **Mock Mode / Live Mode** — API 키 없이도 전체 워크플로 시연 가능. Live 는 Gemini(무료) 또는 OpenAI(유료).

## Documentation (living)

- SPEC: [`docs/superpowers/specs/2026-08-19-career-fit-design.md`](docs/superpowers/specs/2026-08-19-career-fit-design.md)
- PLAN: [`docs/superpowers/plans/2026-08-19-career-fit.md`](docs/superpowers/plans/2026-08-19-career-fit.md)
- Design review: [`docs/reviews/2026-08-19-design-review.md`](docs/reviews/2026-08-19-design-review.md)

---

## Architecture (요약)

```text
[React + Vite + Tailwind]
          │  JSON / multipart
          ▼
[FastAPI backend]
          │
          ├─ document_service   (PDF/DOCX/TXT + size guard)
          ├─ url_extractor      (SSRF-hardened)
          ├─ evidence_matcher   (NFC + substring + Korean particles)
          ├─ score_calculator   (backend 결정론 overall score)
          └─ analyzer_factory
                ├─ MockAnalyzer      (기본, 결정론 sample)
                ├─ GeminiAnalyzer    (Google AI Studio)
                └─ OpenAIAnalyzer    (opt-in)
          │
          ▼
[SQLite]  + [uploads/ filesystem]
```

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- npm 9+

## Setup

```bash
# 1) 환경파일
cp .env.example .env

# 2) 백엔드 (권장: 별도 venv)
cd backend
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Windows Git Bash:   source .venv/Scripts/activate
# macOS/Linux:        source .venv/bin/activate
pip install -e ".[dev]"

# 3) 프론트엔드
cd ../frontend
npm install
```

## Run

터미널 두 개.

**Backend**
```bash
cd backend
uvicorn app.main:app --reload --port 8000
# → http://localhost:8000/api/health    → {"status":"ok","mode":"MOCK",…}
# → http://localhost:8000/docs          → Swagger
```

**Frontend**
```bash
cd frontend
npm run dev
# → http://localhost:5173
```

## Mock Mode (기본값 · API 키 없이)

`.env` 기본값:
```env
MOCK_MODE=true
```

이 상태에서는 LLM 호출 없이 결정론 sample 응답이 반환된다. 채용 담당자가 키 없이도 전체 워크플로를 확인할 수 있다.

## Live Mode

⚠ **먼저 아래 [3rd-party data flow](#3rd-party-data-flow) 를 읽어 주세요.**

### A. Google Gemini (무료 티어)

[Google AI Studio](https://aistudio.google.com/apikey) 에서 키 발급 후:
```env
MOCK_MODE=false
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-3.6-flash
```

### B. OpenAI (유료)

```env
MOCK_MODE=false
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

- API 키는 backend 에만 존재하고 프론트로 전달되지 않는다.
- 프로바이더 키가 없으면 자동으로 **MOCK** 로 fallback 되고, 프론트 상단 배지가 `MOCK (auto)` 로 표시되며 사유를 툴팁으로 보여준다.
- 사용자가 UI 에서 명시적으로 요청한 분석이 실패했을 때는 fallback 하지 않고 진짜 오류를 보고한다.

---

## Testing

```bash
# Backend
cd backend
pytest -v

# Frontend
cd ../frontend
npm run test:run
npm run build
```

---

## 3rd-party data flow

**LIVE 모드에서는 업로드한 자료 원문이 선택한 프로바이더로 전송된다.**

- Google Gemini (AI Studio 무료 티어): 제출한 프롬프트가 모델 개선에 활용될 수 있음.
  [Gemini API Terms](https://ai.google.dev/gemini-api/terms).
- OpenAI API: 기본적으로 학습 데이터로 사용되지 않으나 계정 설정에 따라 다름.
  [OpenAI API data-usage policy](https://openai.com/policies/api-data-usage-policies).

실제 개인 이력서로 시연하기 전에 위 정책을 확인하는 것을 강력히 권장한다.
`.env.example` 의 `MOCK_MODE=true` 는 이 이유로 안전한 기본값이다.

---

## Security Notes

- API 키는 backend 환경변수로만 관리, `.env` 는 gitignore.
- 업로드: MIME/확장자 whitelist, 20MB 상한, 경로 조작 방지, sanitize whitelist `[A-Za-z0-9._가-힣\-]+`.
- URL extractor: `http/https` 만, private IP 대역 차단, 표준 웹 포트만, redirect 재검증, 5s 타임아웃, 2MB body 상한.
- SQL Injection: SQLAlchemy ORM 만 사용.
- XSS: React 기본 escape.
- 개인 이력서 파일은 절대 리포에 커밋되지 않는다 (`uploads/` 는 gitignore).

## Disclaimer

이 서비스는 포트폴리오 및 개인 지원 참고용 MVP다. 실제 채용 판단이나 인사 결정은
직접 이력서와 공고를 검토해서 내려야 한다. AI 분석 결과는 참고 신호에 불과하다.
