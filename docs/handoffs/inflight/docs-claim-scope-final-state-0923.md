# #65 质检补验与文档终态 · 2026-09-23

## 这个分支做什么

修正 #65 的 INDEX、旧待办和 #75/#76 候选卡，补主干快照门禁；只改文档。详情见 `docs/handoffs/2026-09-23-claim-scope-final-state.md`。

## 决策与被否方案

- 独立树补验 `9a0227986`，不用脏主树或旧 head 收据改签。
- 保留 #75 的 `da761024e` 审计树，不追主干移动审查对象。
- 不接管 #858 在途树；已有其他会话新提交。
- parity 元数据写旁置 manifest，不覆写旧证据或修改 CLI 接口。

## 当前状态

全量已结束，整体 RED：`9a0227986` 上 14567P/1F/85S/2X，collected=14655；前端六步与 registry 五项均 0。失败是 `test_real_turn_terminal_claim_does_not_publish_an_incomplete_artifact_list` 第 160 行读到 queued 而非 completed；单独复跑 1P，根因未定位，不能抹掉全量红。文档已提交推送，PR [#883](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/883) 保留 WIP，未合 main；与 `4315d9d5f` 的预览合并无冲突。

证据根 `~/.finance-runtime/reviews/claim-scope-final-20260923/`；唯一全量收据 `receipts/gate-R2GxQOZc/pytest.json`，整体退出码在 `runner.log`。

## 已验证

#858/#879 merge record 回读三项成立；#879 本轮分支与工作树已清理。两冻结回答在 `9a0227986` 的完整 JSON 与 #872 修复后基线相等，元数据见上述证据根 `parity-manifest.json`。文档 diff 与提交前检查通过。

## 未验证 / 已知边界

#75 独立 K3 审查、#76 L5 live、运行时接入及设计稿 §5 六条均未完成。门禁只签被测快照，不冒充本分支新 head 或之后 main 的收据。生产 8792 未操作。

## 下一步

先定位上述全量红项并取得新完整绿收据，再按确切候选核对门禁与授权后合文档 PR。不要把这份主干快照收据移签给文档 head。#75/#76 与运行时接入的授权边界不变。

## 踩过的坑

#854 API closed/merged=false 与 Git 已合入是两件事。旧 #872 缺陷已修，不重复派修。`docs/closeout-workorders-0922` 已有他人新工作，不能按已合分支清理。只复用现有门禁，本轮无新增通用工具。
