import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { getLimitUpCalendar } from "../../river/api";
import { ObservationWorkbench } from "./ObservationWorkbench";
import { observationPrompt } from "../../river/observation";
import type { ObservationRecord } from "../../river/observation";
vi.mock("../../river/api", () => ({ getLimitUpCalendar: vi.fn() }));
const props = { date: "2026-09-24", dates: ["2026-09-23", "2026-09-24"], onDate: vi.fn(), onEvidence: vi.fn() };
const store = "foresight.observation-workbench.v1";
const snapshot = (day = "2026-09-24", stage = "下跌阶段") => ({ trade_date: day, status: "available", report: { facts: { market_stage: stage, total_amount: 16526.49, volume_ratio: 87.5, top3_industry_ratio: 42.7, advancers: 1118, advancers_ma5: 2829 } }, provenance: { sha256: "original-sha", generated_at: "2026-09-24T19:00:00+08:00", source_path: "2026-09-24-daily-review.json" } });
const response = (data: unknown) => ({ ok: true, json: async () => data }) as Response;
beforeEach(() => {
  const values = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, String(value)); },
    removeItem: (key: string) => { values.delete(key); },
    clear: () => values.clear(),
  });
  vi.stubGlobal("navigator", { locks: { request: vi.fn(async (_name: string, write: () => void) => write()) } });
  vi.mocked(getLimitUpCalendar).mockReset().mockResolvedValue({ start: "2026-09-24", end: "2026-09-24", days: [], stats: { trading_days: 0, avg_total: 0, avg_max_boards: 0, max_boards: 0, max_boards_date: null } });
  vi.stubGlobal("fetch", vi.fn(async () => response(snapshot())));
});
afterEach(() => vi.unstubAllGlobals());
function fill() {
  fireEvent.change(screen.getByLabelText("待验证假设"), { target: { value: "回流是否扩散" } });
  fireEvent.change(screen.getByLabelText("确认条件"), { target: { value: "明确观察后续续量和联动" } });
  fireEvent.change(screen.getByLabelText("推翻条件"), { target: { value: "续量失败则降级" } });
  fireEvent.change(screen.getByLabelText("拟复查日期"), { target: { value: "2026-09-28" } });
  screen.getAllByRole("combobox", { name: /人工判定/ }).forEach(select => fireEvent.change(select, { target: { value: "missing" } }));
}
it("shows facts without automatically checking any framework condition", async () => {
  render(<ObservationWorkbench {...props}/>);
  expect(await screen.findByText("87.5%")).toBeInTheDocument();
  screen.getAllByRole("combobox", { name: /人工判定/ }).forEach(select => expect(select).toHaveValue("pending"));
  expect(screen.getByText(/没有30／60分钟结构读数/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "风远 · 双锚与兑现" }));
  expect(screen.getByText(/L2净额不等于持有人身份/)).toBeInTheDocument();
  expect(screen.getByText(/全市场最高板不自动等于当前板块/)).toBeInTheDocument();
});
it("requires falsification and a future review date, while allowing explicit missing evidence", async () => {
  render(<ObservationWorkbench {...props}/>);
  await screen.findByText("87.5%");
  fireEvent.click(screen.getByRole("button", { name: "冻结这次观察" }));
  expect(screen.getByText(/请先写清观察对象与待验证假设/)).toBeInTheDocument();
  fill();
  fireEvent.change(screen.getByLabelText("拟复查日期"), { target: { value: "2026-09-23" } });
  fireEvent.click(screen.getByRole("button", { name: "冻结这次观察" }));
  expect(screen.getByText(/请选择晚于观察数据日/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("拟复查日期"), { target: { value: "2026-09-28" } });
  fireEvent.click(screen.getByRole("button", { name: "冻结这次观察" }));
  const record = JSON.parse(window.localStorage.getItem(store)!).records[0] as ObservationRecord;
  expect(record.strict_point_in_time).toBe(false);
  expect(record.evidence.archive_sha256).toBe("original-sha");
  expect(record.form.assessments.market.verdict).toBe("missing");
});
it("freezes original conditions and appends review without changing them or sending a model call", async () => {
  const { container } = render(<ObservationWorkbench {...props}/>);
  await screen.findByText("87.5%"); fill();
  fireEvent.click(screen.getByRole("button", { name: "冻结这次观察" }));
  fireEvent.change(screen.getByLabelText("推翻条件"), { target: { value: "事后想改门槛" } });
  const recordCard = within(container.querySelector(".obs-record") as HTMLElement);
  expect(recordCard.getByText(/续量失败则降级/)).toBeInTheDocument();
  expect(recordCard.queryByText(/事后想改门槛/)).not.toBeInTheDocument();
  fireEvent.change(recordCard.getByRole("textbox", { name: /复查证据/ }), { target: { value: "09-28行情尚缺，不能判断结果" } });
  fireEvent.click(recordCard.getByRole("button", { name: "追加：信息不足" }));
  const record = JSON.parse(window.localStorage.getItem(store)!).records[0] as ObservationRecord;
  expect(record.reviews).toHaveLength(1);
  expect(record.form.invalidation).toBe("续量失败则降级");
  fireEvent.click(recordCard.getByRole("button", { name: "生成Agent核验问题" }));
  expect(screen.getByRole("textbox", { name: "Agent核验问题" })).toHaveValue(observationPrompt(record));
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(observationPrompt(record)).toContain("人工判断不是事实证据");
});
it("keeps a missing archive explicit instead of falling back to another date", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => response({ trade_date: "2026-09-23", status: "missing", report: null })));
  render(<ObservationWorkbench {...props} date="2026-09-23"/>);
  expect(await screen.findByText(/这一天没有结构化日报/)).toBeInTheDocument();
  expect(screen.queryByText("87.5%")).not.toBeInTheDocument();
  expect(fetch).toHaveBeenCalledWith("/api/river/daily-review?as_of=2026-09-23", expect.anything());
});
it("does not let late prior-date evidence populate the newly selected day", async () => {
  let release!: (response: Response) => void;
  vi.stubGlobal("fetch", vi.fn().mockImplementationOnce(() => new Promise<Response>(resolve => { release = resolve; })).mockResolvedValue(response(snapshot("2026-09-23", "后选日期证据"))));
  const { rerender } = render(<ObservationWorkbench {...props}/>);
  rerender(<ObservationWorkbench {...props} date="2026-09-23"/>);
  await screen.findByText("后选日期证据");
  await act(async () => { release(response(snapshot())); });
  expect(screen.queryByText("下跌阶段")).not.toBeInTheDocument();
  expect(screen.getByText("后选日期证据")).toBeInTheDocument();
});
it("restores browser drafts on remount and separates different dates", async () => {
  const { unmount } = render(<ObservationWorkbench {...props}/>);
  await screen.findByText("87.5%");
  fireEvent.change(screen.getByLabelText("待验证假设"), { target: { value: "尚未冻结的观察" } });
  unmount();
  const { rerender } = render(<ObservationWorkbench {...props}/>);
  expect(screen.getByLabelText("待验证假设")).toHaveValue("尚未冻结的观察");
  rerender(<ObservationWorkbench {...props} date="2026-09-23"/>);
  expect(screen.getByLabelText("待验证假设")).toHaveValue("");
  await screen.findByText(/日报读取失败/);
});

