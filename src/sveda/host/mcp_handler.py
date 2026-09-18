from __future__ import annotations

import inspect
import json
import time
from typing import Any

from sveda.host.constants import (
    CHAT_ID_HEADER,
    MCP_PROTOCOL_VERSION,
    PAGE_CONTEXT_HEADER,
    PAGE_CONTEXT_MAX_BYTES,
)
from sveda.host.manager import HostManager
from sveda.host.schema import build_input_schema, tool_annotations
from sveda.host.tool import HostCallContext


def _tool_attr(tool: Any, name: str, default: str = "") -> str:
    value = getattr(tool, name, default)
    return value() if callable(value) else str(value or default)


def _to_mcp_tool(tool: Any) -> dict[str, Any]:
    name = _tool_attr(tool, "name")
    mode = _tool_attr(tool, "mode", "read")
    return {
        "name": name,
        "title": name,
        "description": _tool_attr(tool, "description"),
        "inputSchema": build_input_schema(tool),
        "annotations": tool_annotations(mode),
        "_meta": {
            "domain": _tool_attr(tool, "domain", "other"),
            "mode": mode,
        },
    }


def _json_rpc_result(id_: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _json_rpc_error(id_: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def _encode_tool_result(result: Any) -> dict[str, Any]:
    if isinstance(result, str):
        text = result
    else:
        text = json.dumps(result, ensure_ascii=False)
    return {"content": [{"type": "text", "text": text}], "isError": False}


def _normalize_headers(headers: dict[str, Any] | None) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in (headers or {}).items():
        if isinstance(value, list):
            normalized[str(key).lower()] = str(value[0]) if value else ""
        else:
            normalized[str(key).lower()] = str(value)
    return normalized


def _read_page_context(headers: dict[str, str]) -> dict[str, Any] | None:
    raw = headers.get(PAGE_CONTEXT_HEADER) or headers.get("x-sveda-page-context")
    if not raw or len(raw) > PAGE_CONTEXT_MAX_BYTES:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _read_chat_id(headers: dict[str, str]) -> str | None:
    raw = headers.get(CHAT_ID_HEADER) or headers.get("x-sveda-chat-id")
    if not raw:
        return None
    value = raw.strip()
    return value or None


def handle_host_mcp_request(
    host: HostManager,
    body: Any,
    *,
    user: Any,
    headers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = body if isinstance(body, dict) else {}
    method = str(payload.get("method") or "")
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    id_ = payload.get("id")
    is_notification = id_ is None

    normalized = _normalize_headers(headers)
    call_context = HostCallContext(
        user=user,
        page_context=_read_page_context(normalized),
        chat_id=_read_chat_id(normalized),
    )

    if method == "notifications/initialized":
        return {"status": 202, "body": None}

    if method == "initialize":
        result: dict[str, Any] = {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {
                "name": host.server_name or "Host Application",
                "version": host.server_version or "0.1.0",
            },
        }
        instructions = (host.instructions or "").strip()
        if instructions:
            result["instructions"] = instructions
        return {
            "status": 200,
            "body": _json_rpc_result(id_, result),
            "session_id": f"sess-{int(time.time() * 1000)}",
        }

    if method == "tools/list":
        per_page = min(
            250,
            max(1, int(params.get("per_page") or params.get("perPage") or 250)),
        )
        tools = [_to_mcp_tool(tool) for tool in host.resolve_tools()]
        cursor = str(params.get("cursor") or "")
        start = 0 if cursor == "" else int(cursor)
        slice_ = tools[start : start + per_page]
        next_index = start + len(slice_)
        list_result: dict[str, Any] = {"tools": slice_}
        if next_index < len(tools):
            list_result["nextCursor"] = str(next_index)
        return {"status": 200, "body": _json_rpc_result(id_, list_result)}

    if method == "tools/call":
        name = str(params.get("name") or "")
        arguments = params.get("arguments")
        if not isinstance(arguments, dict):
            arguments = {}
        tool = next(
            (candidate for candidate in host.resolve_tools() if _tool_attr(candidate, "name") == name),
            None,
        )
        if tool is None:
            return {
                "status": 200,
                "body": _json_rpc_result(
                    id_,
                    {
                        "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
                        "isError": True,
                    },
                ),
            }
        try:
            handle = getattr(tool, "handle")
            try:
                outcome = handle(arguments, call_context)
            except TypeError:
                outcome = handle(arguments)
            if inspect.isawaitable(outcome):
                raise TypeError("Async tool handlers require handle_host_mcp_request_async.")
            return {"status": 200, "body": _json_rpc_result(id_, _encode_tool_result(outcome))}
        except Exception as exc:
            message = str(exc) or "Tool execution failed."
            return {
                "status": 200,
                "body": _json_rpc_result(
                    id_,
                    {"content": [{"type": "text", "text": message}], "isError": True},
                ),
            }

    if is_notification:
        return {"status": 202, "body": None}

    return {
        "status": 200,
        "body": _json_rpc_error(id_, -32601, f"Method not found: {method}"),
    }
