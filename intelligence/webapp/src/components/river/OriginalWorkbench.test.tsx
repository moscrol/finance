import { useState } from "react";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getKline, getLimitUpCalendar, getRiverMeta } from "../../river/api";
import type { LimitUpCalendar, RiverMeta } from "../../river/types";
import { LimitUpDashboard } from "./LimitUpDashboard";
import { OriginalDailyReview } from "./OriginalDailyReview";
import { RiverWorkbench as Home } from "./RiverHome";
import { TimelineViewport } from "./TimelineViewport";

vi.mock("../../river/api", () => ({ getKline: vi.fn(), getLimitUpCalendar: vi.fn(), getRiverMeta: vi.fn() }));
vi.mock("./ShKline", () => ({ ShKline: () => <span>original index base</span> }));
vi.mock("./DailyReviewWorkspace", () => ({ DailyReviewWorkspace: ({ date }: { date: string }) => <div data-testid="review-date">{date}</div> }));
vi.mock("./DailyRiverDashboard", () => ({ AttentionPanel: ({ date, sector }: { date: string; sector: { name: string } | null }) => <div>公开消息面板 {date} {sector?.name ?? "全部方向"}</div> }));
vi.mock("./RiverWorkbench", () => ({ RiverWorkbench: ({ focusDate, onEntityChange, onPublicAttention }: { focusDate: string; onEntityChange: (entity: unknown) => void; onPublicAttention: (entity: unknown, day: string) => void }) => <div>原六轨 {focusDate}<button onClick={() => onEntityChange({ id: "S1", name: "芯片", amount: null, pct_chg: null })}>选芯片</button><button onClick={() => onPublicAttention({ id: "S1", name: "芯片", amount: null, pct_chg: null }, focusDate)}>六轨转公开消息</button></div> }));

function calendar(end = "2026-09-24"): LimitUpCalendar {
  const ds = end === "2026-09-24" ? ["2026-09-23", end] : [end];
  return { start: ds[0], end, days: ds.map((trade_date, i) => ({ trade_date, ladder: { "2": 1, "5": 1 }, promotion_rate: { "2": 20, "5": 50 }, promotion_estimated: [2], total: 2, high_boards: 1, max_boards: 5, market: null, leader: { name: "甲股", height: 5, ts_code: "000001.SZ" }, top_themes: [], details: [
    { name: "甲股", ts_code: "000001.SZ", boards: 5, theme: "芯片", pct: 10, first_limit_date: "2026-09-18" },
    { name: `乙股${i}`, ts_code: "000002.SZ", boards: 2, theme: null, pct: 9.9, first_limit_date: "2026-09-22" },
  ] })), stats: { trading_days: ds.length, avg_total: 2, avg_max_boards: 5, max_boards: 5, max_boards_date: end } };
}
const market = (day = "2026-09-24") => ({ days: [{ date: day }], sectors: [], end: day, start: day, calendar: ["2026-01-06", "2026-09-23", "2026-09-24"], latest_market_date: "2026-09-24" });
const response = (value: unknown) => ({ ok: true, json: async () => value }) as Response;
beforeEach(() => {
  vi.mocked(getLimitUpCalendar).mockReset().mockImplementation(async (_days, end) => calendar(end ?? undefined));
  vi.mocked(getKline).mockReset().mockRejectedValue(new Error("no chart in test"));
  vi.mocked(getRiverMeta).mockReset().mockResolvedValue({ latest: "2026-09-24", trading_days: ["2026-09-23", "2026-09-24"] } as RiverMeta);
  vi.stubGlobal("fetch", vi.fn(async (url: string) => response(market(new URL(url, "https://test.invalid").searchParams.get("end") ?? undefined))));
});
afterEach(() => vi.unstubAllGlobals());

