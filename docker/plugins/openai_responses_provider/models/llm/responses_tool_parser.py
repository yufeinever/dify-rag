from __future__ import annotations

from typing import Any, Iterable


def get_field(obj: Any, name: str, default: Any = None) -> Any:
    """Read a field from either OpenAI SDK objects or proxy-returned dicts."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def item_to_function_call_data(item: Any, fallback_call_id: str = "") -> dict[str, str] | None:
    """Extract a Responses API function_call item into Dify-compatible data."""
    if get_field(item, "type") != "function_call":
        return None

    nested_function = get_field(item, "function", {}) or {}
    call_id = get_field(item, "call_id") or get_field(item, "id") or fallback_call_id
    name = get_field(item, "name") or get_field(nested_function, "name") or ""
    arguments = get_field(item, "arguments")
    if arguments is None:
        arguments = get_field(nested_function, "arguments")

    return {
        "call_id": str(call_id or fallback_call_id),
        "name": str(name or ""),
        "arguments": str(arguments or ""),
    }


def get_event_field(event: Any, name: str, default: Any = None) -> Any:
    """Read a streaming event field from either SDK objects or dict events."""
    return get_field(event, name, default)


def merge_function_call_data(
    pending: dict[int, dict[str, str]],
    output_index: int,
    data: dict[str, str] | None,
) -> None:
    """Merge partial function call state without overwriting known values with blanks."""
    if data is None:
        return

    current = pending.setdefault(output_index, {"call_id": "", "name": "", "arguments": ""})
    for key in ("call_id", "name", "arguments"):
        value = data.get(key)
        if value:
            current[key] = value


def append_function_call_arguments_delta(
    pending: dict[int, dict[str, str]],
    output_index: int,
    delta: str,
    item_id: str = "",
) -> None:
    current = pending.setdefault(
        output_index,
        {"call_id": item_id or f"call_{output_index}", "name": "", "arguments": ""},
    )
    if item_id and not current.get("call_id"):
        current["call_id"] = item_id
    current["arguments"] = current.get("arguments", "") + (delta or "")


def finalize_function_call_arguments(
    pending: dict[int, dict[str, str]],
    output_index: int,
    arguments: str,
    name: str = "",
    item_id: str = "",
) -> None:
    current = pending.setdefault(
        output_index,
        {"call_id": item_id or f"call_{output_index}", "name": "", "arguments": ""},
    )
    if item_id and not current.get("call_id"):
        current["call_id"] = item_id
    if name:
        current["name"] = name
    current["arguments"] = arguments or ""


def collect_response_output_function_calls(output_items: Iterable[Any] | None) -> dict[int, dict[str, str]]:
    pending: dict[int, dict[str, str]] = {}
    for index, item in enumerate(output_items or []):
        data = item_to_function_call_data(item, fallback_call_id=f"call_{index}")
        merge_function_call_data(pending, index, data)
    return pending


def valid_function_call_data(
    calls: Iterable[dict[str, str]],
    allowed_names: set[str],
) -> list[dict[str, str]]:
    """Return only function calls that Dify can execute as declared tools."""
    valid: list[dict[str, str]] = []
    allowed_names = {name for name in allowed_names if name}
    for call in calls:
        name = (call.get("name") or "").strip()
        if not name:
            continue
        if name not in allowed_names:
            continue
        call_id = (call.get("call_id") or name).strip() or name
        arguments = call.get("arguments") or "{}"
        valid.append({"call_id": call_id, "name": name, "arguments": arguments})
    return valid
