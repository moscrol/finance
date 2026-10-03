import { useEffect, useRef, useState, type ReactNode } from "react";
import "../../riverOriginal.css";

/** Shared column width for K-line and facts. Horizontal scroll never changes the window. */
export function TimelineViewport({ dates, selected, labelWidth = 112, children, label }: {
  dates: string[]; selected: string | null; labelWidth?: number;
  children: (compact: boolean) => ReactNode; label: string;
}) {
  const [compact, setCompact] = useState(false);
  const scroll = useRef<HTMLDivElement>(null);
  const dateKey = dates.join(",");
  useEffect(() => {
    const node = scroll.current;
    if (!node) return;
    const reveal = () => {
      const column = Array.from(node.querySelectorAll<HTMLElement>("[data-trade-date]")).find(el => el.dataset.tradeDate === selected);
      if (!column) return;
      const left = column.getBoundingClientRect().left - node.getBoundingClientRect().left + node.scrollLeft;
      const right = left + column.getBoundingClientRect().width;
      if (right > node.scrollLeft + node.clientWidth) node.scrollLeft = right - node.clientWidth + 12;
      else if (left < node.scrollLeft + labelWidth + 12) node.scrollLeft = Math.max(0, left - labelWidth - 12);
    };
    reveal();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(reveal);
    observer?.observe(node);
    return () => observer?.disconnect();
  }, [selected, dateKey, compact, labelWidth]);
  return <section className={`time-window ${compact ? "is-compact" : "is-readable"}`} aria-label={label} style={{ ["--time-label-width" as string]: `${labelWidth + 12}px` }}>
    <div className="time-window-tools"><div className="river-segment" role="group" aria-label={`${label}密度`}><button type="button" aria-pressed={!compact} className={!compact ? "active" : ""} onClick={() => setCompact(false)}>逐日阅读</button><button type="button" aria-pressed={compact} className={compact ? "active" : ""} onClick={() => setCompact(true)}>压缩总览</button></div><span>{compact ? "全窗口概览；悬停查看数值" : "左右滑动查看历史；指数与下方数据保持逐列对齐"}<b>{dates.length} 个交易日</b></span></div>
    <div ref={scroll} className="time-window-scroll" tabIndex={0} role="region" aria-label={`${label}横向滚动区域`}><div style={{ minWidth: compact ? undefined : labelWidth + dates.length * 42 + 20 }}>{children(compact)}</div></div>
  </section>;
}
