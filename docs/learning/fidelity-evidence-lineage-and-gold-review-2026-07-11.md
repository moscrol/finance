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

## 技术选型对比

| 方案 | 优点 | 缺点 | 结论 |
|---|---|---|---|
| 事后正则补引用 | 快 | 容易制造虚假证据 | 不采用 |
| 上游 lineage contract | 可审计、可复现 | 需要改数据链路 | 采用 |
| 直接让模型生成 Gold | 省人工 | 不是人工金标准 | 不采用 |
| JSON CLI + 静态 HTML | 简单、可版本化、无服务依赖 | 交互弱于 Web 应用 | 当前采用 |
| 带数据库的审核 Web 应用 | 交互和权限更强 | 维护成本高 | 样本扩大后再评估 |

可迁移知识点：先用文件型工作流验证 schema 和流程，再决定是否上数据库，是审计工具和标注平台常用的渐进式设计。
