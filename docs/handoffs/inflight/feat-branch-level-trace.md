# 在途交接 · feat/branch-level-trace（基座 gitea/main `504cbbc9`，PR #619）

## 这个分支做什么
从「量分支内每批派发数」出发，候选口 8799 同题跑四遍，量出两道新顶并修掉：
1. **账本口径**（用户拍 C）：分支秒此前累加转记父账本（三支 150s 记 450s）+ 父臂批结算再记 180s，540s 账本在墙钟 190s 归零，
   父臂墙钟还剩 396s 却 `deadline_exhausted`、判官 unavailable。现在秒是墙钟：分支只向父账本扣次数（`consume_call_slot`），
   父臂批结算记一次；起分支前父臂预留一批次数 + 一次合成的秒 + 保险丝 8 次（`admit_branches`），留不下就拒、拒绝带准入账。
2. **分支契约**：`required_outputs=()` 让模型只能自造 output id → `unknown_output` → 6/6 支必 partial。现在声明唯一
   `branch_findings`，第 4 遍 3/3 支收尾被接受。

分支级 trace（`batches / budget / invalid_actions / root_budget / admission`）是量出这两道顶的手段，随 PR 一起进。
收据 `docs/verification/2026-09-07-branch-level-trace.md`（§4 两道顶、§5 C、§6 修法与第 3、4 遍读数）。

## 决策与被否方案
- C（A 口径 + B 预留）/ 否 A 单独（父臂仍可能被挤）/ 否 B 单独（累加口径下分支跑满父臂仍死）。
- 预留量取现有常数（`batch_call_cap` / `synthesis_reserve`）+ 一个新常数 `PARENT_TAIL_LLM_RESERVE=8` / 否再造一套档位表。
- 分支契约给一个合法 output / 否把 `unknown_output` 在分支里降成 FORMAT 回灌（多烧一轮且靠模型配合）/ 否提示词说「bindings 留空」（与宪法冲突）。
- 读数用候选口 8799（本分支树 + 生产启动器改两行）/ 否合入切流再跑——合入切流按仓规等用户拍。
- quick 每批帽 4 不动：第 1、2 遍在咬，第 3、4 遍模型改成每批 1 个工具一次没咬；它不是首要变量。

## 当前状态
6 个提交到 `64428242`，已推 gitea，PR #619 描述已更新。`test_sub_research*.py` 42P/0F（新增 15），14 个变异各击杀 ≥1；
干净树全量 7995P/0F/76S，`check_test_receipt.py` 可采信。候选口已停。**未合、未切 8792。**

## 未验证 / 已知边界
- live n=4（同题），第 3、4 遍各 1 次验证 C 与契约修法；机制是确定性的（`before == after_branches`、`invalid_actions == []`），比例不是。
- deep 档两支从 6 → 4 次是预留的代价；deep 起步 12 次的账本本来就小。
- `PARENT_TAIL_LLM_RESERVE=8` 是估的（消化 1 + 合成 1 + 判官 ≤3 + 修复 ≤2 + 余量），max 档余量 119 远不到；只在默认 40 的档位会碰到。
- 分支自报缺口（缺一手公告等）是数据面 / 工具面的真缺口，不是运行时约束。

## 下一步（待用户）
1. 合入 #619 → 切 8792 → 同题再跑一遍读 `branch_completed.stop_reason`（应 `model_finish`）与 `root_budget`。
2. A/B/C 28 题 max 全景（Codex 额度看用户）。
3. `test_run_agent_runtime_benchmark::test_live_runner_uses_fresh_context_per_backend_without_cross_arm_state` 改成持有引用（`id()` 地址复用假红，另立单）。

## 踩过的坑
- `EpisodeEvent.payload` 走 `_json_freeze`：list 变 tuple。
- 测试助手 `_event(seq, kind, **payload)` 与 payload 里的 `kind` 键撞名，直接构造 `EpisodeEvent`。
- `invalid_action.disposition` 是协议层处置（`integrity_violation`），与 Episode `stop_reason=invalid_model_finish` 是两层。
- 候选口 `/api/health/ready` 的 `market_data_consistency` 红与 8792 同步，日常窗口，不是候选口的问题。
- 全量一遍 1 红是 `id()` 地址复用抖动，单跑 / 复跑即绿。
