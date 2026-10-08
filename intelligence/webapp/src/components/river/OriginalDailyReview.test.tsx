import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { OriginalDailyReview } from "./OriginalDailyReview";

vi.mock("../../river/api", () => ({ getKline: vi.fn().mockRejectedValue(new Error("no chart")) }));
vi.mock("./ShKline", () => ({ ShKline: () => null }));
afterEach(() => vi.unstubAllGlobals());

it.each([
  ["2026-08-04", "available"], ["2026-08-04", "missing"],
  ["2020-01-06", "available"], ["2020-01-06", "missing"],
])("keeps requested archive %s when outside the market calendar, archive=%s", async (selected, status) => {
  const notify = vi.fn();
  const requests: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    requests.push(url);
    const body = url.includes("daily-overview") ? {
      start: selected < "2026-08-03" ? null : "2026-08-03", end: selected < "2026-08-03" ? null : "2026-08-03", latest_market_date: "2026-08-05",
      days: selected < "2026-08-03" ? [] : [{ date: "2026-08-03" }], calendar: ["2026-08-03", "2026-08-05"], sectors: [],
    } : {
      schema_version: 1, trade_date: new URL(url, "https://test.invalid").searchParams.get("as_of"),
      status, available_dates: [selected], message: "所选日期无归档",
      report: status === "missing" ? null : { facts: {}, industries: [], matrices: { double_red: [], stock_highs: [], limit_up: [] }, engines: [], sections: [], diagnostics: [], warnings: [], core_board: [] },
    };
    return { ok: true, json: async () => body };
  }));
  render(<OriginalDailyReview focusDate={selected} onFocusDate={notify} onResearch={vi.fn()} onAttention={vi.fn()}/>);
  await waitFor(() => expect(requests).toContain(`/api/river/daily-review?as_of=${selected}`));
  expect(requests).not.toContain("/api/river/daily-review?as_of=2026-08-03");
  expect(notify).not.toHaveBeenCalled();
  expect(screen.getByLabelText("复盘当前交易日")).toHaveValue(selected);
  expect(screen.getByText(/所选日报日期暂无行情/)).toBeInTheDocument();
  if (status === "missing") expect(await screen.findByText("这一天尚无结构化日报归档")).toBeInTheDocument();
  else expect(await screen.findByText(`${selected} 日报`)).toBeInTheDocument();
});

it.each(["error", "pending"])("loads the selected archive independently while the market request is %s", async marketState => {
  const selected = "2026-08-04";
  const notify = vi.fn();
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url.includes("daily-overview")) return marketState === "error"
      ? { ok: false, status: 503 }
      : new Promise<Response>(() => {});
    return { ok: true, json: async () => ({
      schema_version: 1, trade_date: selected, status: "available", available_dates: [selected],
      report: { facts: {}, industries: [], matrices: { double_red: [], stock_highs: [], limit_up: [] }, engines: [], sections: [], diagnostics: [], warnings: [], core_board: [] },
    }) };
  }));
  render(<OriginalDailyReview focusDate={selected} onFocusDate={notify} onResearch={vi.fn()} onAttention={vi.fn()}/>);
  await waitFor(() => expect(fetch).toHaveBeenCalledWith(`/api/river/daily-review?as_of=${selected}`, expect.anything()));
  expect(await screen.findByRole("button", { name: "展开完整日报 · 0 章节" })).toBeInTheDocument();
  expect(screen.getByLabelText("复盘当前交易日")).toHaveValue(selected);
  expect(notify).not.toHaveBeenCalled();
  if (marketState === "error") expect(await screen.findByRole("alert")).toHaveTextContent("503");
});
