# 报告逐声明证据血缘与 Gold 人审工作台

## 目标

本阶段只修复“报告能否被验证”，不调整预测、选股或题材排序参数。

- P0：报告生成时原生携带逐声明证据血缘；
- P1：提供双人 Gold 审核流程，但程序不得自动批准；
- 保持 `decision_eligible=false`，直到人工 Gold 和 PIT 版本缺口都满足要求。

## 为什么必须在上游生成 lineage

事后从 Markdown 文本猜来源虽然实现最快，但不能证明该来源确实参与了声明生成，也容易把报告级引用误当成逐声明证据。

正确链路是：

```text
DuckDB fact_* 行
  -> MarketAdapter 保留 source / updated_at
  -> ThemeRadarService 绑定 table / field / entity / valid_time / source_time
  -> theme-candidates.json 输出 evidence_catalog
  -> logic-market-match 保留候选证据
  -> daily-agent 输出 claims + evidence_catalog
  -> JSON / Markdown / HTML 从同一 canonical report 渲染
  -> claim_fidelity 优先读取显式 claims
```

每条证据使用内容哈希生成稳定 ID。相同来源描述会自然去重，也不会依赖列表顺序。

可迁移知识点：这种“内容寻址”模式同样适用于数据湖 manifest、特征血缘和 RAG 引用去重。

## 原始事实与派生事实

- `source_kind=table_row`：可定位到具体表、字段、实体和时间；
- `source_kind=derived`：必须带 derivation 元数据，不能伪装成原始行；
- `scope=claim`：真实逐声明证据，计入 evidence coverage；
- `scope=inferred`：评测器的确定性映射，只辅助数字核验，不计入覆盖率；
- 报告级引用不能替代 claim-level evidence。

没有真实 `updated_at/source_time` 的旧产物保持无证据，不自动补造。

## Gold 人审状态

工作台支持：

- `candidate`
- `pending`
- `needs_review`
- `unverifiable`
- `approved`

双人分别填写：

- expected type；
- entity classification；
- stage feature；
- causal support；
- timeline event / position；
- notes。

工作台计算逐字段一致率，初始目标为 `>= 80%`。存在分歧时 consensus 自动保持 `needs_review`，不能进入批准。

批准必须显式执行：

```bash
python3 scripts/gold_review_workbench.py approve \
  --consensus consensus.gold.json \
  --approver HUMAN_NAME \
  --confirmation I_APPROVE_GOLD \
  --out approved.gold.json
```

该确认只证明“有人主动执行批准动作”，不能替代实际审核。`pending`、`needs_review` 和 `unverifiable` 均不得按通过计分；已批准 Gold 文件禁止覆盖。

## 15–20 个分层样本

先从 Phase 2 selection 中选择 15–20 个有 exact-date canonical report 的日期：

```bash
python3 scripts/gold_review_workbench.py select \
  --selection phase2.selection.json \
  --count 20 \
  --out gold-review-batch.json
```

选择器按月份、市场阶段和 PIT 数据完整度确定性 round-robin。缺报告的 55 个日期继续作为 negative control，不进入 Gold 报告忠实度审核。

扩大到 80 日之前，应先完成：

1. 两位人工 reviewer；
2. 一致率统计；
3. 分歧裁决；
4. 显式批准；
5. 确认不可验证项未被算作通过。

## P4-D：150–300 条 claim 分层抽样

P4-D 不再只抽“日期”，而是从 P4-B/P4-C 之后的 forward daily-agent
claim manifest 中抽“声明”。当前先把工具和审核协议固定下来；7/13–7/17
真实 forward artifacts 出来后再填首批样本。

推荐命令：

```bash
python3 scripts/gold_review_workbench.py sample-claims \
  --reports 'market_feature_store/exports/*-daily-agent.json' \
  --target-count 200 \
  --seed fidelity-gold-review-v1 \
  --out gold-review-claim-batch.json

python3 scripts/gold_review_workbench.py validate-batch \
  --batch gold-review-claim-batch.json

python3 scripts/gold_review_workbench.py init-batch-review \
  --batch gold-review-claim-batch.json \
  --reviewer reviewer-a \
  --out gold-review.reviewer-a.json

python3 scripts/gold_review_workbench.py init-batch-review \
  --batch gold-review-claim-batch.json \
  --reviewer reviewer-b \
  --out gold-review.reviewer-b.json
```

抽样规则是 deterministic 的：

```text
valid fidelity-contract daily-agent reports
  -> bucket(public/evidence scope, manifest_scope, claim_type, evidence coverage)
  -> hash-order within each stratum by seed
  -> sorted-stratum round-robin until 150–300 target_count
```

这样能避免被海量 public narrative 或单一数字 claim 淹没。`batch_sha256`
封住样本集；改 seed、claim 内容、report hash 或样本顺序都会改变 batch hash。

样本不足 150 时 batch 状态为 `insufficient_forward_claims`，不能初始化 Gold
review，也不能作为 decision evidence。这正是当前阶段的预期：工具先就绪，
等 forward claims 足量后再开始双人独立审核。

双盲纪律：

- reviewer-a / reviewer-b 分别拿各自 JSON；
- 未完成前不得读取对方 review 或 consensus；
- 两个 reviewer 名必须不同；
- `summary` 会输出逐字段一致率和 Cohen's kappa；
- 有任何分歧时 consensus 保持 `needs_review`，必须人工裁决；
- `pending`、`unverifiable`、`needs_review` 都不算通过。

目标口径：

- 首批 claim 样本：150–300 条，推荐 200；
- 双人一致率：先用 `>= 0.80` 作为最低门槛；
- 不可验证项单独统计，不允许混入通过率；
- 仍保持 `decision_eligible=false`，直到 10–20 个前向交易日、replay 通过率、
  claim coverage、Gold 审核一致率全部达标。

## 技术选型对比

| 方案 | 优点 | 缺点 | 结论 |
|---|---|---|---|
| 事后正则补引用 | 快 | 容易制造虚假证据 | 不采用 |
| 上游 lineage contract | 可审计、可复现 | 需要改数据链路 | 采用 |
| 直接让模型生成 Gold | 省人工 | 不是人工金标准 | 不采用 |
| JSON CLI + 静态 HTML | 简单、可版本化、无服务依赖 | 交互弱于 Web 应用 | 当前采用 |
| 带数据库的审核 Web 应用 | 交互和权限更强 | 维护成本高 | 样本扩大后再评估 |

可迁移知识点：先用文件型工作流验证 schema 和流程，再决定是否上数据库，是审计工具和标注平台常用的渐进式设计。
