"""LLM client — OpenAI Responses API or Moonshot/Kimi chat completions."""
import json
import time
import uuid

from openai import OpenAI, OpenAIError, RateLimitError

from langbridge_code.llm.debug import print_llm_request, print_llm_response


class ApiQuotaExceeded(RuntimeError):
    """Non-retryable provider quota limit (e.g. Moonshot organization TPD)."""


def rate_limit_is_non_retryable(error: RateLimitError) -> bool:
    """Return True when backing off will not help until quota resets."""
    text = str(error).lower()
    return (
        "tpd" in text
        or "tokens per day" in text
        or "rate_limit_reached_error" in text and "daily" in text
    )


def quota_exceeded_message(error: RateLimitError) -> str:
    return (
        "API daily token quota is exhausted (provider TPD limit). "
        "Wait for the daily reset, or switch provider/model/API key in ~/.langbridge/config.json."
    )


def format_api_error(error: BaseException) -> str:
    if isinstance(error, ApiQuotaExceeded):
        return str(error)
    if isinstance(error, RateLimitError) and rate_limit_is_non_retryable(error):
        return quota_exceeded_message(error)
    text = str(error).strip()
    if "429" in text and "tpd" in text.lower():
        return quota_exceeded_message(RateLimitError(text))
    if len(text) > 400:
        return f"Request failed: {text[:400]}…"
    return f"Request failed: {text}"
from langbridge_code.llm.parse import extract_output_text
from langbridge_code.settings import API_BASE_URL, API_PROVIDER, load_config


def make_client(api_key):
    kwargs = {"api_key": api_key}
    if API_BASE_URL:
        kwargs["base_url"] = API_BASE_URL
    return OpenAI(**kwargs)


def uses_responses_api(provider=None):
    return (provider or API_PROVIDER) == "openai"


def to_chat_tools(tool_schemas):
    tools = []
    for schema in tool_schemas or []:
        tools.append({
            "type": "function",
            "function": {
                "name": schema["name"],
                "description": schema.get("description", ""),
                "parameters": schema.get("parameters", {"type": "object", "properties": {}}),
            },
        })
    return tools


def to_chat_messages(agent_input):
    messages = []
    pending_calls = []

    def flush_calls():
        nonlocal pending_calls
        if not pending_calls:
            return
        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": call["call_id"],
                    "type": "function",
                    "function": {
                        "name": call["name"],
                        "arguments": call.get("arguments") or "{}",
                    },
                }
                for call in pending_calls
            ],
        })
        pending_calls = []

    for item in agent_input:
        role = item.get("role")
        if role in {"system", "user", "assistant"}:
            flush_calls()
            messages.append({"role": role, "content": item.get("content", "")})
            continue

        item_type = item.get("type")
        if item_type == "function_call":
            pending_calls.append(item)
            continue
        if item_type == "function_call_output":
            flush_calls()
            messages.append({
                "role": "tool",
                "tool_call_id": item["call_id"],
                "content": item.get("output", ""),
            })
            continue
        if item_type == "message":
            flush_calls()
            text = extract_output_text([item])
            if text:
                messages.append({"role": "assistant", "content": text})

    flush_calls()
    return messages


def from_chat_message(message):
    output = []
    reasoning = getattr(message, "reasoning_content", None) or getattr(message, "reasoning", None)
    if reasoning:
        output.append({
            "type": "reasoning",
            "summary": [{"type": "summary_text", "text": str(reasoning)}],
        })

    tool_calls = getattr(message, "tool_calls", None) or []
    if tool_calls:
        for call in tool_calls:
            fn = call.function
            output.append({
                "type": "function_call",
                "name": fn.name,
                "call_id": call.id or f"call_{uuid.uuid4().hex[:12]}",
                "arguments": fn.arguments or "{}",
            })
        return output

    content = message.content
    if content:
        output.append({
            "type": "message",
            "content": [{"type": "output_text", "text": content}],
        })
    return output


def create_model_response(
    api_key,
    model,
    agent_input,
    *,
    tool_schemas=None,
    reasoning=None,
    label="agent",
):
    print_llm_request(label, model, agent_input, tool_schemas)
    client = make_client(api_key)
    last_error = None
    for attempt in range(8):
        try:
            if uses_responses_api():
                kwargs = {"model": model, "input": agent_input}
                if tool_schemas:
                    kwargs["tools"] = tool_schemas
                if reasoning is not None:
                    kwargs["reasoning"] = reasoning
                response = client.responses.create(**kwargs)
                data = response.model_dump(exclude_none=True)
            else:
                kwargs = {
                    "model": model,
                    "messages": to_chat_messages(agent_input),
                }
                if tool_schemas:
                    kwargs["tools"] = to_chat_tools(tool_schemas)
                response = client.chat.completions.create(**kwargs)
                message = response.choices[0].message
                data = {"output": from_chat_message(message)}
            print_llm_response(label, data)
            return data
        except RateLimitError as error:
            if rate_limit_is_non_retryable(error):
                raise ApiQuotaExceeded(quota_exceeded_message(error)) from error
            last_error = error
            time.sleep(min(2 ** attempt, 30))
        except OpenAIError as error:
            raise RuntimeError(str(error)) from error
    if isinstance(last_error, RateLimitError) and rate_limit_is_non_retryable(last_error):
        raise ApiQuotaExceeded(quota_exceeded_message(last_error)) from last_error
    raise RuntimeError(str(last_error)) from last_error
