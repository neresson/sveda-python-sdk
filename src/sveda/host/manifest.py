from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sveda._version import __version__
from sveda.host.mcp_handler import _to_mcp_tool

if TYPE_CHECKING:
    from sveda.host.manager import HostManager

HOST_MANIFEST_SCHEMA = "sveda.host/v1"


def host_hooks(host: HostManager) -> dict[str, bool]:
    return {
        "resolve_tools": host._resolve_tools_using is not None,
        "policy": host._policy_using is not None,
        "authorize": host._authorize_using is not None,
        "visitor_id": host._visitor_id_using is not None,
        "mint_token": host._mint_token_using is not None,
    }


def build_host_manifest(
    host: HostManager,
    user: Any = None,
    *,
    language: str = "python",
    version: str = __version__,
) -> dict[str, Any]:
    authenticated = user is not None
    policy = host.policy_for(user) if authenticated else None

    return {
        "schema": HOST_MANIFEST_SCHEMA,
        "sdk": {"language": language, "version": version},
        "subject": {
            "authenticated": authenticated,
            "policy": policy,
        },
        "hooks": host_hooks(host),
        "tools": [_to_mcp_tool(tool) for tool in host.resolve_tools(user)],
    }
