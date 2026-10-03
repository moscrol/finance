import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReviewSnapshot } from "../../river/reviewTypes";
import type { SectorSeries } from "../../river/dailyTypes";
import { DailyReviewWorkspace } from "./DailyReviewWorkspace";

const dates = ["2026-09-23", "2026-09-24"];
const sectors: SectorSeries[] = [{ id: "S1", key: "S1|芯片", name: "芯片", points: [[1, 800, 15], [-2, 750, -10]] }];
const tableColumns = ["排序", "股票", "代码", "涨幅", "成交额", "当日开根加权", "新高状态", "命中双红", "双红题材"];
function fixture(day = "2026-09-24"): ReviewSnapshot {
  return { schema_version: 1, trade_date: day, status: "available", available_dates: dates,
    provenance: { source_path: `market_feature_store/exports/${day}-daily-review.json`, generated_at: "2026-09-29 10:00:00", sha256: "test", note: "归档不代表当时已知。" },
    report: { facts: { top3_industry_ratio: 42.7, top3_industry_ratio_delta_pp: -.6, concentration_state: "正常", double_red_count: 0, single_red_count: 10, stock_high_120d_count: 56 },
      industries: ["电子", "机械设备"], matrices: {
        double_red: [{ industry: "电子", status: "available", dates, rows: [["申万一级：电子（占比/涨跌幅）", "28.1%/0.2%", "-/-2.9%"], ["芯片", "🔥1.0%/15.0/800", "-2.0%/-10.0/750"]] }, { industry: "机械设备", status: "available", dates, rows: [["机床", "1.2%/5.0/30", "2.0%/6.0/40"]] }],
        stock_highs: [{ industry: "电子", status: "empty", dates: [], rows: [] }, { industry: "机械设备", status: "empty", dates: [], rows: [] }],
        limit_up: [{ industry: "电子", status: "available", dates, rows: [["芯片", 0, "-"]] }],
      }, engines: [{ industry: "电子", columns: tableColumns, rows: [[1, "测试股", "600001.SH", "7.87%", "80.5亿", "70.60", "历史新高", "否", "-"]] }, { industry: "机械设备", columns: tableColumns, rows: [[1, "机械甲", "600002.SH", "10%", "10亿", "31.62", "120日新高", "否", "-"]] }],
      sections: [{ id: "concentration", index: 3, title: "成交前三行业", blocks: [{ kind: "table", columns: ["日期", "前三占比", "集中度", "行业1", "占比1", "行业2", "占比2", "行业3", "占比3"], rows: [["昨日", "43.30%", "正常", "机械设备", "7.70%", "电子", "28.10%", "医药生物", "7.50%"], ["今日", "42.70%", "正常", "电子", "27.10%", "机械设备", "8.40%", "医药生物", "7.20%"]] }] }, { id: "sentiment", index: 2, title: "市场情绪", blocks: [{ kind: "note", text: "<img src=x onerror=alert(1)>" }] }], diagnostics: ["空矩阵不等于零。"], warnings: [], core_board: [] },
  };
}
const response = (data: unknown) => ({ ok: true, json: async () => data }) as Response;
beforeEach(() => vi.stubGlobal("fetch", vi.fn(async (url: string) => response(fixture(new URL(url, "https://test.invalid").searchParams.get("as_of")!)))));
afterEach(() => vi.unstubAllGlobals());
const props = { date: "2026-09-24", sectors, marketDates: dates, onDate: vi.fn() };

