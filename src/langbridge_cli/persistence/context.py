"""Session message reconstruction and context compaction.

Rebuilds PM conversation history from session logs, and compacts live message
lists (PM loop or L4/L5/L3 specialist loops) with one shared strategy:

1. Tool result clearing — older tool rounds become one-line [cleared] metadata.
2. Recent files pin — last N read_file contents stay in COMPACTION_CONTEXT.
3. History summary — LLM-generated HISTORY_SUMMARY when still over budget.

Full tool traces remain in session logs / worklogs; compaction only affects
messages sent to the model.
"""
from __future__ import annotations

import json
from collections import OrderedDict

from langbridge_cli.llm.parse import extract_output_text, truncate_text
from langbridge_cli.settings import (
    COMPACT_LLM_INPUT_CHARS,
    COMPACT_LOOP_FRACTION,
    COMPACT_RECENT_FILES_KEEP,
    COMPACT_TOOL_STEPS_KEEP,
    COMPACT_USE_LLM,
    MAX_TOOL_SUMMARY_OUTPUT_CHARS,
    STALE_TOOL_OUTPUT_CHARS,
    SUMMARY_TARGET_CHARS,
)

CLEARED_PREFIX = "[cleared]"
COMPACTION_CONTEXT_PREFIX = "COMPACTION_CONTEXT:\n"
HISTORY_SUMMARY_PREFIX = "HISTORY_SUMMARY:\n"

COMPACTION_SUMMARY_SYSTEM = """You compress conversation history for a coding agent that will keep working.

Preserve with high recall:
- The user's task and current goal
- Architectural decisions and why they were made
- Unresolved bugs, failing tests, and open questions
- Files created, edited, or inspected and what changed
- Implementation details the agent must not forget

Omit or shorten heavily:
- Raw tool output (already cleared in the transcript)
- Redundant exploration and repeated reads
- Verbatim file contents (pinned separately under COMPACTION_CONTEXT)

Return a concise bullet-list summary only. No preamble."""


# --- session log reconstruction ------------------------------------------------


def restore_session_messages(records, *, api_key=None, model=None, max_context_tokens=None):
    if not records:
        return []

    messages = restore_full_session_messages(records)
    compact_messages_if_needed(
        messages,
        api_key=api_key,
        model=model,
        max_context_tokens=max_context_tokens,
        label="session compaction",
    )
    return messages


def restore_full_session_messages(records):
    messages = initial_messages_from_record(records[0])
    for record in records:
        user = record.get("user")
        if user:
            messages.append({"role": "user", "content": user})
        append_turn_messages(messages, record.get("steps", []), record.get("assistant", ""))
    return messages


def initial_messages_from_record(record):
    messages = clone(record.get("input") or record.get("agent_input") or [])
    initial = []
    for message in messages:
        if message.get("role") == "user":
            break
        initial.append(message)
    return initial


def records_to_messages(records):
    messages = []
    for record in records:
        user = record.get("user")
        if user:
            messages.append({"role": "user", "content": user})
        append_turn_messages(messages, record.get("steps", []), record.get("assistant", ""))
    return messages


def append_turn_messages(messages, steps, assistant_reply):
    messages.extend(tool_items_from_steps(steps))
    if assistant_reply:
        messages.append({"role": "assistant", "content": assistant_reply})


def tool_items_from_steps(steps):
    items = []
    for step in steps:
        if "output" in step:
            items.extend(tool_items_from_output(step["output"]))
        else:
            items.extend(tool_items_from_formatted_step(step))
    return items


def tool_items_from_output(output):
    return [
        clone(item)
        for item in output
        if item.get("type") in {"reasoning", "function_call", "function_call_output"}
    ]


def tool_items_from_formatted_step(step):
    reasoning = step.get("reasoning", [])
    if not reasoning and step.get("action"):
        return previous_tool_activity_message(step)

    items = []
    items.extend(clone(reasoning))
    action = step.get("action", [])
    if isinstance(action, dict):
        action = action.get("tool_calls", [])

    for item in action:
        if item.get("name") and item.get("call_id"):
            items.append(
                {
                    "type": "function_call",
                    "call_id": item["call_id"],
                    "name": item["name"],
                    "arguments": json.dumps(item.get("arguments", {}), ensure_ascii=False),
                }
            )

    for item in step.get("observation", []):
        if item.get("call_id"):
            items.append(
                {
                    "type": "function_call_output",
                    "call_id": item["call_id"],
                    "output": item.get("output", ""),
                }
            )
    return items


