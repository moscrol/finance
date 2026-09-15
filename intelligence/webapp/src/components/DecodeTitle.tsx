import { useEffect, useRef, useState } from "react";

const GLYPHS = "01#$%&*+-/<>=?@ABCDEFGHKMNPRSTUVWXYZ";
const DURATION_MS = 620;

/**
 * matrix-decode 移植：文本变化时从左到右「解码」入场。
 * 首次挂载与测试环境直接显示最终文本，避免闪烁与断言抖动。
 */
export function DecodeTitle({ text }: { text: string }) {
  const [display, setDisplay] = useState(text);
  const mounted = useRef(false);

  useEffect(() => {
    if (!mounted.current) {
      mounted.current = true;
      setDisplay(text);
      return;
    }
    if (import.meta.env.MODE === "test") {
      setDisplay(text);
      return;
    }
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setDisplay(text);
      return;
    }
    let raf = 0;
    let start: number | null = null;
    const frame = (ts: number) => {
      if (start === null) start = ts;
      const progress = Math.min((ts - start) / DURATION_MS, 1);
      const resolved = Math.floor(progress * text.length);
      let out = "";
      for (let i = 0; i < text.length; i += 1) {
        const ch = text[i];
        if (i < resolved || /\s/.test(ch)) {
          out += ch;
        } else if (i < resolved + 6) {
          out += GLYPHS[Math.floor(Math.random() * GLYPHS.length)];
        } else {
          out += " ";
        }
      }
      setDisplay(out);
      if (progress < 1) {
        raf = requestAnimationFrame(frame);
      } else {
        setDisplay(text);
      }
    };
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, [text]);

  return <>{display}</>;
}
