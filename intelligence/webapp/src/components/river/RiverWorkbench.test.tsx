import type { ReactNode } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getKline, getRiverMeta, getTimeline, searchEntities } from "../../river/api";
import type { EntityHit, RiverMeta, Timeline } from "../../river/types";
import { RiverWorkbench } from "./RiverWorkbench";

vi.mock("../../river/api", () => ({ getKline: vi.fn(), getRiverMeta: vi.fn(), getTimeline: vi.fn(), searchEntities: vi.fn() }));
vi.mock("./RiverTimeline", () => ({ RiverTimeline: ({ selected }: { selected: string | null }) => <div data-testid="timeline-selected">{selected}</div> }));
vi.mock("./TimelineViewport", () => ({ TimelineViewport: ({ children }: { children: (compact: boolean) => ReactNode }) => children(false) }));
vi.mock("./ScanPanel", () => ({ ScanPanel: ({ asOf }: { asOf: string }) => <div data-testid="scan-as-of">{asOf}</div> }));
vi.mock("./CohortPanel", () => ({ CohortPanel: () => null }));
vi.mock("./RangePanel", () => ({ RangePanel: () => null }));
vi.mock("./SliceDrawer", () => ({ SliceDrawer: () => null }));
vi.mock("./ShKline", () => ({ ShKline: () => null }));

const DAYS = ["2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24"];
const sector: EntityHit = { id: "S1", name: "芯片", pct_chg: 1, amount: 10 };
const hot: EntityHit[] = [{ id: "L1", name: "最新日热门", pct_chg: 3, amount: 99 }];
const meta = () => ({ latest: DAYS[DAYS.length - 1], trading_days: DAYS, default_entity: sector, hot_entities: hot, coverage: undefined }) as unknown as RiverMeta;
const timeline = (start: string, end: string, skip: string[] = []) => ({
  entity: { id: "S1", name: "芯片" }, start, end,
  days: DAYS.filter(d => d >= start && d <= end && !skip.includes(d)).map(date => ({ date })),
  trading_days: DAYS.length,
}) as unknown as Timeline;

describe("river six-track date identity", () => {
  beforeEach(() => {
    vi.mocked(getRiverMeta).mockReset().mockImplementation(async () => meta());
    vi.mocked(getKline).mockReset().mockResolvedValue({ days: [] } as never);
    vi.mocked(getTimeline).mockReset().mockImplementation(async (_e, start, end) => timeline(start, end));
    vi.mocked(searchEntities).mockReset().mockResolvedValue({ as_of: "2026-09-22", items: [{ id: "H1", name: "历史日候选", pct_chg: 2, amount: 5 }] });
  });

  it("keeps a historical day that the window has no row for, instead of jumping to the latest", async () => {
    vi.mocked(getTimeline).mockImplementation(async (_e, start, end) => timeline(start, end, ["2026-09-22"]));
    render(<RiverWorkbench focusDate="2026-09-22" />);
    expect(await screen.findByText(/所选日 2026-09-22 不在本窗口返回的六轨数据中/)).toBeVisible();
    expect(screen.getByTestId("timeline-selected")).toHaveTextContent("2026-09-22");
    expect(screen.getByTestId("scan-as-of")).toHaveTextContent("2026-09-22");
  });

  it("refresh re-reads the tracks of a custom window, not only the date directory", async () => {
    render(<RiverWorkbench />);
    await screen.findByTestId("timeline-selected");
    fireEvent.change(screen.getByLabelText("起始日"), { target: { value: "2026-09-22" } });
    await waitFor(() => expect(getTimeline).toHaveBeenLastCalledWith("芯片", "2026-09-22", "2026-09-24"));
    const before = vi.mocked(getTimeline).mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: /刷新/ }));
    await waitFor(() => expect(vi.mocked(getTimeline).mock.calls.length).toBe(before + 1));
    expect(getTimeline).toHaveBeenLastCalledWith("芯片", "2026-09-22", "2026-09-24");
    expect(getRiverMeta).toHaveBeenCalledTimes(2);
  });

  it("ranks default candidates on the selected historical day, not the latest day", async () => {
    render(<RiverWorkbench focusDate="2026-09-22" />);
    await screen.findByTestId("timeline-selected");
    fireEvent.focus(screen.getByRole("combobox", { name: "选择板块或题材" }));
    expect(await screen.findByText("历史日候选")).toBeVisible();
    expect(searchEntities).toHaveBeenCalledWith("", "2026-09-22");
    expect(screen.queryByText("最新日热门")).not.toBeInTheDocument();
    expect(screen.getByText("2026-09-22 成交额靠前的板块")).toBeVisible();
  });

  it("discloses a failed index chart and offers an in-place retry", async () => {
    vi.mocked(getKline).mockRejectedValueOnce(new Error("boom"));
    render(<RiverWorkbench />);
    expect(await screen.findByText(/上证 K 线底座读取失败/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "重试" }));
    await waitFor(() => expect(screen.queryByText(/上证 K 线底座读取失败/)).not.toBeInTheDocument());
    expect(getKline).toHaveBeenCalledTimes(2);
  });

  it("shows a six-track read failure with a retry that keeps the same window", async () => {
    vi.mocked(getTimeline).mockRejectedValueOnce(new Error("503"));
    render(<RiverWorkbench />);
    expect(await screen.findByText(/六轨读取失败/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "重试六轨" }));
    expect(await screen.findByTestId("timeline-selected")).toHaveTextContent("2026-09-24");
  });
});
