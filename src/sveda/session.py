from __future__ import annotations

from typing import Any

import httpx

from sveda.client import SvedaClient
from sveda.exceptions import APIError


def start_host_session(
    base_url: str,
    host_api_key: str,
    visitor_id: str,
    *,
    host_mcp_url: str | None = None,
    host_mcp_token: str | None = None,
    http_client: httpx.Client | None = None,
) -> dict[str, Any]:
    origin = base_url.rstrip("/")
    with SvedaClient(
        origin,
        host_api_key=host_api_key,
        http_client=http_client,
    ) as client:
        token = client.embed.create_token(
            visitor_id=visitor_id,
            host_mcp_url=host_mcp_url,
            host_mcp_token=host_mcp_token,
        )
    if token.token == "":
        raise APIError("Sidecar returned an empty embed token.")
    return {
        "origin": origin,
        "token": token.token,
        "expires_in": token.expires_in,
        "appearance": token.appearance,
    }