def previous_tool_activity_message(step):
    lines = []
    observations = {
        item.get("call_id"): item.get("output", "")
        for item in step.get("observation", [])
        if item.get("call_id")
    }
    action = step.get("action", [])
    if isinstance(action, dict):
        action = action.get("tool_calls", [])

    for item in action:
        name = item.get("name")
        call_id = item.get("call_id")
        if not name:
            continue
        arguments = json.dumps(item.get("arguments", {}), ensure_ascii=False)
        output = truncate_text(observations.get(call_id, ""), MAX_TOOL_SUMMARY_OUTPUT_CHARS)
        lines.append(f"- {name}({arguments}): {output}")

    if not lines:
        return []
    return [{"role": "assistant", "content": "Previous tool activity:\n" + "\n".join(lines)}]


def estimate_tokens(value):
    return len(json.dumps(value, ensure_ascii=False)) // 4


def clone(value):
    return json.loads(json.dumps(value, ensure_ascii=False))


# --- compaction ----------------------------------------------------------------


class RecentFileStore:
    """Retains full read_file content for the most recently accessed paths."""

    def __init__(self, max_files: int = COMPACT_RECENT_FILES_KEEP):
        self.max_files = max_files
        self._files: OrderedDict[str, str] = OrderedDict()

    def record_read(self, path: str, content: str) -> None:
        path = path.strip()
        if not path:
            return
        if path in self._files:
            del self._files[path]
        self._files[path] = content
        while len(self._files) > self.max_files:
            self._files.popitem(last=False)

    def format_block(self) -> str:
        if not self._files:
            return ""
        lines = [
            "Recently accessed files (full content retained; older read_file tool "
            "outputs in history were cleared):",
            "",
        ]
        for path, content in reversed(self._files.items()):
            lines.append(f"### {path}")
            lines.append(content)
            lines.append("")
        return "\n".join(lines).rstrip()


def is_cleared_output(output: str) -> bool:
    return str(output).startswith(CLEARED_PREFIX)


