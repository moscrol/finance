const headingLine = /^#{1,3}\s/;
const listLine = /^\s*(?:[-*+]|\d+\.)\s/;

/** Insert the blank lines Markdown needs so headings and lists can breathe. */
export function normalizeAnswerMarkdown(source: string): string {
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  const out: string[] = [];
  for (const line of lines) {
    const previous = out.at(-1) ?? "";
    const previousFilled = previous.trim().length > 0;
    if (headingLine.test(line) && previousFilled) {
      out.push("");
    } else if (
      listLine.test(line) &&
      previousFilled &&
      !listLine.test(previous)
    ) {
      out.push("");
    }
    out.push(line);
  }
  return out.join("\n");
}
