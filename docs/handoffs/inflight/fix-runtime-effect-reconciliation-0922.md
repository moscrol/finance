# Runtime 未知效果 / 费用对账

## 这个分支做什么
堵住「崩溃窗口里的外部请求可能已计费，但账本记 0」：恢复把未知窗口登记成 durable 凭证，花这份余额之前设闸。不做跨进程续跑驱动，不做自动对账（对账要能付钱的人来做，恢复只登记）。

## 当前状态
PR #865（base `fix/runtime-entry-identity-0922`；栈 3/3 顶层：#843 → #864 → #865，按序合、不跳层）。已推；带 `WIP:` 守卫。代码 `aec5a6d50`，门页 `a737888b3`；head 已前向合并 `gitea/main@f24a61a8a` 并含下两层最新 tip，四叶收据绑在本 head，代表三层一起落地后的树。未合并、未部署、未独审（候选挂 #75 队列）。

## 原则与决策
**未知效果双向保守：证据按没发生、成本按已发生。**
- 凭证挂 `EpisodeState.unreconciled_effects`，否塞进 `budget_snapshot`（脑裂）；对账 = 扣账 + 清空一次原子跃迁，清单即去重凭证。
- 恢复只登记不扣账；`charge_unknown_effects` 作用在快照；只扣调用格不扣秒；格数不够记 `slots_unavailable` 不写负余额；无快照有未清效果抛错。
- `restore_root_budget(unreconciled_effects=...)` 必填无默认；未派发的声明不进清单；不做 reserve-then-settle；`replay="safe"` 是幂等声明不是费用声明。

## 已验证
作者侧全量（`18495609f`）13059P/85S/2X/0F；`test_episode_effects.py` 10P；变异四处各正确变红。
#69 阳性对照：给 `restore_root_budget` 的清单参数加默认值 `()` → 恰好 `test_the_gate_has_no_default_so_a_forgetful_caller_cannot_slip_through` 一条红；还原 sha256 一致、复绿（`~/.finance-runtime/reviews/runtime-identity-effects-20260922/positive-controls/`）。
`gen_runtime_catalog.py --check` exit 0；`docs/runtime/events.md` 里 `episode_restore.py` 是 `model_error/tool_error/finish/finalization_recovery_outcome` 的发射点。
本 head 的四叶收据与 1F 四读数：同目录 `gate-*/`（合入前置）。

## 未验证 / 已知边界
没有对账的执行者：非空清单 = episode 停下等人，有意 fail closed，合入前请确认可接受。闸只拦 `restore_root_budget` 一扇门。秒数永远对不上。两位独立终审未满足。

## 下一步
1. #75 独立 QC。2. 用户确认后按 #843 → #864 → #865 顺序 `merge --record`，每合一张在 main tip 复跑 python 叶。3. 跨进程续跑驱动：`entry_identity_bound=True` 才允许自动续跑，续跑前对账。4. 审第二扇门。

## 踩过的坑
`close()`/`resumable()`/`_EpisodeLedger.put_state` 三处逐字段重建，加字段必须都透传；`close()` 里登记要排在 `_synthesize_finish` 之前。被收紧的断言（「恢复一字不写」→「不伪造结算、不推进程序计数器」）不是迁就实现。
