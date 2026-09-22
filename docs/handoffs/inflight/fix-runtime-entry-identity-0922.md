# Runtime 入口身份绑定

## 这个分支做什么
接 #843 的恢复收尾：恢复前先问「这是谁的 episode」，补入口身份绑定；不碰续跑驱动、不碰费用对账。

## 当前状态
基线 e7e12a189（#843 最新提交），本分支新提交见 git log。代码已落：`episode_entry_identity.py` 新模块 + 检查点字段 + 恢复门 + adapter/app 盖章。未合并、未部署、未开独立审查。
背景与被否方案见[日期快照](../2026-09-22-runtime-entry-identity.md)。

## 决策与被否方案
- 身份由入口对着服务端 run 记录核验后签发；否「从旧日志读出主人」（自授权）、否信 `?user=` 自报。
- `None`（未绑定）是值不是通配：两边都无才算一致，一边有一边无判不匹配；否「未绑定谁都能恢复」、否「一律强制绑定」（会关掉离线复盘并推翻上百用例调用形状）。
- 身份放 `ResearchRunContext` 尾部默认字段，由 adapter 无条件覆写；否塞进任务合同（会漂进提示词/收据）、否给 registry_factory 加参（打断固定参数替身）。
- episode 编号铸出后才 `.bind()`；否装配期预绑（注入式 task_id 会把旧编号盖到新 episode）。
- 中途换主人 = 保存失败（同预算/授权/证据围栏）；否「以新为准」、否静默保留旧值。

## 已验证
新套件 35P；conformance+restore/store/writer/persistence/authorization 317P/3S/1X；adapter+agent_episode+session+steer+inbox 261P；workbench_api 126P；`-k episode|research_contract|run_store|restore|contract` 2040P；Ruff 改动文件全绿。
反例覆盖：跨用户/跨会话/跨 run/跨消息、未绑定↔已绑定两个方向、伪造落盘身份、过期截止下拒绝时零字节写入、恢复写回的检查点仍带主人。

## 未验证 / 已知边界
全量 `pytest -q` 未跑完（单机约 90 分钟量级），不能声称全绿；前端未跑。
身份只证「同一扇门同一会话」，不证崩溃前那次外部请求是否已执行/已计费——续跑仍不安全。
关联子 episode（父子任务）恢复仍整体拒绝，不在本轮。`EpisodeScope.user_id` 仍为空串，未接身份（避免漂进工具收据）。

## 下一步
1. 跑完全量测试再谈合入。2. 未知效果/费用对账。3. 跨进程恢复驱动（要求 `RestoreResult.entry_identity_bound=True` 才允许自动续跑），临时目录真实中断验收。

## 踩过的坑
`restore_episode` 的 `close()` / `resumable()` 重建 `EpisodeState` 时逐字段列举——新增字段不透传就会「恢复一次丢主人」，退化成谁都能接管；已补回归用例，后续加字段先看这两处。
测试用的 episode_id 是 `run-alpha:msg-alpha`，run/message id 本就在编号里，断言「身份不进事件流」只能用 user/conversation id。
