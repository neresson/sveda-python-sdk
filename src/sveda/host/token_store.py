from __future__ import annotations

import secrets
import time
from dataclasses import dataclass


@dataclass(slots=True)
class _TokenRecord:
    user_id: str
    ability: str
    expires_at: float


class McpTokenStore:
    def __init__(self) -> None:
        self._tokens: dict[str, _TokenRecord] = {}

    def mint(
        self,
        user_id: str,
        *,
        ability: str = "sveda:mcp",
        ttl_seconds: int = 3600,
        token_name: str = "sveda-mcp",
    ) -> str:
        del token_name
        ttl = max(60, int(ttl_seconds))
        token = secrets.token_hex(32)
        self._tokens[token] = _TokenRecord(
            user_id=str(user_id),
            ability=ability,
            expires_at=time.time() + ttl,
        )
        return token

    def verify(
        self,
        plain_token: str,
        expected_ability: str = "sveda:mcp",
    ) -> dict[str, str] | None:
        record = self._tokens.get(str(plain_token or ""))
        if record is None:
            return None
        if record.expires_at <= time.time():
            self._tokens.pop(plain_token, None)
            return None
        if expected_ability and record.ability != expected_ability:
            return None
        return {"user_id": record.user_id, "ability": record.ability}

    def revoke_for_user(self, user_id: str, token_name: str = "sveda-mcp") -> None:
        del token_name
        target = str(user_id)
        for token, record in list(self._tokens.items()):
            if record.user_id == target:
                self._tokens.pop(token, None)