describe("original ladder reading flow", () => {
  it("keeps an unrecorded day missing in the chart, cells and detail", async () => {
    const missing = calendar();
    Object.assign(missing.days[1], { total: null, high_boards: null, max_boards: null, ladder: {}, details: [], promotion_rate: {}, promotion_estimated: [] });
    vi.mocked(getLimitUpCalendar).mockResolvedValue(missing);
    const { container } = render(<LimitUpDashboard/>);
    expect(await screen.findByRole("gridcell", { name: "2026-09-24 2板 数据缺失" })).toHaveTextContent("缺");
    expect(screen.getByText(/不能据此判断没有连板股/)).toBeInTheDocument();
    expect(container.querySelectorAll(".spark-dot")).toHaveLength(1);
    expect(screen.queryByText("这一天没有 2 板及以上的个股")).not.toBeInTheDocument();
  });
  it("previous/next and same-day review share the selected date", async () => {
    const onFocusDate = vi.fn(), onOpenRiver = vi.fn();
    render(<LimitUpDashboard onFocusDate={onFocusDate} onOpenRiver={onOpenRiver}/>);
    await screen.findByRole("combobox", { name: "连板当前交易日" });
    fireEvent.click(screen.getByRole("button", { name: "连板上一交易日" }));
    expect(onFocusDate).toHaveBeenLastCalledWith("2026-09-23");
    expect(screen.getByRole("combobox", { name: "连板当前交易日" })).toHaveValue("2026-09-23");
    fireEvent.click(screen.getByRole("button", { name: "同日复盘 ↗" }));
    expect(onOpenRiver).toHaveBeenCalledWith("2026-09-23");
  });
  it("clicking a rung filters stocks and provides actual code/first-board detail", async () => {
    render(<LimitUpDashboard/>);
    fireEvent.click(await screen.findByRole("gridcell", { name: "2026-09-24 5板 1家" }));
    expect(screen.getByRole("button", { name: "查看甲股连板详情" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "查看乙股1连板详情" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "查看甲股连板详情" }));
    const detail = screen.getByRole("region", { name: "连板个股详情" });
    expect(detail).toHaveTextContent("000001.SZ");
    expect(detail).toHaveTextContent("2026-09-18");
    expect(detail).toHaveTextContent("题材标签不等于经验证");
    fireEvent.click(screen.getByRole("button", { name: "连板上一交易日" }));
    expect(screen.queryByRole("region", { name: "连板个股详情" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "查看乙股0连板详情" })).toBeInTheDocument();
  });
  it("a controlled date update does not accidentally clear the just-clicked rung", async () => {
    const onFocusDate = vi.fn();
    const { rerender } = render(<LimitUpDashboard focusDate="2026-09-24" onFocusDate={onFocusDate}/>);
    fireEvent.click(await screen.findByRole("gridcell", { name: "2026-09-23 5板 1家" }));
    rerender(<LimitUpDashboard focusDate="2026-09-23" onFocusDate={onFocusDate}/>);
    await waitFor(() => expect(screen.getByRole("button", { name: "5板 · 1家" })).toHaveAttribute("aria-pressed", "true"));
  });
  it("latest window escapes a historical anchor and explicitly propagates its actual date", async () => {
    const notify = vi.fn();
    render(<LimitUpDashboard focusDate="2026-01-06" onFocusDate={notify}/>);
    await screen.findByText(/2026-01-06 梯队/);
    fireEvent.click(screen.getByRole("button", { name: "最新窗口" }));
    await screen.findByText(/2026-09-24 梯队/);
    expect(getLimitUpCalendar).toHaveBeenLastCalledWith(60, null);
    expect(notify).toHaveBeenLastCalledWith("2026-09-24");
  });
  it("history cutoff requests an explicit endpoint window, retaining estimated-rate notes", async () => {
    render(<LimitUpDashboard/>);
    await screen.findByRole("combobox", { name: "连板当前交易日" });
    fireEvent.change(screen.getByLabelText("连板历史截止日"), { target: { value: "2026-01-06" } });
    await screen.findByText(/2026-01-06 梯队/);
    expect(getLimitUpCalendar).toHaveBeenLastCalledWith(60, "2026-01-06");
    expect(screen.getByText(/分母（昨日首板数）/)).toBeInTheDocument();
  });
});

