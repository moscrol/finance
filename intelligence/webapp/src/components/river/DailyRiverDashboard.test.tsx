import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DailyOverview } from "../../river/dailyTypes";
import { DailyRiverDashboard } from "./DailyRiverDashboard";
import { contiguousReturn, heatColor } from "../../river/dailyMath";

const fixture = {
  days: ["2026-09-23", "2026-09-24"].map((date, i) => ({ date, sh_index_open: 3100, sh_index_high: 3150, sh_index_low: 3090, sh_index_close: 3120 + i, sh_index_pct_chg: i ? -1 : 1,
    ma5: 3100, ma20: 3110, total_amount: 10000, amount_vs_yesterday_pct: -5, amount_ma20: null,
    advancers: 1200, limit_up: 40, limit_down: 8, market_stage: "下跌阶段", stage_day: 2, volume_state: null, strength_avg_pct: .6,
    sh_index_source: "test-fixture", sector_count: 2, sector_valid_count: 2, sector_up_count: 1, sector_down_count: 1, sector_flat_count: 0,
    sector_gainers: [], sector_losers: [], sector_amount_leaders: [], limitup: null })),
  calendar: ["2026-09-22", "2026-09-23", "2026-09-24"], start: "2026-09-23", end: "2026-09-24",
  latest_market_date: "2026-09-24", latest_sector_date: "2026-09-24", gaps: [],
  sectors: [
    { id: "s1", name: "铜", key: "s1|铜", points: [[0, 100, .5], [2, 120, .6]] },
    { id: "s2", name: "铜缆", key: "s2|铜缆", points: [null, [-1, 80, null]] },
  ],
} as DailyOverview;

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => ({ ok: true, json: async () => url.includes("opinion-attention") ? { collection_status: "not_connected", events: [], gaps: [], visible_observations: 0, event_count: 0 } : structuredClone(fixture) })));
});
afterEach(() => vi.unstubAllGlobals());

describe("daily river", () => {
  it("does not turn missing cells into zero or compound through a gap", () => {
    expect(heatColor(null)).toBe("");
    expect(heatColor(0)).not.toBe("");
    expect(contiguousReturn([[1, 1, 0], null, [1, 1, 0]], 2, 3)).toBeNull();
    expect(contiguousReturn([[10, 1, 0], [-10, 1, 0]], 1, 2)).toBeCloseTo(-1);
  });
  it("selecting a heat cell links date and sector and opens research", async () => {
    const onFocusDate = vi.fn(), onResearch = vi.fn();
    render(<DailyRiverDashboard onFocusDate={onFocusDate} onResearch={onResearch}/>);
    fireEvent.click(await screen.findByRole("button", { name: "铜 2026-09-23 0.00%" }));
    expect(onFocusDate).toHaveBeenCalledWith("2026-09-23");
    expect(screen.getByRole("combobox", { name: "当前交易日" })).toHaveValue("2026-09-23");
    fireEvent.click(screen.getByRole("button", { name: "展开板块六轨" }));
    expect(onResearch).toHaveBeenCalledWith(expect.objectContaining({ id: "s1", name: "铜", pct_chg: 0 }), "2026-09-23");
  });
  it("external date changes synchronize the selected session", async () => {
    const { rerender } = render(<DailyRiverDashboard focusDate="2026-09-24"/>);
    await screen.findByRole("button", { name: "铜 2026-09-23 0.00%" });
    rerender(<DailyRiverDashboard focusDate="2026-09-23"/>);
    await waitFor(() => expect(screen.getByRole("combobox", { name: "当前交易日" })).toHaveValue("2026-09-23"));
  });
  it("an external date outside the window requests a historical window", async () => {
    const { rerender } = render(<DailyRiverDashboard focusDate="2026-09-24"/>);
    await screen.findByRole("button", { name: "铜 2026-09-23 0.00%" });
    rerender(<DailyRiverDashboard focusDate="2026-09-22"/>);
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(expect.stringContaining("end=2026-09-22"), expect.anything()));
  });
  it("search and ranking controls affect the heatmap", async () => {
    render(<DailyRiverDashboard/>);
    await screen.findByRole("button", { name: "铜 2026-09-23 0.00%" });
    fireEvent.change(screen.getByRole("textbox", { name: "搜索板块" }), { target: { value: "s2" } });
    expect(screen.queryByRole("button", { name: "铜 2026-09-23 0.00%" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "铜缆 2026-09-24 -1.00%" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "当日榜单" }));
    expect(within(screen.getByRole("table")).getByText("成交额 / 亿")).toBeInTheDocument();
    expect(within(screen.getByRole("table")).getByText("板块边际量")).toBeInTheDocument();
    expect(screen.queryByText("涨跌家数差占比")).not.toBeInTheDocument();
  });
  it("shows a truthful unconnected opinion state, not fake metrics", async () => {
    render(<DailyRiverDashboard/>);
    fireEvent.click(await screen.findByRole("tab", { name: "舆论观察" }));
    expect(await screen.findByText("数据接口已就绪，等待真实信源。")).toBeInTheDocument();
    expect(screen.getByText("付费采集未开启")).toBeInTheDocument();
  });
  it("API failure is visible and retryable", async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new Error("后端不可用"));
    render(<DailyRiverDashboard/>);
    expect(await screen.findByRole("alert")).toHaveTextContent("后端不可用");
    fireEvent.click(screen.getByRole("button", { name: "重新读取" }));
    expect(await screen.findByRole("button", { name: "铜 2026-09-23 0.00%" })).toBeInTheDocument();
  });
});
