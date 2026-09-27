import { useEffect, useRef, useState } from "react";

import { postResearchEvolutionEvents } from "../api";
import { startResearchActivity } from "../researchActivity";

const TERMS = "仅记录本次会话的应用内可见区间和隐藏区间，不记录输入内容。可见不等于一直在操作；隐藏不扣端到端耗时，不推断外部查阅时间。关闭页面或切会话会停止，异常退出可能缺测。自用记录不计入配对任务效果。计时同意独立于研究测量同意。";

/** 默认关闭；只记会话级观测，不把优先队列的 task_id 冒充冻结试点分配。
 * 生命周期绑定 owner/会话，而非检查器当前 tab；pagehide（含 bfcache）停止且不自动恢复。
 */
export function ResearchActivityControl({
  conversationId,
  user,
}: {
  conversationId: string;
  user: string;
}) {
  const [enabled, setEnabled] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const actions = useRef({ start: async () => {}, stop: async () => {} });

  useEffect(() => {
    let disposed = false;
    let starting = false;
    let generation = 0;
    let consentHash = "";
    let clock: ReturnType<typeof startResearchActivity> | null = null;
    let closingBatch: Array<Record<string, unknown>> | null = null;
    let lastEnd = 0;
    const pending = new Set<Promise<void>>();
    const showError = (caught: unknown) => {
      if (!disposed) setError(caught instanceof Error ? caught.message : "记录未保存");
    };
    const consent = (action: "grant" | "withdraw", hash: string) => {
      // 结束区间在撤回生效前；05 按 event_at 判断同意范围，同毫秒不能误删最后一段。
      const at = new Date(Math.max(Date.now(), action === "withdraw" ? lastEnd + 1 : 0)).toISOString();
      return {
        event_id: crypto.randomUUID(), event_type: "consent_changed", event_at: at,
        participant_id: user,
        payload: {
          consent_version: "workbench-activity-v2", scopes: ["activity-timer"],
          effective_at: at, action, terms_hash: hash,
          initiator: "user", assistance_source: "workbench",
        },
      };
    };
    const send = (events: Array<Record<string, unknown>>) => {
      // 立即发 keepalive 请求；不能把卸载时的末段放在慢请求后的 Promise 队列里。
      // 无跨会话持久队列/自动重试；失败留缺口，不悄悄当作已保存。
      const request = postResearchEvolutionEvents(conversationId, events, user);
      pending.add(request);
      void request.catch(showError).finally(() => pending.delete(request));
      return request;
    };
    const stop = async () => {
      generation += 1; // 未收到同意回包时切走，也不允许异步回包重启旧钟。
      if (!disposed) { setBusy(true); setEnabled(false); }
      const batch: Array<Record<string, unknown>> = [];
      closingBatch = batch;
      clock?.stop();
      clock = null;
      closingBatch = null;
      if (consentHash) {
        batch.push(consent("withdraw", consentHash));
        consentHash = "";
      }
      if (batch.length) void send(batch).catch(() => {});
      await Promise.allSettled([...pending]);
      if (!disposed) setBusy(starting);
    };
    const start = async () => {
      if (starting || clock || pending.size) return;
      starting = true;
      const current = generation;
      setBusy(true);
      setError("");
      let hash = "";
      let sent = false;
      try {
        const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(TERMS));
        if (disposed || current !== generation) return;
        hash = `sha256:${Array.from(new Uint8Array(bytes), (b) => b.toString(16).padStart(2, "0")).join("")}`;
        sent = true;
        await send([consent("grant", hash)]);
        if (disposed || current !== generation) {
          await send([consent("withdraw", hash)]);
          return;
        }
        consentHash = hash;
        clock = startResearchActivity("", (event) => {
          lastEnd = Date.parse(event.payload.end);
          const row = { ...event, task_id: null, participant_id: user };
          if (closingBatch) closingBatch.push(row);
          else void send([row]).catch(() => {});
        });
        setEnabled(true);
      } catch (caught) {
        showError(caught);
        // 网络失败可能只是回包丢失；尽力补撤回，仍不宣称撤回已送达。
        if (sent) await send([consent("withdraw", hash)]).catch(() => {});
      } finally {
        starting = false;
        if (!disposed) setBusy(false);
      }
    };
    actions.current = { start, stop };
    const onPageHide = () => { void stop(); };
    window.addEventListener("pagehide", onPageHide);
    return () => {
      disposed = true;
      window.removeEventListener("pagehide", onPageHide);
      void stop();
    };
  }, [conversationId, user]);

  return (
    <section aria-label="使用计时" className="inspector-section">
      <p>{TERMS}</p>
      <button type="button" disabled={busy} onClick={() => void (enabled ? actions.current.stop() : actions.current.start())}>
        {enabled ? "停止使用计时" : "同意并开始本次计时"}
      </button>
      <p role="status">{enabled ? "正在记录；切到后台只暂停应用内活跃计时" : "使用计时已关闭；研究测量同意不变"}</p>
      {error && <p role="alert">计时有缺口（未确认保存）：{error}</p>}
    </section>
  );
}
