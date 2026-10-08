import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { ReviewHistory } from "../../river/historyTypes";
import { buildReviewEvidencePacket } from "../../river/reviewEvidence";
import { ReviewReadingGuide } from "./ReviewReadingGuide";

const data: ReviewHistory = {
  schema_version: 1, knowledge_mode: "archived_report_not_as_known", start: "2026-09-23", end: "2026-09-24", requested_end: "2026-09-24", requested_days: 5, calendar_complete: true,
  industry: "电子", industries: ["电子"], metrics: [{ key: "total_amount", label: "市场成交额", unit: "亿元", source_field: "facts.total_amount" }], coverage: { available: 1, total: 2 }, limits: { max_rows_per_day_section: 80 }, notes: ["合成证据"],
  evidence_contract: { version: "review-evidence/v1", scope: "连续视图已接入数据", groups: ["市场环境", "行业位置", "子板块表现", "个股发动机"].map((label, i) => ({ id: String(i), label, question: "待核对的问题", fields: ["metrics.total_amount"], boundary: "合成测试边界" })), join_keys: ["points[].date"], citation_rule: "引用字段与哈希", missing_semantics: { not_in_list: "未列入不等于零" }, provenance_policy: { formula_version: null, point_in_time_guaranteed: false }, agent_rules: ["先核对覆盖率"] },
  points: [{ date: "2026-09-24", status: "available", reason: null, provenance: { source_path: "synthetic.json", generated_at: "2026-09-29", sha256: "synthetic-hash", note: "测试" }, metrics: { total_amount: 123.4 }, deltas: {}, comparison_date: null, top_industries: ["电子"], industry_rank: 1, industry_status: "ranked", matrices: { double_red: { status: "available", rows: [{ name: "芯片", value: "🔥1.0%/15.0/800" }], truncated: false }, stock_highs: { status: "not_reported", rows: [], truncated: false }, limit_up: { status: "available", rows: [{ name: "芯片", value: 0 }], truncated: false } }, engines: { columns: ["股票", "代码"], rows: [["甲", "000001"], ["乙", "000002"], ["丙", "000003"], ["丁", "000004"]], total_rows: 100, truncated: true }, warnings: ["截断"], detail_url: "/api/river/daily-review?as_of=2026-09-24" }],
};
afterEach(() => { sessionStorage.clear(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
it("exports all data kinds and original rows, separately from user interpretations", () => {
  const before = JSON.stringify(data);
  const draft = { question: "强化是否成立？", method: "先看市场再看行业", cautions: "不把缺口当退潮" };
  const packet = buildReviewEvidencePacket(data, "2026-09-24", draft);
  expect(packet.evidence).toBe(data);
  expect(packet.evidence.points[0].engines?.rows).toHaveLength(4);
  expect(packet.evidence.points[0].engines?.truncated).toBe(true);
  expect(Object.keys(packet.evidence.points[0].matrices)).toEqual(["double_red", "stock_highs", "limit_up"]);
  expect(packet.user_instructions.method).toBe(draft.method);
  expect(packet.user_instructions.role).toBe("user_authored_research_guidance_not_market_facts");
  expect(packet.context.selected_date_in_window).toBe(true);
  expect(packet.response_contract.pointer_base).toContain("/evidence/points/");
  expect(JSON.stringify(data)).toBe(before);
});
it("keeps out-of-window selection explicit and rejects incompatible contracts", () => {
  const draft = { question: "", method: "", cautions: "" };
  expect(buildReviewEvidencePacket(data, "2020-01-01", draft).context.selected_date_in_window).toBe(false);
  expect(() => buildReviewEvidencePacket({ ...data, evidence_contract: undefined }, null, draft)).toThrow("数据种类合同");
});
it("renders the shared vocabulary and retains only method drafts across remounts", () => {
  const { unmount } = render(<ReviewReadingGuide data={data} selectedDate="2026-09-24"/>);
  for (const label of ["市场环境", "行业位置", "子板块表现", "个股发动机"]) expect(screen.getByRole("heading", { name: label })).toBeInTheDocument();
  fireEvent.click(screen.getByText("告诉 Agent：这些数据应该怎样联立解读"));
  fireEvent.change(screen.getByLabelText("先看什么，再结合什么"), { target: { value: "先查缺口，再比较量能与上涨广度" } });
  unmount();
  render(<ReviewReadingGuide data={{ ...data, industry: "机械设备" }} selectedDate="2026-09-23"/>);
  fireEvent.click(screen.getByText("告诉 Agent：这些数据应该怎样联立解读"));
  expect(screen.getByLabelText("先看什么，再结合什么")).toHaveValue("先查缺口，再比较量能与上涨广度");
  expect(screen.getByText(/本次交接：.*机械设备/)).toHaveTextContent("2026-09-23");
  fireEvent.click(screen.getByRole("button", { name: "清空解读说明" }));
  expect(screen.getByLabelText("先看什么，再结合什么")).toHaveValue("");
});
it("downloads the complete evidence and authored instructions without any network/model call", async () => {
  const create = vi.fn<(blob: Blob) => string>(() => "blob:test");
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: create, revokeObjectURL: vi.fn() }));
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
  render(<ReviewReadingGuide data={data} selectedDate="2026-09-24"/>);
  fireEvent.click(screen.getByText("告诉 Agent：这些数据应该怎样联立解读"));
  fireEvent.change(screen.getByLabelText("这次想判断什么"), { target: { value: "量能与榜内顺位是否支持强化？" } });
  fireEvent.click(screen.getByRole("button", { name: "导出 Agent 联立证据包" }));
  expect(click).toHaveBeenCalledTimes(1);
  const text = await new Promise<string>(resolve => { const r = new FileReader(); r.onload = () => resolve(String(r.result)); r.readAsText(create.mock.calls[0][0]); });
  const packet = JSON.parse(text);
  expect(packet.evidence).toEqual(data);
  expect(packet.user_instructions.question).toBe("量能与榜内顺位是否支持强化？");
  expect(fetch).not.toHaveBeenCalled();
});
it("fails visibly with an old backend and handles denied browser storage", () => {
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("denied"); });
  const { rerender } = render(<ReviewReadingGuide data={data} selectedDate={null}/>);
  fireEvent.click(screen.getByText("告诉 Agent：这些数据应该怎样联立解读"));
  expect(screen.getByRole("status")).toHaveTextContent("未允许保存草稿");
  rerender(<ReviewReadingGuide data={{ ...data, evidence_contract: undefined }} selectedDate={null}/>);
  expect(screen.getByText(/Agent 交接暂不可用/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "导出 Agent 联立证据包" })).not.toBeInTheDocument();
});
