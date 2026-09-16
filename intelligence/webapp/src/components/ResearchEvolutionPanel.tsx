import { useState } from "react";

import type {
  EvidenceCatalogView,
  EvolutionReceiptRef,
  EvolutionTrackable,
  MaintenanceItem,
  ResearchEvolutionActionResult,
  ResearchEvolutionView,
  ResearchPriorityRow,
} from "../types";
import "./researchEvolution.css";

interface ResearchEvolutionPanelProps {
  view: ResearchEvolutionView | null;
  /** 落一个管理动作 / 任务选择；由 App 调 `postResearchEvolutionAction` 后刷新投影。 */
  onAction?: (body: Record<string, unknown>) => void;
  /** 「从现在开始跟踪」建绑定。 */
  onBind?: (body: Record<string, unknown>) => void;
  /** 受控证据目录：建绑定表单选版本时调。 */
  onFetchCatalog?: (entity: string, asOf: string) => Promise<EvidenceCatalogView>;
  /** 需要读回包的动作（练习作答 / 收据原件）：返回服务端结果给面板展示。 */
  runAction?: (body: Record<string, unknown>) => Promise<ResearchEvolutionActionResult>;
  /** 「继续核查」：把服务端给的 continuation 交给现有 POST 消息入口。 */
  onContinue?: (prompt: string, continuation: Record<string, unknown>) => void;
  busy?: boolean;
}

/** 显式确认成果（QC V3/V4 纠偏）：服务端无法自动证明「新判断属于本轮复核」时，
 * 由用户点名本轮已完成的核查 run 与成果判断。只列当前代际已完成的关联 run；
 * 判断候选取自台账投影，服务端仍会做会话/时间/存在性/重复消费校验。 */
