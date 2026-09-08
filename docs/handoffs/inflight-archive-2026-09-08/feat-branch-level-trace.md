# 在途交接 · feat/branch-level-trace（已合 #619 → main `1010970a`，8792 已切）

## 这个分支做什么
从「量分支内每批派发数」出发，候选口 8799 同题四遍量出两道顶并修掉，随后合入切流、8792 同题一遍闭环：
1. **账本口径 C**（用户拍）：秒是墙钟——分支只向父账本扣次数（`consume_call_slot`），父臂批结算记一次；起分支前父臂预留
   一批次数 + 一次合成的秒 + 保险丝 8 次（`admit_branches`），留不下就拒、拒绝带准入账。此前三支 150s 累加记 450s + 批结算 180s，
   540s 账本在墙钟 190s 归零、判官 unavailable。
2. **分支契约**：`required_outputs=()` 让模型只能自造 output id → `unknown_output` → 6/6 支必 partial。现在唯一 `branch_findings`，
   切后 8792 探针 3/3 支收尾被接受。
3. 分支级 trace（`batches / budget / invalid_actions / root_budget / admission`）进 `tool_result.telemetry` 与 durable `branch_completed`。

收据 `docs/verification/2026-09-07-branch-level-trace.md`；spec `2026-09-03-subagent-tool-design.md` §6-4 已改口径。

## 决策与被否方案
- C / 否 A 单独（父臂仍可能被挤）/ 否 B 单独（累加口径下分支跑满父臂仍死）。
- 分支契约给合法 output / 否 `unknown_output` 在分支降 FORMAT 回灌（多烧一轮）/ 否提示词「bindings 留空」（与宪法冲突）。
- 读数用候选口、合入切流等用户拍 / 否先切再量。
- quick 每批帽 4 不动：四遍 live 里咬与不咬各半，模型节奏（每批 1 个 vs 5–7 个）是首要变量，帽不是。

## 当前状态
8792=`1010970acc85`，回滚锚 `cutover-20260907g-branchtrace-rollback-8792.txt`（回 `d65ed0155eb9`）。切后同题探针
`probe-cutover-0907g/run_20260907_123827_249342`：父臂 completed（修复 1 轮）、judge repaired、`judge_unavailable_count=0`、
`content_degraded_count=0`、分支 3/3 `model_finish`、`invalid_actions=[]`、父账本秒分支前后 525.3 → 525.3、账本收尾剩 352s；
口径 `fact_theme_limit_heat_daily`×8 / `fact_market_daily`×4，数据日 2026-09-03 == 库内最新。
门禁：main tip `1010970a` 干净树 7995P/0F/76S 可采信；webapp 四件套绿（webapp 与 `d65ed015` 逐字节相同）。

## 未验证 / 已知边界
- live n=5 同题（候选口 4 + 8792 1）；两个修法机制确定性（`before == after_branches`、`invalid_actions == []`），比例不是。
- deep 两支 6 → 4 次是预留代价；`PARENT_TAIL_LLM_RESERVE=8` 是估的，max 余量 118 远不到，默认 40 的档位才会碰到。
- 分支自报缺口（缺一手公告等）是数据面 / 工具面真缺口。

## 下一步
1. A/B/C 28 题 max 全景：Codex 额度看用户；跑之前先用 `scripts/eval_variance_baseline.py` 同 rev 同题出翻转率基线，否则单次差异不能下结论。
2. 能力 frontier 向量（工具发现 / 证据产出 / 上下文效率 / 修复恢复 / 验证完整性 / 墙钟 / 分支健康度）：分支侧字段已在 `branch_completed` 里，
   缺的是 eval 侧按 run 聚合的一张表。
3. 分支模型节奏（每批 1 个 vs 5–7 个工具）为什么变——同模型同题两种都出现，可能与 `_append_tool_budget_state` 注入的余量文案有关，未量。

## 踩过的坑
- `audit_deploy_ledger.py record` 不带 `--ledger` 时写 `FINANCE_WS/state/deploy-ledger.jsonl`（app 自己的 startup 账本），
  看板读的是 `~/.finance-runtime/deploy-ledger.jsonl`——切流规程那条命令要补 `--port 8792 --ledger ~/.finance-runtime/deploy-ledger.jsonl`，本次两本都记了。
- `EpisodeEvent.payload` 走 `_json_freeze`：list 变 tuple。`invalid_action.disposition` 是协议层处置，与 `stop_reason` 是两层。
- 候选口 / 8792 `readiness` 的 `market_data_consistency` 红是日常窗口。
- 全量一遍 1 红是 `id()` 地址复用假红，本 PR 把那个测试改成持有引用。
