/** Tokyo-night palette, matching the Python TUI. */
export const ACCENT = "#7aa2f7";
export const GREEN = "#9ece6a";
export const YELLOW = "#e0af68";
export const RED = "#f7768e";
export const DIM = "gray";

export function styleColor(style?: string): string | undefined {
  switch (style) {
    case "accent":
      return ACCENT;
    case "success":
      return GREEN;
    case "warn":
      return YELLOW;
    case "error":
      return RED;
    case "dim":
    default:
      return undefined;
  }
}
