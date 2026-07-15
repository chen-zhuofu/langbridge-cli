"""End-to-end TUI test: drives the real TS TUI + real Python engine in a pty,
against a fake OpenAI-compatible LLM server. Asserts on rendered frames.

Usage: .venv/bin/python tui/e2e/run_e2e.py
"""
from __future__ import annotations

import fcntl
import os
import pty
import re
import select
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tui" / "e2e"))
from fake_llm import serve  # noqa: E402

PORT = 8931
ANSI_RE = re.compile(rb"\x1b\[[0-9;?<>=]*[a-zA-Z]|\x1b[()][A-Z0-9]|\x1b[=>]")

PASS = []
FAIL = []


class TuiSession:
    def __init__(self, workdir: Path, *, rows=40, cols=120, scripted_engine=False):
        env = dict(os.environ)
        env["PATH"] = os.path.expanduser("~/.local/node/bin") + ":" + env.get("PATH", "")
        env["TERM"] = "xterm-256color"
        env["LANGBRIDGE_API_PROVIDER"] = "moonshot"
        env["MOONSHOT_API_KEY"] = "e2e-test-key"
        env["LANGBRIDGE_API_BASE_URL"] = f"http://127.0.0.1:{PORT}/v1"
        env["LANGBRIDGE_API_STREAMING_ENABLED"] = "0"
        env["LANGBRIDGE_MODEL"] = "fake-model"
        env["LANGBRIDGE_ARTIFACTS_DIR"] = str(workdir / "artifacts")
        env["LANGBRIDGE_AGENT_STATE_DIR"] = str(workdir / "agent-state")
        if scripted_engine:
            env["LANGBRIDGE_BRIDGE_MODULE"] = "fake_engine"
            env["PYTHONPATH"] = str(REPO / "tui" / "e2e")
        self.master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        self.proc = subprocess.Popen(
            ["node", str(REPO / "tui" / "dist" / "cli.js")],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=env,
            cwd=str(workdir),
            preexec_fn=os.setsid,
        )
        os.close(slave)
        self.raw = b""

    def drain(self, seconds: float) -> None:
        end = time.time() + seconds
        while time.time() < end:
            ready, _, _ = select.select([self.master], [], [], 0.1)
            if ready:
                try:
                    self.raw += os.read(self.master, 65536)
                except OSError:
                    return

    def text(self) -> str:
        return ANSI_RE.sub(b"", self.raw).decode("utf-8", "replace")

    def send(self, data: bytes) -> None:
        os.write(self.master, data)

    def type_line(self, text: str) -> None:
        for byte in text.encode("utf-8"):
            self.send(bytes([byte]))
            time.sleep(0.01)
        self.send(b"\r")

    def wait_for(self, needle: str, timeout: float = 15) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            if needle in self.text():
                return True
            self.drain(0.2)
        return False

    def alive(self) -> bool:
        return self.proc.poll() is None

    def close(self) -> None:
        try:
            os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)


def check(name: str, ok: bool, context: str = "") -> None:
    (PASS if ok else FAIL).append(name)
    print(("PASS " if ok else "FAIL ") + name)
    if not ok and context:
        print("  --- context tail ---")
        print("\n".join(context.splitlines()[-25:]))


