import React from "react";
import { Box, Text } from "ink";

import { ACCENT } from "../theme.js";

interface Props {
  value: string;
  cursor: number;
  width: number;
  focused: boolean;
  busy: boolean;
}

const INVERSE_ON = "\u001b[7m";
const INVERSE_OFF = "\u001b[27m";
const INPUT_LINES_MIN = 1;
const INPUT_LINES_MAX = 12;

/** Approximate terminal column width of one character (CJK and fullwidth = 2). */
function charWidth(char: string): number {
  const code = char.codePointAt(0) ?? 0;
  if (
    (code >= 0x1100 && code <= 0x115f) ||
    (code >= 0x2e80 && code <= 0xa4cf) ||
    (code >= 0xac00 && code <= 0xd7a3) ||
    (code >= 0xf900 && code <= 0xfaff) ||
    (code >= 0xfe30 && code <= 0xfe4f) ||
    (code >= 0xff00 && code <= 0xff60) ||
    (code >= 0xffe0 && code <= 0xffe6) ||
    code >= 0x20000
  ) {
    return 2;
  }
  return 1;
}

function wrapColumns(text: string, columns: number): number {
  if (!text) return 1;
  let rows = 1;
  let used = 0;
  for (const char of text) {
    if (char === "\n") {
      rows += 1;
      used = 0;
      continue;
    }
    const w = charWidth(char);
    if (used + w > columns && used > 0) {
      rows += 1;
      used = 0;
    }
    used += w;
  }
  return rows;
}

/**
 * Multi-line composer rendering. Input handling lives in the app (useInput);
 * this component only draws the text with a solid cursor block.
 *
 * No blinking caret: Ink redraws the whole screen on each blink, which clears
 * native terminal drag-selection before the user can copy.
 *
 * The whole line is one string child (cursor styled via raw ANSI codes), never
 * sibling <Text> nodes: Ink's insertBeforeNode skips markDirty, so inserting a
 * text node before the cursor (first keystroke into an empty composer) leaves
 * a stale 1-column Yoga measurement and the text wraps one character per line.
 */
export function Composer({ value, cursor, width, focused, busy }: Props) {
  const empty = value.length === 0;
  const before = value.slice(0, cursor);
  const at = value[cursor] ?? " ";
  const after = value.slice(cursor + 1);
  // Prompt ("❯ ") + border padding leave this many columns for the text.
  const textWidth = Math.max(20, width - 8);
  const contentRows = wrapColumns(empty ? " " : before + at + after, textWidth);
  const height = Math.max(INPUT_LINES_MIN, Math.min(contentRows, INPUT_LINES_MAX));
  const cursorText = at === "\n" ? " \n" : at;
  const rendered = focused
    ? before + INVERSE_ON + cursorText + INVERSE_OFF + after
    : before + at + after;
  const placeholder = busy
    ? "Agent is busy — Enter queues your next message…"
    : "Message LangBridge…";

  return (
    <Box
      borderStyle="round"
      borderColor={focused ? ACCENT : "gray"}
      paddingX={1}
      height={height + 2}
      overflow="hidden"
    >
      <Text color={ACCENT} bold>
        {"\u276f "}
      </Text>
      <Box flexGrow={1}>
        {empty ? (
          <Text dimColor>
            {focused ? `${INVERSE_ON} ${INVERSE_OFF}` : " "}
            {placeholder}
          </Text>
        ) : (
          <Text wrap="wrap">{rendered}</Text>
        )}
      </Box>
    </Box>
  );
}

export function composerRowCount(value: string, width: number): number {
  const textWidth = Math.max(20, width - 8);
  const contentRows = wrapColumns(value || " ", textWidth);
  const height = Math.max(INPUT_LINES_MIN, Math.min(contentRows, INPUT_LINES_MAX));
  // border top + bottom
  return height + 2;
}
