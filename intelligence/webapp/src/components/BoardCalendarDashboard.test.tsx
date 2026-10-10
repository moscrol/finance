import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getBoardCalendar } from "../api";
import type { BoardCalendar, BoardCalendarDay } from "../types";
import { BoardCalendarDashboard } from "./BoardCalendarDashboard";

vi.mock("../api", () => ({
  getBoardCalendar: vi.fn(),
}));

const mockedGetBoardCalendar = vi.mocked(getBoardCalendar);

function currentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function calendarFor(month: string, minBoards: number): BoardCalendar {
  const day = `${month}-24`;
  const stock = {
    stock_ts_code: "000001.SZ",
    stock_name: minBoards === 2 ? "乙公司" : "甲公司",
    boards: minBoards === 2 ? 2 : 6,
    theme: "测试题材",
    pct_chg: 10,
  };
  const group = { boards: stock.boards, stocks: [stock] };
  const calendarDay = {
    date: day,
    weekday: 3,
    is_trading_day: true,
    calendar_status: "trading" as const,
    data_status: "available" as const,
    board_groups: [group],
    stock_count: 1,
  };
  return {
    status: "ok",
    message: "已加载交易日与连板数据",
    start_date: `${month}-01`,
    end_date: `${month}-30`,
    min_boards: minBoards,
    recommended_min_boards: 3,
    market_data_cutoff: day,
    board_data_cutoff: day,
    calendar_days: [calendarDay],
    trading_days: [calendarDay],
  };
}

