# Workbench P2 Feedback Loop Verification

- 日期：2026-07-16
- 分支：`fix/workbench-product-maturity-p0`
- 结论：P2 本地验收通过；未合并 main，未部署 canonical 8792

## 胜率看板

Workbench 验证页新增“双盲 verdict 后验”，直接复用
`dual_blind_forecast.py aggregate`，没有复制或改写 verdict 事实。

展示口径：

- 严格命中率：`hit / (hit + miss + partial)`。
- 半分校准率：`(hit + 0.5 × partial) / 已裁定`。
- 每个 Agent / source 独立累计，方向样本达到 25 才显示“可分题式统计”。
- `direction:*` 与 `market:*` 命名空间现已正确归类，不再掉进 unknown。

当前真实台账投影：Codex/duckdb 与 Claude/duckdb 各 4/25 个方向样本，均为
`0 hit / 2 miss / 2 partial`，严格命中率 0%，半分校准率 25%。样本不足，因此
看板只显示“样本积累中”，不做优劣裁决。

## 错因反思与 lessons

miss/partial 会按 date/agent/source 回链冻结答卷，一次批量生成 reflection JSON。
反思只包含事前答卷、相关 hypothesis/evidence 和事后 verdict，禁止补写当时不可见信息。

- LLM 可用：生成 `pending_review` 候选。
- LLM 不可用/输出不可解析：生成 `pending_llm`，后续自动重试，不阻断 verdict。
- 历史 verdict 找不到源答卷：计入 `orphaned`，不凭空生成反思。
- 人工批准后才写 `lessons.jsonl`；驳回后从审批队列移除。
- source fingerprint 绑定审批，原 verdict/context 变化后旧批准不会掩盖新候选。

真实 ledger 无 LLM 烟测生成 10 个 reflection 批次；2026-07-06 两个 briefing 流没有
对应源答卷，被正确记录为 orphaned。

## §8 批注规则回流

解析结构化“问题 / 应该改成 / 下次硬规则”，以 stable id 幂等写入
`rule_candidates.jsonl`。规则采用 append-only 状态事件，支持 approve/reject；只有
latest status=approved 的规则进入 prompt。

Workbench 验证页现在直接展示 pending reflection/rule，支持批准和驳回。API 对反思
文件名做路径约束，审批写入不修改 verdict。

每日双盲自动链会：

1. 重试 pending reflection；
2. 同步 §8 规则候选；
3. 读取最近 5 条 approved lessons/rules；
4. 作为“历史 prior、非市场事实”附入两位考生的事前 prompt。

## 全量验收

```text
Full Python: 1822 passed, 1 skipped（8 条既有 utcnow deprecation warnings）
Frontend lint: PASS
Frontend typecheck: PASS
Frontend unit: 56 passed
Frontend production build: PASS
Playwright E2E: 15 passed（desktop/tablet/mobile）
Registry checks: 4/4 PASS
```

第一次 E2E 启动命中 Homebrew Python 3.14，因没有 uvicorn 未进入测试；显式设置
`WORKBENCH_PYTHON=/Users/a77/finance-workspace-private/.venv-workbench/bin/python` 后
15/15 通过。这是测试解释器选择问题，不是产品失败。
