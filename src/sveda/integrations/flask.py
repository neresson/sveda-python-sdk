from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sveda.host.http import process_host_mcp_http
from sveda.host.manager import HostManager

if TYPE_CHECKING:
    from flask import Flask


def register_host_mcp(app: Any, host: HostManager, path: str = "/mcp/sveda") -> None:
    from flask import Response, request

    @app.post(path)
    def _sveda_host_mcp() -> Response:
        status, headers, body = process_host_mcp_http(
            host,
            body=request.get_data(),
            headers={key: value for key, value in request.headers.items()},
        )
        if body is None:
            return Response(status=status, headers=headers)
        return Response(body, status=status, headers=headers, mimetype="application/json")
