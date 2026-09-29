import { useCallback, useEffect, useState } from "react";
import { BookOpen, ClipboardCheck, Layers3, Radio } from "lucide-react";
import type { EntityHit, RiverMeta } from "../../river/types";
import { getRiverMeta } from "../../river/api";
import { ObservationWorkbench } from "./ObservationWorkbench";
import { OriginalDailyReview } from "./OriginalDailyReview";
import { AttentionPanel } from "./DailyRiverDashboard";
import { RiverWorkbench as RiverResearch } from "./RiverWorkbench";
import "../../riverOriginal.css";

/** Three reading levels in the original Workbench entry, sharing one date and entity. */
export function RiverWorkbench({ focusDate = null, onFocusDate, onOpenLadder }: {
  focusDate?: string | null; onFocusDate?: (date: string) => void; onOpenLadder?: (date: string) => void;
} = {}) {
  const [view, setView] = useState<"daily" | "research" | "attention" | "observation">("daily");
  const [entity, setEntity] = useState<EntityHit | null>(null);
  const [localDate, setLocalDate] = useState<string | null>(focusDate);
  const [meta, setMeta] = useState<RiverMeta | null>(null);
  const [metaError, setMetaError] = useState(false);
  const [metaRevision, setMetaRevision] = useState(0);
  useEffect(() => {
    let active = true;
    setMetaError(false);
    getRiverMeta(400).then(data => { if (active) setMeta(data); }).catch(() => { if (active) setMetaError(true); });
    return () => { active = false; };
  }, [metaRevision]);
  const date = focusDate ?? localDate ?? meta?.latest ?? null;
  const pickDate = useCallback((day: string) => { setLocalDate(day); onFocusDate?.(day); }, [onFocusDate]);
  return <div className="river-original original-river-home">
    <nav className="original-home-nav" aria-label="原工作台长河模式"><div role="group" aria-label="长河阅读层次"><button type="button" className={view === "daily" ? "active" : ""} aria-pressed={view === "daily"} onClick={() => setView("daily")}><BookOpen size={14}/>每日复盘</button><button type="button" className={view === "observation" ? "active" : ""} aria-pressed={view === "observation"} onClick={() => setView("observation")}><ClipboardCheck size={14}/>观察验证</button><button type="button" className={view === "research" ? "active" : ""} aria-pressed={view === "research"} onClick={() => setView("research")}><Layers3 size={14}/>板块六轨</button><button type="button" className={view === "attention" ? "active" : ""} aria-pressed={view === "attention"} onClick={() => setView("attention")}><Radio size={14}/>公开消息</button></div><span>{date ?? "交易日待确认"}{entity ? ` · ${entity.name}` : " · 全市场"}</span>{onOpenLadder && <button type="button" disabled={!date} onClick={() => date && onOpenLadder(date)}>同日连板 ↗</button>}</nav>
    {view === "daily" && <OriginalDailyReview focusDate={date} onFocusDate={pickDate} onResearch={(next, day) => { setEntity(next); pickDate(day); setView("research"); }} onAttention={(next, day) => { setEntity(next ? { id: next.id, name: next.name, pct_chg: null, amount: null } : null); pickDate(day); setView("attention"); }}/>}
    {view === "observation" && <ObservationWorkbench date={date} dates={meta?.trading_days ?? []} subject={entity?.name ?? "全市场"} onDate={pickDate} onEvidence={next => { if (next === "ladder") { if (date) onOpenLadder?.(date); } else setView(next); }}/> }
    {view === "research" && <><div className="original-evidence-note"><b>研报覆盖 ≠ 公开消息热度</b><span>六轨中的研报泳道按报告份数展示；公开消息的传播来源、转载去重和事实核验状态在独立页签，不相加成一个“舆论分”。</span></div><RiverResearch focusDate={date} onFocusDate={pickDate} initialEntity={entity} onEntityChange={setEntity} onPublicAttention={(next, day) => { setEntity(next); pickDate(day); setView("attention"); }}/></>}
    {view === "attention" && <div className="output-workbench original-public-panel"><div className="output-workbench-header"><div><Radio size={15}/><strong>公开消息传播</strong><span>不是研报覆盖，也不是事实可信度评分</span></div></div><div className="original-selection-bar"><label>所选交易日<select aria-label="公开消息交易日" value={date ?? ""} onChange={e => pickDate(e.target.value)}>{!meta?.trading_days.length && <option value={date ?? ""}>{date ?? "读取中…"}</option>}{date && meta?.trading_days.length && !meta.trading_days.includes(date) ? <option value={date}>{date}</option> : null}{meta?.trading_days.slice().reverse().map(d => <option key={d}>{d}</option>)}</select></label><span>筛选：{entity?.name ?? "全部已映射方向"}</span></div>{metaError && <p className="river-hint">交易日目录暂不可读。<button type="button" onClick={() => setMetaRevision(n => n + 1)}>重试日期</button></p>}{date ? <AttentionPanel date={date} sector={entity} onClear={() => setEntity(null)}/> : <div className="surface-loading">尚未取得有效交易日，不用今天的日期冒充最新行情。</div>}</div>}
  </div>;
}
