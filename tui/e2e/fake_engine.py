"""Scripted protocol engine for TS TUI e2e tests (no LLM, no agent).

Emits approval / question flows deterministically so the UI side of those
interactions can be asserted; everything else echoes.
"""
from __future__ import annotations

import json
import sys


def send(event: dict) -> None:
    sys.stdout.write(json.dumps(event, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> None:
    send(
        {
            "type": "hello",
            "model": "scripted-model",
            "version": "0.0-test",
            "cwd": "~/e2e",
            "git_branch": "",
            "sessions": [],
        }
    )
    send(
        {
            "type": "state",
            "state": "ready",
            "workflow": "",
            "turn_active": False,
            "yolo": False,
            "queued": 0,
            "goal_active": False,
        }
    )
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        message = json.loads(raw)
        kind = message.get("type")
        if kind == "quit":
            return
        if kind == "user_message":
            text = message.get("text", "")
            if "NEED_APPROVAL" in text:
                send(
                    {
                        "type": "approval_request",
                        "summary": "Worker: approve write on demo.txt?",
                        "details": '{\n  "path": "demo.txt"\n}',
                    }
                )
            elif "ASK_ME" in text:
                send(
                    {
                        "type": "question",
                        "text": "Which color?\n\n1. red\n2. blue\n\nReply with 1-3, or type a custom answer.",
                        "options": ["red", "blue"],
                    }
                )
            else:
                send({"type": "assistant", "text": f"scripted: {text}"})
                send({"type": "turn_end", "status": "ok"})
        elif kind == "approval":
            approved = bool(message.get("approved"))
            send({"type": "approval_resolved", "approved": approved})
            send({"type": "assistant", "text": "approved path" if approved else "denied path"})
            send({"type": "turn_end", "status": "ok"})
        elif kind == "answer":
            # Mirror the real engine: numeric replies map to the option list.
            options = ["red", "blue"]
            text = (message.get("text") or "").strip()
            resolved = options[int(text) - 1] if text in {"1", "2"} else text
            send({"type": "answer_recorded", "text": resolved})
            send({"type": "assistant", "text": f"answer was: {resolved}"})
            send({"type": "turn_end", "status": "ok"})
        elif kind == "yolo":
            send(
                {
                    "type": "state",
                    "state": "ready",
                    "workflow": "",
                    "turn_active": False,
                    "yolo": bool(message.get("value")),
                    "queued": 0,
                    "goal_active": False,
                }
            )


if __name__ == "__main__":
    main()