describe("original daily navigation", () => {
  const props = { focusDate: "2026-09-24", onFocusDate: vi.fn(), onResearch: vi.fn(), onAttention: vi.fn() };
  it("renders the report for the selected date even if the independent index graph fails", async () => {
    render(<OriginalDailyReview {...props}/>);
    expect(await screen.findByTestId("review-date")).toHaveTextContent("2026-09-24");
    expect(await screen.findByText(/指数图暂不可读/)).toBeInTheDocument();
  });
  it("does not let a late initial market response overwrite a newer external historical date", async () => {
    let release!: (value: Response) => void;
    const notify = vi.fn();
    vi.stubGlobal("fetch", vi.fn().mockImplementationOnce(() => new Promise<Response>(resolve => { release = resolve; })).mockResolvedValue(response(market("2026-01-06"))));
    const { rerender } = render(<OriginalDailyReview {...props} onFocusDate={notify}/>);
    rerender(<OriginalDailyReview {...props} focusDate="2026-01-06" onFocusDate={notify}/>);
    await act(async () => { release(response(market())); });
    expect(await screen.findByTestId("review-date")).toHaveTextContent("2026-01-06");
    expect(notify).not.toHaveBeenCalledWith("2026-09-24");
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining("end=2026-01-06"), expect.anything());
  });
  it("latest fetches an unanchored window rather than silently pinning the old latest date", async () => {
    function Controlled() {
      const [date, setDate] = useState("2026-01-06");
      return <OriginalDailyReview {...props} focusDate={date} onFocusDate={setDate}/>;
    }
    render(<Controlled/>);
    expect(await screen.findByTestId("review-date")).toHaveTextContent("2026-01-06");
    fireEvent.click(screen.getByRole("button", { name: "最新" }));
    await waitFor(() => expect(screen.getByTestId("review-date")).toHaveTextContent("2026-09-24"));
    expect(fetch).toHaveBeenLastCalledWith("/api/river/daily-overview?days=40", expect.anything());
  });
  it("keeps the market failure visible while mounting the independent selected archive", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, status: 404 })));
    render(<OriginalDailyReview {...props}/>);
    expect(await screen.findByRole("alert")).toHaveTextContent("配套后端已发布");
    expect(screen.getByTestId("review-date")).toHaveTextContent("2026-09-24");
  });
});

describe("single original river entry", () => {
  it("retains the six-track entry and separates report coverage from public attention", async () => {
    render(<Home focusDate="2026-09-24"/>);
    await screen.findByTestId("review-date");
    fireEvent.click(screen.getByRole("button", { name: "板块六轨" }));
    expect(screen.getByText("原六轨 2026-09-24")).toBeInTheDocument();
    expect(screen.getByText("研报覆盖 ≠ 公开消息热度")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "六轨转公开消息" }));
    expect(await screen.findByText("公开消息面板 2026-09-24 芯片")).toBeInTheDocument();
  });
  it("opens the ladder on the exact current day", async () => {
    const onOpenLadder = vi.fn();
    render(<Home focusDate="2026-09-23" onOpenLadder={onOpenLadder}/>);
    fireEvent.click(screen.getByRole("button", { name: "同日连板 ↗" }));
    expect(onOpenLadder).toHaveBeenCalledWith("2026-09-23");
    await screen.findByTestId("review-date");
  });
});

it("density changes presentation, not the selected date or underlying time window", () => {
  const { container } = render(<TimelineViewport label="测试时间轴" dates={["2026-09-23", "2026-09-24"]} selected="2026-09-24">{compact => <div data-trade-date="2026-09-24">{compact ? "compact" : "readable"}</div>}</TimelineViewport>);
  expect(screen.getByText("readable")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "压缩总览" }));
  expect(screen.getByText("compact")).toBeInTheDocument();
  expect(container.querySelector('[data-trade-date="2026-09-24"]')).toBeInTheDocument();
  expect(within(screen.getByRole("region", { name: "测试时间轴横向滚动区域" })).getByText("compact")).toBeInTheDocument();
});
