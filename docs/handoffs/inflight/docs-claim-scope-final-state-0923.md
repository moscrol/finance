# #65 与发布测试隔离的授权收口 · 2026-09-23

## 这个分支做什么

#883 承载文档订正与 #885 测试修复，按用户“继续推进，可以合并的内容你就合并”授权推进。决策见 `docs/handoffs/2026-09-23-claim-scope-authorized-closeout.md`。

## 决策与被否方案

- 已前向 `main@bbd53487f` 并收入 #885 head `0e9b4f3b7`，保留提交祖先；否决把旧收据改签新组合。
- 单一组合候选完整验证后合 #883，#885 留承接记录；否决静默关 PR。
- 保留旧红现场及 #75 冻结审计树；不追主干移动旧证据对象。

## 当前状态

原始 `9a0227986` 全量 1F 保留；同型测试隔离缺陷已由 #885 修复，未改生产状态机。用户已给本轮合入授权，不再等待同一句确认。实际门禁与合入状态从下列原件回读，不能把文件里的待办当作仍未执行。

本轮证据根 `~/.finance-runtime/reviews/claim-scope-authorized-merge-20260923/`：`gates/runner.log`、`gates/receipts/gate-*/pytest.json`、`gates/frontend/frontend.json`、`gates/registry-*.log`、`gates/receipt-check.log`、`merge-883.json`、`pr-885-resolution.json`。缺失、失败或身份不符即不能签通过。

## 已验证

#885 旧屏障对照 1P/1F、修后 3P、模块 144P，head 0e9 完整门禁通过；仅对旧 head 成立。当前两测试文件与 0e9 逐字相同，相对主干只有测试与文档。历史 parity 及 #858/#879 回读见原日期快照；不改写旧原件。

## 未验证 / 已知边界

#75 K3、#76 L5、运行时接入及设计稿 §5 验收不在本次授权内；8792 不操作。每份收据只签实际被测 revision，不覆盖后来 main。

## 下一步

按确切候选回读本轮门禁、PR 与 merge record；若未合且门禁全绿，执行已授权合入；若已合，核验 #885 接替记录及清理归属，不重复合并。后续验收单独处理。

## 踩过的坑

#854 API merged=false 不推翻 Git 合入事实。`docs/closeout-workorders-0922`、#75 审计树、原红测试树及 `docs/claim-scope-merge-65` 必须保留。只清理本轮完成且 clean 的自有树，不触碰他人在途内容。