describe("canonical daily review workspace", () => {
  it("preserves compound cells, reference gaps, day provenance and industry share identities", async () => {
    render(<DailyReviewWorkspace {...props}/>);
    const matrix = await screen.findByRole("table", { name: "电子 双红矩阵" });
    expect(within(matrix).getByText("🔥1.0%/15.0/800")).toBeInTheDocument();
    expect(within(matrix).getByText("-/-2.9%")).toBeInTheDocument();
    expect(screen.getByText("昨日 28.10%")).toBeInTheDocument();
    expect(screen.getByText(/生成于 2026-09-29/)).toBeInTheDocument();
    expect(screen.queryByText("涨跌家数差占比")).not.toBeInTheDocument();
  });
  it("industry selection links matrix and stock engine; stock detail keeps the original score", async () => {
    render(<DailyReviewWorkspace {...props}/>);
    fireEvent.click(await screen.findByRole("button", { name: "聚焦机械设备行业" }));
    expect(screen.getByRole("table", { name: "机械设备 双红矩阵" })).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "机械设备 个股发动机" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "查看机械甲发动机明细" }));
    expect(within(screen.getByRole("region", { name: "个股发动机明细" })).getByText("31.62")).toBeInTheDocument();
  });
  it("empty high mapping is not zero and counts preserve literal zero versus dash", async () => {
    render(<DailyReviewWorkspace {...props}/>);
    fireEvent.click(await screen.findByRole("button", { name: "120日新高" }));
    expect(screen.getByText(/全市场120日新高为 56 只/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "涨停矩阵" }));
    const table = screen.getByRole("table", { name: "电子 涨停矩阵" });
    expect(within(table).getByRole("button", { name: "芯片 2026-09-23 0" })).toBeInTheDocument();
    expect(within(table).getByRole("button", { name: "芯片 2026-09-24 —" })).toBeInTheDocument();
  });
  it("matrix date selection uses a full date and external dates load exact archives", async () => {
    const onDate = vi.fn();
    const { rerender } = render(<DailyReviewWorkspace {...props} onDate={onDate}/>);
    fireEvent.click(await screen.findByRole("button", { name: "复盘切换至 2026-09-23" }));
    expect(onDate).toHaveBeenCalledWith("2026-09-23");
    rerender(<DailyReviewWorkspace {...props} date="2026-09-23" onDate={onDate}/>);
    await waitFor(() => expect(fetch).toHaveBeenCalledWith("/api/river/daily-review?as_of=2026-09-23", expect.anything()));
    await screen.findByText(/数据日 2026-09-23/);
  });
  it("same-day exact sector mapping opens research and attention with the selected date", async () => {
    const onResearch = vi.fn(), onAttention = vi.fn(), onSelectSector = vi.fn();
    render(<DailyReviewWorkspace {...props} onResearch={onResearch} onAttention={onAttention} onSelectSector={onSelectSector}/>);
    fireEvent.click(await screen.findByRole("button", { name: "芯片" }));
    expect(onSelectSector).toHaveBeenCalledWith(sectors[0]);
    fireEvent.click(screen.getByRole("button", { name: "板块六轨" }));
    expect(onResearch).toHaveBeenCalledWith({ id: "S1", name: "芯片", amount: 750, pct_chg: -2 }, "2026-09-24");
    fireEvent.click(screen.getByRole("button", { name: "同日公开消息" }));
    expect(onAttention).toHaveBeenCalledWith(sectors[0], "2026-09-24");
  });
  it("ambiguous sector identity disables research rather than inventing a code", async () => {
    render(<DailyReviewWorkspace {...props} sectors={[...sectors, { ...sectors[0], id: "S2", key: "S2|芯片" }]} onResearch={vi.fn()}/>);
    fireEvent.click(await screen.findByRole("button", { name: "芯片" }));
    expect(screen.getByRole("button", { name: "板块六轨" })).toBeDisabled();
    expect(screen.getByText(/未找到同日唯一板块代码/)).toBeInTheDocument();
  });
  it("missing archive does not show another day's matrices and allows an explicit date jump", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => response({ ...fixture(), status: "missing", report: null })));
    const onDate = vi.fn();
    render(<DailyReviewWorkspace {...props} onDate={onDate}/>);
    await screen.findByText("这一天尚无结构化日报归档");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "2026-09-23" }));
    expect(onDate).toHaveBeenCalledWith("2026-09-23");
  });
  it("aborted old requests cannot replace the new date even if transport ignores abort", async () => {
    let release!: (value: Response) => void;
    vi.stubGlobal("fetch", vi.fn().mockImplementationOnce(() => new Promise<Response>(r => { release = r; })).mockResolvedValue(response(fixture("2026-09-23"))));
    const { rerender } = render(<DailyReviewWorkspace {...props}/>);
    rerender(<DailyReviewWorkspace {...props} date="2026-09-23"/>);
    await screen.findByText(/数据日 2026-09-23/);
    await act(async () => { release(response(fixture())); });
    expect(screen.queryByText(/数据日 2026-09-24/)).not.toBeInTheDocument();
    expect(screen.getByText(/数据日 2026-09-23/)).toBeInTheDocument();
  });
  it("wrong-date response fails closed and retry uses the current date", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(response(fixture("2026-09-23"))).mockResolvedValue(response(fixture())));
    render(<DailyReviewWorkspace {...props}/>);
    expect(await screen.findByRole("alert")).toHaveTextContent("日期不一致");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "重试日报" }));
    await screen.findByRole("table", { name: "电子 双红矩阵" });
  });
  it("full archive preserves text as text, never executes embedded HTML", async () => {
    const { container } = render(<DailyReviewWorkspace {...props}/>);
    fireEvent.click(await screen.findByRole("button", { name: "展开完整日报 · 2 章节" }));
    expect(screen.getByText("<img src=x onerror=alert(1)>")).toBeInTheDocument();
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByLabelText("完整日报归档")).toHaveTextContent("原始表格与结论");
  });
});