def scenario_basic_turn_and_commands(workdir: Path) -> None:
    tui = TuiSession(workdir)
    try:
        check("startup renders banner", tui.wait_for("Send /help for commands", 20), tui.text())
        check("engine hello (model in status)", tui.wait_for("fake-model", 15), tui.text())

        # Simple turn end-to-end through the fake LLM.
        tui.type_line("hello e2e")
        check("user line echoed", tui.wait_for("\u2726 hello e2e", 10), tui.text())
        check("assistant reply rendered", tui.wait_for("e2e-reply: hello e2e", 20), tui.text())

        # /help
        tui.type_line("/help")
        check("/help output", tui.wait_for("/goal <condition>", 5), tui.text())

        # /queue empty
        tui.type_line("/queue")
        check("/queue empty message", tui.wait_for("No queued messages", 5), tui.text())

        # /goal status without goal
        tui.type_line("/goal")
        check("/goal empty status", tui.wait_for("No active goal", 5), tui.text())

        # /yolo on shows in status bar
        tui.type_line("/yolo on")
        check("yolo announce", tui.wait_for("Yolo mode on", 5), tui.text())
        check("yolo status flag", tui.wait_for("· yolo", 5), tui.text())
        tui.type_line("/yolo off")
        check("yolo off announce", tui.wait_for("Yolo mode off", 5), tui.text())

        # Unknown command
        tui.type_line("/nope")
        check("unknown command warning", tui.wait_for("Unknown command: /nope", 5), tui.text())

        # Multi-line input via Ctrl+J
        tui.send(b"line-one")
        time.sleep(0.2)
        tui.send(b"\n")  # Ctrl+J = newline byte 0x0a
        time.sleep(0.2)
        tui.send(b"line-two")
        time.sleep(0.2)
        tui.send(b"\r")
        check("multi-line message sent", tui.wait_for("e2e-reply: line-one", 20), tui.text())

        # Second turn reuses session (context grows, no crash)
        tui.type_line("again please")
        check("second turn ok", tui.wait_for("e2e-reply: again please", 20), tui.text())

        # Mouse events: wheel scrolls (no crash), clicks never leak into the
        # composer as text.
        tui.send(b"\x1b[<64;10;10M" * 3)  # wheel up
        tui.drain(0.5)
        tui.send(b"\x1b[<65;10;10M" * 3)  # wheel down
        tui.drain(0.5)
        tui.send(b"\x1b[<0;20;12M\x1b[<0;20;12m")  # click press + release
        tui.drain(0.5)
        tui.type_line("after mouse events")
        check("clean turn after mouse events", tui.wait_for("e2e-reply: after mouse events", 20), tui.text())

        check("tui still alive", tui.alive(), tui.text())
    finally:
        tui.close()


def scenario_tool_round_trip(workdir: Path) -> None:
    """Main-agent tool call (bash) executes and the turn completes.

    Main-agent tools are not approval-gated by the engine (same as the old
    Python TUI); the approval UI itself is exercised in the scripted-engine
    scenario below.
    """
    tui = TuiSession(workdir)
    try:
        tui.wait_for("Send /help for commands", 20)
        tui.type_line("USE_TOOL run something")
        check("tool call traced", tui.wait_for("bash(", 25), tui.text())
        check(
            "turn completes after tool round",
            tui.wait_for("tool finished; e2e reply after approval", 25),
            tui.text(),
        )
    finally:
        tui.close()


def scenario_approval_and_question_ui(workdir: Path) -> None:
    """Approval + planner-question UI against a scripted protocol engine."""
    tui = TuiSession(workdir, scripted_engine=True)
    try:
        check("scripted engine hello", tui.wait_for("scripted-model", 15), tui.text())

        # Approve with Ctrl+A.
        tui.type_line("NEED_APPROVAL please")
        check("approval prompt appears", tui.wait_for("Approval needed", 10), tui.text())
        check("approval details render", tui.wait_for('"path": "demo.txt"', 5), tui.text())
        tui.send(b"\x01")
        check("approved marker", tui.wait_for("\u2713 Approved.", 10), tui.text())
        check("approved path reply", tui.wait_for("approved path", 10), tui.text())

        # Deny with Ctrl+D. Wait on this turn's own echo plus a drain so the
        # second approval prompt (same text as the first) is actually up.
        tui.type_line("NEED_APPROVAL again")
        tui.wait_for("NEED_APPROVAL again", 10)
        tui.drain(2.0)
        tui.send(b"\x04")
        check("denied marker", tui.wait_for("\u2717 Denied.", 10), tui.text())
        check("denied path reply", tui.wait_for("denied path", 10), tui.text())

        # Planner question: numeric answer maps to option.
        tui.type_line("ASK_ME a question")
        check("question renders", tui.wait_for("Which color?", 10), tui.text())
        tui.type_line("1")
        check("answer echoed as user", tui.wait_for("answer was: red", 10), tui.text())
    finally:
        tui.close()


def scenario_queue_while_busy(workdir: Path) -> None:
    tui = TuiSession(workdir)
    try:
        tui.wait_for("Send /help for commands", 20)
        tui.type_line("SLOW first")
        time.sleep(1.0)  # busy inside the 3s slow call
        tui.type_line("queued second")
        check("queued notice", tui.wait_for("Queued (1 message", 10), tui.text())
        check("first reply arrives", tui.wait_for("slow reply done", 25), tui.text())
        check("queued turn auto-runs", tui.wait_for("e2e-reply: queued second", 25), tui.text())
    finally:
        tui.close()


