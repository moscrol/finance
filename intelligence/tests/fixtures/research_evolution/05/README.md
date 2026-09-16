# 05 夹具：用户价值测量（全部 `synthetic`）

由 `intelligence/tests/product_value_fixtures.py` 生成，**不要手改**；改场景后重跑：

```bash
.venv-workbench/bin/python -m intelligence.tests.product_value_fixtures
```

`test_product_value_cli.py::test_fixtures_on_disk_match_generator` 会在漂移时变红。所有事件 `provenance.kind=synthetic`，只用于工程验收；它们进不了真人分母，`summarize` 会把它们隔离到 `synthetic_check`。

| 目录 | 场景 | 预期收据 / 读数 |
|---|---|---|
| `complete_pair/` | 完整配对（fact_check，p01 交叉做两案） | `valid`；原流程 45 分钟（10:00–10:50 扣 5 分钟预登记暂停），辅助 20 分钟，省时 0.5556；质量 7 → 8，严重错误 0；已知费用 CNY 0.46（span 级 0.15 被 run 级覆盖，不重复加） |
| `failed_retry/` | 第一次 run 失败（无 report.json）后重试完成，第二次降级 | `incomplete`；尝试 2（失败 1 / 降级 1），任务仍算完成；已知 CNY 0.12；`c-fr-2` 只有 tokens 无费率 → `unknown_cost_components`；省时 0.4 |
| `cost_gaps/` | 缺费率 / 自审缺用量 / 失败重试无账 / 人工救援未计费 / 混币种；未同意盲审 | `incomplete`；已知 `{CNY 0.30, USD 0.05}` 不合并；未知组件 3 项；`usage_missing:c-cg-r`；评审被排除（`blind_review_consent_missing`），质量 unknown；原流程计时 `estimated` |
| `empty_cohort/` | 只有一条同意记录 | 无收据；总结 `engineering_complete / pending / unstarted`，全部值 null |
| `cohort_signals/` | 主动复用（1 主动 / 1 人工催促 / 1 来源未知）、回检（1 完成 / 1 仅查看 / 1 自动）、付款与退款、托管费 | `synthetic_check`：复用 1/3 → fail；回检 0.5（j-01 仅查看且自动回检不计）；续费 `renewal_window_not_reached`（p05 退款不算首付）；成本 unknown |
| `all/` | 以上四个有事件的场景合并 | 三份收据 `valid / incomplete / incomplete`；总结 `engineering_complete / pending / unstarted`，`synthetic=true` |

## 命令

```bash
PY=.venv-workbench/bin/python
F=intelligence/tests/fixtures/research_evolution/05

$PY -m intelligence.eval.product_value validate  --events $F/all/events.jsonl --protocol $F/protocol.yaml
# → accepted 69 / rejected [] / conflicts []，exit 0

$PY -m intelligence.eval.product_value summarize --events $F/all/events.jsonl --protocol $F/protocol.yaml \
    --evidence-json $F/all/evidence.json --due-rechecks $F/all/due_rechecks.json --out-dir /tmp/pv-out
# → receipts {pair-01: valid, pair-02: incomplete, pair-03: incomplete}
# → engineering_status=engineering_complete, field_status=pending, commercial_status=unstarted, synthetic=true
# → /tmp/pv-out/{receipt-pair-0N.json,.md, pilot-summary.json,.md}，Markdown 顶部带 SYNTHETIC 横幅

$PY -m intelligence.eval.product_value measure --events $F/complete_pair/events.jsonl --protocol $F/protocol.yaml --out-dir /tmp/pv-one
# 不给 --evidence-json：run 引用记 missing → incomplete（run_evidence_missing:r-cp-1）
```

`protocol.yaml` 已冻结（含 `protocol_hash`）；改任何字段再喂给 CLI 会以 exit 2 拒绝，这是刻意的：改判据要另开一版协议。
