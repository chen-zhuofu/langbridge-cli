import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Box, Text, useApp, useInput, useStdout } from "ink";

import { Bridge } from "./bridge.js";
import type { EngineEvent, SessionItem } from "./protocol.js";
import { ChatLine, makeLine } from "./state.js";
import { HELP_TEXT } from "./help.js";
import { ACCENT, YELLOW } from "./theme.js";
import { Banner } from "./components/Banner.js";
import { ChatLog, totalRowCount } from "./components/ChatLog.js";
import { Composer } from "./components/Composer.js";
import { SessionPicker } from "./components/SessionPicker.js";
import { StatusBar } from "./components/StatusBar.js";

const INPUT_LINES_MIN = 3;
const INPUT_LINES_MAX = 12;

interface EngineState {
  state: string;
  workflow: string;
  turnActive: boolean;
  yolo: boolean;
  queued: number;
  goalActive: boolean;
}

const PHASE_MAP: Record<string, string> = {
  ready: "idle",
  thinking: "thinking",
  working: "composing",
  shell: "shell",
  "waiting for approval": "waiting",
  "waiting for answer": "waiting",
  paused: "waiting",
  stopping: "shell",
};

export function App() {
  const { exit } = useApp();
  const { stdout } = useStdout();
  const bridge = useMemo(() => new Bridge(), []);

  const [lines, setLines] = useState<ChatLine[]>([]);
  const [thinking, setThinking] = useState<{ role: string; text: string } | null>(null);
  const [engine, setEngine] = useState<EngineState>({
    state: "ready",
    workflow: "",
    turnActive: false,
    yolo: false,
    queued: 0,
    goalActive: false,
  });
  const [hello, setHello] = useState({ model: "", version: "", cwd: "", gitBranch: "" });
  const [sessionLabel, setSessionLabel] = useState("new (unsaved)");
  const [contextLine, setContextLine] = useState("");
  const [bannerVisible, setBannerVisible] = useState(true);
  // Composer text lives in refs: terminal input can arrive as multi-char
  // chunks (fast typing, paste, SSH), and processing them char-by-char through
  // setState closures drops keystrokes. A version counter triggers re-render.
  const inputRef = useRef("");
  const cursorRef = useRef(0);
  const [, setInputVersion] = useState(0);
  const input = inputRef.current;
  const cursor = cursorRef.current;
  const [inputLines, setInputLines] = useState(INPUT_LINES_MIN);
  const [scrollOffset, setScrollOffset] = useState(0);
  const [picker, setPicker] = useState<{ sessions: SessionItem[]; highlighted: number; startup: boolean } | null>(null);
  const [pendingApproval, setPendingApproval] = useState(false);
  const [pendingQuestion, setPendingQuestion] = useState(false);
  const [size, setSize] = useState({
    columns: stdout?.columns || 100,
    rows: stdout?.rows || 30,
  });

  // Re-render (and re-clamp the layout) whenever the terminal is resized.
  useEffect(() => {
    if (!stdout) return;
    const onResize = () => setSize({ columns: stdout.columns, rows: stdout.rows });
    stdout.on("resize", onResize);
    return () => {
      stdout.off("resize", onResize);
    };
  }, [stdout]);

  // Mouse wheel scrolling: enable SGR mouse reporting (like the old Textual
  // TUI). Wheel events arrive as escape sequences handled in the key handler.
  // Opt out with LANGBRIDGE_TUI_MOUSE=0 (restores normal terminal selection).
  const mouseEnabled = !["0", "false", "no", "off"].includes(
    (process.env["LANGBRIDGE_TUI_MOUSE"] || "").trim().toLowerCase(),
  );
  useEffect(() => {
    if (!stdout || !mouseEnabled) return;
    stdout.write("\u001b[?1000;1006h");
    const disable = () => stdout.write("\u001b[?1000;1006l");
    process.on("exit", disable);
    return () => {
      process.off("exit", disable);
      disable();
    };
  }, [stdout, mouseEnabled]);

  const sessionsRef = useRef<SessionItem[]>([]);
  const engineRef = useRef(engine);
  engineRef.current = engine;
  const linesRef = useRef<ChatLine[]>(lines);
  linesRef.current = lines;
  // Set during layout below; used to clamp scrolling from the key handler.
  const chatViewRef = useRef({ height: 10, width: 80 });

  const scrollBy = useCallback((delta: number) => {
    setScrollOffset((offset) => {
      const view = chatViewRef.current;
      const max = Math.max(0, totalRowCount(linesRef.current, view.width) - view.height);
      return Math.max(0, Math.min(max, offset + delta));
    });
  }, []);
  const pendingQuestionRef = useRef(false);
  pendingQuestionRef.current = pendingQuestion;

  const append = useCallback((line: ChatLine) => {
    setLines((previous) => {
      const next = [...previous, line];
      return next.length > 3000 ? next.slice(next.length - 3000) : next;
    });
  }, []);

  const writeSystem = useCallback(
    (text: string, style?: string) => append(makeLine("system", text, { style })),
    [append],
  );

  // --- engine events -------------------------------------------------------

  useEffect(() => {
    const onEvent = (event: EngineEvent) => {
      switch (event.type) {
        case "hello":
          setHello({ model: event.model, version: event.version, cwd: event.cwd, gitBranch: event.git_branch });
          sessionsRef.current = event.sessions;
          if (event.sessions.length > 0) {
            setPicker({ sessions: event.sessions, highlighted: 0, startup: true });
          }
          break;
        case "system":
          writeSystem(event.text, event.style);
          break;
        case "assistant":
          setThinking(null);
          append(makeLine("assistant", event.text));
          break;
        case "queued":
          append(makeLine("user", event.text, { queued: true }));
          break;
        case "turn_started":
          append(makeLine("user", event.text));
          break;
        case "trace":
          setThinking(null);
          append(
            makeLine("trace", event.kind === "action" ? `\u21b3 ${event.text}` : event.text, {
              style: event.role,
            }),
          );
          break;
        case "stream":
          setThinking({
            role: event.role,
            text: event.kind === "action_stream" ? `→ ${event.text}` : event.text,
          });
          break;
        case "state":
          setEngine({
            state: event.state,
            workflow: event.workflow,
            turnActive: event.turn_active,
            yolo: event.yolo,
            queued: event.queued,
            goalActive: event.goal_active,
          });
          if (!event.turn_active) setThinking(null);
          break;
        case "context_line":
          setContextLine(event.text);
          break;
        case "approval_request":
          setPendingApproval(true);
          writeSystem(`\u26a0 Approval needed: ${event.summary}`, "warn");
          if (event.details) writeSystem(event.details);
          writeSystem("Ctrl+A approve \u00b7 Ctrl+D deny \u00b7 Ctrl+Y yolo  (or /approve, /deny, /yolo)");
          break;
        case "approval_resolved":
          setPendingApproval(false);
          writeSystem(event.approved ? "\u2713 Approved." : "\u2717 Denied.", event.approved ? "success" : "error");
          break;
        case "question":
          setPendingQuestion(true);
          writeSystem("\u2753 Planner asks:", "accent");
          writeSystem(event.text, "accent");
          break;
        case "answer_recorded":
          setPendingQuestion(false);
          if (event.text) append(makeLine("user", event.text));
          break;
        case "turn_end":
          setThinking(null);
          if (event.status === "stopped") writeSystem("\u25a0 Stopped.", "error");
          if (event.status === "error" && event.message) writeSystem(`\u25a0 ${event.message}`, "error");
          break;
        case "sessions":
          sessionsRef.current = event.items;
          break;
        case "session_new":
          setLines([]);
          setSessionLabel("new (unsaved)");
          break;
        case "session_resumed": {
          setLines([]);
          setScrollOffset(0);
          setSessionLabel(event.label);
          writeSystem(`Resumed: ${event.label}`);
          const conversation = event.conversation ?? [];
          if (conversation.length > 0) {
            for (const message of conversation) {
              append(makeLine(message.role === "user" ? "user" : "assistant", message.text));
            }
          } else if (event.preview) writeSystem(event.preview);
          else writeSystem("No progress recorded yet for this session.");
          break;
        }
        case "queue": {
          if (event.items.length === 0) writeSystem("No queued messages.");
          else {
            writeSystem("Queued messages (next first):");
            event.items.forEach((item, index) => {
              const preview = item.replace(/\n/g, " ");
              writeSystem(`  ${index + 1}. ${preview.length > 120 ? preview.slice(0, 117) + "..." : preview}`);
            });
          }
          break;
        }
      }
    };
    bridge.on("event", onEvent);
    bridge.on("stderr", (text: string) => writeSystem(text, "error"));
    bridge.on("exit", () => exit());
    return () => {
      bridge.removeAllListeners();
    };
  }, [bridge, append, writeSystem, exit]);

  useEffect(() => {
    return () => bridge.quit();
  }, [bridge]);

  // --- commands -------------------------------------------------------------

  const sessionAt = useCallback(
    (arg?: string): SessionItem | null => {
      const sessions = sessionsRef.current;
      if (!arg || !/^\d+$/.test(arg)) {
        writeSystem("Usage: /resume <n> (see /sessions).", "warn");
        return null;
      }
      const index = parseInt(arg, 10) - 1;
      if (index < 0 || index >= sessions.length) {
        writeSystem(`No session number ${arg}. See /sessions.`, "warn");
        return null;
      }
      return sessions[index];
    },
    [writeSystem],
  );

  const openPicker = useCallback(() => {
    if (engineRef.current.turnActive) {
      writeSystem("Agent is busy. Use /stop first.", "warn");
      return;
    }
    bridge.send({ type: "list_sessions" });
    // sessionsRef updates on the next tick; open with what we have now.
    setTimeout(() => {
      if (sessionsRef.current.length === 0) writeSystem("No saved sessions.");
      else setPicker({ sessions: sessionsRef.current, highlighted: 0, startup: false });
    }, 150);
  }, [bridge, writeSystem]);

  const handleCommand = useCallback(
    (text: string) => {
      const parts = text.split(/\s+/);
      const cmd = parts[0].toLowerCase();
      const arg = parts[1];
      switch (cmd) {
        case "/exit":
        case "/quit":
          bridge.quit();
          exit();
          break;
        case "/help":
          writeSystem(HELP_TEXT);
          break;
        case "/new":
          bridge.send({ type: "new_session" });
          break;
        case "/sessions":
          openPicker();
          break;
        case "/resume":
          if (!arg) openPicker();
          else {
            const session = sessionAt(arg);
            if (session) bridge.send({ type: "resume_session", path: session.path });
          }
          break;
        case "/delete": {
          const session = sessionAt(arg);
          if (session) bridge.send({ type: "delete_session", path: session.path });
          break;
        }
        case "/approve":
          if (arg === "on" || arg === "off") bridge.send({ type: "yolo", value: arg === "on" });
          else bridge.send({ type: "approval", approved: true });
          break;
        case "/yolo":
          if (arg === "on" || arg === "off") bridge.send({ type: "yolo", value: arg === "on" });
          else bridge.send({ type: "yolo", value: !engineRef.current.yolo });
          break;
        case "/deny":
          bridge.send({ type: "approval", approved: false });
          break;
        case "/pause":
          bridge.send({ type: "pause_toggle" });
          break;
        case "/stop":
          bridge.send({ type: "stop" });
          break;
        case "/queue":
          if (arg === "clear") bridge.send({ type: "queue_clear" });
          else bridge.send({ type: "queue_list" });
          break;
        case "/goal":
          bridge.send({ type: "goal", text: text.slice("/goal".length).trim() });
          break;
        case "/banner":
          if (arg === "on") setBannerVisible(true);
          else if (arg === "off") setBannerVisible(false);
          else setBannerVisible((visible) => !visible);
          break;
        default:
          writeSystem(`Unknown command: ${cmd}. Try /help.`, "warn");
      }
    },
    [bridge, exit, openPicker, sessionAt, writeSystem],
  );

  const bumpInput = useCallback(() => setInputVersion((version) => version + 1), []);

  const editInput = useCallback(
    (mutate: (value: string, cursor: number) => [string, number]) => {
      const [nextValue, nextCursor] = mutate(inputRef.current, cursorRef.current);
      inputRef.current = nextValue;
      cursorRef.current = Math.max(0, Math.min(nextValue.length, nextCursor));
      bumpInput();
    },
    [bumpInput],
  );

  const submit = useCallback(() => {
    const text = inputRef.current.trim();
    inputRef.current = "";
    cursorRef.current = 0;
    bumpInput();
    if (!text) return;
    if (text.startsWith("/")) {
      handleCommand(text);
      return;
    }
    if (pendingQuestionRef.current) {
      bridge.send({ type: "answer", text });
      return;
    }
    if (!engineRef.current.turnActive) append(makeLine("user", text));
    bridge.send({ type: "user_message", text });
  }, [append, bridge, bumpInput, handleCommand]);

  // --- keyboard --------------------------------------------------------------

  // Ink re-subscribes its stdin listener whenever the handler identity changes;
  // keys arriving in that window are dropped. Keep the subscription stable by
  // routing through a ref.
  const handleKeyRef = useRef<(char: string, key: any) => void>(() => {});
  useInput(
    useCallback((char: string, key: any) => handleKeyRef.current(char, key), []),
  );

  handleKeyRef.current = (char, key) => {
    // Mouse reporting (SGR): wheel up = button 64, wheel down = 65. Ink strips
    // the leading ESC, so match with it optional. Clicks are stripped below.
    if (char) {
      const wheelEvents = char.match(/(?:\u001b)?\[<6[45];\d+;\d+[Mm]/g);
      if (wheelEvents && wheelEvents.length > 0) {
        let delta = 0;
        for (const event of wheelEvents) delta += event.includes("<64;") ? 3 : -3;
        if (delta !== 0) scrollBy(delta);
        return;
      }
    }

    if (picker) {
      if (key.escape) {
        setPicker(null);
        return;
      }
      if (key.upArrow) {
        setPicker((current) =>
          current ? { ...current, highlighted: Math.max(0, current.highlighted - 1) } : current,
        );
        return;
      }
      if (key.downArrow) {
        setPicker((current) =>
          current
            ? { ...current, highlighted: Math.min(current.sessions.length - 1, current.highlighted + 1) }
            : current,
        );
        return;
      }
      if (key.return) {
        const chosen = picker.sessions[picker.highlighted];
        setPicker(null);
        if (chosen) bridge.send({ type: "resume_session", path: chosen.path });
        return;
      }
      if (char === "n") {
        setPicker(null);
        return;
      }
      return;
    }

    if (key.ctrl) {
      switch (char) {
        case "a":
          bridge.send({ type: "approval", approved: true });
          return;
        case "d":
          bridge.send({ type: "approval", approved: false });
          return;
        case "y":
          bridge.send({ type: "yolo", value: !engineRef.current.yolo });
          return;
        case "p":
          bridge.send({ type: "pause_toggle" });
          return;
        case "s":
          bridge.send({ type: "stop" });
          return;
        case "r":
          openPicker();
          return;
        case "b":
          setBannerVisible((visible) => !visible);
          return;
        case "c":
          bridge.quit();
          exit();
          return;
        case "j":
          editInput((value, position) => [value.slice(0, position) + "\n" + value.slice(position), position + 1]);
          return;
      }
    }

    if (key.pageUp) {
      scrollBy(5);
      return;
    }
    if (key.pageDown) {
      scrollBy(-5);
      return;
    }

    if (key.return && !char.includes("\r") && !char.includes("\n")) {
      if (key.shift) {
        editInput((value, position) => [value.slice(0, position) + "\n" + value.slice(position), position + 1]);
      } else {
        submit();
      }
      return;
    }
    if (key.backspace || key.delete) {
      editInput((value, position) =>
        position > 0 ? [value.slice(0, position - 1) + value.slice(position), position - 1] : [value, position],
      );
      return;
    }
    if (key.leftArrow) {
      editInput((value, position) => [value, position - 1]);
      return;
    }
    if (key.rightArrow) {
      editInput((value, position) => [value, position + 1]);
      return;
    }
    if (key.upArrow || key.downArrow) {
      // Move between composer lines when multi-line; otherwise scroll chat.
      const value = inputRef.current;
      const rows = value.split("\n");
      if (rows.length > 1) {
        const upTo = value.slice(0, cursorRef.current);
        const row = upTo.split("\n").length - 1;
        const col = upTo.length - (upTo.lastIndexOf("\n") + 1);
        const target = key.upArrow ? row - 1 : row + 1;
        if (target >= 0 && target < rows.length) {
          let position = 0;
          for (let i = 0; i < target; i++) position += rows[i].length + 1;
          cursorRef.current = position + Math.min(col, rows[target].length);
          bumpInput();
        }
      } else if (key.upArrow) {
        scrollBy(1);
      } else {
        scrollBy(-1);
      }
      return;
    }
    if (char && !key.ctrl && !key.meta) {
      // Strip terminal control sequences that leak over SSH, plus mouse
      // click/release reports (ESC may already be stripped by Ink).
      const cleaned = char
        .replace(/(?:\u001b)?\[<\d+;\d+;\d+[Mm]/g, "")
        .replace(/\u001b\[[0-9;<>=?]*[a-zA-Z~]/g, "");
      if (!cleaned) return;
      // A chunk may contain several characters (fast typing / paste) and may
      // embed Enter (\r) or Ctrl+J (\n): insert text segments, submit on \r,
      // newline on \n.
      const segments = cleaned.split(/(\r|\n)/);
      for (const segment of segments) {
        if (!segment) continue;
        if (segment === "\r") {
          submit();
        } else if (segment === "\n") {
          editInput((value, position) => [value.slice(0, position) + "\n" + value.slice(position), position + 1]);
        } else {
          editInput((value, position) => [value.slice(0, position) + segment + value.slice(position), position + segment.length]);
        }
      }
      setScrollOffset(0);
    }
  };

  // --- layout ---------------------------------------------------------------

  const width = size.columns;
  const height = size.rows;
  // Banner: marginTop 1 + border 2 + paddingY 2 + 6 text lines. If this total
  // exceeds the real rendered height, the whole layout overflows the terminal
  // and Ink cannot repaint the top rows (stale/garbled lines when scrolling).
  const bannerRows = bannerVisible ? 11 : 0;
  const composerRows = Math.max(inputLines, Math.min(input.split("\n").length, INPUT_LINES_MAX)) + 2;
  const thinkingRows = thinking ? 1 : 0;
  const chatHeight = Math.max(3, height - bannerRows - composerRows - thinkingRows - 2);
  chatViewRef.current = { height: chatHeight, width: width - 4 };

  const phase = PHASE_MAP[engine.state] ?? "composing";

  return (
    <Box flexDirection="column" width={width} height={height} overflow="hidden">
      {bannerVisible ? (
        <Banner cwd={hello.cwd} session={sessionLabel} model={hello.model} version={hello.version} />
      ) : null}
      {picker ? (
        <Box flexGrow={1} alignItems="center" justifyContent="center">
          <SessionPicker sessions={picker.sessions} highlighted={picker.highlighted} />
        </Box>
      ) : (
        <ChatLog lines={lines} height={chatHeight} width={width - 4} scrollOffset={scrollOffset} />
      )}
      {thinking ? (
        <Box paddingX={2} height={1} overflow="hidden">
          <Text dimColor italic wrap="truncate">
            <Text color={ACCENT}>{"\u2026 "}</Text>
            <Text color={ACCENT}>{thinking.role} thinking</Text>
            {`: ${thinking.text.replace(/\s+/g, " ").slice(0, 200)}`}
          </Text>
        </Box>
      ) : null}
      <Box marginX={2} flexDirection="column">
        <Composer value={input} cursor={cursor} lines={inputLines} focused={!picker} />
      </Box>
      <StatusBar
        model={hello.model}
        phase={phase}
        state={engine.state}
        workflow={engine.workflow}
        goalActive={engine.goalActive}
        yolo={engine.yolo}
        queued={engine.queued}
        cwd={hello.cwd}
        gitBranch={hello.gitBranch}
        contextLine={contextLine}
        bannerVisible={bannerVisible}
      />
    </Box>
  );
}
