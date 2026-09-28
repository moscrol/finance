import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getBoardCalendar } from "../api";
import type { BoardCalendar } from "../types";
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

  it("reloads the selected month when the month navigation is used", async () => {
    const user = userEvent.setup();
    render(<BoardCalendarDashboard />);
    await screen.findByText("6-000001 甲公司");

    await user.click(screen.getByRole("button", { name: "下个月" }));

    await waitFor(() => {
      expect(mockedGetBoardCalendar).toHaveBeenCalledTimes(2);
    });
    expect(mockedGetBoardCalendar.mock.calls[1][0]).not.toBe(
      mockedGetBoardCalendar.mock.calls[0][0],
    );
  });
});