it("reports unavailable browser persistence without claiming the record reached the server", async () => {
  render(<ObservationWorkbench {...props}/>);
  await screen.findByText("87.5%");
  vi.spyOn(window.localStorage, "setItem").mockImplementation(() => { throw new Error("quota"); });
  fill();
  fireEvent.click(screen.getByRole("button", { name: "冻结这次观察" }));
  expect(screen.getByRole("alert")).toHaveTextContent("浏览器存储不可用");
  expect(screen.queryByText(/原始条件已冻结到本浏览器/)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "导出记录" })).toBeInTheDocument();
  expect(localStorage.getItem(store)).toBeNull();
});

it("keeps a failed review append in memory without changing the persisted frozen record", async () => {
  render(<ObservationWorkbench {...props}/>);
  await screen.findByText("87.5%"); fill();
  fireEvent.click(screen.getByRole("button", { name: "冻结这次观察" }));
  await screen.findByText(/原始条件已冻结到本浏览器/);
  const before = localStorage.getItem(store)!;
  const original = JSON.parse(before).records[0] as ObservationRecord;
  vi.spyOn(window.localStorage, "setItem").mockImplementation(() => { throw new Error("quota"); });
  fireEvent.change(screen.getByLabelText(`复查证据 ${original.id}`), { target: { value: "待导出的复查证据" } });
  fireEvent.click(screen.getByRole("button", { name: "追加：信息不足" }));
  await screen.findByText(/复查仅在本页内存追加/);
  expect(localStorage.getItem(store)).toBe(before);
  expect(screen.getByText("待导出的复查证据", { selector: "p" })).toBeInTheDocument();
  expect(screen.queryByText(/已追加人工复查/)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "导出记录" })).toBeInTheDocument();
});

