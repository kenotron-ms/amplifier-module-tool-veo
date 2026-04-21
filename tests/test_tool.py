"""Unit tests for VeoTool — no external API calls."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from amplifier_module_tool_veo.tool import VeoTool

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_tool(config: dict | None = None) -> VeoTool:
    from tests.conftest import _ModuleCoordinator

    coordinator = _ModuleCoordinator()
    return VeoTool(config or {}, coordinator)


# ---------------------------------------------------------------------------
# Protocol surface
# ---------------------------------------------------------------------------


def test_tool_name():
    tool = make_tool()
    assert tool.name == "veo"


def test_tool_description_mentions_operations():
    tool = make_tool()
    for op in ("generate", "image_to_video", "reference_images", "extend"):
        assert op in tool.description


def test_input_schema_structure():
    tool = make_tool()
    schema = tool.input_schema
    assert schema["type"] == "object"
    props = schema["properties"]
    # Core params
    for field in ("operation", "prompt", "output_path", "model"):
        assert field in props, f"Missing field: {field}"
    # Image inputs
    for field in ("image_path", "last_frame_path", "reference_image_paths"):
        assert field in props
    # Extension
    assert "video_uri" in props
    # Config params
    for field in ("aspect_ratio", "duration_seconds", "resolution",
                  "person_generation", "number_of_videos", "seed",
                  "poll_interval_seconds"):
        assert field in props, f"Missing config field: {field}"
    # Only "operation" is required
    assert schema["required"] == ["operation"]


def test_operation_enum():
    tool = make_tool()
    enum_values = tool.input_schema["properties"]["operation"]["enum"]
    assert set(enum_values) == {"generate", "image_to_video", "reference_images", "extend"}


def test_aspect_ratio_enum():
    tool = make_tool()
    enum_values = tool.input_schema["properties"]["aspect_ratio"]["enum"]
    assert "16:9" in enum_values
    assert "9:16" in enum_values


def test_resolution_enum():
    tool = make_tool()
    enum_values = tool.input_schema["properties"]["resolution"]["enum"]
    assert set(enum_values) == {"720p", "1080p", "4k"}


def test_duration_enum():
    tool = make_tool()
    enum_values = tool.input_schema["properties"]["duration_seconds"]["enum"]
    assert "4" in enum_values
    assert "8" in enum_values


# ---------------------------------------------------------------------------
# API key guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_api_key_returns_failure():
    tool = make_tool()
    with patch.dict(os.environ, {}, clear=True):
        # Remove GOOGLE_API_KEY if it exists
        os.environ.pop("GOOGLE_API_KEY", None)
        result = await tool.execute({"operation": "generate", "prompt": "test"})
    assert result.success is False
    assert "GOOGLE_API_KEY" in result.output


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_requires_prompt():
    tool = make_tool()
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "fake-key"}):
        result = await tool.execute({"operation": "generate"})
    assert result.success is False
    assert "prompt" in result.output.lower()


@pytest.mark.asyncio
async def test_image_to_video_requires_image_path():
    tool = make_tool()
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "fake-key"}):
        result = await tool.execute({"operation": "image_to_video", "prompt": "test"})
    assert result.success is False
    assert "image_path" in result.output


@pytest.mark.asyncio
async def test_image_to_video_missing_image_file():
    tool = make_tool()
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "fake-key"}):
        result = await tool.execute({
            "operation": "image_to_video",
            "prompt": "test",
            "image_path": "/nonexistent/image.png",
        })
    assert result.success is False
    assert "not found" in result.output.lower()


@pytest.mark.asyncio
async def test_reference_images_requires_paths():
    tool = make_tool()
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "fake-key"}):
        result = await tool.execute({"operation": "reference_images", "prompt": "test"})
    assert result.success is False
    assert "reference_image_paths" in result.output


@pytest.mark.asyncio
async def test_reference_images_too_many():
    tool = make_tool()
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "fake-key"}):
        result = await tool.execute({
            "operation": "reference_images",
            "prompt": "test",
            "reference_image_paths": ["a.png", "b.png", "c.png", "d.png"],
        })
    assert result.success is False
    assert "3" in result.output


@pytest.mark.asyncio
async def test_extend_requires_video_uri():
    tool = make_tool()
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "fake-key"}):
        result = await tool.execute({"operation": "extend"})
    assert result.success is False
    assert "video_uri" in result.output


@pytest.mark.asyncio
async def test_unknown_operation():
    tool = make_tool()
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "fake-key"}):
        # Need a mock client so we get past import but fail on unknown op
        with patch("amplifier_module_tool_veo.tool.VeoTool.execute", wraps=tool.execute):
            pass
        # Patch google.genai at import level so the client creation doesn't fail
        mock_genai = MagicMock()
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_genai.types = MagicMock()
        with patch.dict("sys.modules", {"google": MagicMock(), "google.genai": mock_genai}):
            result = await tool.execute({"operation": "fly_to_the_moon"})
    assert result.success is False
    assert "fly_to_the_moon" in result.output


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def test_resolve_path_absolute():
    tool = make_tool({"working_dir": "/tmp/work"})
    path = tool._resolve_path("/absolute/path.mp4")
    assert path == Path("/absolute/path.mp4")


def test_resolve_path_relative_with_working_dir():
    tool = make_tool({"working_dir": "/tmp/work"})
    path = tool._resolve_path("output.mp4")
    assert path == Path("/tmp/work/output.mp4")


def test_resolve_path_relative_without_working_dir():
    tool = make_tool()
    path = tool._resolve_path("output.mp4")
    assert path == Path("output.mp4")


def test_resolve_output_path_default_timestamped():
    tool = make_tool({"working_dir": "/tmp/work"})
    path = tool._resolve_output_path(None, "generate")
    assert path.suffix == ".mp4"
    assert "generate" in path.name
    assert path.parent == Path("/tmp/work")


def test_resolve_output_path_explicit():
    tool = make_tool()
    path = tool._resolve_output_path("my_video.mp4", "generate")
    assert path == Path("my_video.mp4")


# ---------------------------------------------------------------------------
# _build_config
# ---------------------------------------------------------------------------


def test_build_config_returns_none_when_empty():
    tool = make_tool()
    mock_types = MagicMock()
    result = tool._build_config(mock_types, {})
    assert result is None
    mock_types.GenerateVideosConfig.assert_not_called()


def test_build_config_passes_all_params():
    tool = make_tool()
    mock_types = MagicMock()
    tool._build_config(mock_types, {
        "aspect_ratio": "9:16",
        "duration_seconds": "8",
        "resolution": "1080p",
        "person_generation": "allow_adult",
        "number_of_videos": 1,
        "seed": 42,
    })
    mock_types.GenerateVideosConfig.assert_called_once_with(
        aspect_ratio="9:16",
        duration_seconds="8",
        resolution="1080p",
        person_generation="allow_adult",
        number_of_videos=1,
        seed=42,
    )


def test_build_config_merges_extra():
    tool = make_tool()
    mock_types = MagicMock()
    last_frame = MagicMock()
    tool._build_config(mock_types, {"resolution": "720p"}, extra={"last_frame": last_frame})
    call_kwargs = mock_types.GenerateVideosConfig.call_args[1]
    assert call_kwargs["resolution"] == "720p"
    assert call_kwargs["last_frame"] is last_frame


# ---------------------------------------------------------------------------
# _load_image
# ---------------------------------------------------------------------------


def test_load_image_jpeg():
    tool = make_tool()
    mock_types = MagicMock()
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(b"\xff\xd8\xff\xe0fake jpeg bytes")
        tmp_path = f.name
    try:
        tool._load_image(mock_types, tmp_path)
        call_kwargs = mock_types.Image.call_args[1]
        assert call_kwargs["mime_type"] == "image/jpeg"
        assert isinstance(call_kwargs["image_bytes"], bytes)
    finally:
        os.unlink(tmp_path)


def test_load_image_png():
    tool = make_tool()
    mock_types = MagicMock()
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(b"\x89PNG\r\n\x1a\nfake png")
        tmp_path = f.name
    try:
        tool._load_image(mock_types, tmp_path)
        call_kwargs = mock_types.Image.call_args[1]
        assert call_kwargs["mime_type"] == "image/png"
    finally:
        os.unlink(tmp_path)


def test_load_image_file_not_found():
    tool = make_tool()
    mock_types = MagicMock()
    with pytest.raises(FileNotFoundError):
        tool._load_image(mock_types, "/nonexistent/image.png")


# ---------------------------------------------------------------------------
# mount() function
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mount_raises_on_missing_dependency():
    import sys
    from unittest.mock import patch

    from tests.conftest import _ModuleCoordinator

    coordinator = _ModuleCoordinator()

    with (
        patch.dict(sys.modules, {"google": None, "google.genai": None}),
        pytest.raises(ImportError, match="google-genai"),
    ):
        from amplifier_module_tool_veo import mount
        await mount(coordinator)
