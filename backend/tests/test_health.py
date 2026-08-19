"""Health endpoint tests — SPEC §15."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_health_default_is_mock(client: TestClient) -> None:
    """With no env set, ``MOCK_MODE`` defaults to true → mode=MOCK, effective=MOCK."""
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["mode"] == "MOCK"
    assert body["effective_mode"] == "MOCK"
    assert body["provider"] == "mock"
    assert body["fallback_reason"] is None


def test_health_reports_effective_mock_when_key_missing(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    """Grill Me #1 Finding 8: LIVE mode without key must expose the fallback.

    User set ``MOCK_MODE=false, LLM_PROVIDER=gemini`` but forgot the key.
    The health response must report ``mode=LIVE, effective_mode=MOCK`` and
    include a human-readable ``fallback_reason``.  The frontend badge relies
    on this to render "MOCK (auto)" instead of a misleading "LIVE · Gemini".
    """
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    # GEMINI_API_KEY intentionally NOT set.

    from app.config import reset_settings_cache

    reset_settings_cache()

    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "LIVE"
    assert body["effective_mode"] == "MOCK"
    assert body["provider"] == "mock"
    assert body["fallback_reason"] is not None
    assert "GEMINI_API_KEY" in body["fallback_reason"]


def test_health_reports_live_when_key_present(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test-only")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.6-flash")

    from app.config import reset_settings_cache

    reset_settings_cache()

    r = client.get("/api/health")
    body = r.json()
    assert body["mode"] == "LIVE"
    assert body["effective_mode"] == "LIVE"
    assert body["provider"] == "gemini"
    assert body["model"] == "gemini-3.6-flash"
    assert body["fallback_reason"] is None
