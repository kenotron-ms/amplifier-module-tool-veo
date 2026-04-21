"""Amplifier tool module: Veo video generation via Google Gemini API."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

__amplifier_module_type__ = "tool"

if TYPE_CHECKING:
    from amplifier_core import ModuleCoordinator


async def mount(coordinator: ModuleCoordinator, config: dict[str, Any] | None = None) -> None:
    """Mount the Veo tool into the Amplifier coordinator."""
    try:
        import google.genai  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "google-genai is not installed. Run: pip install google-genai>=1.0.0"
        ) from exc

    from amplifier_core import ModuleCoordinator as _MC  # noqa: F401

    config = config or {}

    # Pull session working directory from coordinator capabilities
    if "working_dir" not in config:
        working_dir = coordinator.get_capability("session.working_dir")
        if working_dir:
            config["working_dir"] = working_dir

    from .tool import VeoTool

    tool = VeoTool(config, coordinator)
    await coordinator.mount("tools", tool, name=tool.name)
