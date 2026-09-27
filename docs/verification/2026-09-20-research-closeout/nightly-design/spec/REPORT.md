需收口：候选有 1 项刷新认证缺口、1 项安全但影响跨午夜重跑的约束冲突；吸收 main 后另有 1 项集成条件。

固定候选 `6356ffd5e703b30948f687baaaf60102bf97f0a5`，比较 `4ace5ec2e9b7735d90eb15bc2351fa193c1120b8...6356ffd5e703b30948f687baaaf60102bf97f0a5`。只审 Spec，不改候选、不合并、不取真实数据。

- **R1 / P2 / 当前候选数据正确性：刷新未完成仍返回成功。** 设计要求“再按日重算板块日线和下游”，且旧 success 不证明输入未变（[runbook:62](/Users/a77/fwp-wt-nightly-review-0917/skills/duckdb-backfill/references/backfill-runbook.md:62)）。**Evidence → Finding：**真实小库中已有 3 个成功板块；当 180 日内无合格基线时，`--include-completed` 返回 `stitched=0, skipped.no_baseline=3, audit_complete=true`，CLI 仍 rc=0；底表价已 12，成员价仍 10。[恢复调用只消费进程状态](/Users/a77/fwp-wt-nightly-review-0917/scripts/recover_local_review.py:120)，未认证本轮刷新。可用基线对照重建 3 个、成员价为 12。最小修复：恢复模式要求本轮请求刷新的候选全部完成，否则阻断；保留普通非刷新模式，不放宽基线、不虚构名单。本轮证明到 CLI 与成员完成审计，未冒称已实测发布坏库。

- **R2 / P2 / 当前候选安全但不可用：合法快照跨午夜回放被旧时刻规则拒绝。** 原口径明确“不能按 updated_at 日期 ≠ trade_date 判”（[runbook:40](/Users/a77/fwp-wt-nightly-review-0917/skills/duckdb-backfill/references/backfill-runbook.md:40)）。**Evidence → Finding：**同一字节的 09-17 快照，两次均通过 `f297` 业务日核验；22:00 回放通过来源检查，09-18 00:01 回放因实际写入时刻触发 `source-semantics FAIL`。恢复入口[回放后调用该门](/Users/a77/fwp-wt-nightly-review-0917/scripts/recover_local_review.py:133)，因此中断后合法重跑不能完成。验收需区分已核验业务日与真实回放时刻；不得改日期、倒写时间或伪造来源。此项保持拒绝发布，不是日期污染实证。

- **I1 / P2 / 仅吸收 main 后的集成条件：可选同花顺 skip 被恢复当失败。** main 明示缺 key 保留 skip 合同（冻结源码 `run_review_sync.py:363–377`）。**Evidence → Finding：**保留 main 四个同花顺步骤和候选指数 flag 的函数级合流探针，缺 key 在首步 `hithink-stock-daily` 抛错；有 key 且叶子成功的对照完成。[恢复判据](/Users/a77/fwp-wt-nightly-review-0917/scripts/recover_local_review.py:125)需识别计划明示可跳过的并跑源，同时继续阻断必需步骤失败；不可笼统放行所有 skip。此项不否定旧两日成功。

新离线：指定解释器定向 **36 passed**；另有上述反例和正常对照，必需步骤/同日门/跨日门/对齐门失败均不写成功状态。旧两日 19/20 表、114P 仅为历史交接记载；本轮未跑生产、全仓、前端、E2E、registry，不能签无人值守或合并准入。完整身份、命令和测试边界见 [EVIDENCE.md](/Users/a77/.finance-runtime/reviews/research-closeout-20260920/nightly-design/spec/EVIDENCE.md)。
