/** 客户端区间钟：隐藏只切换区间类型，不改变整段任务的起止时刻。
 * 不记录键盘/鼠标，不猜用户在其他页面干什么，不自报任务完成。
 */
export interface ActivityEvent {
  event_id: string;
  event_type: "time_interval";
  event_at: string;
  task_id: string;
  payload: {
    interval_id: string;
    start: string;
    end: string;
    activity: "user_active" | "pause";
    clock_source: "client";
    visibility: "visible" | "hidden";
    pause_reason: "tab_hidden" | null;
    initiator: "user";
    assistance_source: "workbench";
  };
}

function monotonicWallClock(): () => number {
  const wall = Date.now();
  const tick = performance.now();
  // 用单调时钟量经过时长、墙钟只做起点，避免手动校时让区间重叠/凭空增长。
  return () => wall + Math.max(0, performance.now() - tick);
}

export function startResearchActivity(
  taskId: string,
  emit: (event: ActivityEvent) => void,
  target: Document = document,
  now: () => number = monotonicWallClock(),
  id: () => string = () => crypto.randomUUID(),
): { stop: () => void } {
  let start = Math.floor(now());
  let hidden = target.visibilityState === "hidden";
  let stopped = false;
  const flush = () => {
    const end = Math.max(start, Math.floor(now()));
    if (end > start) {
      const intervalId = id();
      emit({
        event_id: intervalId,
        event_type: "time_interval",
        event_at: new Date(end).toISOString(),
        task_id: taskId,
        payload: {
          interval_id: intervalId,
          start: new Date(start).toISOString(),
          end: new Date(end).toISOString(),
          activity: hidden ? "pause" : "user_active",
          clock_source: "client",
          visibility: hidden ? "hidden" : "visible",
          // 这是未许可扣减的观察原因，不是休息/放弃/任务结束。
          pause_reason: hidden ? "tab_hidden" : null,
          initiator: "user",
          assistance_source: "workbench",
        },
      });
    }
    start = end;
  };
  const onVisibility = () => {
    const next = target.visibilityState === "hidden";
    if (next === hidden) return;
    flush();
    hidden = next;
  };
  target.addEventListener("visibilitychange", onVisibility);
  return {
    stop() {
      if (stopped) return;
      stopped = true;
      target.removeEventListener("visibilitychange", onVisibility);
      flush();
    },
  };
}
