import {
  ArrowDownRight,
  ArrowUpRight,
  CircleAlert,
  DatabaseZap,
  Gauge,
  Layers3,
  Radar,
  ShieldCheck,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { useState, type CSSProperties } from "react";
import {
  approveForecastReflection,
  rejectForecastReflection,
  setForecastRuleStatus,
} from "../api";
import type {
  DataFreshnessStatus,
  MarketOverview,
  SignalCard,
  WorkbenchOverview,
  WorkbenchSection,
} from "../types";

interface OutputWorkbenchProps {
  overview: WorkbenchOverview;
  section: Exclude<WorkbenchSection, "ask">;
  onRefresh: () => void;
  refreshing: boolean;
}

const statusLabels: Record<DataFreshnessStatus["status"], string> = {
  complete: "完整",
  stale: "较旧",
  missing: "缺失",
  partial: "部分",
  failed: "失败",
  running: "运行中",
};

function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${value >= 0 ? "+" : ""}${formatNumber(value, 1)}%`;
}

function formatAmount(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  if (Math.abs(value) >= 100_000_000) {
    return `${formatNumber(value / 100_000_000, 0)} 亿`;
  }
  return formatNumber(value, 0);
}

function FreshnessRail({
  statuses,
}: {
  statuses: DataFreshnessStatus[];
}) {
  return (
    <section className="freshness-rail" aria-label="数据新鲜度">
      <div className="freshness-title">
        <DatabaseZap aria-hidden="true" size={15} />
        <span>数据状态</span>
      </div>
      <div className="freshness-items">
        {statuses.map((item) => (
          <div className="freshness-item" key={item.key} title={item.message}>
            <span className={`freshness-dot ${item.status}`} aria-hidden="true" />
            <span>{item.label}</span>
            <time>
              {item.date ?? "无日期"}
              {item.coverage
                ? ` · 覆盖 ${item.coverage.covered}/${item.coverage.total}`
                : ""}
            </time>
            <strong className={`freshness-status ${item.status}`}>
              {statusLabels[item.status]}
            </strong>
          </div>
        ))}
      </div>
    </section>
  );
}

function Metric({
  label,
  value,
  context,
  tone = "neutral",
}: {
  label: string;
  value: string;
  context: string;
  tone?: "positive" | "negative" | "neutral";
}) {
  return (
    <article className={`output-metric ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{context}</small>
    </article>
  );
}

