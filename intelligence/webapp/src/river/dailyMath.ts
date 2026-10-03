import type { SectorPoint } from "./dailyTypes";

export function contiguousReturn(points: SectorPoint[], end: number, width = 5): number | null {
  if (end + 1 < width) return null;
  const values = points.slice(end - width + 1, end + 1).map(p => p?.[0]);
  if (values.some(v => v == null || !Number.isFinite(v))) return null;
  return (values.reduce<number>((acc, value) => acc * (1 + value! / 100), 1) - 1) * 100;
}
export function heatColor(value: number | null | undefined): string {
  if (value == null) return "";
  if (value === 0) return "#f2f1ed";
  const a = Math.min(.72, .10 + Math.abs(value) / 7 * .62);
  return value > 0 ? `rgba(208, 86, 65, ${a})` : `rgba(50, 139, 111, ${a})`;
}
