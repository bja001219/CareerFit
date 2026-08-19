"""Config tests — SPEC §7 boot validation, Grill Me #1 Finding 14."""
from __future__ import annotations

import pytest

from app.models.errors import ConfigurationError


def test_default_settings_construct_without_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import reset_settings_cache, get_settings

    reset_settings_cache()
    settings = get_settings()
    assert settings.mock_mode is True
    assert abs(sum(settings.weights.values()) - 1.0) < 1e-6


def test_config_rejects_weights_not_summing_to_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Grill Me #1 Finding 14: silent bad weights would produce >100 scores."""
    monkeypatch.setenv("WEIGHT_RESPONSIBILITY", "0.35")  # sums to 1.05
    monkeypatch.setenv("WEIGHT_REQUIREMENT", "0.35")
    monkeypatch.setenv("WEIGHT_TECH", "0.20")
    monkeypatch.setenv("WEIGHT_EXPERIENCE", "0.10")
    monkeypatch.setenv("WEIGHT_PREFERRED", "0.05")

    from app.config import reset_settings_cache, get_settings

    reset_settings_cache()

    with pytest.raises(ConfigurationError) as excinfo:
        get_settings()
    assert "1.0" in str(excinfo.value)


def test_config_accepts_explicit_weight_override_that_still_sums(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WEIGHT_RESPONSIBILITY", "0.20")
    monkeypatch.setenv("WEIGHT_REQUIREMENT", "0.40")
    monkeypatch.setenv("WEIGHT_TECH", "0.20")
    monkeypatch.setenv("WEIGHT_EXPERIENCE", "0.15")
    monkeypatch.setenv("WEIGHT_PREFERRED", "0.05")

    from app.config import reset_settings_cache, get_settings

    reset_settings_cache()
    settings = get_settings()
    assert settings.weights["requirement"] == 0.40


def test_active_model_reflects_effective_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    # No OPENAI_API_KEY → effective_mode = MOCK → model = mock-1.0
    from app.config import reset_settings_cache, get_settings

    reset_settings_cache()
    settings = get_settings()
    assert settings.mode == "LIVE"
    assert settings.effective_mode == "MOCK"
    assert settings.active_model == "mock-1.0"
    assert settings.active_provider == "mock"