function ConfirmOutcomeForm({
  item,
  view,
  busy,
  onAction,
}: {
  item: MaintenanceItem;
  view: ResearchEvolutionView;
  busy?: boolean;
  onAction: (body: Record<string, unknown>) => void;
}) {
  const rejudgment = (item.management?.rejudgment ?? {}) as Record<string, unknown>;
  const currentRequest = String(rejudgment.request_event_id ?? "");
  const eligibleRuns = (view.maintenance?.run_links ?? []).filter(
    (link) =>
      link.item_id === item.id &&
      String(link.request_event_id ?? "") === currentRequest &&
      link.run_status === "completed",
  );
  const judgments = (view.inputs.trackable_objects ?? []).filter(
    (t) => t.object_ref.kind === "judgment",
  );
  const [runId, setRunId] = useState<string>("");
  const [judgmentRef, setJudgmentRef] = useState<string>("");
  // QC 第六轮 P2：候选集合随投影刷新变化（表单打开时 run 可能还在跑，完成后才出现）。
  // useState 不会重新初始化，所以有效选择**派生**自候选：选中值不在候选里就回落到
  // 唯一候选/空；提交前再验一次所选 run 仍在当前代已完成候选里。
  const selectedRun = eligibleRuns.some((link) => link.run_id === runId)
    ? runId
    : eligibleRuns.length === 1
      ? eligibleRuns[0].run_id
      : "";
  const selectedJudgment = judgments.some((t) => t.object_ref.ref === judgmentRef)
    ? judgmentRef
    : "";
  const canSubmit = !busy && selectedRun !== "" && selectedJudgment !== "";

  return (
    <div className="re-confirm" aria-label="确认成果">
      <p className="re-muted">
        服务端无法自动证明新判断属于本轮复核（多代际或多条待复核），请显式点名。
      </p>
      {eligibleRuns.length === 0 ? (
        <p className="re-muted">还没有已完成的核查 run——先「继续核查」并等它跑完。</p>
      ) : (
        <>
          <label>
            本轮核查 run
            <select value={selectedRun} onChange={(e) => setRunId(e.target.value)}>
              {eligibleRuns.length !== 1 && <option value="">选择 run…</option>}
              {eligibleRuns.map((link) => (
                <option key={link.run_id} value={link.run_id}>
                  {link.run_id}（登记于 {String(link.registered_at ?? "")}）
                </option>
              ))}
            </select>
          </label>
          <label>
            成果判断
            <select
              value={selectedJudgment}
              onChange={(e) => setJudgmentRef(e.target.value)}
            >
              <option value="">选择本轮产生的新判断…</option>
              {judgments.map((t) => (
                <option key={t.object_ref.ref} value={t.object_ref.ref}>
                  {t.title || t.object_ref.ref}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            disabled={!canSubmit}
            onClick={() =>
              onAction({
                action: "link_run",
                idempotency_key: `link_run_confirm:${item.id}:${selectedRun}:${selectedJudgment}`,
                item_id: item.id,
                run_id: selectedRun,
                new_judgment_ref: selectedJudgment,
                expected_item_version: item.item_version,
                expected_management_revision: item.management_revision,
              })
            }
          >
            确认这条判断是本轮成果
          </button>
        </>
      )}
    </div>
  );
}

/** 变化类型 → 用户看得懂的业务标签。哈希/内部版本只在详情里给，不上主屏。 */
const CHANGE_LABEL: Record<string, string> = {
  content_changed: "依据变了",
  source_corrected: "来源被更正",
  source_expired: "来源已失效",
  dependency_missing: "依据读不到",
  condition_evaluated: "登记的条件有了读数",
  unchanged: "没有变化",
};

const REASON_LABEL: Record<string, string> = {
  hash_changed: "同一份来源换了新版本",
  explicit_supersession: "被新版本明确取代",
  validity_ended: "有效期结束",
  ref_unresolved: "引用解析不到",
  time_metadata_missing: "缺记录时刻",
  dependency_unbound: "还没有绑定依据",
  condition_true: "条件已触发",
  condition_false: "条件未触发",
  condition_unknown: "条件还判不了",
  no_change: "没有变化",
};

const STATE_LABEL: Record<string, string> = {
  observed: "已观测",
  requires_review: "需复核",
  unknown: "还不知道",
};

const MODULE_LABEL: Record<string, string> = {
  maintenance: "待复核",
  priority: "下一步研究",
  diagnostics: "我的复盘",
  validation_receipts: "方法验证收据",
  product_value_receipts: "使用测量收据",
};

const STATUS_TEXT: Record<string, string> = {
  ok: "可用",
  unknown: "缺输入，还判不了",
  pending: "等未来到期",
  error: "出错了",
  unavailable: "模块未接入",
  wiring_in_progress: "接线开发中",
};

function label(map: Record<string, string>, key: string | null | undefined): string {
  if (!key) return "—";
  return map[key] ?? key;
}

/**
 * 研究进化面板：`GET /api/conversations/{id}/research-evolution` 的只读展示 + 四个动作。
 *
 * 三条展示纪律（spec 06 §4.2 / §4.4）：
 * 1. 哈希变化写「需复核」，**不**写「已证伪」；
 * 2. 每段的 `module_status` 与 `gaps` 必须露出来——缺输入不能显示成 0 或空列表；
 * 3. 03 / 05 的收据只给引用与状态，普通主屏不出现概率承诺。
 */
export function ResearchEvolutionPanel({
  view,
  onAction,
  onBind,
  onFetchCatalog,
  runAction,
  onContinue,
  busy = false,
}: ResearchEvolutionPanelProps) {
  const [openDetail, setOpenDetail] = useState<string | null>(null);
  const [openConfirm, setOpenConfirm] = useState<string | null>(null);

  if (!view) {
    return <div className="inspector-empty">选择一个会话后显示需要复核的旧判断与下一步研究。</div>;
  }

  const maintenance = view.maintenance;
  const items = (maintenance?.items ?? []).filter(
    (item) => item.status !== "closed" && item.status !== "superseded",
  );
  const priority = view.priority;
  const diagnostics = view.diagnostics;
  const trackable = view.inputs.trackable_objects ?? [];
  const unbound = trackable.filter((item) => !item.bound);

  const act = (item: MaintenanceItem, action: string, extra: Record<string, unknown> = {}) => {
    onAction?.({
      action,
      idempotency_key: `${action}:${item.id}:${item.item_version}:${item.management_revision}`,
      item_id: item.id,
      expected_item_version: item.item_version,
      expected_management_revision: item.management_revision,
      ...extra,
    });
  };

  return (
    <section className="research-evolution" aria-label="研究进化">
      <ModuleStatusBar view={view} />

      <h3>待复核</h3>
      {maintenance === null ? (
        <p className="research-evolution-empty">
          {label(STATUS_TEXT, view.module_status.maintenance.status)}
          {view.module_status.maintenance.reason === "no_bindings"
            ? "：原记录没有完整依据，尚不能比较变化。选一条判断「从现在开始跟踪」后，这里会显示哪条依据变了。"
            : "。"}
        </p>
      ) : items.length === 0 ? (
        <p className="research-evolution-empty">
          {view.module_status.maintenance.status === "ok"
            ? `已跟踪 ${view.inputs.bindings} 条依赖，当前没有需要复核的变化。`
            : `${label(STATUS_TEXT, view.module_status.maintenance.status)}${
                view.module_status.maintenance.reason === "current_source_unreadable"
                  ? "：当前版本读不出来，判不了有没有变化——这不是「没有变化」。"
                  : "。"
              }`}
        </p>
      ) : (
        <ul className="research-evolution-list" aria-label="待复核">
          {items.map((item) => (
            <li key={item.id} className={`re-item re-${item.epistemic_state}`}>
              <div className="re-item-head">
                <strong>{label(CHANGE_LABEL, item.change_type)}</strong>
                <span className="re-badge">{label(STATE_LABEL, item.epistemic_state)}</span>
                <span className="re-muted">{label(REASON_LABEL, item.reason_code)}</span>
              </div>
              <p className="re-object">{item.object_ref.ref}</p>
              {item.gaps.length > 0 && (
                <p className="re-gap">
                  还缺：{item.gaps.map((gap) => gap.reason).join("、")}
                </p>
              )}
              <p className="re-muted">
                数据截止 {item.knowledge_cutoff} · 时点等级 {item.pit_grade}
                {item.status !== "open" ? ` · 当前状态 ${item.status}` : ""}
              </p>
              <div className="re-actions">
                <button type="button" disabled={busy} onClick={() => act(item, "claim")}>
                  开始复核
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    act(item, "snooze", {
                      snooze_until: new Date(Date.now() + 86_400_000).toISOString(),
                    })
                  }
                >
                  稍后处理
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    onAction?.({
                      action: "rejudge",
                      idempotency_key: `rejudge:${item.id}:${item.item_version}:${item.management_revision}`,
                      item_id: item.id,
                      expected_item_version: item.item_version,
                      expected_management_revision: item.management_revision,
                      __continue: true,
                    })
                  }
                >
                  继续核查
                </button>
                <button
                  type="button"
                  disabled={busy || item.current.length === 0}
                  onClick={() => act(item, "reviewed_no_change")}
                  title={
                    item.current.length === 0
                      ? "这条是条件触发，没有可核对的来源版本"
                      : "只关闭这条待复核，不改原判断"
                  }
                >
                  核对后判断未变
                </button>
                <button
                  type="button"
                  className="re-link"
                  onClick={() => setOpenDetail(openDetail === item.id ? null : item.id)}
                >
                  {openDetail === item.id ? "收起详情" : "详情"}
                </button>
                {item.status === "rejudgment_requested" && onAction && (
                  <button
                    type="button"
                    className="re-link"
                    onClick={() =>
                      setOpenConfirm(openConfirm === item.id ? null : item.id)
                    }
                  >
                    {openConfirm === item.id ? "收起确认" : "确认成果"}
                  </button>
                )}
              </div>
                {item.status === "rejudgment_requested" &&
                onAction &&
                openConfirm === item.id &&
                view && (
                  <ConfirmOutcomeForm
                    key={`${item.id}:${String(((item.management?.rejudgment ?? {}) as Record<string, unknown>).request_event_id ?? "")}`}
                    item={item}
                    view={view}
                    busy={busy}
                    onAction={onAction}
                  />
                )}
              {openDetail === item.id && (
                <dl className="re-detail" aria-label="内部版本详情">
                  <div>
                    <dt>原依据</dt>
                    <dd>{item.before.map((v) => `${v.ref}@${v.source_hash ?? "无哈希"}`).join("；") || "—"}</dd>
                  </div>
                  <div>
                    <dt>当前依据</dt>
                    <dd>{item.current.map((v) => `${v.ref}@${v.source_hash ?? "无哈希"}`).join("；") || "—"}</dd>
                  </div>
                  <div>
                    <dt>项版本</dt>
                    <dd>
                      {item.item_version} · 管理修订 {item.management_revision}
                    </dd>
                  </div>
                </dl>
              )}
            </li>
          ))}
        </ul>
      )}

      {unbound.length > 0 && (
        <>
          <h3>还没有依据的旧记录</h3>
          <ul className="research-evolution-list" aria-label="可开始跟踪">
            {unbound.slice(0, 5).map((item) => (
              <li key={item.object_ref.ref} className="re-item re-unbound">
                <p className="re-object">{item.title || item.object_ref.ref}</p>
                <p className="re-muted">
                  {item.bound
                    ? ""
                    : item.gaps.length > 0
                      ? `原记录没有完整依据，尚不能比较变化（${item.gaps
                          .map((gap) => gap.reason)
                          .join("、")}）。`
                      : "原记录没有完整依据，尚不能比较变化。"}
                  从现在开始跟踪：补选这条判断依赖的证据后，以后它变了这里会提醒你。
                </p>
                {onBind && onFetchCatalog && (
                  <BindForm
                    trackable={item}
                    defaultAsOf={view.inputs.as_of}
                    busy={busy}
                    onFetchCatalog={onFetchCatalog}
                    onBind={onBind}
                  />
                )}
              </li>
            ))}
          </ul>
        </>
      )}

      <h3>下一步研究</h3>
      {priority === null ? (
        <p className="research-evolution-empty">{label(STATUS_TEXT, view.module_status.priority.status)}</p>
      ) : (
        <>
          <ul className="research-evolution-list" aria-label="下一步研究">
            {priority.selected.map((row) => (
              <PriorityRow key={row.task_id} row={row} busy={busy} onAction={onAction} />
            ))}
          </ul>
          {priority.critical_not_selected_ids.length > 0 && (
            <p className="re-gap">
              未入选的关键项 {priority.critical_not_selected_ids.length} 条：预算或条数上限挡住了，不是不重要。
            </p>
          )}
          <details className="re-more">
            <summary>
              推迟 {priority.deferred.length} · 等待区 {priority.blocked.length}
            </summary>
            <ul className="research-evolution-list">
              {[...priority.deferred, ...priority.blocked].map((row) => (
                <li key={row.task_id} className="re-item">
                  <p className="re-object">{row["标题"]}</p>
                  <p className="re-muted">{row["原因"]}</p>
                </li>
              ))}
            </ul>
          </details>
          {priority.limitations.length > 0 && (
            <p className="re-gap">{priority.limitations.join("；")}</p>
          )}
        </>
      )}

      <h3>我的复盘</h3>
      {diagnostics === null ? (
        <p className="research-evolution-empty">
          {view.module_status.diagnostics.reason === "policy_not_registered"
            ? "暂无法诊断：还没有登记生产诊断策略。"
            : label(STATUS_TEXT, view.module_status.diagnostics.status)}
        </p>
      ) : (
        <>
          {view.module_status.diagnostics.synthetic && (
            <p className="re-gap">当前诊断策略是合成件，仅供工程验收，不代表真实流程判定。</p>
          )}
          <ul className="research-evolution-list" aria-label="流程诊断">
            {diagnostics.findings
              .filter((finding) => finding.classification === "issue")
              .map((finding) => (
                <li key={finding.id} className="re-item">
                  <div className="re-item-head">
                    <strong>{finding.kind}</strong>
                    <span className="re-badge">{finding.actor_group}</span>
                  </div>
                  <p className="re-object">{finding.observed}</p>
                  <p className="re-muted">应当：{finding.expected}</p>
                  {finding.limitation && <p className="re-gap">{finding.limitation}</p>}
                </li>
              ))}
          </ul>
          {diagnostics.findings.every((finding) => finding.classification !== "issue") && (
            <p className="research-evolution-empty">暂无法诊断：现有记录不足以举证任何流程问题。</p>
          )}
          {diagnostics.exercise && runAction && (
            <ExerciseCard exercise={diagnostics.exercise} busy={busy} runAction={runAction} />
          )}
        </>
      )}

      <ReceiptRefs view={view} runAction={runAction} busy={busy} />
      {onContinue && <span hidden aria-hidden="true" />}
    </section>
  );
}

/** 「从现在开始跟踪」的绑定表单：选实体与站立日 → 拉受控证据目录 → 勾选版本 → 提交。 */
function BindForm({
  trackable,
  defaultAsOf,
  busy,
  onFetchCatalog,
  onBind,
}: {
  trackable: EvolutionTrackable;
  defaultAsOf: string;
  busy: boolean;
  onFetchCatalog: (entity: string, asOf: string) => Promise<EvidenceCatalogView>;
  onBind: (body: Record<string, unknown>) => void;
}) {
  const [open, setOpen] = useState(false);
  const [entity, setEntity] = useState("");
  const [asOf, setAsOf] = useState(defaultAsOf);
  const [catalog, setCatalog] = useState<EvidenceCatalogView | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = () => {
    if (!entity.trim()) return;
    setLoading(true);
    setError(null);
    onFetchCatalog(entity.trim(), asOf)
      .then((cat) => {
        setCatalog(cat);
        setSelected(
          new Set(
            cat.versions
              .map((version) => String(version.ref ?? ""))
              .filter((ref) => ref !== ""),
          ),
        );
      })
      .catch((caught: unknown) =>
        setError(caught instanceof Error ? caught.message : "证据目录拉取失败"),
      )
      .finally(() => setLoading(false));
  };

  const toggle = (ref: string) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(ref)) next.delete(ref);
      else next.add(ref);
      return next;
    });
  };

  if (!open) {
    return (
      <div className="re-actions">
        <button type="button" disabled={busy} onClick={() => setOpen(true)}>
          从现在开始跟踪
        </button>
      </div>
    );
  }
  return (
    <div className="re-bind-form">
      <label>
        证据实体
        <input
          type="text"
          value={entity}
          placeholder="例：制冷剂"
          onChange={(event) => setEntity(event.target.value)}
        />
      </label>
      <label>
        站立日
        <input type="date" value={asOf} onChange={(event) => setAsOf(event.target.value)} />
      </label>
      <button type="button" disabled={loading || !entity.trim()} onClick={load}>
        {loading ? "正在拉取…" : "拉取可用证据"}
      </button>
      {error && <p className="re-gap">{error}</p>}
      {catalog && !catalog.available && (
        <p className="re-gap">
          这个实体的证据读不到（{catalog.reason ?? "未知原因"}），现在不能建绑定。
        </p>
      )}
      {catalog?.available && (
        <fieldset>
          <legend>这条判断依赖哪些证据（pit {catalog.pit_grade}）</legend>
          {catalog.versions.map((version) => {
            const ref = String(version.ref ?? "");
            if (!ref) return null;
            return (
              <label key={ref} className="re-bind-ref">
                <input
                  type="checkbox"
                  checked={selected.has(ref)}
                  onChange={() => toggle(ref)}
                />
                {ref}
                {version.recorded_at ? ` · 记录于 ${String(version.recorded_at)}` : ""}
              </label>
            );
          })}
          {catalog.versions.length === 0 && (
            <p className="re-muted">目录里没有可用版本，换个站立日试试。</p>
          )}
        </fieldset>
      )}
      <div className="re-actions">
        <button
          type="button"
          disabled={busy || !catalog?.available || selected.size === 0}
          onClick={() =>
            onBind({
              object_ref: trackable.object_ref,
              entity: entity.trim(),
              as_of: asOf,
              evidence_refs: [...selected],
            })
          }
        >
          开始跟踪
        </button>
        <button type="button" className="re-link" onClick={() => setOpen(false)}>
          收起
        </button>
      </div>
      <p className="re-muted">
        绑定从这一刻生效：服务端会解析所选证据的真实版本作为基线，不会声称知道判断当天的样子。
      </p>
    </div>
  );
}

