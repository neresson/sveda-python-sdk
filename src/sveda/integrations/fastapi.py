from __future__ import annotations

from typing import Any

from sveda.host.http import process_host_mcp_http
from sveda.host.manager import HostManager


def create_host_mcp_router(host: HostManager) -> Any:
    from fastapi import APIRouter, Request, Response

    router = APIRouter()

    @router.post("")
    async def sveda_host_mcp(request: Request) -> Response:
        body = await request.body()
        status, headers, payload = process_host_mcp_http(
            host,
            body=body,
            headers={key: value for key, value in request.headers.items()},
        )
        return Response(content=payload or b"", status_code=status, headers=headers)

    return router
