import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { DailyReportProjection } from "../types";
import { DailyReportView } from "./DailyReportView";

const projection: DailyReportProjection = {
  report_type: "daily_agent",
  title: "日常研究雷达",
  date: "2026-07-01",
  source_mode: "canonical_json",
  plain_summary: [
    "1 个旧逻辑重新活跃，0 个新方向进入候选。",
    "今日研究队列共 2 项。",
    "优先关注氢能源，结论仍需结合证据层级验证。",
  ],
  metrics: [
    { label: "旧逻辑重新活跃", value: "1", tone: "attention" },
    { label: "需要补官方证据", value: "1" },
  ],
  sections: [
    {
      title: "值得关注",
      items: [
        {
          title: "氢能源",
          summary: "多信号共振，但仍需官方事实确认。",
          badges: ["旧逻辑唤醒", "旧逻辑待验证"],
          meta: [{ label: "代表股票", value: "金宏气体、昊华科技" }],
          next_action: "查公告、调研纪要和订单。",
          details: ["缺失：L3 官方验证"],
        },
      ],
    },
    {
      title: "今天要做什么",
      items: [
        {
          title: "风电",
          summary: "盘面触发但缺少基线材料。",
          badges: ["补题材研究"],
          next_action: "补齐题材边界和核心公司。",
        },
      ],
    },
  ],
  glossary: [
    { term: "IMA", definition: "快速建立题材边界、产业链位置与核心公司的研究卡。" },
    { term: "L3", definition: "公告、订单或调研等官方事实。" },
  ],
  provenance: {
    canonical_path: "market_feature_store/exports/2026-07-01-daily-agent.json",
    rendered_path: "复盘/daily/2026-07-01/2026-07-01-daily-agent.html",
    warnings: [],
    original_report_available: true,
    original_artifact_id: "daily_agent:2026-07-01:html:legacy",
    generated_at: "2026-07-01T20:28:58+08:00",
  },
};

describe("DailyReportView", () => {
  it("renders the five report layers with reader-facing labels", () => {
    render(<DailyReportView projection={projection} />);

    expect(screen.getByTestId("daily-summary")).toHaveTextContent("三件需要知道的事");
    expect(screen.getByTestId("daily-metrics")).toHaveTextContent("研究工作量");
    expect(screen.getByTestId("daily-sections")).toHaveTextContent("值得关注");
    expect(screen.getByTestId("daily-glossary")).toHaveTextContent("术语表");
    expect(screen.getByTestId("daily-provenance")).toHaveTextContent(
      "market_feature_store/exports/2026-07-01-daily-agent.json",
    );
    expect(screen.getByText("旧逻辑重新活跃")).toBeInTheDocument();
    expect(screen.getByText("查公告、调研纪要和订单。")).toBeInTheDocument();
  });

  it("keeps glossary and the original report behind disclosure controls", async () => {
    const user = userEvent.setup();
    render(
      <DailyReportView
        projection={projection}
        originalReportUrl="/api/artifacts/legacy/content"
      />,
    );

    const glossary = screen.getByText("术语表").closest("details");
    const original = screen.getByText("原始报告").closest("details");
    expect(glossary).not.toHaveAttribute("open");
    expect(original).not.toHaveAttribute("open");

    await user.click(screen.getByText("术语表"));
    expect(glossary).toHaveAttribute("open");
    await user.click(screen.getByText("原始报告"));
    expect(original).toHaveAttribute("open");
    expect(screen.getByTitle("原始报告：日常研究雷达")).toHaveAttribute(
      "sandbox",
      "allow-scripts",
    );
  });

  it("renders canonical review tables, folding wide matrices by default", () => {
    const reviewProjection: DailyReportProjection = {
      ...projection,
      report_type: "daily_review",
      title: "2026-09-02 每日市场复盘",
      sections: [
        {
          title: "个股载体",
          items: [
            {
              title: "3板及以上个股",
              summary: "3板及以上个股 6 只，最高连板 4 板。",
              badges: ["§11"],
            },
          ],
          tables: [
            {
              title: "3板及以上个股",
              columns: ["股票", "连板数", "首板日期"],
              rows: [["国芳集团", 4, "2026-08-28"]],
            },
            {
              title: "涨停题材 · 电子",
              columns: [
                "题材",
                "08-13",
                "08-14",
                "08-17",
                "08-18",
                "08-19",
                "08-20",
                "08-21",
                "08-24",
                "09-02",
              ],
              rows: [["芯片", 9, 21, 23, 10, 1, 4, 14, 5, 11]],
            },
          ],
        },
        {
          title: "数据覆盖",
          items: [],
          tables: [
            {
              title: "数据覆盖检查",
              columns: ["表", "状态"],
              rows: [["fact_market_daily", "OK"]],
            },
          ],
        },
      ],
    };
    render(<DailyReportView projection={reviewProjection} />);

    const stockTables = screen.getByTestId("daily-tables-个股载体");
    expect(stockTables).toHaveTextContent("国芳集团");
    expect(stockTables).toHaveTextContent("2026-08-28");
    const compact = screen.getByText("3板及以上个股", { selector: "summary span" }).closest("details");
    const matrix = screen.getByText("涨停题材 · 电子").closest("details");
    expect(compact).toHaveAttribute("open");
    expect(matrix).not.toHaveAttribute("open");
    expect(matrix).toHaveTextContent("1 行 · 10 列");
    // 只有表、没有条目的分组也要显示
    expect(screen.getByTestId("daily-tables-数据覆盖")).toHaveTextContent("fact_market_daily");
  });

  it("surfaces the legacy compatibility warning", () => {
    const legacyProjection: DailyReportProjection = {
      ...projection,
      report_type: "daily_review",
      source_mode: "legacy_html_projection",
      provenance: {
        ...projection.provenance,
        canonical_path: null,
        warnings: ["当前内容来自历史 HTML 的兼容投影，仅提取已知章节。"],
      },
    };
    render(<DailyReportView projection={legacyProjection} />);

    expect(screen.getByRole("status")).toHaveTextContent("兼容投影");
    expect(screen.getByText("市场温度")).toBeInTheDocument();
  });
});
