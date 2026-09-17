from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class EmbedToken:
    token: str
    visitor_id: str
    expires_in: int
    appearance: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> EmbedToken:
        appearance = payload.get("appearance")
        raw_expires = payload.get("expires_in", 3600)
        if raw_expires is None:
            raw_expires = 3600
        return cls(
            token=str(payload.get("token", "")),
            visitor_id=str(payload.get("visitor_id", "")),
            expires_in=max(60, int(raw_expires)),
            appearance=appearance if isinstance(appearance, dict) else None,
        )


@dataclass(frozen=True)
class Message:
    explanation: str
    tokens_used: int
    chat_id: str
    payload: dict[str, Any]

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Message:
        data = dict(payload)
        return cls(
            explanation=str(data.get("explanation", "")),
            tokens_used=int(data.get("tokens_used") or 0),
            chat_id=str(data.get("chat_id", "")),
            payload=data,
        )
