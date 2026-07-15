/** Chat line model rendered by the log. */

export type LineKind = "user" | "assistant" | "system" | "trace";

export interface ChatLine {
  id: number;
  kind: LineKind;
  text: string;
  style?: string;
  queued?: boolean;
}

let nextId = 1;

export function makeLine(kind: LineKind, text: string, extra?: Partial<ChatLine>): ChatLine {
  return { id: nextId++, kind, text, ...extra };
}
