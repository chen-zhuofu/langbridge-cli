import React from "react";
import { Box, Text } from "ink";

import { ACCENT, GREEN, RED, YELLOW } from "../theme.js";

interface Props {
  model: string;
  phase: string;
  state: string;
  workflow: string;
  goalActive: boolean;
  yolo: boolean;
  queued: number;
  cwd: string;
  gitBranch: string;
  contextLine: string;
}

export function StatusBar(props: Props) {
  const stateColor = props.state === "ready" ? undefined : props.state === "stopping" ? RED : YELLOW;
  return (
    <Box justifyContent="space-between" paddingX={3} height={2} flexWrap="wrap" overflow="hidden">
      <Text>
        <Text color={ACCENT}>{props.model}</Text>
        {"  "}
        <Text color={stateColor} dimColor={!stateColor}>
          {props.phase}
        </Text>
        {props.workflow ? <Text dimColor>{` · ${props.workflow}`}</Text> : null}
        {props.goalActive ? (
          <Text bold color={ACCENT}>
            {" · ◎ goal"}
          </Text>
        ) : null}
        {props.yolo ? (
          <Text bold color={YELLOW}>
            {" · yolo"}
          </Text>
        ) : null}
        {props.queued > 0 ? (
          <Text bold color={YELLOW}>
            {` · ${props.queued} queued ${props.queued === 1 ? "msg" : "msgs"}`}
          </Text>
        ) : null}
        {"   "}
        <Text dimColor>{props.cwd}</Text>
        {props.gitBranch ? <Text color={GREEN} dimColor>{`  \u2387 ${props.gitBranch}`}</Text> : null}
      </Text>
      {props.contextLine ? <Text dimColor>{props.contextLine}</Text> : null}
    </Box>
  );
}