def parse_tool_arguments(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def cleared_tool_summary(name: str, arguments, raw_output: str) -> str:
    args = parse_tool_arguments(arguments)
    output = str(raw_output)

    if name == "read_file":
        path = args.get("path", "?")
        lines = output.count("\n") + 1 if output else 0
        return (
            f"{CLEARED_PREFIX} read_file({path}): {lines} lines were read earlier. "
            "Full content may appear under COMPACTION_CONTEXT; call read_file again if needed."
        )
    if name == "grep":
        query = truncate_text(str(args.get("query", "")), 80)
        return (
            f"{CLEARED_PREFIX} grep({query!r}): results cleared "
            f"({len(output)} chars). Re-run grep if you need matches again."
        )
    if name == "glob":
        pattern = args.get("pattern", "?")
        return (
            f"{CLEARED_PREFIX} glob({pattern!r}): listing cleared "
            f"({len(output)} chars). Re-run glob if needed."
        )
    if name == "list_dir":
        path = args.get("path", ".")
        return f"{CLEARED_PREFIX} list_dir({path}): listing cleared. Re-run if needed."
    if name == "run_tests":
        path = args.get("path", ".")
        snippet = truncate_text(output.replace("\n", " "), 120)
        return f"{CLEARED_PREFIX} run_tests({path}): {snippet}"
    if name == "execute_program":
        cmd = truncate_text(str(args.get("command", "")), 80)
        snippet = truncate_text(output.replace("\n", " "), 120)
        return f"{CLEARED_PREFIX} execute_program({cmd}): {snippet}"
    if name in {"edit_file", "create_file", "delete_file"}:
        path = args.get("path", "?")
        snippet = truncate_text(output.replace("\n", " "), 160)
        return f"{CLEARED_PREFIX} {name}({path}): {snippet}"
    if name == "read_skill":
        skill = args.get("name", "?")
        return f"{CLEARED_PREFIX} read_skill({skill}): content cleared; call read_skill again if needed."
    if name in {"ask_l4_engineer", "ask_l5_engineer"}:
        snippet = truncate_text(output.replace("\n", " "), 200)
        return f"{CLEARED_PREFIX} {name}(…): {snippet}"

    snippet = truncate_text(output.replace("\n", " "), STALE_TOOL_OUTPUT_CHARS)
    arg_text = truncate_text(json.dumps(args, ensure_ascii=False), 120)
    return f"{CLEARED_PREFIX} {name}({arg_text}): {snippet}"


def record_tool_read(store: RecentFileStore | None, name: str, arguments, output: str) -> None:
    if store is None or name != "read_file":
        return
    path = parse_tool_arguments(arguments).get("path")
    if path and not str(output).startswith("Tool error"):
        store.record_read(str(path), str(output))


def hydrate_file_store_from_messages(messages: list) -> RecentFileStore:
    store = RecentFileStore()
    pending_reads: dict[str, str] = {}
    for message in messages:
        if message.get("type") == "function_call" and message.get("name") == "read_file":
            call_id = message.get("call_id")
            path = parse_tool_arguments(message.get("arguments")).get("path")
            if call_id and path:
                pending_reads[call_id] = str(path)
            continue
        if message.get("type") != "function_call_output":
            continue
        call_id = message.get("call_id")
        path = pending_reads.pop(call_id, None)
        if path:
            store.record_read(path, str(message.get("output", "")))
    return store


def serialize_messages_for_llm_summary(messages: list) -> str:
    lines: list[str] = []
    call_labels: dict[str, str] = {}

    for message in messages:
        role = message.get("role")
        if role == "system":
            continue
        if role == "user":
            content = str(message.get("content", "")).strip()
            if content:
                lines.append(f"USER:\n{content}")
            continue
        if role == "assistant":
            content = str(message.get("content", ""))
            if content.startswith(COMPACTION_CONTEXT_PREFIX):
                lines.append("PINNED_FILES: recent file contents are kept outside this transcript.")
                continue
            if content.startswith(HISTORY_SUMMARY_PREFIX):
                continue
            content = content.strip()
            if content:
                lines.append(f"ASSISTANT:\n{content}")
            continue

        item_type = message.get("type")
        if item_type == "function_call":
            call_id = message.get("call_id", "")
            label = f"{message.get('name', 'unknown')}({message.get('arguments', '{}')})"
            if call_id:
                call_labels[call_id] = label
            lines.append(f"TOOL_CALL: {label}")
            continue
        if item_type == "function_call_output":
            call_id = message.get("call_id", "")
            label = call_labels.get(call_id, "unknown")
            output = str(message.get("output", ""))
            if is_cleared_output(output):
                lines.append(f"TOOL_RESULT ({label}): {output}")
            else:
                lines.append(f"TOOL_RESULT ({label}): {truncate_text(output, 2000)}")

    return "\n\n".join(lines)


def summarize_history_with_llm(
    api_key: str,
    model: str,
    messages: list,
    *,
    label: str = "compaction",
) -> str:
    transcript = serialize_messages_for_llm_summary(messages)
    if not transcript.strip():
        return ""

    prompt = (
        "Summarize the agent transcript below so the agent can continue without "
        "the full message history.\n\n"
        f"{truncate_text(transcript, COMPACT_LLM_INPUT_CHARS)}"
    )
    from langbridge_cli.llm.client import create_model_response

    data = create_model_response(
        api_key,
        model,
        [
            {"role": "system", "content": COMPACTION_SUMMARY_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        label=label,
    )
    summary = extract_output_text(data.get("output", [])).strip()
    if not summary:
        return ""
    return truncate_text(summary, SUMMARY_TARGET_CHARS)


def iter_tool_rounds(messages: list) -> list[tuple[int, list[int]]]:
    rounds: list[tuple[int, list[int]]] = []
    index = 0
    round_idx = 0
    while index < len(messages):
        item = messages[index]
        item_type = item.get("type")
        if item.get("role") or item_type not in {"reasoning", "function_call", "function_call_output"}:
            index += 1
            continue
        if item_type == "function_call_output":
            index += 1
            continue

        indices: list[int] = []
        saw_output = False
        while index < len(messages):
            current = messages[index]
            current_type = current.get("type")
            if current_type == "function_call_output":
                indices.append(index)
                saw_output = True
                index += 1
                continue
            if current_type == "function_call":
                if saw_output:
                    break
                indices.append(index)
                index += 1
                continue
            if current_type == "reasoning":
                indices.append(index)
                index += 1
                continue
            break

        if indices:
            rounds.append((round_idx, indices))
            round_idx += 1
    return rounds


def clear_old_tool_outputs(messages: list, *, keep_recent_steps: int = COMPACT_TOOL_STEPS_KEEP) -> int:
    rounds = iter_tool_rounds(messages)
    if len(rounds) <= keep_recent_steps:
        return 0

    cleared = 0
    cutoff = rounds[-keep_recent_steps][0] if keep_recent_steps else len(rounds)
    for round_idx, indices in rounds:
        if round_idx >= cutoff:
            continue
        calls = {
            messages[i]["call_id"]: messages[i]
            for i in indices
            if messages[i].get("type") == "function_call" and messages[i].get("call_id")
        }
        for i in indices:
            item = messages[i]
            if item.get("type") != "function_call_output":
                continue
            if is_cleared_output(item.get("output", "")):
                continue
            call = calls.get(item.get("call_id"))
            name = call.get("name", "unknown") if call else "unknown"
            arguments = call.get("arguments", "{}") if call else "{}"
            item["output"] = cleared_tool_summary(name, arguments, item.get("output", ""))
            cleared += 1
    return cleared


def _find_compaction_message_index(messages: list, prefix: str) -> int | None:
    for index, message in enumerate(messages):
        if message.get("role") == "assistant" and str(message.get("content", "")).startswith(prefix):
            return index
    return None


def sync_compaction_context(messages: list, store: RecentFileStore | None) -> None:
    block = store.format_block() if store else ""
    existing = _find_compaction_message_index(messages, COMPACTION_CONTEXT_PREFIX)
    if not block:
        if existing is not None:
            messages.pop(existing)
        return

    content = COMPACTION_CONTEXT_PREFIX + block
    if existing is not None:
        messages[existing]["content"] = content
    else:
        messages.append({"role": "assistant", "content": content})


def sync_history_summary(
    messages: list,
    *,
    api_key: str | None = None,
    model: str | None = None,
    label: str = "compaction",
) -> None:
    if not (api_key and model and COMPACT_USE_LLM):
        return

    existing = _find_compaction_message_index(messages, HISTORY_SUMMARY_PREFIX)
    summary = summarize_history_with_llm(api_key, model, messages, label=label)
    if not summary.strip():
        return

    content = HISTORY_SUMMARY_PREFIX + summary
    if existing is not None:
        messages[existing]["content"] = content
        return

    insert_at = 1
    for index, message in enumerate(messages):
        if message.get("role") == "user":
            insert_at = index + 1
            break
    messages.insert(insert_at, {"role": "assistant", "content": content})


def _resolve_max_context_tokens(max_context_tokens):
    if max_context_tokens is not None:
        return max_context_tokens
    from langbridge_cli.settings import MAX_AGENT_CONTEXT_TOKENS

    return MAX_AGENT_CONTEXT_TOKENS


def maybe_compact_messages(
    messages: list,
    *,
    max_context_tokens: int,
    file_store: RecentFileStore | None = None,
    keep_recent_steps: int | None = None,
    api_key: str | None = None,
    model: str | None = None,
    label: str = "compaction",
) -> dict:
    before = estimate_tokens(messages)
    threshold = int(max_context_tokens * COMPACT_LOOP_FRACTION)
    if before <= threshold:
        return {"compacted": False, "tokens_before": before, "tokens_after": before, "cleared": 0}

    store = file_store or hydrate_file_store_from_messages(messages)
    cleared = clear_old_tool_outputs(
        messages,
        keep_recent_steps=keep_recent_steps if keep_recent_steps is not None else COMPACT_TOOL_STEPS_KEEP,
    )
    sync_compaction_context(messages, store)

    after = estimate_tokens(messages)
    heavy_threshold = int(max_context_tokens * 0.8)
    llm_summary = False
    if after > heavy_threshold:
        sync_history_summary(messages, api_key=api_key, model=model, label=label)
        llm_summary = bool(api_key and model and COMPACT_USE_LLM)
        after = estimate_tokens(messages)

    return {
        "compacted": True,
        "tokens_before": before,
        "tokens_after": after,
        "cleared": cleared,
        "llm_summary": llm_summary,
    }


def compact_messages_if_needed(
    messages: list,
    *,
    api_key=None,
    model=None,
    max_context_tokens=None,
    file_store: RecentFileStore | None = None,
    label: str = "compaction",
) -> dict:
    """Compact messages in place when over the configured context fraction."""
    return maybe_compact_messages(
        messages,
        max_context_tokens=_resolve_max_context_tokens(max_context_tokens),
        file_store=file_store,
        api_key=api_key,
        model=model,
        label=label,
    )