def scenario_stop(workdir: Path) -> None:
    tui = TuiSession(workdir)
    try:
        tui.wait_for("Send /help for commands", 20)
        tui.type_line("SLOW long call")
        time.sleep(1.0)
        tui.send(b"\x13")  # Ctrl+S stop
        check("stopping notice", tui.wait_for("Stopping the agent", 10), tui.text())
        check("stopped marker", tui.wait_for("\u25a0 Stopped.", 15), tui.text())
        # Composer must be usable again.
        tui.type_line("after stop")
        check("turn after stop works", tui.wait_for("e2e-reply: after stop", 20), tui.text())
    finally:
        tui.close()


def scenario_sessions(workdir: Path) -> None:
    # First run creates a session.
    tui = TuiSession(workdir)
    try:
        tui.wait_for("Send /help for commands", 20)
        tui.type_line("remember me session")
        tui.wait_for("e2e-reply: remember me session", 20)
        tui.drain(1.0)
    finally:
        tui.close()

    # Second run: startup picker lists it; Enter resumes.
    tui = TuiSession(workdir)
    try:
        check("startup picker shows", tui.wait_for("Resume a session", 20), tui.text())
        check("picker lists saved session", tui.wait_for("remember-me-session", 5), tui.text())
        tui.send(b"\r")
        check("resume announcement", tui.wait_for("Resumed: session-", 10), tui.text())
        check("history replays user line", tui.wait_for("\u2726 remember me session", 5), tui.text())
        check("history replays assistant line", tui.wait_for("e2e-reply: remember me session", 5), tui.text())
        tui.type_line("hello resumed")
        check("turn in resumed session", tui.wait_for("e2e-reply: hello resumed", 25), tui.text())
    finally:
        tui.close()

    # Third run: Esc on picker starts a new session; /new works while ready.
    tui = TuiSession(workdir)
    try:
        tui.wait_for("Resume a session", 20)
        tui.send(b"\x1b")  # Esc
        check("esc dismisses picker", tui.wait_for("Send /help for commands", 10), tui.text())
        tui.type_line("/new")
        tui.drain(0.5)
        check("tui alive after /new", tui.alive(), tui.text())
    finally:
        tui.close()


def scenario_cjk_composer(workdir: Path) -> None:
    """Wide (CJK) input must stay on one composer line.

    Regression: Ink's insertBeforeNode skips markDirty, so the first keystroke
    into the empty composer kept a stale 1-column text measurement and every
    character wrapped onto its own line ("开发" rendered vertically).
    """
    tui = TuiSession(workdir, scripted_engine=True)
    try:
        tui.wait_for("Send /help for commands", 20)
        tui.send("开发".encode("utf-8"))
        check("CJK renders on one line", tui.wait_for("\u276f 开发", 10), tui.text())
    finally:
        tui.close()


def scenario_banner_and_quit(workdir: Path) -> None:
    tui = TuiSession(workdir)
    try:
        tui.wait_for("Send /help for commands", 20)
        tui.send(b"\x02")  # Ctrl+B hide banner
        tui.drain(0.5)
        check("banner hint flips", tui.wait_for("ctrl+b show header", 5), tui.text())
        tui.send(b"\x03")  # Ctrl+C quit
        end = time.time() + 8
        while time.time() < end and tui.alive():
            time.sleep(0.2)
        check("ctrl+c quits", not tui.alive(), tui.text())
    finally:
        tui.close()


def main() -> int:
    server = serve(PORT)
    try:
        scenarios = [
            scenario_basic_turn_and_commands,
            scenario_tool_round_trip,
            scenario_approval_and_question_ui,
            scenario_queue_while_busy,
            scenario_stop,
            scenario_sessions,
            scenario_cjk_composer,
            scenario_banner_and_quit,
        ]
        for scenario in scenarios:
            print(f"=== {scenario.__name__} ===")
            with tempfile.TemporaryDirectory(prefix="tui-e2e-") as tmp:
                workdir = Path(tmp)
                (workdir / "artifacts").mkdir()
                try:
                    scenario(workdir)
                except Exception as error:  # noqa: BLE001
                    check(f"{scenario.__name__} crashed: {error}", False)
    finally:
        server.shutdown()
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("Failed:", ", ".join(FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
