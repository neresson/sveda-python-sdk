from __future__ import annotations

from typing import Any

from sveda.host.http import process_host_mcp_http
from sveda.host.manager import HostManager


def host_mcp_view(host: HostManager) -> Any:
    from django.http import HttpResponse
    from django.views.decorators.csrf import csrf_exempt
    from django.views.decorators.http import require_POST

    @csrf_exempt
    @require_POST
    def view(request: Any) -> HttpResponse:
        headers: dict[str, str] = {}
        authorization = request.META.get("HTTP_AUTHORIZATION")
        if authorization:
            headers["Authorization"] = authorization
        page_context = request.META.get("HTTP_X_SVEDA_PAGE_CONTEXT")
        if page_context:
            headers["X-Sveda-Page-Context"] = page_context
        chat_id = request.META.get("HTTP_X_SVEDA_CHAT_ID")
        if chat_id:
            headers["X-Sveda-Chat-Id"] = chat_id

        status, headers, body = process_host_mcp_http(
            host,
            body=request.body,
            headers=headers,
        )
        if body is None:
            return HttpResponse(status=status, headers=headers)
        return HttpResponse(body, status=status, headers=headers, content_type="application/json")

    return view
