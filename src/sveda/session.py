from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx

from sveda.client import SvedaClient
from sveda.exceptions import APIError


def start_host_session(
    base_url: str = "",
    host_api_key: str = "",
    visitor_id: str = "",
    *,
    host: Any | None = None,
    user: Any | None = None,
    request_origin: str | None = None,
    host_mcp_url: str | None = None,
    host_mcp_token: str | None = None,
    mint_mcp_token: Callable[[], str] | None = None,
    http_client: httpx.Client | None = None,
) -> dict[str, Any]:
    if host is not None:
        from sveda.host.manager import HostManager

        if not isinstance(host, HostManager):
            raise TypeError("host must be a HostManager instance.")
        session_user = user if user is not None else {"id": visitor_id or "anonymous"}
        return host.start_session(session_user, request_origin=request_origin)

    origin = base_url.rstrip("/")
    mcp_url = host_mcp_url
    mcp_token = host_mcp_token
    if mint_mcp_token is not None and not str(mcp_token or "").strip():
        mcp_token = mint_mcp_token()

    with SvedaClient(
        origin,
        host_api_key=host_api_key,
        http_client=http_client,
    ) as client:
        token = client.embed.create_token(
            visitor_id=visitor_id or None,
            host_mcp_url=mcp_url,
            host_mcp_token=mcp_token,
        )
    if token.token == "":
        raise APIError("Sidecar returned an empty embed token.")
    return {
        "origin": origin,
        "token": token.token,
        "expires_in": token.expires_in,
        "appearance": token.appearance,
    }
