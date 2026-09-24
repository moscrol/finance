import { useEffect } from "react";

// 与 styles.css 里 `[data-spotlight], .starter-grid > button, …::after` 的列表保持一致
const SPOTLIGHT_SELECTOR =
  "[data-spotlight], .starter-grid > button, .output-card, .output-metric, .market-hero";

/**
 * Beautiful UI · SpotlightCard（移植自 vidio/library/设计系统/Beautiful-UI/js/beautiful-ui.js）。
 *
 * 只往卡片上写三个 CSS 变量（--spot-x / --spot-y / --spot-o），高光本身由
 * `[data-spotlight]::after` 的径向渐变绘制；一个 document 级监听器服务所有卡片。
 * 触屏（hover: none）和 prefers-reduced-motion 下不启用。
 */
export function useSpotlight(): void {
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    if (
      window.matchMedia("(hover: none)").matches ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      return;
    }

    let lastCard: HTMLElement | null = null;
    const onMove = (event: PointerEvent) => {
      const target = event.target;
      const card =
        target instanceof Element
          ? target.closest<HTMLElement>(SPOTLIGHT_SELECTOR)
          : null;
      if (lastCard && lastCard !== card) {
        lastCard.style.setProperty("--spot-o", "0");
      }
      if (card) {
        const rect = card.getBoundingClientRect();
        card.style.setProperty("--spot-x", `${event.clientX - rect.left}px`);
        card.style.setProperty("--spot-y", `${event.clientY - rect.top}px`);
        card.style.setProperty("--spot-o", "1");
      }
      lastCard = card;
    };

    document.addEventListener("pointermove", onMove, { passive: true });
    return () => {
      document.removeEventListener("pointermove", onMove);
      lastCard?.style.setProperty("--spot-o", "0");
    };
  }, []);
}
