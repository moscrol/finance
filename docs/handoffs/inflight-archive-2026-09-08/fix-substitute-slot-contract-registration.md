# fix/substitute-slot-contract-registration

## 这个分支做什么

**生产回归 hotfix**。P1-b（#372）给 `compile_research_program` 加的
`substitute_observation` FactSlot 被 `episode_factory._required_output_ids`
汇进契约 output_ids，而该 id 未在 episode_factory 登记 →
`build_episode_context` fail-closed 抛 `ValueError: missing
_OUTPUT_DESCRIPTIONS['substitute_observation']`——**命中三词族（题材+个股+观察）
的题在 8792=`20858faf` 上整题炸**。发现于 #2 侦察时对 SPT 题冻结契约（03:2x，
夜间无用户流量窗口）。

## 修复

fact slot 进契约需要三处登记，全部补齐：
1. `_OUTPUT_DESCRIPTIONS`（缺则装配炸——本次炸点）；
2. `_ADVISORY_OUTPUT_IDS`（缺则可选取数收据被当必选格判失败——隐性第二坑）；
3. `_required_output_evidence_types` fact-slot 组（缺则回退全量能力列表误导预算）。

## 防复发

`test_substitute_slot_contract.py::test_every_program_fact_slot_is_registered_in_contract_layer`
把「三处登记」变成结构不变量：遍历 `_SLOT_BY_OPERATOR` 全部 slot 断言三处齐。
下一个人新增 FactSlot 漏任何一处 → 红。另一条回归锁原样复现生产炸点
（SPT 两题 decide_turn → build_episode_context 必须成功且槽位/工具映射正确）。

## 已验证

- 红→绿：炸点原样复现（ValueError）→ 修复后 52 过（探针全家 + market_watch + outlook）。
- 契约相关筛选 78 过；ruff 0。全量后台在跑。

## 教训（可复用）

- **新增 fact slot 必须 rg 全部消费方**：`required_fact_slots` 的消费不止
  strict pack/预取，还有 episode 契约装配这条汇入桥。
- 全量 6400P 绿不等于覆盖：没有用例走「三词族题→build_episode_context」，
  结构一致性测试比补单点用例更抗回归。
- 测试里连续 build_episode_context 要用唯一 task_id（root budget 注册表拒重）。
