"""Runtime settings for CareerFit backend.

Loads from environment (with ``.env`` support via python-dotenv) into an
immutable dataclass.  Two important properties:

* :pyattr:`Settings.effective_mode` — what the analyzer factory will *actually*
  serve.  Falls back to ``"MOCK"`` when the configured live provider has no
  key.  The UI must render its Mode badge from this, not from :pyattr:`mode`.
* :pyattr:`Settings.fallback_reason` — human-readable reason when
  ``effective_mode`` differs from ``mode``.  Surfaced in ``/api/health`` so
  the operator can tell a silent fallback apart from a broken deploy.

The weight configuration is validated on construction so a boot-time
misconfig fails loudly (:pyexc:`app.models.errors.ConfigurationError`)
instead of producing scores outside ``[0, 100]``.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

try:
    from dotenv import find_dotenv, load_dotenv
except ImportError:  # pragma: no cover - dev dep
    find_dotenv = None  # type: ignore[assignment]
    load_dotenv = None  # type: ignore[assignment]
else:
    _dotenv_path = find_dotenv(usecwd=True)
    if _dotenv_path:
        load_dotenv(_dotenv_path, override=False)


Provider = Literal["gemini", "openai"]
Mode = Literal["MOCK", "LIVE"]


DEFAULT_WEIGHTS: dict[str, float] = {
    "responsibility": 0.30,
    "requirement": 0.35,
    "tech": 0.20,
    "experience": 0.10,
    "preferred": 0.05,
}


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _get_list(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _get_provider(default: Provider = "gemini") -> Provider:
    raw = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    if raw in {"gemini", "google"}:
        return "gemini"
    if raw in {"openai", "gpt"}:
        return "openai"
    return default


def _load_weights() -> dict[str, float]:
    """Read weight overrides from env; fall back to DEFAULT_WEIGHTS untouched."""
    return {
        "responsibility": _get_float("WEIGHT_RESPONSIBILITY", DEFAULT_WEIGHTS["responsibility"]),
        "requirement": _get_float("WEIGHT_REQUIREMENT", DEFAULT_WEIGHTS["requirement"]),
        "tech": _get_float("WEIGHT_TECH", DEFAULT_WEIGHTS["tech"]),
        "experience": _get_float("WEIGHT_EXPERIENCE", DEFAULT_WEIGHTS["experience"]),
        "preferred": _get_float("WEIGHT_PREFERRED", DEFAULT_WEIGHTS["preferred"]),
    }


@dataclass(frozen=True)
class Settings:
    llm_provider: Provider
    openai_api_key: str | None
    openai_model: str
    gemini_api_key: str | None
    gemini_model: str
    mock_mode: bool
    max_upload_bytes: int
    max_url_bytes: int
    cors_allow_origins: list[str]
    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))

    def __post_init__(self) -> None:
        # Weight-sum validation (SPEC §14; Grill Me #1 Finding 14).
        total = sum(self.weights.values())
        if abs(total - 1.0) > 1e-6:
            # Import here to avoid circular import: models -> config would loop.
            from app.models.errors import ConfigurationError

            raise ConfigurationError(
                f"Scoring weights must sum to 1.0, got {total:.6f}. "
                f"Check WEIGHT_* env variables: {self.weights}"
            )

    @property
    def mode(self) -> Mode:
        """User-configured mode via MOCK_MODE env variable."""
        return "MOCK" if self.mock_mode else "LIVE"

    @property
    def has_live_credentials(self) -> bool:
        """Whether the configured provider actually has a usable key."""
        if self.llm_provider == "gemini":
            return bool(self.gemini_api_key)
        if self.llm_provider == "openai":
            return bool(self.openai_api_key)
        return False

    @property
    def effective_mode(self) -> Mode:
        """What analyzer_factory will actually serve.

        Returns ``"MOCK"`` when either mock_mode is enabled or the configured
        live provider lacks credentials.  This is the value the UI badge
        should reflect so a silent fallback is visible.
        """
        if self.mock_mode:
            return "MOCK"
        if not self.has_live_credentials:
            return "MOCK"
        return "LIVE"

    @property
    def active_model(self) -> str:
        if self.effective_mode == "MOCK":
            return "mock-1.0"
        return self.openai_model if self.llm_provider == "openai" else self.gemini_model

    @property
    def active_provider(self) -> str:
        if self.effective_mode == "MOCK":
            return "mock"
        return self.llm_provider

    @property
    def fallback_reason(self) -> str | None:
        """Human-readable reason when mode ≠ effective_mode; ``None`` otherwise."""
        if self.mode == self.effective_mode:
            return None
        # mode=LIVE, effective_mode=MOCK
        if self.llm_provider == "gemini":
            return "LLM_PROVIDER=gemini 이지만 GEMINI_API_KEY 가 설정되지 않았습니다."
        if self.llm_provider == "openai":
            return "LLM_PROVIDER=openai 이지만 OPENAI_API_KEY 가 설정되지 않았습니다."
        return f"프로바이더 '{self.llm_provider}' 의 API 키가 없습니다."


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        llm_provider=_get_provider("gemini"),
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
        mock_mode=_get_bool("MOCK_MODE", True),
        max_upload_bytes=_get_int("MAX_UPLOAD_BYTES", 20 * 1024 * 1024),
        max_url_bytes=_get_int("MAX_URL_BYTES", 2 * 1024 * 1024),
        cors_allow_origins=_get_list(
            "CORS_ALLOW_ORIGINS",
            ["http://localhost:5173", "http://localhost:5174", "http://localhost:5175"],
        ),
        weights=_load_weights(),
    )


def reset_settings_cache() -> None:
    """Test helper: clear the settings cache and cached SDK clients."""
    get_settings.cache_clear()
    try:  # avoid circular import at module load
        from app.services import analyzer_factory  # noqa: WPS433 — runtime local

        analyzer_factory.reset_client_cache()
    except ImportError:  # pragma: no cover
        pass
