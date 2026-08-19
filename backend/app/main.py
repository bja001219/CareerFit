"""CareerFit FastAPI entrypoint (Phase 1 skeleton).

실제 라우터 · DB · analyzer 는 Phase 2 이후에 채워진다. 이 파일은 지금은
health check 만 노출하여 uvicorn 부팅이 되는지 검증하기 위한 최소 skeleton 이다.
"""
from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(
    title="CareerFit",
    description="Career × Job Posting Fit Analyzer",
    version="0.2.0",
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "phase": "1-skeleton"}
