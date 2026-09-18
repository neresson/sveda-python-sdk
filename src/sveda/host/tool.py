from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class HostCallContext:
    user: Any
    page_context: dict[str, Any] | None = None
    chat_id: str | None = None


@runtime_checkable
class HostTool(Protocol):
    def name(self) -> str: ...

    def description(self) -> str: ...

    def schema(self) -> dict[str, Any]: ...

    def mode(self) -> str: ...

    def domain(self) -> str: ...

    def handle(
        self,
        arguments: dict[str, Any],
        context: HostCallContext | None = None,
    ) -> Any: ...
