// 数字与颜色的统一口径：红涨绿跌（A 股习惯），缺失一律显示「—」而不是 0。

export function fmtPct(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}%`;
}

export function fmtNum(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toLocaleString("zh-CN", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

/** 成交额：库里单位是「亿」。≥1 万亿显示「x.x 万亿」。 */
export function fmtAmount(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (Math.abs(value) >= 10000) return `${(value / 10000).toFixed(2)} 万亿`;
  if (Math.abs(value) >= 100) return `${value.toFixed(0)} 亿`;
  return `${value.toFixed(1)} 亿`;
}

export function fmtDateShort(date: string): string {
  // 2026-09-24 → 09-24
  return date.length >= 10 ? date.slice(5, 10) : date;
}

export function fmtTs(ts: string | null | undefined): string {
  if (!ts) return "未知";
  return ts.replace("T", " ").slice(0, 16);
}

export function signClass(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value) || value === 0) return "flat";
  return value > 0 ? "up" : "down";
}

/** 把数值映射到 0~1 的强度，用于热力格。 */
export function intensity(value: number | null | undefined, scale: number): number {
  if (value === null || value === undefined || Number.isNaN(value) || scale <= 0) return 0;
  return Math.min(1, Math.abs(value) / scale);
}

/** 红涨绿跌的背景色，alpha 随强度变化。 */
export function heatColor(value: number | null | undefined, scale: number): string {
  const level = intensity(value, scale);
  if (value === null || value === undefined || level === 0) return "transparent";
  const alpha = 0.12 + level * 0.78;
  return value > 0 ? `rgba(198, 62, 52, ${alpha.toFixed(3)})` : `rgba(46, 125, 84, ${alpha.toFixed(3)})`;
}

/** 单色（橙）强度色，用于计数类。 */
export function monoColor(value: number | null | undefined, scale: number, rgb = "204, 118, 42"): string {
  const level = intensity(value, scale);
  if (level === 0) return "transparent";
  return `rgba(${rgb}, ${(0.12 + level * 0.8).toFixed(3)})`;
}

export function stageTone(stage: string | null | undefined): string {
  if (!stage) return "none";
  const s = stage.replace("阶段", "");
  if (s.includes("主升") || s.includes("上涨")) return "bull";
  if (s.includes("下跌")) return "bear";
  if (s.includes("顶部")) return "top";
  if (s.includes("底部")) return "bottom";
  return "side";
}

export function shortStage(stage: string | null | undefined): string {
  return (stage ?? "").replace("阶段", "");
}
