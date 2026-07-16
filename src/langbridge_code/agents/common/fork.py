"""Forks of a live agent context (prefix-cache friendly).

A fork reuses the agent's message list verbatim and appends one instruction,
so the provider can serve the shared prefix from cache. One-pass forks write
progress notes; tool-using forks handle bounded side workflows such as memory
maintenance. A fresh LLM cannot read the raw traces, but the live context
already has everything.
"""
from __future__ import annotations

import json

from langbridge_code.agents.common import control
from langbridge_code.settings import MAX_AGENT_STEPS
from langbridge_code.tools.common.purpose import without_purpose


def fork_one_pass(api_key, model, messages: list[dict], instruction: str, *, label: str = "fork") -> str:
    from langbridge_code.llm.client import create_model_response
    from langbridge_code.llm.parse import extract_output_text

    forked = list(messages) + [{"role": "user", "content": instruction}]
    data = create_model_response(api_key, model, forked, label=label)
    return extract_output_text(data.get("output", [])).strip()


def fork_agent(
    api_key,
    model,
    messages: list[dict],
    instruction: str,
    *,
    tool_schemas,
    tools,
    label: str = "fork agent",
    max_steps: int = MAX_AGENT_STEPS,
) -> str:
    """Fork live context and run a tool-using agent until its final reply."""
    from langbridge_code.llm.client import create_model_response
    from langbridge_code.llm.parse import extract_output_text

    forked = list(messages) + [{"role": "user", "content": instruction}]
    for _ in range(max_steps):
        control.checkpoint()
        data = control.run_interruptible(
            lambda: create_model_response(
                api_key,
                model,
                forked,
                tool_schemas=tool_schemas,
                reasoning={"summary": "auto"},
                label=label,
            )
        )
        output = list(data.get("output", []))
        forked.extend(output)
        calls = [item for item in output if item.get("type") == "function_call"]
        if not calls:
            return extract_output_text(output).strip()
        for call in calls:
            call_id = call.get("call_id")
            try:
                arguments = without_purpose(json.loads(call.get("arguments") or "{}"))
                name = call.get("name")
                if name not in tools:
                    raise ValueError(f"Unknown {label} tool: {name}")
                result = tools[name](**arguments)
            except Exception as error:
                result = f"Tool error: {error}"
            forked.append(
                {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": result,
                }
            )
    return f"{label} stopped: max steps."
