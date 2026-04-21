"""Unit tests for model alias resolution."""
from __future__ import annotations

from amplifier_module_tool_veo.tool import _DEFAULT_MODEL, _MODEL_ALIASES, _resolve_model

# ---------------------------------------------------------------------------
# _resolve_model
# ---------------------------------------------------------------------------


def test_resolve_none_returns_none():
    assert _resolve_model(None) is None


def test_resolve_empty_string_returns_none():
    assert _resolve_model("") is None


def test_resolve_default_model_passthrough():
    assert _resolve_model(_DEFAULT_MODEL) == _DEFAULT_MODEL


def test_resolve_alias_veo_3_1():
    assert _resolve_model("veo-3.1") == "veo-3.1-generate-preview"
    assert _resolve_model("veo31") == "veo-3.1-generate-preview"
    assert _resolve_model("3.1") == "veo-3.1-generate-preview"


def test_resolve_alias_fast():
    assert _resolve_model("fast") == "veo-3.1-fast-generate-preview"
    assert _resolve_model("veo-3.1-fast") == "veo-3.1-fast-generate-preview"


def test_resolve_alias_lite():
    assert _resolve_model("lite") == "veo-3.1-lite-generate-preview"
    assert _resolve_model("veo-3.1-lite") == "veo-3.1-lite-generate-preview"


def test_resolve_alias_veo3():
    assert _resolve_model("veo-3") == "veo-3.0-generate-001"
    assert _resolve_model("veo3") == "veo-3.0-generate-001"


def test_resolve_alias_veo3_fast():
    assert _resolve_model("veo-3-fast") == "veo-3.0-fast-generate-001"
    assert _resolve_model("veo3-fast") == "veo-3.0-fast-generate-001"


def test_resolve_alias_veo2():
    assert _resolve_model("veo-2") == "veo-2.0-generate-001"
    assert _resolve_model("veo2") == "veo-2.0-generate-001"


def test_resolve_alias_case_insensitive():
    assert _resolve_model("FAST") == "veo-3.1-fast-generate-preview"
    assert _resolve_model("Lite") == "veo-3.1-lite-generate-preview"
    assert _resolve_model("VEO-3.1") == "veo-3.1-generate-preview"


def test_resolve_unknown_passthrough():
    """An unknown string should pass through unchanged (allows full model IDs)."""
    full_id = "veo-9.0-generate-001"
    assert _resolve_model(full_id) == full_id


def test_resolve_strips_whitespace():
    assert _resolve_model("  fast  ") == "veo-3.1-fast-generate-preview"


def test_all_aliases_resolve_to_valid_strings():
    for alias, expected in _MODEL_ALIASES.items():
        assert isinstance(expected, str)
        assert len(expected) > 0
        result = _resolve_model(alias)
        assert result == expected, f"Alias {alias!r} → {result!r} (expected {expected!r})"


# ---------------------------------------------------------------------------
# VeoTool model config/env/default precedence
# ---------------------------------------------------------------------------


def make_tool(config: dict | None = None) -> object:
    from amplifier_module_tool_veo.tool import VeoTool
    from tests.conftest import _ModuleCoordinator

    return VeoTool(config or {}, _ModuleCoordinator())


def test_default_model_used_when_nothing_configured():
    tool = make_tool()
    assert tool.model == _DEFAULT_MODEL


def test_config_model_takes_priority(monkeypatch):
    monkeypatch.setenv("VEO_MODEL", "veo-2")
    tool = make_tool({"model": "fast"})
    assert tool.model == "veo-3.1-fast-generate-preview"


def test_env_var_used_when_no_config_model(monkeypatch):
    monkeypatch.setenv("VEO_MODEL", "veo-2")
    tool = make_tool()
    assert tool.model == "veo-2.0-generate-001"


def test_default_used_when_no_config_and_no_env(monkeypatch):
    monkeypatch.delenv("VEO_MODEL", raising=False)
    tool = make_tool()
    assert tool.model == _DEFAULT_MODEL


def test_poll_interval_default():
    tool = make_tool()
    assert tool.poll_interval == 10


def test_poll_interval_from_config():
    tool = make_tool({"poll_interval_seconds": 30})
    assert tool.poll_interval == 30
