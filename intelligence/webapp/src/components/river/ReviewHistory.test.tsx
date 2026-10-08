import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ReviewHistory } from "./ReviewHistory";
import type { ReviewHistory as History } from "../../river/historyTypes";

function fixture(industry = "电子"): History {
  return { schema_version: 1, knowledge_mode: "archived_report_not_as_known", requested_end: "2026-09-24", start: "2026-09-23", end: "2026-09-24", requested_days: 20, calendar_complete: true, industry, industries: ["电子", "机械设备"], coverage: { available: 1, total: 2 }, limits: {}, notes: ["归档不是当时可知"], metrics: [{ key: "total_amount", label: "市场成交额", unit: "亿元", source_field: "facts.total_amount" }], points: ["2026-09-23", "2026-09-24"].map((date, i) => ({ date, status: i ? "available" : "missing", reason: null, provenance: i ? { source_path: "archive.json", generated_at: "2026-09-29", sha256: "test-hash", note: "archive" } : null, metrics: { total_amount: i ? 120 : null }, deltas: {}, comparison_date: null, top_industries: i ? ["电子"] : [], industry_rank: i ? 1 : null, industry_status: i ? "ranked" : "unknown", engines: null, matrices: {}, warnings: [], detail_url: `/api/river/daily-review?as_of=${date}` })) };
}
const response = (body: unknown) => ({ ok: true, json: async () => body }) as Response;
const props = { initialEnd: "2026-09-24", selectedDate: "2026-09-24", onSelect: vi.fn(), onOpenReport: vi.fn() };
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });
it("keeps the window pinned when selecting a missing day and opens that exact report", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => response(fixture())));
  render(<ReviewHistory {...props}/>);
  fireEvent.click(await screen.findByRole("button", { name: "连续复盘选日 2026-09-23" }));
  expect(props.onSelect).toHaveBeenCalledWith("2026-09-23");
  expect(screen.getByLabelText("连续复盘截止日")).toHaveValue("2026-09-24");
  expect(screen.getByText(/当日缺少结构化归档/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /打开当日完整复盘/ }));
  expect(props.onOpenReport).toHaveBeenCalledWith("2026-09-23");
  expect(fetch).toHaveBeenCalledTimes(1);
});
it("rejects mismatched responses and can retry", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(response({ ...fixture(), requested_end: "2026-09-22" })).mockResolvedValue(response(fixture())));
  render(<ReviewHistory {...props}/>);
  expect(await screen.findByRole("alert")).toHaveTextContent("未展示错位数据");
  fireEvent.click(screen.getByRole("button", { name: "重试连续复盘" }));
  expect(await screen.findByText("test-hash")).toBeInTheDocument();
});
it("ignores a slow obsolete industry response", async () => {
  let resolveOld!: (r: Response) => void;
  vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(response(fixture())).mockImplementationOnce(() => new Promise(r => { resolveOld = r; })).mockResolvedValue(response(fixture())));
  render(<ReviewHistory {...props}/>);
  await screen.findByText("test-hash");
  fireEvent.change(screen.getByLabelText("连续复盘行业"), { target: { value: "机械设备" } });
  // During loading, the auto choice restores the pinned initial industry.
  fireEvent.change(screen.getByLabelText("连续复盘行业"), { target: { value: "" } });
  await screen.findByText("test-hash");
  await act(async () => { resolveOld(response(fixture("机械设备"))); });
  expect(screen.getByLabelText("连续复盘行业")).toHaveValue("电子");
});
it("exports the same structured response with its gaps and provenance", async () => {
  const create = vi.fn<(blob: Blob) => string>(() => "blob:evidence");
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: create, revokeObjectURL: vi.fn() }));
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  vi.stubGlobal("fetch", vi.fn(async () => response(fixture())));
  render(<ReviewHistory {...props}/>);
  await screen.findByText("test-hash");
  fireEvent.click(screen.getByRole("button", { name: /导出本窗证据/ }));
  await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
  const text = await new Promise<string>(resolve => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.readAsText(create.mock.calls[0][0] as Blob); });
  expect(JSON.parse(text)).toEqual({ ...fixture(), selected_date: "2026-09-24" });
});
it("marks why a matrix or engine table is absent instead of a bare dash", async () => {
  const data = fixture("计算机");
  const [missing, available] = data.points;
  data.points = [
    { ...missing, date: "2026-09-22" },
    { ...available, date: "2026-09-23", engines_status: "not_in_scope", industry_status: "not_in_list", industry_rank: null,
      matrices: { double_red: { status: "not_in_scope", rows: [], truncated: false } } },
    { ...available, date: "2026-09-24", engines_status: "empty",
      matrices: { double_red: { status: "available", rows: [{ name: "芯片", value: "1.0%" }], truncated: false } } },
  ];
  data.coverage = { available: 2, total: 3 };
  vi.stubGlobal("fetch", vi.fn(async () => response({ ...data, start: "2026-09-22" })));
  render(<ReviewHistory {...props} initialEnd="2026-09-24" selectedDate="2026-09-24"/>);
  const row = (await screen.findByText("芯片", { selector: "th" })).closest("tr")!;
  expect([...row.querySelectorAll("td")].map(td => td.textContent)).toEqual(["缺档", "未覆盖", "1.0%"]);
  expect(screen.getByText("列入但暂无")).toBeInTheDocument();
  expect(screen.getAllByText("未覆盖")).toHaveLength(2); // matrix cell + engine row
  expect(screen.getByText(/列入前三但归档写明暂无可排序个股/)).toBeVisible();
});
