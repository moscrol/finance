# 在途交接 · feat/checkpoint-rule-id-bias（工单 INDEX #24 / PR #592）

> **09-16 当前状态更正**：用户已明确授权，PR #592 已合 main@c1f8416a，收口 #747 已合918f8d5a，主干四叶全绿；8792未切。实际收据 `docs/verification/2026-09-16-release-merge.md`，运行面接续 `docs/handoffs/inflight/fix-release-gate-closeout.md`。下文为合入前历史，“等合并”不再成立。

> 2026-09-15 更新：按 PR #592 质检意见前向合并 `gitea/main@1fef3d27`，四处冲突已解，全量 9,670P/0F。等合并授权。

## 这个分支做什么
可证伪点台账加 `rule_id / rule_verdict / rule_receipt`（读者 `calibrate.by_rule` + `render_report`），`checkpoint register --rule-id` 登记时**回显**该规则最近收据四态（不拦截）；新模块 `checkpoint_bias.py` 偏差目录 v1 四条（`late_streak / post_miss_streak / rule_not_firing / revenge_reentry`，只从台账 + 旁路库确定性算，算不出即 unverifiable）+ `checkpoint bias-scan`。设计稿 §10.2 第一条「理性 / 非理性按过程定义」的机器实现。

## 2026-09-15 前向合并（四处冲突）

质检意见（09-11）：「对 main 真冲突 `intelligence/cli.py`、`intelligence/services/checkpoints.py`，请 rebase 后重开验收」。实际前向合并撞到四处——本单加的字段与工单 #34（投影门禁）/ #37（情景树）加的字段落在同一批位置：

| 冲突 | 处置 |
|---|---|
| `checkpoints.py` 函数拆分 × 投影门禁 | 本单把 `register_checkpoint` 拆成纯函数 `build_checkpoint_record` + 写盘壳（为了「先 build 再扫偏差，id/ts 与落盘完全一致」）；main 在 `register_checkpoint` 里加了投影门禁。**门禁移进纯函数侧**——拆分后若只在 register 挡，CLI 的「先 build 再扫偏差」那条路径会绕开门。register 透传 `object_type / hindsight / projection_hash / model_id / user_authored` 五个参数 |
| `Calibration` / `calibrate` / `render_report` | 两个新维度并存：本单的 `by_rule`（按方法论规则）与 main 的 `by_object_type`（用户决策 / agent 判断 / 观察剧本）。四个桶一起累加，报告两段都出 |
| `cli.py` 两处 | 都是「各加各的函数」（本单 `_add_bias_source_args` / `_bias_sources` / `_scan_one`；main `personal-export` / observation 系列），两侧全留 |
| `ledger-map.md` / INDEX | ledger-map 保留本单的四字段行（是 main 那行的超集）+ main 独有的情景树行；INDEX 取 main 全表（含 #25 真状态与 #27+ 新行）+ 本分支真实的 #24 行 |

**测试随主干基线更新**（两条，都是基线漂移不是行为改变）：① 记录形状断言加 `object_type / hindsight / projection_hash`——main 已把它们改成恒在字段，本单只负责「不加 rule 四字段」；② `checkpoint_bias` 的规则夹具补 `sharing / owner`——main 的规则 schema（PR #589 第四刀）已改必填，不补则测试挂在校验上、测不到它要测的编译器行为。

## 当前状态
tip `641931d0`（merge 提交）。干净树全量 **9,670 passed / 0 failed / 77 skipped / 2 xfailed**（496 s，exit 0，日志 `/tmp/592-full.log`），ruff 全绿，merge-tree 对 main 干净。

## 未验证 / 已知边界
- 真库 `bias-scan` 读数是 09-05 那轮的（见本文件历史版本 / PR 正文），本轮未重跑——前向合并只动了字段装配与报告拼装，未动四条偏差判据。
- 本轮未跑前端 / e2e 叶子（本枝不碰 webapp）。

## 下一步
1. 用户过目 → 合并 PR #592（等确认，不自合）。
2. 合入后 INDEX #24 行改「已合」。

## 踩过的坑
- 合并中（`MERGE_HEAD` 存在）不能用 pathspec 提交：`git commit -m … -- <files>` 会静默不产生提交，`git log` 还停在旧尖。要先 `git commit --no-edit` 收口再 `--amend` 改信息。
