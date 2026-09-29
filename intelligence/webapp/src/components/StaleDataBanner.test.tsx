import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StaleDataBanner } from "./StaleDataBanner";

const base = {
  as_of: "2026-09-24",
  expected_trade_date: "2026-09-28",
  lag_trading_days: 1,
  missing_trade_dates: ["2026-09-28"],
  calendar_certain: true,
  checked_at: "2026-09-29T11:50:00+08:00",
};

describe("StaleDataBanner", () => {
  it("names the lag and the missing trading days", () => {
    render(<StaleDataBanner freshness={base} />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("盘面数据截至 2026-09-24");
    expect(alert).toHaveTextContent("共 1 个交易日");
    expect(alert).toHaveTextContent("缺 09-28");
  });

  it("renders nothing when data is current", () => {
    const { container } = render(
      <StaleDataBanner freshness={{ ...base, lag_trading_days: 0, missing_trade_dates: [] }} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("says the calendar cannot decide instead of guessing", () => {
    render(
      <StaleDataBanner
        freshness={{ ...base, lag_trading_days: null, expected_trade_date: null, calendar_certain: false }}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("无法判断");
  });

  it("marks truncated missing lists", () => {
    render(
      <StaleDataBanner
        freshness={{ ...base, lag_trading_days: 40, missing_trade_dates: ["2026-08-01", "2026-08-02"] }}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("等 40 天");
  });
});
