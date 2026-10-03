import { useEffect, useRef } from "react";

/**
 * 科技感背景层（仅 data-theme="tech" 时挂载）：
 * 顶部微光 + 点阵 + 单色粒子星座 + 胶片噪点。
 * 粒子在 running=true 时轻微加速并向右上汇聚，表达「正在研究」。
 * 技巧移植自 HyperFrames registry 的 aurora-drift / grain-field /
 * dynamic-grid / grain-overlay / constellation-hub，按网页运行时
 * 改写为 CSS keyframes + requestAnimationFrame（不依赖 GSAP）。
 */
export function TechBackdrop({ running }: { running: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const runningRef = useRef(running);
  runningRef.current = running;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    // jsdom 等环境没有 matchMedia；此时直接不启动粒子动画
    if (
      typeof window.matchMedia !== "function" ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      return;
    }
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const COUNT = 56;
    const LINK = 120 * dpr;
    let width = 0;
    let height = 0;
    let raf = 0;
    let parts: Array<{
      x: number;
      y: number;
      vx: number;
      vy: number;
      r: number;
    }> = [];

    const resize = () => {
      width = canvas.width = window.innerWidth * dpr;
      height = canvas.height = window.innerHeight * dpr;
      canvas.style.width = `${window.innerWidth}px`;
      canvas.style.height = `${window.innerHeight}px`;
    };
    const init = () => {
      parts = Array.from({ length: COUNT }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.1 * dpr,
        vy: (Math.random() - 0.5) * 0.1 * dpr,
        r: (Math.random() * 1.2 + 0.5) * dpr,
      }));
    };
    resize();
    init();
    const onResize = () => {
      resize();
      init();
    };
    window.addEventListener("resize", onResize);

    const tick = () => {
      raf = requestAnimationFrame(tick);
      if (document.hidden) return;
      const active = runningRef.current;
      const boost = active ? 2.1 : 1;
      const anchorX = width * 0.78;
      const anchorY = height * 0.16;
      ctx.clearRect(0, 0, width, height);
      for (const p of parts) {
        if (active) {
          p.vx += (anchorX - p.x) * 0.0000016 * dpr;
          p.vy += (anchorY - p.y) * 0.0000016 * dpr;
        }
        p.vx *= 0.996;
        p.vy *= 0.996;
        p.x += p.vx * boost;
        p.y += p.vy * boost;
        if (p.x < -20) p.x = width + 20;
        if (p.x > width + 20) p.x = -20;
        if (p.y < -20) p.y = height + 20;
        if (p.y > height + 20) p.y = -20;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(43, 38, 32, 0.2)";
        ctx.fill();
      }
      const linkAlpha = active ? 0.085 : 0.055;
      for (let a = 0; a < parts.length; a += 1) {
        for (let b = a + 1; b < parts.length; b += 1) {
          const dx = parts[a].x - parts[b].x;
          const dy = parts[a].y - parts[b].y;
          const dist = Math.hypot(dx, dy);
          if (dist < LINK) {
            ctx.beginPath();
            ctx.moveTo(parts[a].x, parts[a].y);
            ctx.lineTo(parts[b].x, parts[b].y);
            ctx.strokeStyle = `rgba(43, 38, 32, ${(
              linkAlpha *
              (1 - dist / LINK)
            ).toFixed(4)})`;
            ctx.lineWidth = dpr * 0.6;
            ctx.stroke();
          }
        }
      }
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
    };
  }, []);

  return (
    <div className="tech-backdrop" aria-hidden="true">
      <div className="tech-spotlight" />
      <div className="tech-dotgrid" />
      <canvas ref={canvasRef} className="tech-particles" />
      <div className="tech-grain" />
    </div>
  );
}