/** 03 练习卡：先作答（提交即登记曝光，再评分）；也可以直接「揭示答案」。练习结果不进方法统计。 */
function ExerciseCard({
  exercise,
  busy,
  runAction,
}: {
  exercise: Record<string, unknown>;
  busy: boolean;
  runAction: (body: Record<string, unknown>) => Promise<ResearchEvolutionActionResult>;
}) {
  const exerciseId = String(exercise.id ?? "");
  const visibleRefs = Array.isArray(exercise.visible_evidence_refs)
    ? exercise.visible_evidence_refs.map(String)
    : [];
  const [rationale, setRationale] = useState("");
  const [choicesText, setChoicesText] = useState("");
  const [citedRefs, setCitedRefs] = useState<Set<string>>(new Set());
  const [attempt, setAttempt] = useState(0);
  const [feedback, setFeedback] = useState<Record<string, unknown> | null>(null);
  const [answer, setAnswer] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [working, setWorking] = useState(false);

  const call = (body: Record<string, unknown>, apply: (result: Record<string, unknown>) => void) => {
    setWorking(true);
    setError(null);
    runAction(body)
      .then((result) => apply(result as unknown as Record<string, unknown>))
      .catch((caught: unknown) =>
        setError(caught instanceof Error ? caught.message : "练习动作没有成功"),
      )
      .finally(() => setWorking(false));
  };

  const toggleRef = (ref: string) => {
    setCitedRefs((current) => {
      const next = new Set(current);
      if (next.has(ref)) next.delete(ref);
      else next.add(ref);
      return next;
    });
  };

  const parseChoices = () =>
    choicesText
      .split(/[\s,，、;]+/)
      .map((token) => token.trim())
      .filter(Boolean);

  const submit = () => {
    const next = attempt + 1;
    call(
      {
        action: "submit_exercise",
        idempotency_key: `submit_exercise:${exerciseId}:${next}`,
        exercise_id: exerciseId,
        selected_choices: parseChoices(),
        cited_refs: [...citedRefs],
        rationale,
      },
      (result) => {
        setAttempt(next);
        setFeedback((result.feedback as Record<string, unknown> | undefined) ?? result);
      },
    );
  };

  const reveal = () =>
    call(
      {
        action: "reveal_exercise",
        idempotency_key: `reveal_exercise:${exerciseId}`,
        exercise_id: exerciseId,
      },
      (result) => setAnswer(result),
    );

  const feedbackChecks = Array.isArray(feedback?.checks)
    ? (feedback.checks as Array<Record<string, unknown>>)
    : [];
  const missingRefs = Array.isArray(feedback?.missing_evidence_refs)
    ? (feedback.missing_evidence_refs as unknown[]).map(String)
    : [];
  const answerKey = (answer?.answer_key as Record<string, unknown> | undefined) ?? null;

  return (
    <div className="re-item re-exercise">
      <div className="re-item-head">
        <strong>练一练</strong>
        {exercise.exercise_status ? (
          <span className="re-badge">{String(exercise.exercise_status)}</span>
        ) : null}
      </div>
      <p className="re-object">{String(exercise.prompt ?? "")}</p>
      {typeof exercise.limitation === "string" && exercise.limitation !== "" && (
        <p className="re-gap">{exercise.limitation}</p>
      )}
      {!answer && (
        <>
          <label className="re-exercise-answer">
            你的选择（选项 id，多个用逗号隔开；本题投影未提供选项目录，按题干给出的 id 填）
            <input
              value={choicesText}
              placeholder="例如 c1, c2"
              onChange={(event) => setChoicesText(event.target.value)}
            />
          </label>
          {visibleRefs.length > 0 && (
            <fieldset>
              <legend>你依据了哪些材料（cited_refs）</legend>
              {visibleRefs.map((ref) => (
                <label key={ref} className="re-bind-ref">
                  <input
                    type="checkbox"
                    checked={citedRefs.has(ref)}
                    onChange={() => toggleRef(ref)}
                  />
                  {ref}
                </label>
              ))}
            </fieldset>
          )}
          <label className="re-exercise-answer">
            你的判断
            <textarea
              value={rationale}
              rows={3}
              placeholder="写下你会怎么做、为什么；提交后会登记「你已被曝光」再评分。"
              onChange={(event) => setRationale(event.target.value)}
            />
          </label>
          <div className="re-actions">
            <button type="button" disabled={busy || working} onClick={submit}>
              提交作答
            </button>
            <button type="button" disabled={busy || working} onClick={reveal}>
              揭示答案
            </button>
          </div>
        </>
      )}
      {error && <p className="re-gap">{error}</p>}
      {feedback && (
        <div className="re-detail" aria-label="评分反馈">
          <p>
            评分：<strong>{String(feedback.status ?? "")}</strong>
            <span className="re-muted">（练习结果不进任何方法有效性统计）</span>
          </p>
          {feedbackChecks.length > 0 && (
            <ul>
              {feedbackChecks.map((check) => (
                <li key={String(check.name)}>
                  {check.passed ? "✓" : "✗"} {String(check.name)}：期望 {JSON.stringify(check.expected ?? [])}，你的{" "}
                  {JSON.stringify(check.got ?? [])}
                </li>
              ))}
            </ul>
          )}
          {missingRefs.length > 0 && (
            <p className="re-gap">没引用到的关键材料：{missingRefs.join("、")}</p>
          )}
          {typeof feedback.explanation_ref === "string" && feedback.explanation_ref !== "" && (
            <p className="re-muted">解析：{feedback.explanation_ref}</p>
          )}
        </div>
      )}
      {answer && (
        <div className="re-detail" aria-label="答案">
          {answerKey ? (
            <>
              <p>
                正确选项：{JSON.stringify(answerKey.expected_choices ?? [])}
              </p>
              <p>
                正确引用：{JSON.stringify(answerKey.expected_refs ?? [])}
              </p>
              <p className="re-muted">
                解析：{String(answerKey.explanation_ref ?? "")}（规则 {String(answerKey.rule_id ?? "")}@{String(answerKey.rule_version ?? "")}）
              </p>
            </>
          ) : null}
          {typeof answer.limitation === "string" && answer.limitation !== "" && (
            <p className="re-gap">{answer.limitation}</p>
          )}
        </div>
      )}
    </div>
  );
}

