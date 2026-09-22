# Runtime 入口身份绑定

## 这个分支做什么
接 #843 的恢复收尾：恢复前先问「这是谁的 episode」，补入口身份绑定；不碰续跑驱动、不碰费用对账。

## 当前状态
基线 e7e12a189（#843 最新提交），改动已提交：新模块 `episode_entry_identity.py` + 检查点字段 + 恢复门 + adapter/app 盖章。未合并、未部署、未独审。背景与被否方案见[日期快照](../2026-09-22-runtime-entry-identity.md)。

## 决策与被否方案
- 身份由入口对服务端 run 记录核验后签发；否「从旧日志读主人」（自授权）、否信 `?user=` 自报。
- `None`（未绑定）是值不是通配：两边都无才一致，一有一无判不匹配；否「未绑定谁都能恢复」、否「一律强制绑定」（会关掉离线复盘并推翻上百用例）。
- 身份放 `ResearchRunContext` 尾部默认字段、由 adapter 无条件覆写；否塞进任务合同（会漂进提示词/收据）、否给 registry_factory 加参（打断固定参数替身）。
- episode 编号铸出后才 `.bind()`；否装配期预绑（注入式 task_id 会把旧号盖到新 episode）。
- 中途换主人 = 保存失败（同预算/授权/证据围栏）；否「以新为准」、否静默保留旧值。

## 已验证
全量 `pytest -q -p no:randomly`：13044P/87S/2X，**1F**（详下），38 分 21 秒。新套件 35P；conformance+restore/writer/persistence/authorization 317P；adapter+agent_episode+session/steer/inbox 261P；workbench_api 126P；Ruff 与 pre-commit 全部门禁绿。
反例：跨用户/会话/run/消息、未绑定↔已绑定双向、伪造落盘身份、过期截止下拒绝零写入、恢复写回仍带主人。

## 未验证 / 已知边界
那 1F：`test_workbench_conversation_integration::test_skill_timeout_degrades_one_module_and_continues`，`_SlowSkill` 睡 1.2s 对 `timeout_seconds=1`（0.2s 余量），不经 `_build_continuous_turn_adapter`、不碰 episode 存储/恢复；单跑与整文件跑均绿。未在同等负载下对照基线，只能说「无路径交集且负载敏感」。前端未跑。
身份只证「同一扇门同一会话」，不证崩溃前那次外部请求是否已执行/已计费；续跑仍不安全。
关联子 episode（父子任务）恢复仍整体拒绝。`EpisodeScope.user_id` 仍空串，未接身份（避免漂进工具收据）。

## 下一步
1. 未知效果/费用对账。2. 跨进程恢复驱动：要求 `RestoreResult.entry_identity_bound=True` 才允许自动续跑，临时目录做真实进程中断验收。3. 合入前复跑全量并复核那条负载敏感红。

## 踩过的坑
`restore_episode` 的 `close()` / `resumable()` 重建 `EpisodeState` 时逐字段列举——新增字段不透传就会「恢复一次丢主人」，退化成谁都能接管；已补回归用例，后续加字段先看这两处。
测试 episode_id 是 `run-alpha:msg-alpha`，run/message id 本就在编号里，「身份不进事件流」只能用 user/conversation id 断言。