function TodayPanel({ market }: { market: MarketOverview }) {
  const amountTone =
    (market.amount_vs_yesterday_pct ?? 0) > 0 ? "positive" : "negative";
  return (
    <div className="output-panel-stack">
      <section className="market-hero">
        <div>
          <span className="output-eyebrow">今天是什么市场</span>
          <h1>{market.stage}</h1>
          <p>
            数据截至 {market.trade_date ?? "尚无可确认日期"}。结论仅使用同粒度最新数据，
            旧板块与旧标的不补猜。
          </p>
        </div>
        <div className="market-hero-strength">
          <Gauge aria-hidden="true" size={20} />
          <span>强度拐点</span>
          <strong>{formatPercent(market.strength_marginal_pct)}</strong>
          <small>{market.strength_status ?? "未知"}</small>
        </div>
      </section>

      <section className="output-metrics" aria-label="市场核心指标">
        <Metric
          label="涨家数"
          value={formatNumber(market.advancers)}
          context={`MA5 ${formatNumber(market.advancers_ma5)} · ${
            market.breadth_trend ?? "方向未知"
          }`}
          tone={
            (market.advancers ?? 0) >= (market.advancers_ma5 ?? Infinity)
              ? "positive"
              : "neutral"
          }
        />
        <Metric
          label="涨停 / 跌停"
          value={`${formatNumber(market.limit_up)} / ${formatNumber(
            market.limit_down,
          )}`}
          context="极端情绪温度"
        />
        <Metric
          label="成交额"
          value={formatAmount(market.total_amount)}
          context={`较昨日 ${formatPercent(market.amount_vs_yesterday_pct)}`}
          tone={amountTone}
        />
        <Metric
          label="相对 20 日"
          value={formatPercent(market.amount_vs_ma20_pct)}
          context="成交活跃度"
          tone={(market.amount_vs_ma20_pct ?? 0) >= 0 ? "positive" : "neutral"}
        />
        <Metric
          label="集中度"
          value={formatPercent(market.concentration_pct)}
          context={market.concentration_state ?? "状态未知"}
        />
      </section>

      <div className="today-decision-grid">
        <section className="output-card focus-card">
          <header>
            <Radar aria-hidden="true" size={17} />
            <div>
              <span className="output-eyebrow">赚钱效应集中在哪里</span>
              <h2>当前可确认主线</h2>
            </div>
          </header>
          {market.mainlines.length ? (
            <div className="mainline-tags">
              {market.mainlines.map((theme) => (
                <strong key={theme}>{theme}</strong>
              ))}
            </div>
          ) : (
            <p className="empty-output">暂无可确认的当前主线</p>
          )}
          <p>只展示与市场日期一致的题材级结论。</p>
        </section>
        <section className="output-card risk-card">
          <header>
            <CircleAlert aria-hidden="true" size={17} />
            <div>
              <span className="output-eyebrow">风险与缺口</span>
              <h2>哪些结论暂不能下</h2>
            </div>
          </header>
          <ul>
            {market.risks.map((risk) => (
              <li key={risk}>{risk}</li>
            ))}
          </ul>
        </section>
        <section className="output-card validation-card">
          <header>
            <ShieldCheck aria-hidden="true" size={17} />
            <div>
              <span className="output-eyebrow">明天验证什么</span>
              <h2>可核验信号</h2>
            </div>
          </header>
          <ol>
            {market.validation_points.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ol>
        </section>
      </div>
    </div>
  );
}

function ThemePanel({ overview }: { overview: WorkbenchOverview }) {
  return (
    <div className="output-panel-stack">
      <section className="output-section-heading">
        <div>
          <span className="output-eyebrow">主题状态矩阵</span>
          <h1>知识共识 × 盘面确认</h1>
          <p>
            两条轴独立计时。知识日期与盘面日期不同，不会被合并成“当前事实”。
          </p>
        </div>
        <div className="axis-date-note">
          <span>盘面 {overview.as_of_date ?? "未知"}</span>
          <span>知识 {overview.signal_date ?? "未知"}</span>
        </div>
      </section>
      <section className="theme-matrix" aria-label="主题双轴矩阵">
        <div className="matrix-corner">盘面 ↓ / 知识 →</div>
        {overview.theme_axes.knowledge.map((stage) => (
          <div className="matrix-axis-label" key={stage}>
            {stage}
          </div>
        ))}
        {overview.theme_axes.market.map((marketStage) => (
          <div className="matrix-row" key={marketStage}>
            <div className="matrix-market-label">{marketStage}</div>
            {overview.theme_axes.knowledge.map((knowledgeStage) => {
              const themes = overview.themes.filter(
                (theme) =>
                  theme.market_stage === marketStage &&
                  theme.knowledge_stage === knowledgeStage,
              );
              return (
                <div className="matrix-cell" key={`${marketStage}-${knowledgeStage}`}>
                  {themes.map((theme) => (
                    <article
                      className={`theme-bubble ${
                        theme.detail_status === "stale" ? "stale" : ""
                      }`}
                      key={theme.theme_code || theme.name}
                      style={{
                        "--bubble-scale": `${Math.min(
                          1.35,
                          0.9 + theme.source_count * 0.035,
                        )}`,
                      } as CSSProperties}
                      title={`${theme.evidence_type} · ${theme.direction}`}
                    >
                      <strong>{theme.name}</strong>
                      <small>
                        {theme.detail_status === "current"
                          ? `${theme.sector_count} 板块 · ${theme.stock_count} 个股`
                          : "当前明细未更新"}
                      </small>
                    </article>
                  ))}
                </div>
              );
            })}
          </div>
        ))}
      </section>
      <section className="quadrant-guide">
        <article>
          <strong>知识早 · 盘面早</strong>
          <span>可能存在预期差</span>
        </article>
        <article>
          <strong>知识热 · 盘面冷</strong>
          <span>卖方自嗨或尚未验证</span>
        </article>
        <article>
          <strong>知识冷 · 盘面热</strong>
          <span>市场先动但解释不足</span>
        </article>
        <article>
          <strong>知识热 · 盘面热</strong>
          <span>共识主线，也可能拥挤</span>
        </article>
      </section>
    </div>
  );
}

const signalBuckets: Array<{
  key: keyof WorkbenchOverview["signals"];
  title: string;
}> = [
  { key: "new", title: "新出现" },
  { key: "strengthened", title: "被加强" },
  { key: "weakened", title: "被削弱 / 纠正" },
  { key: "pending", title: "等待验证" },
];

function SignalEvent({ item }: { item: SignalCard }) {
  return (
    <article className="signal-event">
      <header>
        <strong>{item.title}</strong>
        <time>{item.source_date ?? "无日期"}</time>
      </header>
      <small className="signal-source">{item.source_type}</small>
      <p>{item.summary || item.change}</p>
      <dl>
        <div>
          <dt>相对变化</dt>
          <dd>{item.change}</dd>
        </div>
        <div>
          <dt>盘面确认</dt>
          <dd>{item.market_confirmation}</dd>
        </div>
        <div>
          <dt>下一验证</dt>
          <dd>{item.next_validation}</dd>
        </div>
      </dl>
    </article>
  );
}

function SignalPanel({ overview }: { overview: WorkbenchOverview }) {
  const sellside = [
    ["priority", "优先发散", "覆盖低且证据更硬"],
    ["confirmation", "只作确认", "逻辑成立，等待盘面"],
    ["caution", "反向谨慎", "覆盖拥挤，关注兑现"],
  ] as const;
  return (
    <div className="output-panel-stack">
      <section className="output-section-heading">
        <div>
          <span className="output-eyebrow">晨会边际变化</span>
          <h1>只推变化，不重复旧观点</h1>
          <p>事件日期 {overview.signal_date ?? "暂无"}；重复观点折叠在来源台账中。</p>
        </div>
      </section>
      <section className="signal-inbox">
        {signalBuckets.map(({ key, title }) => (
          <div className={`signal-column ${key}`} key={key}>
            <header>
              <span>{title}</span>
              <strong>{overview.signals[key].length}</strong>
            </header>
            {overview.signals[key].map((item, index) => (
              <SignalEvent item={item} key={`${item.title}-${index}`} />
            ))}
            {!overview.signals[key].length && (
              <p className="empty-output">当前没有新增事件</p>
            )}
          </div>
        ))}
      </section>
      <section className="output-card sellside-flow">
        <header>
          <Layers3 aria-hidden="true" size={17} />
          <div>
            <span className="output-eyebrow">当日晚间观点分流</span>
            <h2>卖方情报如何使用</h2>
          </div>
          <time>{overview.sellside_date ?? "暂无日期"}</time>
        </header>
        <div className="sellside-flow-grid">
          {sellside.map(([key, title, description]) => (
            <div key={key}>
              <strong>{title}</strong>
              <small>{description}</small>
              {overview.sellside_flow[key].map((item) => (
                <article key={`${item.theme}-${item.source}`}>
                  <span>{item.theme}</span>
                  <small>
                    {item.source} · {item.mention_count} 次覆盖
                  </small>
                  <p>{item.reason}</p>
                </article>
              ))}
              {!overview.sellside_flow[key].length && (
                <p className="empty-output">暂无符合口径的观点</p>
              )}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function ValidationPanel({
  overview,
  onRefresh,
}: {
  overview: WorkbenchOverview;
  onRefresh: () => void | Promise<void>;
}) {
  const [feedbackAction, setFeedbackAction] = useState<string | null>(null);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const limitup = overview.moneyflow.leaders.filter((row) =>
    row.scan_type.toLowerCase().includes("limit"),
  );
  const top100 = overview.moneyflow.leaders.filter(
    (row) => !row.scan_type.toLowerCase().includes("limit"),
  );
  const approveReflection = async (
    filename: string,
    hypothesisId: string,
    status: "approved" | "rejected" = "approved",
  ) => {
    const action = `reflection:${filename}:${hypothesisId}:${status}`;
    setFeedbackAction(action);
    setFeedbackError(null);
    try {
      if (status === "approved") {
        await approveForecastReflection(filename, [hypothesisId]);
      } else {
        await rejectForecastReflection(filename, [hypothesisId]);
      }
      await onRefresh();
    } catch (caught) {
      setFeedbackError(caught instanceof Error ? caught.message : "批准 lesson 失败");
    } finally {
      setFeedbackAction(null);
    }
  };
  const reviewRule = async (id: string, status: "approved" | "rejected") => {
    const action = `rule:${id}:${status}`;
    setFeedbackAction(action);
    setFeedbackError(null);
    try {
      await setForecastRuleStatus(id, status);
      await onRefresh();
    } catch (caught) {
      setFeedbackError(caught instanceof Error ? caught.message : "更新规则失败");
    } finally {
      setFeedbackAction(null);
    }
  };
  return (
    <div className="output-panel-stack">
      <section className="output-section-heading">
        <div>
          <span className="output-eyebrow">持续校准</span>
          <h1>机构胜率、资金流与假设回检</h1>
          <p>
            胜率只统计完整窗口且样本不少于 5；晨汇 AI 转述不计入机构表现。
          </p>
        </div>
        <span className="hypothesis-status">
          <ShieldCheck aria-hidden="true" size={15} />
          {overview.validation.hypothesis_status}
        </span>
      </section>
      <section className="output-card winrate-card">
        <header>
          <Gauge aria-hidden="true" size={17} />
          <div>
            <span className="output-eyebrow">双盲 verdict 后验</span>
            <h2>Agent 方向命中率</h2>
          </div>
        </header>
        <p>
          partial 按半分展示校准率；每个 Agent / 数据流满
          {overview.forecast_performance.sample_goal} 个方向样本后，才允许比较题式表现。
        </p>
        <div className="output-table-scroll">
          <table className="output-table">
            <thead>
              <tr>
                <th>Agent / 流</th>
                <th>样本进度</th>
                <th>hit / miss / partial</th>
                <th>严格命中率</th>
                <th>半分校准率</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {overview.forecast_performance.rows.map((row) => (
                <tr key={row.key}>
                  <th>{row.agent} / {row.source}</th>
                  <td>{row.sample_count}/{row.sample_goal}</td>
                  <td>{row.hits} / {row.misses} / {row.partial}</td>
                  <td>{formatPercent(row.hit_rate === null ? null : row.hit_rate * 100)}</td>
                  <td>{formatPercent(row.weighted_rate === null ? null : row.weighted_rate * 100)}</td>
                  <td>{row.decision_eligible ? "可分题式统计" : "样本积累中"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!overview.forecast_performance.rows.length && (
            <p className="empty-output">暂无可归类的方向 verdict。</p>
          )}
        </div>
      </section>
      <section className="output-card learning-feedback-card">
        <header>
          <ShieldCheck aria-hidden="true" size={17} />
          <div>
            <span className="output-eyebrow">人工审批门</span>
            <h2>待确认的 Lesson 与硬规则</h2>
          </div>
        </header>
        <p>
          已批准 {overview.learning_feedback.approved_lesson_count} 条 lesson、
          {overview.learning_feedback.approved_rule_count} 条规则；pending 不会进入答卷 prompt。
        </p>
        {feedbackError && <p className="moneyflow-warning">{feedbackError}</p>}
        <div className="sellside-flow-grid">
          <div>
            <strong>错因反思候选</strong>
            {overview.learning_feedback.pending_reflections.slice(0, 6).map((item) => {
              const approveAction = `reflection:${item.reflection_file}:${item.hypothesis_id}:approved`;
              return (
                <article key={approveAction}>
                  <span>{item.agent} · {item.hypothesis_id}</span>
                  <small>{item.date} · {item.failure_mode || item.status}</small>
                  <p>{item.lesson || "等待模型补齐可复用 lesson"}</p>
                  <button
                    type="button"
                    disabled={!item.approvable || feedbackAction !== null}
                    onClick={() => void approveReflection(item.reflection_file, item.hypothesis_id)}
                  >
                    {feedbackAction === approveAction ? "批准中…" : "批准 Lesson"}
                  </button>
                  <button
                    type="button"
                    disabled={feedbackAction !== null}
                    onClick={() => void approveReflection(
                      item.reflection_file,
                      item.hypothesis_id,
                      "rejected",
                    )}
                  >驳回反思</button>
                </article>
              );
            })}
            {!overview.learning_feedback.pending_reflections.length && (
              <p className="empty-output">暂无待确认反思。</p>
            )}
          </div>
          <div>
            <strong>§8 硬规则候选</strong>
            {overview.learning_feedback.pending_rules.slice(0, 6).map((item) => (
              <article key={item.id}>
                <span>{item.date}</span>
                <small>{item.issue || "来自用户批注"}</small>
                <p>{item.rule}</p>
                <div>
                  <button
                    type="button"
                    disabled={feedbackAction !== null}
                    onClick={() => void reviewRule(item.id, "approved")}
                  >批准规则</button>
                  <button
                    type="button"
                    disabled={feedbackAction !== null}
                    onClick={() => void reviewRule(item.id, "rejected")}
                  >驳回</button>
                </div>
              </article>
            ))}
            {!overview.learning_feedback.pending_rules.length && (
              <p className="empty-output">暂无待确认规则。</p>
            )}
          </div>
        </div>
      </section>
      <section className="output-card winrate-card">
        <header>
          <TrendingUp aria-hidden="true" size={17} />
          <div>
            <span className="output-eyebrow">卖方观点后验</span>
            <h2>机构超额胜率榜</h2>
          </div>
        </header>
        <div className="output-table-scroll">
          <table className="output-table">
            <thead>
              <tr>
                <th>机构</th>
                <th>样本</th>
                <th>T+5 超额胜率</th>
                <th>T+10 超额胜率</th>
                <th>均超额</th>
                <th>中位超额</th>
                <th>均回撤</th>
                <th>擅长窗口</th>
              </tr>
            </thead>
            <tbody>
              {overview.winrate.map((row) => (
                <tr key={row.source_id}>
                  <th>{row.name}</th>
                  <td>{row.sample_count}</td>
                  <td>{formatPercent(row.t5_win_rate === null ? null : row.t5_win_rate * 100)}</td>
                  <td>{formatPercent(row.t10_win_rate === null ? null : row.t10_win_rate * 100)}</td>
                  <td>{formatPercent(row.average_excess)}</td>
                  <td>{formatPercent(row.median_excess)}</td>
                  <td>{formatPercent(row.average_drawdown)}</td>
                  <td>{row.best_window}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!overview.winrate.length && (
            <p className="empty-output">完整样本不足，暂不展示机构排名。</p>
          )}
        </div>
      </section>

      <section className="moneyflow-section">
        <header className="moneyflow-heading">
          <div>
            <span className="output-eyebrow">Level2 盘后资金流</span>
            <h2>钱在谁身上，是否持续</h2>
          </div>
          <span className={`moneyflow-state ${overview.moneyflow.status}`}>
            {overview.moneyflow.trade_date ?? "无日期"} · {overview.moneyflow.status}
          </span>
        </header>
        {overview.moneyflow.warnings.map((warning) => (
          <p className="moneyflow-warning" key={warning}>
            <CircleAlert aria-hidden="true" size={14} />
            {warning}
          </p>
        ))}
        <div className="moneyflow-grid">
          <MoneyflowTable title="涨停池资金流榜" rows={limitup} />
          <MoneyflowTable title="成交额前 100 资金流榜" rows={top100} />
          <section className="output-card quant-card">
            <h3>量化买单榜</h3>
            {overview.moneyflow.quant_orders.slice(0, 6).map((row) => (
              <article key={row.stock_code}>
                <strong>{row.stock_name}</strong>
                <span>{formatAmount(row.quant_amount_wan)} 万</span>
                <small>{formatPercent(row.quant_pct_of_big_buy)}</small>
              </article>
            ))}
            {!overview.moneyflow.quant_orders.length && (
              <p className="empty-output">暂无完整扫描结果</p>
            )}
          </section>
        </div>
        <section className="flow-change-strip">
          {overview.moneyflow_trends.slice(0, 8).map((item) => (
            <article key={item.stock_code}>
              <div>
                {item.rank_change !== null && item.rank_change > 0 ? (
                  <ArrowUpRight aria-hidden="true" size={15} />
                ) : (
                  <ArrowDownRight aria-hidden="true" size={15} />
                )}
                <strong>{item.stock_name}</strong>
              </div>
              <span>
                {item.is_new
                  ? "新进榜"
                  : item.rank_change
                    ? `排名 ${item.rank_change > 0 ? "+" : ""}${item.rank_change}`
                    : `${item.history_days} 日样本`}
              </span>
              <small>
                {item.consecutive_inflow_days > 1
                  ? `连续净流入 ${item.consecutive_inflow_days} 日`
                  : item.divergence ?? "资金与价格同向"}
              </small>
            </article>
          ))}
          {!overview.moneyflow_trends.length && (
            <p className="empty-output">跨日样本不足，趋势、新进榜与背离保持未知。</p>
          )}
        </section>
      </section>
    </div>
  );
}

function MoneyflowTable({
  title,
  rows,
}: {
  title: string;
  rows: WorkbenchOverview["moneyflow"]["leaders"];
}) {
  return (
    <section className="output-card moneyflow-card">
      <h3>{title}</h3>
      {rows.slice(0, 6).map((row) => (
        <article key={`${row.stock_code}-${row.scan_type}`}>
          <span className="moneyflow-rank">{row.rank ?? "—"}</span>
          <strong>{row.stock_name}</strong>
          <span className={(row.main_buy_net_wan ?? 0) >= 0 ? "positive" : "negative"}>
            {formatAmount(row.main_buy_net_wan)} 万
          </span>
          <small>{formatPercent(row.pct_change)}</small>
        </article>
      ))}
      {!rows.length && <p className="empty-output">暂无完整扫描结果</p>}
    </section>
  );
}

export function OutputWorkbench({
  overview,
  section,
  onRefresh,
  refreshing,
}: OutputWorkbenchProps) {
  return (
    <main className="output-workbench">
      <header className="output-workbench-header">
        <div>
          <Sparkles aria-hidden="true" size={16} />
          <span>结构化研究工作台</span>
          <strong>{overview.as_of_date ?? "等待数据"}</strong>
        </div>
        <button type="button" onClick={onRefresh} disabled={refreshing}>
          {refreshing ? "刷新中…" : "刷新数据状态"}
        </button>
      </header>
      <FreshnessRail statuses={overview.data_status} />
      <div className="output-workbench-body">
        {section === "today" && <TodayPanel market={overview.market} />}
        {section === "themes" && <ThemePanel overview={overview} />}
        {section === "signals" && <SignalPanel overview={overview} />}
        {section === "validation" && (
          <ValidationPanel overview={overview} onRefresh={onRefresh} />
        )}
      </div>
    </main>
  );
}