function PriorityRow({
  row,
  busy,
  onAction,
}: {
  row: ResearchPriorityRow;
  busy: boolean;
  onAction?: (body: Record<string, unknown>) => void;
}) {
  return (
    <li className="re-item">
      <div className="re-item-head">
        <strong>{row["标题"]}</strong>
        <span className="re-badge">{row["动作类型"]}</span>
      </div>
      <p className="re-muted">{row["组"]}</p>
      <p className="re-muted">
        耗时 {row["耗时"]} · {row["可执行状态"]}
      </p>
      {row["为什么在前"] && <p className="re-muted">{row["为什么在前"].join("；")}</p>}
      {row["还缺什么"] && row["还缺什么"].length > 0 && (
        <p className="re-gap">还缺：{row["还缺什么"].join("、")}</p>
      )}
      <div className="re-actions">
        <button
          type="button"
          disabled={busy}
          onClick={() =>
            onAction?.({
              action: "select_task",
              idempotency_key: `select:${row.task_id}`,
              task_id: row.task_id,
              client_at: new Date().toISOString(),
            })
          }
        >
          选这一项
        </button>
      </div>
    </li>
  );
}

function ModuleStatusBar({ view }: { view: ResearchEvolutionView }) {
  const degraded = Object.entries(view.module_status).filter(([, status]) => status.status !== "ok");
  if (degraded.length === 0) return null;
  return (
    <ul className="re-status" aria-label="模块状态">
      {degraded.map(([name, status]) => (
        <li key={name} className={`re-status-${status.status}`}>
          {label(MODULE_LABEL, name)}：{label(STATUS_TEXT, status.status)}
          {status.reason ? `（${status.reason}）` : ""}
        </li>
      ))}
    </ul>
  );
}

