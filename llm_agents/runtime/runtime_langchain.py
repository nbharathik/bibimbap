"""LangChain-specific runtime helpers for LLM agents."""

from collections.abc import Mapping
from typing import Any

from langchain.chat_models import init_chat_model


def init_model(model_name: str | None, default_model: str):
    return init_chat_model(model_name or default_model)


def extract_token_usage_from_message(msg) -> tuple[int, int]:
    usage = getattr(msg, "usage_metadata", None) or {}
    if isinstance(usage, Mapping) and usage:
        in_tok = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
        out_tok = usage.get("output_tokens") or usage.get("completion_tokens") or 0
        return int(in_tok or 0), int(out_tok or 0)

    rm = getattr(msg, "response_metadata", None) or {}
    if isinstance(rm, Mapping) and rm:
        if any(
            k in rm
            for k in ("input_tokens", "prompt_tokens", "output_tokens", "completion_tokens")
        ):
            in_tok = rm.get("input_tokens") or rm.get("prompt_tokens") or 0
            out_tok = rm.get("output_tokens") or rm.get("completion_tokens") or 0
            return int(in_tok or 0), int(out_tok or 0)

        token_usage = rm.get("token_usage") or rm.get("usage") or {}
        if isinstance(token_usage, Mapping) and token_usage:
            in_tok = token_usage.get("input_tokens") or token_usage.get("prompt_tokens") or 0
            out_tok = token_usage.get("output_tokens") or token_usage.get("completion_tokens") or 0
            return int(in_tok or 0), int(out_tok or 0)

    return 0, 0


def aggregate_token_usage_from_callback(cb) -> tuple[int, int] | None:
    if cb is None or not getattr(cb, "usage_metadata", None):
        return None
    try:
        cb_in = cb_out = 0
        for v in cb.usage_metadata.values():
            if not isinstance(v, Mapping):
                continue
            cb_in += int(v.get("input_tokens") or v.get("prompt_tokens") or 0)
            cb_out += int(v.get("output_tokens") or v.get("completion_tokens") or 0)
        return cb_in, cb_out
    except Exception:
        return None


def normalize_finish_reason(message) -> str | None:
    rm = getattr(message, "response_metadata", None) or {}
    raw = None
    if isinstance(rm, Mapping):
        raw = rm.get("finish_reason") or rm.get("stop_reason")
    if raw is None:
        raw = getattr(message, "finish_reason", None)
    if raw is None:
        return None
    return str(raw).lower()


def content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, Mapping):
                if part.get("type") == "text" and "text" in part:
                    parts.append(str(part["text"]))
                elif "text" in part:
                    parts.append(str(part["text"]))
        return "".join(parts)
    return ""


def parse_messages_for_output_and_tool_calls(msgs) -> tuple[Any, list[dict], int, int]:
    model_out: Any = ""
    parsed_in = parsed_out = 0
    iterations: list[dict] = []

    for message in msgs or []:
        msg_input_tokens, msg_output_tokens = extract_token_usage_from_message(message)
        parsed_in += msg_input_tokens
        parsed_out += msg_output_tokens

        finish_reason = normalize_finish_reason(message)
        if not finish_reason:
            finish_reason = (
                message.response_metadata.get("stop_reason")
                if getattr(message, "response_metadata", None)
                else None
            )
            finish_reason = str(finish_reason).lower() if finish_reason else None

        raw_tool_calls: list = []
        tc_list = getattr(message, "tool_calls", None)
        if isinstance(tc_list, list):
            raw_tool_calls.extend(tc_list)
        elif tc_list:
            raw_tool_calls.append(tc_list)
        single_tc = getattr(message, "tool_call", None)
        if single_tc:
            raw_tool_calls.append(single_tc)

        tool_calls = []
        for tool_call in raw_tool_calls:
            if isinstance(tool_call, Mapping):
                name = tool_call.get("name") or tool_call.get("tool")
                args = tool_call.get("args") or tool_call.get("arguments")
            else:
                name = getattr(tool_call, "name", None)
                args = getattr(tool_call, "args", None) or getattr(tool_call, "arguments", None)

            if not name:
                continue
            if name == "ModelOutput":
                content = getattr(message, "content", None)
                if isinstance(content, list) and content:
                    first = content[0]
                    if isinstance(first, Mapping) and "partial_json" in first:
                        model_out = first.get("partial_json", model_out)
                continue
            tool_calls.append({"name": name, "args": args})

        if finish_reason in ("tool_calls", "tool_call", "tool_use") or tool_calls:
            if tool_calls:
                iterations.append(
                    {
                        "tool_calls": tool_calls,
                        "input_tokens": msg_input_tokens,
                        "output_tokens": msg_output_tokens,
                    }
                )

        if finish_reason in ("stop", "end_turn", "length", "max_tokens"):
            content = getattr(message, "content", None)
            if content is not None:
                text_content = content_to_text(content)
                if text_content:
                    model_out = text_content
                elif not isinstance(content, list):
                    model_out = content

    return model_out, iterations, parsed_in, parsed_out


def extract_messages_from_events(events: list) -> list:
    for event in reversed(events or []):
        if isinstance(event, Mapping):
            messages = event.get("data", {}).get("output", {}).get("messages")
            if messages is not None:
                return messages
    return []


def extract_structured_response_from_events(events: list):
    for event in reversed(events or []):
        if isinstance(event, Mapping):
            output = event.get("data", {}).get("output", {})
            if isinstance(output, Mapping) and "structured_response" in output:
                return output.get("structured_response")
    return None


def fallback_tool_iteration_from_event(event: dict) -> dict | None:
    if not isinstance(event, Mapping):
        return None
    event_type = event.get("event")
    if event_type not in ("on_tool_start", "on_tool_error"):
        return None
    name = event.get("name")
    if not name or name == "ModelOutput":
        return None
    data = event.get("data", {}) or {}
    args = data.get("input") or data.get("inputs")
    return {
        "tool_calls": [{"name": name, "args": args}],
        "input_tokens": 0,
        "output_tokens": 0,
    }