it.each(["freeze", "review"])("preserves another tab's completed records and reviews when this stale tab saves %s", async action => {
  render(<ObservationWorkbench {...props}/>);
  await screen.findByText("87.5%"); fill();
  fireEvent.click(screen.getByRole("button", { name: "冻结这次观察" }));
  const stored = JSON.parse(localStorage.getItem(store)!);
  const original = structuredClone(stored.records[0]) as ObservationRecord;
  const fromOtherTab = { ...structuredClone(original), id: "other-tab-frozen" };
  const otherReview = { recorded_at: "2026-10-03T00:00:00Z", outcome: "insufficient", note: "另一页已完成的复查" };
  localStorage.setItem(store, JSON.stringify({ ...stored, records: [fromOtherTab, { ...original, reviews: [otherReview] }] }));
  // The storage event need not have reached this tab before the next user action.
  if (action === "freeze") fireEvent.click(screen.getByRole("button", { name: "冻结这次观察" }));
  else {
    fireEvent.change(screen.getByLabelText(`复查证据 ${original.id}`), { target: { value: "本页追加复查" } });
    fireEvent.click(screen.getByRole("button", { name: "追加：信息不足" }));
  }
  const records = JSON.parse(localStorage.getItem(store)!).records as ObservationRecord[];
  expect(records.map(record => record.id)).toContain("other-tab-frozen");
  const retained = records.find(record => record.id === original.id)!;
  expect(retained.form).toEqual(original.form);
  expect(retained.evidence).toEqual(original.evidence);
  expect(retained.reviews).toEqual(action === "freeze" ? [otherReview] : [otherReview, expect.objectContaining({ note: "本页追加复查" })]);
});

it.each(["unavailable", "rejected"])("keeps the observation exportable without persisting when the cross-tab lock is %s", async condition => {
  vi.stubGlobal("navigator", condition === "unavailable" ? {} : { locks: { request: vi.fn().mockRejectedValue(new Error("lock denied")) } });
  render(<ObservationWorkbench {...props}/>);
  await screen.findByText("87.5%"); fill();
  fireEvent.click(screen.getByRole("button", { name: "冻结这次观察" }));
  expect(await screen.findByText(/原始条件仅在本页内存冻结/)).toBeInTheDocument();
  expect(localStorage.getItem(store)).toBeNull();
  expect(screen.getByRole("button", { name: "导出记录" })).toBeInTheDocument();
  expect(screen.queryByText(/原始条件已冻结到本浏览器/)).not.toBeInTheDocument();
});

it("does not report a frozen record as saved while its cross-tab lock is pending", async () => {
  render(<ObservationWorkbench {...props}/>);
  await screen.findByText("87.5%"); fill();
  let release!: () => void;
  vi.stubGlobal("navigator", { locks: { request: vi.fn((_name: string, write: () => void) => new Promise<void>(resolve => {
    release = () => { write(); resolve(); };
  })) } });
  fireEvent.click(screen.getByRole("button", { name: "冻结这次观察" }));
  expect(JSON.parse(localStorage.getItem(store)!).records).toEqual([]);
  expect(screen.queryByRole("button", { name: "导出记录" })).not.toBeInTheDocument();
  expect(screen.queryByText(/原始条件已冻结到本浏览器/)).not.toBeInTheDocument();
  await act(async () => release());
  expect(await screen.findByText(/原始条件已冻结到本浏览器/)).toBeInTheDocument();
  expect(JSON.parse(localStorage.getItem(store)!).records).toHaveLength(1);
});
