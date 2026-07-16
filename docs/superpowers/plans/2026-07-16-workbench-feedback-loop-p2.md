# Workbench P2 Feedback Loop Plan

**目标：** 不新增第二份 verdict 事实表，在现有双盲台账上补齐“统计可见、错因反思、批注候选、人工批准、次日注入”的闭环。

## Task 1：双盲胜率投影进 Workbench

- 复用 `scripts/dual_blind_forecast.py aggregate`，不重新定义命中口径。
- Workbench overview 投影 agent/source 的 direction hit/miss/partial、命中率和 25 样本进度。
- 样本 `<25` 明确标记“积累中”，不做优劣裁决；达到 25 后才允许按题式/类别比较。
- Validation UI 同时保留机构后验榜，避免把“卖方来源胜率”和“Agent 方向判断胜率”混为一类。

## Task 2：未命中反思 JSON 与 lessons

- verdict 是唯一裁定事实；miss/partial 按 date/agent/source 回链当日 answer，生成一份 bounded reflection context。
- 使用现有 OpenAI-compatible LLM 适配层一次批量反思；无 key/调用失败时写 pending 状态，不影响 verdict。
- 反思 JSON 只生成候选，不自动进入 prompt。人工 `approve-reflection` 后由唯一 writer 写入 `lessons.jsonl`。
- 每日答卷 prompt 只附最近 N 条 approved lessons，保留来源 date/agent/hypothesis 追踪。

## Task 3：§8 批注 → 硬规则候选

- 只解析 §8 下结构化三字段：问题、应该改成、下次硬规则。
- 非空“下次硬规则”进入 `rule_candidates.jsonl`，初始 pending；幂等 stable id 去重。
- `approve-rule`/`reject-rule` 由人工执行并追加状态事件；只有最新状态 approved 的规则进入 prompt。
- 重渲染继续由现有 `_keep_annotations` 保留原文，候选层不反写用户批注。

## Task 4：自动连接与验证

- 手工/自动 verdict 写入后触发 reflection sync；失败优雅降级。
- `dual_blind_auto.sh` 答卷前同步批注候选并读取 approved learning context。
- 更新 ledger map，登记 reflections、lessons、rule candidates 的 canonical 路径和唯一 writer。
- 覆盖幂等、LLM 失败、审批门、prompt 注入、25 样本门槛、API/UI 渲染测试。

## 明确不做

- 不自动批准 LLM 反思或用户批注规则。
- 不把 verdict 重复写入 foresight checkpoints。
- 不做 D6/D8 特征生成管线。
