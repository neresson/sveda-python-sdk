from __future__ import annotations

from typing import Any


def _normalize_property(definition: Any) -> dict[str, Any]:
    if not isinstance(definition, dict):
        return {"type": "string"}
    rest = {key: value for key, value in definition.items() if key != "required"}
    return rest or {"type": "string"}


def build_input_schema(tool: Any) -> dict[str, Any]:
    input_schema = getattr(tool, "input_schema", None)
    if isinstance(input_schema, dict):
        return input_schema

    raw = tool.schema() if callable(getattr(tool, "schema", None)) else getattr(tool, "schema", {})
    if not isinstance(raw, dict):
        raw = {}

    if raw.get("type") == "object" and isinstance(raw.get("properties"), dict):
        return raw

    properties: dict[str, Any] = {}
    required: list[str] = []

    for key, definition in raw.items():
        if not isinstance(key, str):
            continue
        properties[key] = _normalize_property(definition)
        if isinstance(definition, dict) and definition.get("required") is True:
            required.append(key)

    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def tool_annotations(mode: str) -> dict[str, bool]:
    if mode == "read":
        return {"readOnlyHint": True}
    if mode == "delete":
        return {"readOnlyHint": False, "destructiveHint": True}
    return {"readOnlyHint": False, "destructiveHint": False}
