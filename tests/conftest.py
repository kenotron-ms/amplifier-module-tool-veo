"""Stub amplifier_core so tests run without the Amplifier runtime installed."""
from __future__ import annotations

import sys
import types as stdlib_types

# ---------------------------------------------------------------------------
# Build a minimal amplifier_core stub
# ---------------------------------------------------------------------------

_amplifier_core = stdlib_types.ModuleType("amplifier_core")


class _ToolResult:
    def __init__(
        self,
        *,
        success: bool,
        output: object = None,
        error: dict | None = None,
    ) -> None:
        self.success = success
        self.output = output
        self.error = error

    def __repr__(self) -> str:  # pragma: no cover
        return f"ToolResult(success={self.success}, output={self.output!r})"


class _Hooks:
    async def emit(self, event: str, data: dict) -> None:  # noqa: ARG002
        pass


class _ModuleCoordinator:
    def __init__(self) -> None:
        self.hooks = _Hooks()
        self._capabilities: dict[str, object] = {}

    def get_capability(self, key: str) -> object:
        return self._capabilities.get(key)

    async def mount(self, section: str, obj: object, *, name: str) -> None:
        pass


_amplifier_core.ToolResult = _ToolResult  # type: ignore[attr-defined]
_amplifier_core.ModuleCoordinator = _ModuleCoordinator  # type: ignore[attr-defined]

sys.modules["amplifier_core"] = _amplifier_core
