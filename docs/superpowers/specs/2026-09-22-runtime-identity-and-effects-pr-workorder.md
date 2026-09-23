# 2026-09-22 runtime 行为合同：入口身份绑定 + 未知效果费用对账 推送与 PR 工单

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
上游：#843（`fix/runtime-closeout-0921`，本地 `e7e12a189` 领先远端 `a9a112dfb`；本地版含「fence incomplete streams and terminal delivery」）。三层叠放：#843 → 入口身份 → 费用对账，**合入必须按这个顺序**。姊妹：#75（独立 QC）。

## 背景与动机

- runtime 行为合同修复这条线（#798 → #834 → #843）的剩余项：跨进程恢复、身份、证据、单写者对账。09-22 补上两层，均未推、未合、未独审：
  - **入口身份绑定** `fix/runtime-entry-identity-0922`（HEAD `671fbffc5`，基线 `e7e12a189`，3 提交）：新模块 `intelligence/services/episode_entry_identity.py` + 检查点字段 + 恢复门 + adapter/app 盖章。洞的形状：多用户下拿到 episode 编号就能恢复别人的现场，授权快照与单写者锁都不响；检查点字段是崩掉的进程自己写的，拿它证归属 = 待校验数据自授权。四个选型：身份由入口对服务端 run 记录核验后签发（否「从旧日志读主人」、否信 `?user=`）；`None` 不是通配（两边都无才一致）；放 `ResearchRunContext` 尾部默认字段由 adapter 无条件覆写（否塞进任务合同）；`task_id` 铸出后才 `.bind()`。中途换主人 = 保存失败。坑：`restore_episode` 的 `close()/resumable()` 逐字段重建 `EpisodeState`，新字段不透传就「恢复一次丢主人」，已补透传 + 回归。全量 13044P/87S/2X **+1F**（`test_skill_timeout_degrades_one_module_and_continues`，`_SlowSkill` 睡 1.2s 对 `timeout_seconds=1`，与本改动无路径交集，基线树 5/5 绿 → 负载敏感既有红）。
  - **未知效果 / 费用对账** `fix/runtime-effect-reconciliation-0922`（HEAD `18495609f`，叠在 `671fbffc5` 上，2 提交）：两条记账路径都是事后结算，`budget_snapshot` 只在相位边界拍，崩在 `tool_request → tool_result → consume_call` 之间恢复方读到派发前余额，`restore_root_budget` 里「A future driver must reconcile unknown effects」悬空多轮无机制兜底。原则：**未知效果双向保守——证据按没发生、成本按已发生**。凭证挂 `EpisodeState.unreconciled_effects`；恢复只登记不扣账；`charge_unknown_effects` 作用在快照；只扣调用格不扣秒；格数不够记 `slots_unavailable` 不写负余额；无快照却有未清效果抛错；`restore_root_budget(unreconciled_effects=...)` 必填无默认；未派发的声明不进清单。全量 13059P/85S/2X/0F；新套件 `test_episode_effects.py` 10P；变异四处各正确变红。顺带修了事件发射扫描器两份副本漏 `episode_restore` 的 `synth.add()`。
- **已定的形态决策**：不做 reserve-then-settle（热路径代价，且本轮解决的是已存在日志怎么读）；`replay="safe"` 是效果幂等声明不是费用声明；身份只证「同一扇门同一会话」，不证崩溃前外部请求是否已执行，续跑仍不安全（下一步是跨进程恢复驱动，要求 `RestoreResult.entry_identity_bound=True` 才允许自动续跑）。

## 目标

