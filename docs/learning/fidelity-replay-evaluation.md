# 现状忠实度与历史重放评测

> 目标：先证明 Agent 能准确描述“当时可见的现实与历史”，再讨论预测优化。
> 本评测只读 DuckDB / wiki，输出文件；任何缺失 PIT 证据都记为 `pending`。

## 两道验收

### 1. 现状忠实度

| 指标 | 自动 / 人审 | 定义 |
|---|---|---|
| 数字一致率 | 自动 | 答卷 `evidence_catalog` 的表、字段、实体、日期与 DuckDB 原值逐项比较 |
| 证据覆盖率 | 自动 | 阶段、主判断、方向、标的、阈值、假设中绑定有效证据引用的比例 |
| 截止违规率 | 自动 | `source_time > perspective_date` 的证据比例；目标必须为 0 |
| 实体归类准确率 | 人工金标准 | 公司是否被归到正确题材/产业链角色；不确定时 pending |
| 事实/推断混淆率 | 人工金标准 | Agent 声明类型与审定的 observation / inference / prediction 是否一致 |

自动核验只回答“源行是否一致”，不替人判断复杂语义。比如“涨家数 3200”可以自动对账；
“因此主线已切换”仍需人工金标准和历史重放。

### 2. 历史重放

每个 case 使用两个物理分离的文件：

1. `input.snapshot.json`：仅包含 D0 及以前的 DuckDB 行，并绑定 D0 当时的 wiki commit；
2. `outcome.snapshot.json`：答卷冻结后由独立命令生成，只供 T+1/T+3 裁定。

历史重放的人审指标：

- 事件时间线顺序准确率；
- 阶段特征是否与当时可得事实一致；
- 因果陈述是否绑定证据，是否遗漏关键中间变量或替代解释。

## 10 日 pilot

```bash
python3 scripts/fidelity_replay_eval.py pilot \
  --db db/market_feature_store.duckdb \
  --kb-root /path/to/knowledge-base-private \
  --start 2026-03-02 \
  --end 2026-07-03 \
  --count 10 \
  --out-dir /path/outside/repo/fidelity-replay-v1
```

`pilot` 只生成输入快照，不生成未来结果。答卷冻结后才能运行：

```bash
python3 scripts/fidelity_replay_eval.py outcomes \
  --plan /path/outside/repo/fidelity-replay-v1/pilot.plan.json \
  --db db/market_feature_store.duckdb \
  --out-dir /path/outside/repo/fidelity-replay-v1
```

## 金标准

```bash
python3 scripts/fidelity_replay_eval.py gold-template \
  --answer <answer.json> \
  --out <answer.gold.json>
```

每条 claim 由人填写：

- `expected_type`：`observation / inference / prediction`；
- `entity_classification`：`pass / fail / pending`；
- `timeline_sequence`：`pass / fail / pending`；
- `causal_evidence_binding`：`pass / fail / pending`。

不得把 `pending` 当作通过，也不得用今天的知识回填历史缺口。

Pilot 答卷使用显式 `claims` 列表，每条声明必须写 `declared_type` 并绑定
`evidence_catalog`；这样“数字是事实、阶段是推断、明日表现是预测”不会混成一段无法核验的文字。

## 审计现有台账

```bash
python3 scripts/fidelity_replay_eval.py audit-ledger \
  --ledger-dir docs/learning/forecast-review-ledger \
  --db db/market_feature_store.duckdb \
  --out-json /tmp/fidelity-report.json \
  --out-md /tmp/fidelity-report.md
```

所有报告固定输出 `decision_eligible=false`。只有扩大盲测证明指标稳定后，才另行讨论硬闸门。
