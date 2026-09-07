# 在途交接 · feat/branch-level-trace（基座 gitea/main `504cbbc9`，PR #619）

## 这个分支做什么
09-07 四遍读数收据 §5 的「先量分支内每批派发数再动帽」——量的那一步，并且已经量出来了。分支 Episode 的
`outcome.events` 此前在 `ContinuousSubResearchWorker.run` 被丢掉，父臂只剩合计数。现在每支分支带 `stop_reason`、
逐批派发账 `batches`、预算账 `budget`（含 `batch_call_cap`）、终局拒绝码 `invalid_actions`；`sub_research` 的
telemetry 另带父账本分支前后余量 `root_budget`。同一 `branch_telemetry` 进 `tool_result.telemetry` 与 durable
`branch_completed`。收据 `docs/verification/2026-09-07-branch-level-trace.md`（§4 是 live 读数）。

## 决策与被否方案
- 派发账 / 拒绝码从事件重算 / 否 worker 自报——可校验，自报不可。
- 预算账由协调器从 `_BranchBudgetView` 读 / 否 worker 填——LyingWorker 测试钉住。
- 进摘要不进事件本体 / 否把分支整条事件流塞进父账本。
- 没账不写键 / 否写 0。
- **不切 8792 拿读数**：从本分支树起候选口 8799（生产启动器只改代码根与端口），同题跑两遍 / 否合入切流再跑——
  合入与切流按仓规等用户拍，候选口不碰生产。
- **只量不改**账本口径与每批帽：两者都是设计决定，见收据 §5 三个形状（A 秒=墙钟 / B 保留累加去重复 / C 准入分层预留）。

## 当前状态
提交 `66de98c2`（trace）→ `ad54d4b0`（拒绝码）→ 本次（父账本快照 + live 收据）。`test_sub_research*.py` 36P/0F，
8 个变异各击杀 ≥1；干净树全量见收据 §2。候选口 8799 已停。**未合、未切 8792。**

live 读数（同题两遍，`probe-branchtrace-0907`）：帽 4 在咬（17 批 8 批被拒、16/77 请求，拒时剩余次数都够）；
但 partial 不是它造成的——第 1 遍分支收尾被出口拒（各剩 38–81s），第 2 遍分支首轮模型 55–65s 后跑满 150s，
**父账本把三支 150s 累加记 450s、再被批结算记 180s，540s 账本在墙钟 190s 处归零 → 父臂 224s 停、判官 unavailable**。

## 未验证 / 已知边界
- 第 1 遍分支收尾拒绝码没带出来（摘要是之后加的）；单测复现的同形状是 `unknown_output`，待下一遍 live 判。
- 两遍 partial 原因不同，触发变量是 sol 首轮延迟（7s vs 60s）；n=2，别把它写成比例。
- `rejected_by_cap` 把每批帽与分支剩余次数两种 `tool_budget_exhausted` 记同一个数，靠 `remaining_slots_at_dispatch` 分。

## 下一步（待用户拍）
1. 账本口径：A / B / C 选一个（收据 §5）；我倾向 C。拍了再开分支改，`test_branch_view_settle*` 与 spec §6-4 跟着改。
2. 合入 #619 → 切 8792 → 同题再跑一遍读 `invalid_actions[*].code`；若 `unknown_output`，修法与 #616 同族。
3. 帽 4 等账本修完再动。

## 踩过的坑
- `EpisodeEvent.payload` 走 `_json_freeze`：list 变 tuple。
- `_event(seq, kind, **payload)` 这类测试助手与 payload 里的 `kind` 键撞名，直接构造 `EpisodeEvent`。
- `invalid_action.disposition` 是协议层处置（`integrity_violation`），与 Episode `stop_reason=invalid_model_finish` 是两层。
- 候选口起服务：tmux 会话 + 生产启动器改两行；`/api/health/ready` 的 `market_data_consistency` 红与 8792 同步，不是候选口的问题。
