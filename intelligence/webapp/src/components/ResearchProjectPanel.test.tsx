import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { ResearchProject } from "../types";
import { continuationFor } from "../followups";
import { ResearchProjectPanel } from "./ResearchProjectPanel";

const project: ResearchProject = {
  conversation_id: "conv_1",
  user_id: "alice",
  title: "光模块研究",
  subject: "光模块",
  question_type: "theme_track",
  as_of: "2026-09-08",
  updated_at: "2026-09-09T10:00:00+08:00",
  completed_rounds: 2,
  current_judgment: "光模块主线延续，订单口径已补齐。",
  open_questions: ["北美资本开支指引"],
  materials_read: 5,
  artifacts: ["对话回答"],
  triggers: [
    {
      kind: "checkpoint",
      id: "ck-1",
      claim: "若北美云厂商上修资本开支指引，光模块龙头两周内创新高",
      due: "2026-09-08",
      status: "miss",
      checked_at: "2026-09-08T20:00:00+08:00",
      source: "track_next_watch",
      themes: ["光模块"],
      linked: "conversation",
    },
  ],
  next_questions: [
    {
      type: "counter",
      question: "出现哪些反证应下调对光模块的判断？",
      label: "证伪条件",
      full_prompt: "出现哪些反证应下调对光模块的判断？",
      angle: "D",
      kind: "condition_test",
      kind_label: "检验条件",
      inherits: { subject: "光模块", standing_date: "2026-09-08" },
    },
    {
      type: "gap",
      question: "补齐：北美资本开支指引",
      label: "补齐：北美资本开支指引",
      full_prompt: "关于光模块，上一轮「北美资本开支指引」未完成核验：请只针对这一项补齐证据。",
      angle: "A",
      kind: "gap_fill",
      kind_label: "补关键缺口",
    },
  ],
  prior_status: "miss",
  prior_note: "上次「若北美云厂商上修资本开支指引…」到期裁决为落空，本轮先检验条件，再补证据",
  origin_conversation_id: null,
  warnings: [],
  rounds: [
    {
      index: 1,
      run_id: "run_1",
      question: "光模块这个题材近三个月怎么演绎",
      asked_at: "2026-09-08T09:00:00+08:00",
      status: "completed",
      as_of: "2026-09-08",
      question_type: "theme_track",
      subject: "光模块",
      answer_headline: "基准判断：光模块仍是算力链主线。",
      citations: 3,
      artifacts: ["对话回答"],
      open_gaps: ["北美资本开支指引"],
      warnings: [],
      followups: [],
      continuation: null,
    },
    {
      index: 2,
      run_id: "run_2",
      question: "关于光模块，上一轮「订单口径」未完成核验",
      asked_at: "2026-09-09T09:00:00+08:00",
      status: "completed",
      as_of: "2026-09-08",
      question_type: "theme_track",
      subject: "光模块",
      answer_headline: "光模块主线延续，订单口径已补齐。",
      citations: 2,
      artifacts: ["对话回答"],
      open_gaps: [],
      warnings: [],
      followups: [],
      continuation: { run_id: "run_1", kind: "gap_fill", label: "补齐：订单口径" },
    },
  ],
};

describe("ResearchProjectPanel", () => {
  it("shows empty states without a project or without completed rounds", () => {
    const { rerender } = render(<ResearchProjectPanel project={null} />);
    expect(screen.getByText(/选择一个会话后显示研究项目状态/)).toBeInTheDocument();
    rerender(
      <ResearchProjectPanel
        project={{ ...project, rounds: [{ ...project.rounds[0], status: "running" }] }}
      />,
    );
    expect(screen.getByText(/还没有完成的研究轮次/)).toBeInTheDocument();
  });

  it("renders judgment, open questions, triggers, prior note and rounds from the projection", () => {
    render(<ResearchProjectPanel project={project} />);
    expect(screen.getByRole("region", { name: "研究项目状态" })).toBeInTheDocument();
    expect(screen.getByText("光模块")).toBeInTheDocument();
    expect(screen.getByText(/已研究 2 轮 · 上轮数据截止 2026-09-08/)).toBeInTheDocument();
    expect(screen.getByText("光模块主线延续，订单口径已补齐。")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "未解问题" })).toHaveTextContent("北美资本开支指引");
    expect(screen.getByRole("list", { name: "后续触发点" })).toHaveTextContent("落空");
    expect(screen.getByText(/上次哪个判断|到期裁决为落空/)).toBeInTheDocument();
    const rounds = screen.getByRole("list", { name: "研究轮次" });
    expect(rounds).toHaveTextContent("#1");
    expect(rounds).toHaveTextContent("延续自「补齐：订单口径」");
  });

  it("orders next questions as given and sends continuation of the last completed round on click", async () => {
    const onFollowup = vi.fn();
    const user = userEvent.setup();
    render(<ResearchProjectPanel project={project} onFollowup={onFollowup} />);
    const buttons = screen.getAllByRole("button");
    // 后端已按裁决把「检验条件」排在前面，面板不重排。
    expect(buttons[0]).toHaveTextContent("证伪条件");
    expect(buttons[0]).toHaveAttribute("data-kind", "condition_test");
    expect(buttons[1]).toHaveAttribute("data-kind", "gap_fill");
    // 种类标签是视觉提示（aria-hidden），可访问名仍是卡片标签本身。
    expect(screen.getByRole("button", { name: "证伪条件" })).toBeInTheDocument();

    await user.click(buttons[1]);
    expect(onFollowup).toHaveBeenCalledWith(
      "关于光模块，上一轮「北美资本开支指引」未完成核验：请只针对这一项补齐证据。",
      {
        run_id: "run_2",
        full_prompt:
          "关于光模块，上一轮「北美资本开支指引」未完成核验：请只针对这一项补齐证据。",
        kind: "gap_fill",
        label: "补齐：北美资本开支指引",
      },
    );
  });
});

describe("continuationFor", () => {
  it("returns undefined without a run id and never fabricates coordinates", () => {
    expect(
      continuationFor({ type: "gap", question: "q", kind: "gap_fill" }, null),
    ).toBeUndefined();
    expect(continuationFor({ type: "gap", question: "q" }, "run_1")).toEqual({
      run_id: "run_1",
      full_prompt: "q",
    });
  });

  it("carries kind, source, label, prompt and non-empty inherits", () => {
    expect(
      continuationFor(
        {
          type: "continue",
          question: "q",
          full_prompt: "按我刚才的条件再对一次",
          kind: "continue",
          source: "same_bind:abc",
          label: "同一条件再对",
          inherits: { subject: "光模块", standing_date: "2026-09-08" },
        },
        "run_9",
      ),
    ).toEqual({
      run_id: "run_9",
      full_prompt: "按我刚才的条件再对一次",
      kind: "continue",
      source: "same_bind:abc",
      label: "同一条件再对",
      inherits: { subject: "光模块", standing_date: "2026-09-08" },
    });
  });
});