describe("BoardCalendarDashboard", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockedGetBoardCalendar.mockImplementation(async (month, minBoards = 3) =>
      calendarFor(month, minBoards),
    );
  });

  it("opens the shared historical month and links a trading day to the ladder", async () => {
    const onOpenLadder = vi.fn();
    const user = userEvent.setup();
    render(<BoardCalendarDashboard focusDate="2026-01-24" onOpenLadder={onOpenLadder} />);
    expect(await screen.findByText("2026 年 1 月")).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "查看 2026-01-24 连板梯队" }));
    expect(onOpenLadder).toHaveBeenCalledWith("2026-01-24");
    expect(mockedGetBoardCalendar).toHaveBeenCalledWith("2026-01", undefined);
  });

  it("loads a month and switches between the 3-board and 2-board views", async () => {
    const user = userEvent.setup();
    render(<BoardCalendarDashboard />);

    expect(await screen.findByText("6-000001 甲公司")).toBeInTheDocument();
    expect(screen.getByText(/1 只 ≥3板/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "≥2板" }));

    await waitFor(() => {
      expect(mockedGetBoardCalendar).toHaveBeenLastCalledWith(currentMonth(), 2);
    });
    expect(await screen.findByText("2-000001 乙公司")).toBeInTheDocument();
  });

  it("marks stocks above five boards with the distinct high-board style", async () => {
    const payload = calendarFor(currentMonth(), 3);
    const day = payload.calendar_days[0];
    day.board_groups.push({
      boards: 4,
      stocks: [{ stock_ts_code: "600002.SH", stock_name: "丁公司", boards: 4, theme: null, pct_chg: 10 }],
    });
    day.stock_count = 2;
    payload.trading_days = [day];
    mockedGetBoardCalendar.mockResolvedValue(payload);
    render(<BoardCalendarDashboard />);

    const highStock = await screen.findByText("6-000001 甲公司");
    expect(highStock).toHaveClass("board-calendar-stock--x5");
    const normalStock = screen.getByText("4-600002 丁公司");
    expect(normalStock).not.toHaveClass("board-calendar-stock--x5");
    expect(screen.getByText("6板")).toHaveClass("board-calendar-group-title--x5");
    expect(screen.getByText("4板")).not.toHaveClass("board-calendar-group-title--x5");
    expect(screen.getByText(/超过 5 板的个股/)).toBeInTheDocument();
  });

  it("writes a ≥5-board break on the day it happened, in the unified chip style", async () => {
    const payload = calendarFor(currentMonth(), 3);
    const day = payload.calendar_days[0];
    day.high_board_breaks = [
      { date: day.date, stock_ts_code: "600009.SH", stock_name: "戊公司", height_at_break: 6, theme: "高标题材" },
    ];
    payload.high_board_breaks = day.high_board_breaks;
    payload.high_board_min = 5;
    mockedGetBoardCalendar.mockResolvedValue(payload);
    render(<BoardCalendarDashboard />);

    const cell = await screen.findByRole("article", { name: day.date });
    const inDay = within(cell);
    expect(inDay.getByText("断板")).toHaveClass("board-calendar-group-title--break");
    expect(inDay.getByText("断 6板 戊公司")).toHaveClass("board-calendar-stock--break");
    expect(screen.getByText(/次 ≥5板 高标断板/)).toBeInTheDocument();
  });

  it("legend break threshold follows payload.high_board_min (not a hardcoded 5)", async () => {
    const payload = calendarFor(currentMonth(), 3);
    payload.high_board_min = 6;
    mockedGetBoardCalendar.mockResolvedValue(payload);
    render(<BoardCalendarDashboard />);
    await screen.findByText(/某只 ≥6板个股收盘不再涨停/);
  });

  it("break chip keeps the WCAG-AA muted grey (#6f6a61) for its 9px text", async () => {
    const css = (await import("../styles.css?raw")).default as string;
    const start = css.indexOf(".board-calendar-stock--break");
    const block = css.slice(start, css.indexOf("}", start));
    const colorDecl = block
      .split("\n")
      .map((line) => line.trim())
      .find((line) => line.startsWith("color:"));
    expect(colorDecl).toContain("#6f6a61");
  });

  it("keeps the selected threshold when navigating between months", async () => {
    const user = userEvent.setup();
    render(<BoardCalendarDashboard />);
    await screen.findByText("6-000001 甲公司");
    await user.click(screen.getByRole("button", { name: "≥2板" }));
    await screen.findByText("2-000001 乙公司");
    await user.click(screen.getByRole("button", { name: "下个月" }));

    await waitFor(() => {
      expect(mockedGetBoardCalendar).toHaveBeenCalledTimes(3);
    });
    expect(mockedGetBoardCalendar.mock.calls[2][0]).not.toBe(currentMonth());
    expect(mockedGetBoardCalendar.mock.calls[2][1]).toBe(2);
    expect(screen.getByRole("button", { name: "≥2板" })).toHaveAttribute("aria-pressed", "true");
  });

  it("expands and collapses all groups without losing the collapse button", async () => {
    const payload = calendarFor(currentMonth(), 3);
    const day = payload.calendar_days[0];
    day.board_groups.push({
      boards: 3,
      stocks: Array.from({ length: 9 }, (_, index) => ({
        stock_ts_code: `60000${index}.SH`,
        stock_name: `样本${index}`,
        boards: 3,
        theme: null,
        pct_chg: null,
      })),
    });
    day.stock_count = 10;
    mockedGetBoardCalendar.mockResolvedValue(payload);
    const user = userEvent.setup();
    render(<BoardCalendarDashboard />);

    await user.click(await screen.findByRole("button", { name: "展开其余 2 只" }));
    expect(screen.getByText("3-600008 样本8")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "收起" }));
    expect(screen.queryByText("3-600008 样本8")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "展开其余 2 只" })).toBeVisible();
  });

  it("retries the same month after a failed request", async () => {
    mockedGetBoardCalendar.mockRejectedValueOnce(new Error("连接暂时不可用"));
    const user = userEvent.setup();
    render(<BoardCalendarDashboard />);

    expect(await screen.findByRole("alert")).toHaveTextContent("连接暂时不可用");
    await user.click(screen.getByRole("button", { name: "重试" }));
    expect(await screen.findByText("6-000001 甲公司")).toBeVisible();
    expect(mockedGetBoardCalendar).toHaveBeenCalledTimes(2);
    expect(mockedGetBoardCalendar.mock.calls[1]).toEqual(mockedGetBoardCalendar.mock.calls[0]);
  });

  it("keeps future, closed, unavailable and quiet days visibly distinct", async () => {
    const month = currentMonth();
    const payload = calendarFor(month, 3);
    const statuses: Array<[BoardCalendarDay["calendar_status"], BoardCalendarDay["data_status"]]> = [
      ["closed", "not_applicable"],
      ["future", "not_applicable"],
      ["market_data_missing", "market_data_missing"],
      ["trading", "board_data_missing"],
      ["trading", "available"],
      ["calendar_unknown", "calendar_unknown"],
    ];
    payload.calendar_days = statuses.map(([calendar_status, data_status], index) => ({
      date: `${month}-0${index + 1}`,
      weekday: index,
      is_trading_day: calendar_status === "trading" || calendar_status === "market_data_missing",
      calendar_status,
      data_status,
      board_groups: [],
      stock_count: 0,
    }));
    payload.trading_days = payload.calendar_days.filter((day) => day.calendar_status === "trading");
    mockedGetBoardCalendar.mockResolvedValue(payload);
    render(<BoardCalendarDashboard />);

    const closed = within(await screen.findByRole("article", { name: `${month}-01` }));
    expect(closed.getByText("非交易日")).toBeVisible();
    const future = within(screen.getByRole("article", { name: `${month}-02` }));
    expect(future.getByText("尚未发生，不判断行情")).toBeVisible();
    expect(future.queryByText("非交易日")).not.toBeInTheDocument();
    expect(screen.getByText("未找到市场日数据")).toBeVisible();
    expect(screen.getByText("连板数据缺失", { exact: true })).toBeVisible();
    expect(screen.getAllByText("没有达到门槛的个股")).toHaveLength(1);
    expect(screen.getByText("暂不能确认")).toBeVisible();
  });
  it("refreshes successful data without losing month or threshold", async () => {
    const user = userEvent.setup();
    render(<BoardCalendarDashboard focusDate="2026-09-24" />);
    await screen.findByText("6-000001 甲公司");
    await user.click(screen.getByRole("button", { name: "≥2板" }));
    await screen.findByText("2-000001 乙公司");
    await user.click(screen.getByRole("button", { name: "刷新日历" }));
    await screen.findByText("2-000001 乙公司");
    expect(mockedGetBoardCalendar).toHaveBeenLastCalledWith("2026-09", 2);
    expect(mockedGetBoardCalendar).toHaveBeenCalledTimes(3);
  });

  it("does not label unavailable break coverage as zero events", async () => {
    const payload = calendarFor("2026-09", 3);
    payload.calendar_days[0].high_board_comparison_status = "data_missing";
    mockedGetBoardCalendar.mockResolvedValue(payload);
    render(<BoardCalendarDashboard focusDate="2026-09-24" />);
    expect(await screen.findByText("断板未判定：当日或前一交易日名单缺失")).toBeVisible();
    expect(screen.getByLabelText("日历摘要")).toHaveTextContent("—");
    expect(screen.getByText(/断板可比较 0 \/ 1/)).toBeVisible();
  });

  it("keeps a late old response from replacing a newly selected month", async () => {
    let resolveOld!: (data: BoardCalendar) => void;
    mockedGetBoardCalendar.mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve; }));
    render(<BoardCalendarDashboard focusDate="2026-08-24" />);
    fireEvent.change(screen.getByLabelText("选择月份"), { target: { value: "2026-09" } });
    await screen.findByRole("article", { name: "2026-09-24" });
    await act(async () => { resolveOld(calendarFor("2026-08", 3)); });
    expect(screen.queryByRole("article", { name: "2026-08-24" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("选择月份")).toHaveValue("2026-09");
  });


  it("shows list exits that cannot be called breaks as 待核, with the reason", async () => {
    const payload = calendarFor("2026-09", 3);
    const day = payload.calendar_days[0];
    day.high_board_comparison_status = "available";
    day.high_board_breaks = [
      { date: day.date, stock_ts_code: "600001.SH", stock_name: "真断", height_at_break: 6, theme: null, verification: "traded", close_pct_chg: 4.2 },
    ];
    day.high_board_unresolved = [
      { date: day.date, stock_ts_code: "600002.SH", stock_name: "停牌股", height_at_break: 7, theme: null, reason: "no_trade" },
      { date: day.date, stock_ts_code: "600004.SH", stock_name: "漏名单", height_at_break: 6, theme: null, reason: "closed_at_limit" },
    ];
    payload.high_board_breaks = day.high_board_breaks;
    payload.high_board_unresolved = day.high_board_unresolved;
    payload.unresolved_reasons = { no_trade: "当日无成交行情（停牌或行情缺失），停牌不等于断板" };
    mockedGetBoardCalendar.mockResolvedValue(payload);
    render(<BoardCalendarDashboard focusDate="2026-09-24" />);

    const cell = within(await screen.findByRole("article", { name: day.date }));
    expect(cell.getByText("断 6板 真断")).toHaveAttribute("title", expect.stringContaining("已核行情"));
    expect(cell.getByText("待核")).toHaveClass("board-calendar-group-title--unresolved");
    const suspended = cell.getByText("7板 停牌股 · 停牌/无成交");
    expect(suspended).toHaveClass("board-calendar-stock--unresolved");
    expect(suspended).toHaveAttribute("title", expect.stringContaining("停牌不等于断板"));
    expect(cell.getByText("6板 漏名单 · 名单疑缺")).toBeVisible();
    expect(screen.getByLabelText("日历摘要")).toHaveTextContent("1次");
    expect(screen.getByText(/另有 2 只高标离开名单但不能判为断板/)).toBeVisible();
  });

  it("labels a source switch and today's not-yet-ingested close distinctly", async () => {
    const payload = calendarFor("2026-09", 3);
    payload.calendar_days[0].high_board_comparison_status = "source_mismatch";
    const today: BoardCalendarDay = {
      date: "2026-09-28", weekday: 0, is_trading_day: false, calendar_status: "pending", data_status: "pending",
      board_groups: [], stock_count: 0, high_board_breaks: [], high_board_comparison_status: "pending",
    };
    payload.calendar_days = [...payload.calendar_days, today];
    mockedGetBoardCalendar.mockResolvedValue(payload);
    render(<BoardCalendarDashboard focusDate="2026-09-24" />);

    expect(await screen.findByText("断板未判定：前后两日名单来源不同，口径不可比")).toBeVisible();
    const pending = within(screen.getByRole("article", { name: "2026-09-28" }));
    expect(pending.getByText("今日 · 收盘数据待入库")).toBeVisible();
    expect(pending.getByText("今日数据尚未入库，不是缺档")).toBeVisible();
    expect(screen.getByRole("article", { name: "2026-09-28" })).toHaveClass("pending");
  });

  it("follows a later same-date navigation to another month", async () => {
    const { rerender } = render(<BoardCalendarDashboard focusDate="2026-08-24" />);
    await screen.findByRole("article", { name: "2026-08-24" });
    rerender(<BoardCalendarDashboard focusDate="2026-09-24" />);
    expect(await screen.findByRole("article", { name: "2026-09-24" })).toBeVisible();
    expect(mockedGetBoardCalendar).toHaveBeenLastCalledWith("2026-09", undefined);
  });
});
