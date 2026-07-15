import React from "react";
import { Box, Text, useInput } from "ink";

import { ACCENT } from "../theme.js";

interface Props {
  value: string;
  cursor: number;
  lines: number;
  focused: boolean;
}

const INVERSE_ON = "\u001b[7m";
const INVERSE_OFF = "\u001b[27m";

/**
 * Multi-line composer rendering. Input handling lives in the app (useInput);
 * this component only draws the text with a cursor block.
 *
 * The whole line is one string child (cursor styled via raw ANSI codes), never
 * sibling <Text> nodes: Ink's insertBeforeNode skips markDirty, so inserting a
 * text node before the cursor (first keystroke into an empty composer) leaves
 * a stale 1-column Yoga measurement and the text wraps one character per line.
 */
export function Composer({ value, cursor, lines, focused }: Props) {
  const before = value.slice(0, cursor);
  const at = value[cursor] ?? " ";
  const after = value.slice(cursor + 1);
  const rows = (before + at + after).split("\n").length;
  const height = Math.max(lines, Math.min(rows, 12));
  const cursorText = at === "\n" ? " \n" : at;
  const rendered = focused
    ? before + INVERSE_ON + cursorText + INVERSE_OFF + after
    : before + at + after;
  return (
    <Box borderStyle="round" borderColor={focused ? ACCENT : "blue"} paddingX={1} height={height + 2}>
      <Text color={ACCENT} bold>
        {"\u276f "}
      </Text>
      <Box flexGrow={1}>
        <Text wrap="wrap">{rendered}</Text>
      </Box>
    </Box>
  );
}
