# Runtime 入口身份绑定

## 这个分支做什么
接 #843 的恢复收尾：恢复前先问「这是谁的 episode」，补入口身份绑定；不碰续跑驱动、不碰费用对账（上层 #865）。

## 当前状态
PR #864（base `fix/runtime-closeout-0921`；栈 2/3：#843 → #864 → #865，按序合、不跳层）。已推；带 `WIP:` 守卫，用户确认合入前摘。代码 `691d0ad5c`，门页 `e3024f621`。未合并、未部署、未独审（候选挂 #75 队列）。被否方案见[日期快照](../2026-09-22-runtime-entry-identity.md)。

## 决策与被否方案
- 身份由入口对服务端 run 记录核验后签发；否「从旧日志读主人」（自授权）、否信 `?user=`。
- `None` 是值不是通配：两边都无才一致；否「未绑定谁都能恢复」、否「一律强制绑定」。
- 身份放 `ResearchRunContext` 尾部默认字段、adapter 无条件覆写；否塞进任务合同、否给 registry_factory 加参。
- episode 编号铸出后才 `.bind()`；中途换主人 = 保存失败。

## 已验证
作者侧全量（`671fbffc5`）13044P/87S/2X/1F；那 1F 是 `test_skill_timeout_degrades_one_module_and_continues`，负载敏感既有红（#59 分诊表同名条目），本分支不修。新套件 35P。
#69 阳性对照（顶层树 `18495609f`）：删 `restore_episode.close()` 的 `entry_identity` 透传 → 恰好 `test_recovery_never_unbinds_the_episode_it_just_read[True]` 一条红；还原 sha256 一致、复绿。
顶层 #865 前向 main 后的四叶收据与 1F 四读数见 `~/.finance-runtime/reviews/runtime-identity-effects-20260922/gate-*/`，本分支代码在被测树内。

## 未验证 / 已知边界
身份只证「同一扇门同一会话」，不证崩溃前外部请求是否已执行/已计费。`EpisodeScope.user_id` 仍空串。关联子 episode 恢复仍整体拒绝。两位独立终审未满足。

## 下一步
1. #75 独立 QC。2. 用户确认后按 #843 → #864 → #865 顺序 `gitea_pr.py merge --record`，每合一张在 main tip 复跑 python 叶。3. 跨进程恢复驱动：要求 `RestoreResult.entry_identity_bound=True` 才允许自动续跑。

## 踩过的坑
`restore_episode` 的 `close()`/`resumable()` 逐字段重建 `EpisodeState`，新增字段不透传就「恢复一次丢主人」；加字段先看这两处（费用对账轮第三处是 `_EpisodeLedger.put_state`）。
