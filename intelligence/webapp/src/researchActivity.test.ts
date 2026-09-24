import { afterEach, describe, expect, it, vi } from "vitest";

import { startResearchActivity, type ActivityEvent } from "./researchActivity";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("应用内活跃时钟", () => {
  it("可见→隐藏→恢复保留整个区间，隐藏不伪装完成或许可扣时", () => {
    let now = 0;
    let visibility: DocumentVisibilityState = "visible";
    vi.spyOn(document, "visibilityState", "get").mockImplementation(() => visibility);
    const events: ActivityEvent[] = [];
    let id = 0;
    const clock = startResearchActivity("task-a", (e) => events.push(e), document, () => now, () => `i-${++id}`);
    now = 10_000;
    visibility = "hidden";
    document.dispatchEvent(new Event("visibilitychange"));
    now = 40_000;
    document.dispatchEvent(new Event("visibilitychange")); // 同状态通知不重复计时
    visibility = "visible";
    document.dispatchEvent(new Event("visibilitychange"));
    now = 60_000;
    clock.stop();
    clock.stop();
    expect(events.map((e) => e.payload.activity)).toEqual(["user_active", "pause", "user_active"]);
    expect(events.map((e) => [Date.parse(e.payload.start), Date.parse(e.payload.end)])).toEqual([
      [0, 10_000], [10_000, 40_000], [40_000, 60_000],
    ]);
    expect(events[1].payload.pause_reason).toBe("tab_hidden");
    expect(events.every((e) => e.task_id === "task-a" && e.event_type === "time_interval")).toBe(true);
    now = 70_000;
    visibility = "hidden";
    document.dispatchEvent(new Event("visibilitychange"));
    expect(events).toHaveLength(3);
  });

  it("初始隐藏不产生虚假活跃；回拨时钟不产生负区间", () => {
    let now = 20_000;
    vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
    const events: ActivityEvent[] = [];
    const clock = startResearchActivity("task-a", (e) => events.push(e), document, () => now, () => "i-1");
    now = 10_000;
    clock.stop();
    expect(events).toEqual([]);
  });
});
