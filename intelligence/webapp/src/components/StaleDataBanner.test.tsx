import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { MarketFreshness } from "../types";
import { StaleDataBanner } from "./StaleDataBanner";

const stale: MarketFreshness = {
  as_of: "2026-09-24",
  expected_trade_date: "2026-09-29",
  status: "stale",
  lag_trading_days: 2,
  missing_trade_dates: ["2026-09-28", "2026-09-29"],
  calendar_certain: true,
  checked_at: "2026-09-29T16:00:00+08:00",
};
const current: MarketFreshness = {
  ...stale,
  as_of: "2026-09-29",
  status: "current",
  lag_trading_days: 0,
  missing_trade_dates: [],
};

describe("StaleDataBanner", () => {
  it("names the database cutoff, expected session, and all listed missing dates", () => {
    render(<StaleDataBanner freshness={stale} />);

    const alert = screen.getByRole("alert", { name: "盘面数据日期" });
    expect(alert).toHaveTextContent("库内最新盘面数据截至 2026-09-24");
    expect(alert).toHaveTextContent("最近已收盘交易日 2026-09-29 共 2 个交易日");
    expect(alert).toHaveTextContent("待补日期：2026-09-28、2026-09-29");
    expect(alert).not.toHaveTextContent("本页结论均基于");
  });

  it("renders nothing when the database is current and no other date is selected", () => {
    const { container } = render(<StaleDataBanner freshness={current} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("keeps a historical viewing date neutral when the database is current", () => {
    render(<StaleDataBanner freshness={current} viewingDate="2026-09-24" />);

    const notice = screen.getByRole("status", { name: "观察日期" });
    expect(notice).toHaveTextContent("选择观察日 2026-09-24");
    expect(notice).toHaveTextContent("库内最新盘面日期 2026-09-29");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("盘面数据日期")).not.toBeInTheDocument();
  });

  it("keeps a historical viewing date separate from a genuine database lag", () => {
    render(<StaleDataBanner freshness={stale} viewingDate="2026-09-21" />);

    expect(screen.getByRole("status", { name: "观察日期" })).toHaveTextContent("选择观察日 2026-09-21");
    const alert = screen.getByRole("alert", { name: "盘面数据日期" });
    expect(alert).toHaveTextContent("截至 2026-09-24");
    expect(alert).toHaveTextContent("2 个交易日");
    expect(alert).not.toHaveTextContent("2026-09-21");
  });

  it("does not hide a missing date even when the expected date is known", () => {
    render(<StaleDataBanner freshness={{ ...stale, as_of: null, status: "missing", lag_trading_days: null }} />);

    const notice = screen.getByRole("status", { name: "盘面数据日期" });
    expect(notice).toHaveTextContent("尚未取得盘面数据日期");
    expect(notice).toHaveTextContent("无法判断是否已更新至 2026-09-29");
  });

  it("does not blame the current year when an earlier calendar year is unknown", () => {
    render(<StaleDataBanner freshness={{ ...stale, as_of: "2025-12-31", status: "unknown", lag_trading_days: null, calendar_certain: false }} />);

    const notice = screen.getByRole("status", { name: "盘面数据日期" });
    expect(notice).toHaveTextContent("交易日历信息不完整");
    expect(notice).toHaveTextContent("暂时无法判断");
    expect(notice).not.toHaveTextContent("当前年份");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows an unknown expected date without rendering null or a guessed cutoff", () => {
    render(<StaleDataBanner freshness={{ ...stale, status: "unknown", lag_trading_days: null, expected_trade_date: null, calendar_certain: false }} />);

    const notice = screen.getByRole("status", { name: "盘面数据日期" });
    expect(notice).toHaveTextContent("暂时无法判断");
    expect(notice).not.toHaveTextContent("null");
  });

  it("discloses an invalid date instead of hiding it as current", () => {
    render(<StaleDataBanner freshness={{ ...stale, as_of: "not-a-date", status: "invalid", lag_trading_days: null }} />);

    const notice = screen.getByRole("status", { name: "盘面数据日期" });
    expect(notice).toHaveTextContent("盘面数据日期无效");
    expect(notice).not.toHaveTextContent("not-a-date");
  });

  it("discloses a future database date", () => {
    render(<StaleDataBanner freshness={{ ...stale, as_of: "2026-09-30", status: "future", lag_trading_days: null }} />);

    expect(screen.getByRole("status", { name: "盘面数据日期" })).toHaveTextContent("2026-09-30 晚于今天");
  });

  it("does not present today's unsettled row as finalized closing data", () => {
    render(<StaleDataBanner freshness={{ ...stale, as_of: "2026-09-29", expected_trade_date: "2026-09-28", status: "unsettled", lag_trading_days: null }} />);

    const notice = screen.getByRole("status", { name: "盘面数据日期" });
    expect(notice).toHaveTextContent("尚未到上海时间 15:30");
    expect(notice).toHaveTextContent("暂不视为已确认的收盘数据");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("identifies a truncated list without turning trading days into calendar days", () => {
    render(<StaleDataBanner freshness={{ ...stale, lag_trading_days: 37 }} />);

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("37 个交易日");
    expect(alert).toHaveTextContent("仅列前 2 个");
  });

  it("fails closed when a current status lacks the date needed to support it", () => {
    render(<StaleDataBanner freshness={{ ...current, as_of: null }} />);
    expect(screen.getByRole("status", { name: "盘面数据日期" })).toHaveTextContent("尚未取得盘面数据日期");
  });
});