1. 推送 #843 本地领先提交（先核 `git diff --stat gitea/fix/runtime-closeout-0921..fix/runtime-closeout-0921` 是否含代码；含代码则在 PR 评论写明 head 变动与收据失效）。
2. 推送两条新分支；开两张 PR：入口身份 base = `fix/runtime-closeout-0921`，费用对账 base = `fix/runtime-entry-identity-0922`。描述写明叠放顺序与「合入要按顺序」。
3. 顶层（费用对账 head）前向到最新 main 后低负载四叶；那条 1F 按 #59 分诊表口径给「单跑 ×3 + 低负载整文件 ×1」四个读数。
4. #75 独立 QC 三层各一份或合一份（审查者自造探针 + 作者测试分开记账）。
5. 用户确认后按 #843 → 身份 → 对账顺序 `merge --record`，每合一张在 main tip 复跑 python 叶；文档 `docs/agent-product-door.md` runtime 段随合入同提交更新（若分支未带，合前补）。

## 非目标（写死认领）

- ❌ 不做跨进程续跑驱动（下一张单：真实进程中断验收在临时目录做）。
- ❌ 不做自动对账（对账要能付钱的人来做，恢复只登记）。
- ❌ 不接 `EpisodeScope.user_id`（仍空串，避免漂进工具收据）。
- ❌ 不修 `test_skill_timeout_degrades…` 的 `sleep(1.2)` 与断言（负载敏感既有红，另立单）。
- ❌ 不部署 8792。

## 证据路径

| 文件 | 看什么 |
|---|---|
| `~/fwp-wt-runtime-entry-identity-0922/docs/handoffs/inflight/fix-runtime-entry-identity-0922.md`、`docs/handoffs/2026-09-22-runtime-entry-identity.md` | 四选型、被否方案、1F 分诊 |
| 分支 `fix/runtime-effect-reconciliation-0922`：`docs/handoffs/inflight/fix-runtime-effect-reconciliation-0922.md` | 原则、八条决策、变异读数、扫描器副本修补 |
| `intelligence/services/episode_entry_identity.py`、`episode_restore.py`（`close()/resumable()` 透传）、`episode_store` writer | 身份门与恢复门 |
| `intelligence/tests/test_episode_effects.py`、`test_episode_event_lanes.py`、`scripts/gen_runtime_catalog.py`、`docs/runtime/events.md` | 费用对账测试与事件目录 |
| `~/.finance-runtime/reviews/`（作者未建独立目录时以分支 `docs/verification/` 为准） | 收据与变异证据 |
| #843 PR 与 `fix/runtime-closeout-0921` 的 inflight | 上游剩余项：重复恢复与本机单写者保护 |

## 步骤

1. 开工三连；三棵/两棵树 `status --short` 为空（第二条分支与第一条同树切分支时先确认当前检出的是哪条）。
2. 推送三条分支；开两张 PR。
3. 顶层前向 main（`merge-tree`）；低负载四叶；1F 四读数。
4. 阳性对照（写进 PR）：把 `restore_episode.close()` 里的 `entry_identity` 透传删掉，恢复回归用例必须红；把 `restore_root_budget` 的 `unreconciled_effects` 加回默认值 `None`，「必填无默认」用例必须红；各还原后绿。
5. 交 #75；确认后按顺序合入。
6. INDEX #69 行；三个 inflight ≤3K。

## 验收

- [ ] 三条分支远端 SHA == 本地；两张 PR base 指向正确的上游分支。
- [ ] 顶层 head 四叶收据 revision == head；1F 分诊四读数落盘。
- [ ] 两条阳性对照各恰好红对应用例、还原绿。
- [ ] `docs/runtime/events.md` 里 `episode_restore.py` 作为 `model_error / tool_error / finish / finalization_recovery_outcome` 发射点可见（`gen_runtime_catalog.py --check` exit 0）。
- [ ] 合并记录含授权原话与出处；顺序 #843 → 身份 → 对账。

## 红线

- 只用 pathspec 提交；合入 main 等用户确认；不强推；按顺序合，不跳层。
- pytest / ruff 一律 `.venv-workbench/bin/python -m …`；全量前 `uptime` / 磁盘准入。
- 不动 8792、不写生产 users 根。
- 「手写字段清单的重建点」加字段先搜同类构造点（`replace()` 不出这问题，逐字段列举会）。
- 不写明文密钥。
