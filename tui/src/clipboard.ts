/** Copy text to the local clipboard via OSC 52 (works over SSH/Cursor). */

export function copyToClipboard(stdout: NodeJS.WriteStream | undefined, text: string): boolean {
  const payload = text.replace(/\u001b/g, "");
  if (!stdout || !payload) return false;
  const encoded = Buffer.from(payload, "utf8").toString("base64");
  // BEL-terminated form is widely supported (xterm, VS Code, iTerm2, Cursor).
  stdout.write(`\u001b]52;c;${encoded}\u0007`);
  return true;
}
