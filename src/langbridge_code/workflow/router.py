"""One-shot LLM router: chat vs task, hard vs easy, task type."""
import json
import re

from langbridge_code.agents.roles import ROUTER_PROMPT
from langbridge_code.llm.client import create_model_response
from langbridge_code.llm.parse import print_step_trace
from langbridge_code.persistence.context import recent_chat_turns

_JSON_BLOCK = re.compile(r"\{[\s\S]*\}")


def route(api_key, model, user_message: str, *, messages=None, trace_sink=None) -> dict:
    router_messages = [{"role": "system", "content": ROUTER_PROMPT}]
    if messages:
        router_messages.extend(recent_chat_turns(messages))
    router_messages.append({"role": "user", "content": user_message})

    data = create_model_response(api_key, model, router_messages, label="Router")
    if trace_sink is not None:
        print_step_trace(
            data.get("output", []),
            include_message=True,
            label="Router",
            sink=trace_sink,
        )
    text = _extract_text(data)
    payload = _parse_json(text)
    kind = str(payload.get("kind", "chat")).strip().lower()
    if kind not in {"chat", "task"}:
        kind = "chat"
    task_type = str(payload.get("task_type", "coding")).strip().lower()
    if task_type not in {"coding", "presentation"}:
        task_type = "coding"
    return {
        "kind": kind,
        "hard": bool(payload.get("hard", False)),
        "task_type": task_type,
        "reply": str(payload.get("reply", "") or "").strip(),
        "task_summary": str(payload.get("task_summary", "") or user_message).strip(),
    }


def _extract_text(data):
    for item in data.get("output", []):
        if item.get("type") == "message":
            for part in item.get("content", []):
                if part.get("type") in {"output_text", "text"}:
                    return part.get("text", "")
    return ""


def _parse_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_BLOCK.search(text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return {"kind": "chat", "reply": text}
