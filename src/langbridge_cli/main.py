import os
import sys
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from langbridge_cli.agents import control
from langbridge_cli.agents.agent import run_pm_loop
from langbridge_cli.agents.roles import SYSTEM_PROMPT
from langbridge_cli.settings import (
    CONFIG_DIR,
    DEFAULT_MODEL,
    HISTORY_PATH,
    MAX_AGENT_CONTEXT_TOKENS,
    COMPACT_LOOP_FRACTION,
    load_api_key,
)
from langbridge_cli.persistence.context import (
    compact_messages_if_needed,
    estimate_tokens,
    restore_full_session_messages,
    restore_session_messages,
)
from langbridge_cli.persistence.session import (
    create_run_log_path,
    last_turn_id,
    read_session_records,
    select_previous_session,
    write_session_summary,
)


def main():
    # The Textual UI is the default; set LANGBRIDGE_TERMINAL=1 for the plain REPL.
    if os.environ.get("LANGBRIDGE_TERMINAL", "").strip().lower() not in {"1", "true", "yes", "on"}:
        from langbridge_cli.ui.tui import run_tui

        run_tui()
        return

    api_key = load_api_key()
    model = os.environ.get("LANGBRIDGE_MODEL", DEFAULT_MODEL)
    session = create_prompt_session() if sys.stdin.isatty() else None

    previous_session = select_previous_session(session)
    if previous_session is not None:
        records = read_session_records(previous_session)
        run_log_path = previous_session
        turn_id = last_turn_id(records)
        messages = restore_session_messages(records, api_key=api_key, model=model) or [{"role": "system", "content": SYSTEM_PROMPT}]
    else:
        run_log_path = create_run_log_path()
        turn_id = 0
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    print(f"langbridge-cli using {model}")
    print(f"Agent loop log: {run_log_path}")

    while True:
        try:
            text = read_user_input(session)
        except KeyboardInterrupt:
            print()
            continue
        except EOFError:
            break

        if text.strip() == "/exit":
            break

        turn_id += 1
        threshold = int(MAX_AGENT_CONTEXT_TOKENS * COMPACT_LOOP_FRACTION)
        if estimate_tokens(messages) > threshold:
            fresh = restore_full_session_messages(read_session_records(run_log_path))
            result = compact_messages_if_needed(
                fresh, api_key=api_key, model=model, label="PM session compaction"
            )
            messages.clear()
            messages.extend(fresh)
            if result["compacted"]:
                print("(compacted older context to stay under the token budget)")
        snapshot = list(messages)
        try:
            run_pm_loop(api_key, model, text, run_log_path, turn_id, messages=messages)
        except control.TurnAborted as aborted:
            messages = snapshot
            print(f"\n{aborted} Stopped; send another message.")
            continue
        write_session_summary(api_key, model, run_log_path)


def create_prompt_session():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return PromptSession(history=FileHistory(str(HISTORY_PATH)))


def read_user_input(session):
    if session is not None:
        return session.prompt("langbridge> ")
    return input("langbridge> ")


if __name__ == "__main__":
    main()
