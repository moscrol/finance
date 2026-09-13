import { useState } from "react";

import type {
  MaintenanceItem,
  ResearchEvolutionView,
  ResearchPriorityRow,
} from "../types";
import "./researchEvolution.css";

interface ResearchEvolutionPanelProps {
  view: ResearchEvolutionView | null;
  /** 落一个管理动作 / 任务选择；由 App 调 `postResearchEvolutionAction` 后刷新投影。 */
  onAction?: (body: Record<string, unknown>) => void;
  /** 「继续核查」：把服务端给的 continuation 交给现有 POST 消息入口。 */
  onContinue?: (prompt: string, continuation: Record<string, unknown>) => void;
  busy?: boolean;
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
  onContinue,
  busy = false,
}: ResearchEvolutionPanelProps) {
  const [openDetail, setOpenDetail] = useState<string | null>(null);

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
          已跟踪 {view.inputs.bindings} 条依赖，当前没有需要复核的变化。
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
              </div>
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
                <p className="re-muted">原记录没有完整依据，尚不能比较变化</p>
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
        </>
      )}

      <ReceiptRefs view={view} />
      {onContinue && <span hidden aria-hidden="true" />}
    </section>
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

function ReceiptRefs({ view }: { view: ResearchEvolutionView }) {
  const validation = view.receipt_refs.validation ?? [];
  const productValue = view.receipt_refs.product_value ?? [];
  if (validation.length === 0 && productValue.length === 0) return null;
  return (
    <details className="re-more">
      <summary>原件收据（{validation.length + productValue.length}）</summary>
      <ul className="research-evolution-list">
        {validation.map((ref) => (
          <li key={`v-${ref.receipt_id}`} className="re-item">
            <p className="re-object">方法验证 · {ref.study_id}</p>
            <p className="re-muted">状态 {ref.empirical_status}</p>
          </li>
        ))}
        {productValue.map((ref) => (
          <li key={`p-${ref.receipt_id ?? ref.summary_id}`} className="re-item">
            <p className="re-object">使用测量 · {ref.kind}</p>
            <p className="re-muted">
              {ref.status ?? `${ref.engineering_status} / ${ref.field_status} / ${ref.commercial_status}`}
            </p>
          </li>
        ))}
      </ul>
    </details>
  );
}
