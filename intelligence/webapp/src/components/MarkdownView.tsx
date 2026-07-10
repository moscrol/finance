import DOMPurify from "dompurify";
import { marked } from "marked";
import { useMemo } from "react";

interface MarkdownViewProps {
  source: string;
  className?: string;
}

export function MarkdownView({ source, className = "" }: MarkdownViewProps) {
  const html = useMemo(() => {
    const rendered = marked.parse(source, {
      async: false,
      breaks: true,
      gfm: true,
    }) as string;
    return DOMPurify.sanitize(rendered, {
      USE_PROFILES: { html: true },
    });
  }, [source]);

  return (
    <div
      className={`markdown-view ${className}`}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
