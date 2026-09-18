from __future__ import annotations

import json
import re
from typing import Any

from sveda.host.constants import MCP_PROTOCOL_VERSION
from sveda.host.manager import HostManager
from sveda.host.mcp_handler import handle_host_mcp_request

_BEARER = re.compile(r"^Bearer\s+(.+)$", re.IGNORECASE)


def read_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    match = _BEARER.match(authorization.strip())
    return match.group(1).strip() if match else None


def authenticate_host_mcp(
    host: HostManager,
    authorization: str | None,
) -> dict[str, Any] | None:
    plain = read_bearer_token(authorization)
    if not plain:
        return None
    auth = host.authenticate_bearer_token(plain)
    if auth is None or auth.get("user") is None:
        return None
    if not host.authorize(auth["user"]):
        raise PermissionError("forbidden")
    host.after_authenticate(auth["user"])
    return auth


def process_host_mcp_http(
    host: HostManager,
    *,
    body: bytes | str | dict[str, Any] | None,
    headers: dict[str, Any] | None,
    user: Any | None = None,
    authorization: str | None = None,
) -> tuple[int, dict[str, str], bytes | None]:
    auth_headers = headers or {}
    auth_header = authorization
    if auth_header is None:
        auth_header = auth_headers.get("Authorization") or auth_headers.get("authorization")
        if isinstance(auth_header, list):
            auth_header = auth_header[0] if auth_header else None

    if user is None:
        try:
            auth = authenticate_host_mcp(host, str(auth_header) if auth_header else None)
        except PermissionError:
            return 403, {"Content-Type": "text/plain"}, b"forbidden"
        if auth is None:
            return 401, {"Content-Type": "text/plain"}, b"unauthorized"
        user = auth["user"]

    parsed: Any
    if isinstance(body, dict):
        parsed = body
    elif isinstance(body, (bytes, bytearray)):
        parsed = json.loads(body.decode("utf-8") or "{}")
    elif isinstance(body, str):
        parsed = json.loads(body or "{}")
    else:
        parsed = {}

    outcome = handle_host_mcp_request(host, parsed, user=user, headers=auth_headers)
    response_headers = {"Content-Type": "application/json; charset=utf-8"}
    response_headers["mcp-protocol-version"] = MCP_PROTOCOL_VERSION
    session_id = outcome.get("session_id")
    if isinstance(session_id, str):
        response_headers["mcp-session-id"] = session_id

    if outcome.get("body") is None:
        return int(outcome.get("status", 202)), response_headers, None

    payload = json.dumps(outcome["body"], ensure_ascii=False).encode("utf-8")
    return int(outcome.get("status", 200)), response_headers, payload
