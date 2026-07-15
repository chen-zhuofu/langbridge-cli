import React from "react";
import { Box, Text } from "ink";

import type { SessionItem } from "../protocol.js";
import { ACCENT } from "../theme.js";

interface Props {
  sessions: SessionItem[];
  highlighted: number;
}

const MAX_VISIBLE = 16;

export function SessionPicker({ sessions, highlighted }: Props) {
  const start = Math.max(0, Math.min(highlighted - Math.floor(MAX_VISIBLE / 2), sessions.length - MAX_VISIBLE));
  const visible = sessions.slice(start, start + MAX_VISIBLE);
  return (
    <Box flexDirection="column" borderStyle="round" borderColor={ACCENT} paddingX={2} paddingY={1} width={72}>
      <Text bold color={ACCENT}>
        Resume a session ({sessions.length})
      </Text>
      <Box flexDirection="column" marginTop={1}>
        {visible.map((session, index) => {
          const absolute = start + index;
          const active = absolute === highlighted;
          return (
            <Text key={session.path} inverse={active} color={active ? ACCENT : undefined}>
              {session.label}
            </Text>
          );
        })}
      </Box>
      <Box marginTop={1}>
        <Text dimColor>{"\u2191/\u2193 move \u00b7 Enter resume \u00b7 n new session \u00b7 Esc cancel"}</Text>
      </Box>
    </Box>
  );
}
