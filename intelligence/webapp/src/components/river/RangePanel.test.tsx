import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { getRange } from "../../river/api";
import type { RangeResult } from "../../river/types";
import { RangePanel } from "./RangePanel";

vi.mock("../../river/api", () => ({ getRange: vi.fn() }));
afterEach(() => vi.resetAllMocks());
const result: RangeResult = {
  entity_id: "600001.SH", entity_name: "测试股", kind: "stock", method: "close_to_close",
  start: "2026-08-03", end: "2026-08-05", trustworthy: false, codes_seen: ["600001.SH"],
  coverage: { expected_days: 3, actual_days: 2, complete: false, clean: false, missing_dates: ["2026-08-04"], duplicate_dates: [] },
  values: { cumulative_return_pct: 21 }, peak_date: null, gaps: [], caveats: ["覆盖不完整"],
  curve: [
    { date: "2026-08-03", pct_chg: 10, cum_pct: 10, amount: 100 },
    { date: "2026-08-04", pct_chg: null, cum_pct: null, amount: null },
    { date: "2026-08-05", pct_chg: 10, cum_pct: 21, amount: 100 },
  ],
};

it("breaks the curve at unknown trading days without squeezing the date axis", async () => {
  vi.mocked(getRange).mockResolvedValue(result);
  render(<RangePanel entity="600001.SH" start={result.start} end={result.end} onPickDate={vi.fn()}/>);
  const chart = await screen.findByRole("img", { name: "测试股 区间累计涨幅曲线" });
  const path = chart.querySelector("path.line")!.getAttribute("d")!;
  expect(path.match(/M/g)).toHaveLength(2);
  expect(path).not.toContain("L");
  expect(chart).toHaveTextContent("08-04");
});

it("removes obsolete numeric output while a stricter request is pending", async () => {
  let release!: (value: RangeResult) => void;
  vi.mocked(getRange).mockResolvedValueOnce(result).mockImplementationOnce(() => new Promise(resolve => { release = resolve; }));
  render(<RangePanel entity="600001.SH" start={result.start} end={result.end} onPickDate={vi.fn()}/>);
  await screen.findByRole("img");
  fireEvent.click(screen.getByRole("checkbox"));
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  release({ ...result, values: { cumulative_return_pct: null }, curve: [] });
  await waitFor(() => expect(screen.getByText("区间内没有可画的每日读数")).toBeInTheDocument());
});