function ReceiptRefs({
  view,
  runAction,
  busy,
}: {
  view: ResearchEvolutionView;
  runAction?: (body: Record<string, unknown>) => Promise<ResearchEvolutionActionResult>;
  busy: boolean;
}) {
  const validation = view.receipt_refs.validation ?? [];
  const productValue = view.receipt_refs.product_value ?? [];
  const [opened, setOpened] = useState<Record<string, Record<string, unknown>>>({});
  const [error, setError] = useState<string | null>(null);
  if (validation.length === 0 && productValue.length === 0) return null;

  const openReceipt = (key: string, body: Record<string, unknown>) => {
    if (!runAction) return;
    setError(null);
    runAction(body)
      .then((result) => {
        const receipt = (result.receipt ?? result) as Record<string, unknown>;
        setOpened((current) => ({ ...current, [key]: receipt }));
      })
      .catch((caught: unknown) =>
        setError(caught instanceof Error ? caught.message : "收据读取失败"),
      );
  };

  const receiptBody = (ref: EvolutionReceiptRef): Record<string, unknown> => ({
    action: "read_receipt",
    receipt_kind: ref.kind,
    receipt_id: ref.receipt_id ?? ref.summary_id,
    summary_id: ref.summary_id,
    study_id: ref.study_id,
    idempotency_key: `read_receipt:${ref.kind}:${ref.receipt_id ?? ref.summary_id ?? ref.study_id}`,
  });

  return (
    <details className="re-more">
      <summary>原件收据（{validation.length + productValue.length}）</summary>
      {error && <p className="re-gap">{error}</p>}
      <ul className="research-evolution-list">
        {validation.map((ref) => {
          const key = `v-${ref.receipt_id}`;
          return (
            <li key={key} className="re-item">
              <p className="re-object">方法验证 · {ref.study_id}</p>
              <p className="re-muted">状态 {ref.empirical_status}</p>
              {runAction && (
                <div className="re-actions">
                  <button
                    type="button"
                    className="re-link"
                    disabled={busy}
                    onClick={() => openReceipt(key, receiptBody(ref))}
                  >
                    查看原件
                  </button>
                </div>
              )}
              {opened[key] && (
                <pre className="re-receipt">{JSON.stringify(opened[key], null, 2)}</pre>
              )}
            </li>
          );
        })}
        {productValue.map((ref) => {
          const key = `p-${ref.receipt_id ?? ref.summary_id}`;
          return (
            <li key={key} className="re-item">
              <p className="re-object">使用测量 · {ref.kind}</p>
              <p className="re-muted">
                {ref.status ?? `${ref.engineering_status} / ${ref.field_status} / ${ref.commercial_status}`}
              </p>
              {runAction && (ref.receipt_id || ref.summary_id) && (
                <div className="re-actions">
                  <button
                    type="button"
                    className="re-link"
                    disabled={busy}
                    onClick={() => openReceipt(key, receiptBody(ref))}
                  >
                    查看原件
                  </button>
                </div>
              )}
              {opened[key] && (
                <pre className="re-receipt">{JSON.stringify(opened[key], null, 2)}</pre>
              )}
            </li>
          );
        })}
      </ul>
    </details>
  );
}
