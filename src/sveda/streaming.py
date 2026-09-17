from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

SSE_DONE_LINE = "data: [DONE]"

STREAM_EVENTS = frozenset(
    {
        "message.start",
        "text.delta",
        "reasoning.delta",
        "tool.call",
        "tool.result",
        "tool.progress",
        "context.usage",
        "chat.title",
        "max_steps",
        "message.end",
        "error",
    }
)


@dataclass(frozen=True)
class StreamEvent:
    type: str
    payload: dict[str, Any]

    def __getattr__(self, name: str) -> Any:
        try:
            return self.payload[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def to_dict(self) -> dict[str, Any]:
        return self.payload


def parse_sse_line(line: str) -> StreamEvent | None:
    trimmed = line.strip()
    if not trimmed.startswith("data:"):
        return None

    payload = trimmed[5:].strip()
    if payload == "" or payload == "[DONE]":
        return None

    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError:
        return None

    if not isinstance(decoded, dict):
        return None

    event_type = decoded.get("type")
    if not isinstance(event_type, str) or event_type not in STREAM_EVENTS:
        return None

    return StreamEvent(type=event_type, payload=decoded)


def iter_sse_lines(lines: Iterable[str]) -> Iterator[StreamEvent]:
    for line in lines:
        event = parse_sse_line(line)
        if event is not None:
            yield event


def iter_sse_text(content: str) -> Iterator[StreamEvent]:
    return iter_sse_lines(content.splitlines())
