import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { getKline, getLimitUpCalendar } from "../../river/api";
import type { LimitUpCalendar } from "../../river/types";
import { LimitUpDashboard } from "./LimitUpDashboard";

vi.mock("../../river/api", () => ({ getLimitUpCalendar: vi.fn(), getKline: vi.fn() }));
vi.mock("./ShKline", () => ({ ShKline: () => null }));
function calendar(date: string): LimitUpCalendar {
  return { start: date, end: date, days: [{ trade_date: date, ladder: { "3": 1 }, promotion_rate: {}, promotion_estimated: [], total: 1, high_boards: 1, max_boards: 3,
    details: [], top_themes: [], market: null, leader: null }], stats: { trading_days: 1, avg_total: 1, avg_max_boards: 3, max_boards: 3, max_boards_date: date } };
}
beforeEach(() => {
  vi.mocked(getLimitUpCalendar).mockReset();
  vi.mocked(getLimitUpCalendar).mockImplementation(async (_days, end) => calendar(end ?? "2026-09-24"));
  vi.mocked(getKline).mockReset();
  vi.mocked(getKline).mockRejectedValue(new Error("no price fixture"));
});
it("opens the linked historical window rather than jumping to the latest date", async () => {
  render(<LimitUpDashboard focusDate="2026-01-06"/>);
  await waitFor(() => expect(getLimitUpCalendar).toHaveBeenCalledWith(60, "2026-01-06"));
  expect(await screen.findByText(/2026-01-06 梯队/)).toBeInTheDocument();
});
it("reanchors when a different linked date is outside the loaded window", async () => {
  const { rerender } = render(<LimitUpDashboard focusDate="2026-09-24"/>);
  await screen.findByText(/2026-09-24 梯队/);
  rerender(<LimitUpDashboard focusDate="2026-01-06"/>);
  expect(await screen.findByText(/2026-01-06 梯队/)).toBeInTheDocument();
  expect(getLimitUpCalendar).toHaveBeenCalledWith(60, "2026-01-06");
});
it("ignores an obsolete request after unmount", async () => {
  let resolveFirst: (value: LimitUpCalendar) => void = () => undefined;
  vi.mocked(getLimitUpCalendar).mockImplementationOnce(() => new Promise(resolve => { resolveFirst = resolve; }));
  const { unmount } = render(<LimitUpDashboard focusDate="2026-09-24"/>);
  await waitFor(() => expect(getLimitUpCalendar).toHaveBeenCalledTimes(1));
  unmount();
  resolveFirst(calendar("2026-09-24"));
  await Promise.resolve();
  // Unmounted request must not start a follow-up K-line fetch.
  await waitFor(() => expect(getKline).not.toHaveBeenCalled());
});
