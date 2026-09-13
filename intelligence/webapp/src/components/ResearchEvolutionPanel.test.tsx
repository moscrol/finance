import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ResearchEvolutionView } from "../types";
import { ResearchEvolutionPanel } from "./ResearchEvolutionPanel";

function makeView(overrides: Partial<ResearchEvolutionView> = {}): ResearchEvolutionView {
  return {
    schema_version: "research-evolution-view/v1",
    owner_user_id: "default",
    conversation_id: "conv_1",
    view_version: "test",
    view_digest: "d0",
    generated_at: "2026-09-14T08:00:00+00:00",
    maintenance: {
      id: "jm-1",
      as_of: "2026-09-14",
      knowledge_cutoff: "2026-09-14",
      pit_grade: "strict",
      hindsight: false,
      gaps: [],
      counts: { items_open: 1 },
      items: [
        {
          id: "jmi-1",
          item_version: "v1",
          object_ref: {
            kind: "judgment",
            id: "j1",
            namespace: "judgments",
            version_or_hash: "content_sha256:abc",
            ref: "judgments.jsonl:j1",
            scope: {},
          },
          before: [{ ref: "fact_sector_daily:2026-09-01", source_hash: "h1", recorded_at: null, derivation: "deterministic" }],
          current: [{ ref: "fact_sector_daily:2026-09-01", source_hash: "h2", recorded_at: null, derivation: "deterministic" }],
          change_type: "content_changed",
          reason_code: "hash_changed",
          epistemic_state: "requires_review",
          condition_result: null,
          condition_role: null,
          as_of: "2026-09-14",
          knowledge_cutoff: "2026-09-14",
          pit_grade: "strict",
          gaps: [],
          action: "review_evidence",
          status: "open",
          management_revision: 0,
          management: {},
        },
      ],
    },
    priority: null,
    diagnostics: null,
    receipt_refs: { validation: [], product_value: [] },
    module_status: {
      maintenance: { status: "ok", reason: null, synthetic: false },
      priority: { status: "unknown", reason: "no_sources", synthetic: false },
      diagnostics: { status: "unknown", reason: "policy_not_registered", synthetic: false },
      validation_receipts: { status: "unknown", reason: "no_study_frozen", synthetic: false },
      product_value_receipts: { status: "unknown", reason: "no_measurement_yet", synthetic: false },
    },
    gaps: [],
    inputs: {
      as_of: "2026-09-14",
      knowledge_cutoff: "2026-09-14",
      budget_minutes: null,
      bindings: 1,
      trackable_objects: [],
    },
    ...overrides,
  };
}

describe("ResearchEvolutionPanel", () => {
  it("哈希变化显示为需复核，不出现已证伪", () => {
    render(<ResearchEvolutionPanel view={makeView()} />);
    const list = screen.getByLabelText("待复核");
    expect(within(list).getByText("依据变了")).toBeInTheDocument();
    expect(within(list).getByText("需复核")).toBeInTheDocument();
    expect(within(list).getByText("同一份来源换了新版本")).toBeInTheDocument();
    expect(screen.queryByText(/已证伪/)).not.toBeInTheDocument();
    expect(screen.queryByText(/refuted/i)).not.toBeInTheDocument();
  });

  it("哈希与内部版本只在详情里出现，不上主屏", () => {
    render(<ResearchEvolutionPanel view={makeView()} />);
    expect(screen.queryByText(/h2/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "详情" }));
    const detail = screen.getByLabelText("内部版本详情");
    expect(within(detail).getByText(/fact_sector_daily:2026-09-01@h2/)).toBeInTheDocument();
    expect(within(detail).getByText(/v1 · 管理修订 0/)).toBeInTheDocument();
  });

  it("动作带上当前项版本与管理修订，幂等键随之变化", () => {
    const onAction = vi.fn();
    render(<ResearchEvolutionPanel view={makeView()} onAction={onAction} />);
    fireEvent.click(screen.getByRole("button", { name: "开始复核" }));
    expect(onAction).toHaveBeenCalledWith(
      expect.objectContaining({
        action: "claim",
        item_id: "jmi-1",
        expected_item_version: "v1",
        expected_management_revision: 0,
        idempotency_key: "claim:jmi-1:v1:0",
      }),
    );
  });

  it("条件项没有可核对的来源版本时，「核对后判断未变」不可点", () => {
    const view = makeView();
    view.maintenance!.items[0] = {
      ...view.maintenance!.items[0],
      change_type: "condition_evaluated",
      reason_code: "condition_true",
      current: [],
      before: [],
    };
    render(<ResearchEvolutionPanel view={view} />);
    expect(screen.getByRole("button", { name: "核对后判断未变" })).toBeDisabled();
  });

  it("缺输入显示为「还判不了」，不显示成 0 条或空白", () => {
    render(<ResearchEvolutionPanel view={makeView()} />);
    const status = screen.getByLabelText("模块状态");
    expect(within(status).getByText(/下一步研究：缺输入，还判不了/)).toBeInTheDocument();
    expect(within(status).getByText(/我的复盘：缺输入，还判不了/)).toBeInTheDocument();
    expect(screen.getByText(/暂无法诊断：还没有登记生产诊断策略/)).toBeInTheDocument();
  });

  it("还没有绑定依据时，说清楚是「尚不能比较变化」而不是「没有问题」", () => {
    const view = makeView({
      maintenance: null,
      module_status: {
        ...makeView().module_status,
        maintenance: { status: "unknown", reason: "no_bindings", synthetic: false },
      },
    });
    render(<ResearchEvolutionPanel view={view} />);
    expect(screen.getByText(/原记录没有完整依据，尚不能比较变化/)).toBeInTheDocument();
  });

  it("未入选的关键项要点名，不能只显示入选的三条", () => {
    const view = makeView({
      priority: {
        report_id: "rp_1",
        policy_version: "research-priority-policy/v1",
        summary: {},
        selected: [
          {
            task_id: "rt_1",
            标题: "复核放弃条件",
            动作类型: "复核放弃/降级条件",
            组: "第 1 组｜明确登记的放弃或降级条件已触发",
            耗时: "600 秒（estimated）",
            可执行状态: "今天可做",
            为什么在前: ["条件已触发"],
            还缺什么: [],
            click_payload: { task_id: "rt_1" },
          },
        ],
        deferred: [],
        blocked: [],
        critical_not_selected_ids: ["rt_9", "rt_10"],
        gaps: [],
        limitations: ["合成输入，不代表真实优先级"],
        synthetic: true,
        hindsight: false,
      },
      module_status: {
        ...makeView().module_status,
        priority: { status: "ok", reason: null, synthetic: false },
      },
    });
    render(<ResearchEvolutionPanel view={view} />);
    expect(screen.getByText(/未入选的关键项 2 条/)).toBeInTheDocument();
    expect(screen.getByText(/合成输入，不代表真实优先级/)).toBeInTheDocument();
  });

  it("面板上不出现概率承诺或「方法已验证」徽章", () => {
    const { container } = render(<ResearchEvolutionPanel view={makeView()} />);
    const text = container.textContent ?? "";
    for (const banned of ["方法已验证", "Brier", "胜率", "概率优势"]) {
      expect(text).not.toContain(banned);
    }
  });
});
