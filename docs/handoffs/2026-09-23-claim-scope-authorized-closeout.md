# #65 文档与发布测试修复的授权收口 · 2026-09-23

## 后续检查索引

以下准备阶段冻结为 `264bc9d0d`。首次组合门禁另报取消测试清理时序 1F，原件保持 RED；受控复现、最小补修与下一轮 `retry-02/gates/` 原件见 `2026-09-23-cancel-test-cleanup-wait.md`。因此下面“两测试文件与 #885 逐字相同”只描述第一次冻结，不描述后续补修候选。最终合入回读仍在根下 `merge-883.json`，不能把第一轮 `gates/` 当成绿门禁。

## 授权与范围

用户最新原话：**“继续推进，可以合并的内容你就合并”**。出处：pi session `01a0cbdf-8033-71c3-9314-9cf6c26bc033`，紧接 #885 完整验证报告的用户消息。

本轮由 #883 同时承载原文档订正和 #885 的测试隔离修复。已在干净 `docs/claim-scope-final-state-0923` 中前向合并 `gitea/main@bbd53487f4cefdae97eae90f7322394d36e65462` 与 #885 head `0e9b4f3b7cb29eaa0f53dbfa95fa4d9483fd9c3c`；保留原提交祖先，不 squash、不强推。两测试文件与 #885 逐字相同，相对主干没有新增生产代码、前端或配置改动。

授权仅用于这条收尾链的具备条件内容；不启动 #75 独立模型审查、#76 L5 真实模型验收、claim-scope 运行时接入或生产部署。

## 发现与决定

- 旧快照 `9a0227986` 的全量 14567P/1F 仍是失败。原现场缺少唤醒屏障的 run_id，不能把时间关联冒充完整轨迹。
- #885 对同型故障作了受控复现：全类同名报告屏障让当前 run 在 queued 时被读取；旧实现对照 1P/1F，实例和 run_id 限定后 3P、相关模块 144P。原件及决定见 `2026-09-23-run-publication-test-isolation.md`。
- #885 head `0e9b4f3b7` 的完整门禁为 14569P/0F/85S/2X，前端、E2E、registry 通过。这份收据不签本次组合候选，因为主干已加入 #876，文档内容也不同。

| 采用 | 不采用 | 理由 |
|---|---|---|
| #883 承载两张 PR 的组合候选，冻结后重跑完整门禁 | 分别跑重叠全量，或把旧 head 收据拼给新树 | 一次完整验证覆盖实际合入内容，不增加生产改动 |
| 保留原始红记录，另写本轮状态 | 把旧失败改成通过 | 失败来源与后续修复必须可追溯 |
| #885 留具名承接记录 | 静默关闭或声称它另有一张 merge commit | PR 对象状态与 Git 内容已进入主干是不同事实 |

## 收据与合入回读

本轮原件根：`~/.finance-runtime/reviews/claim-scope-authorized-merge-20260923/`。

- `gates/runner.log`、`gates/python.log`、`gates/receipts/gate-*/pytest.json`：实际被测 revision、完整收集面和 Python 退出码。
- `gates/frontend/frontend.json` 与分步日志：前端六项、身份前后稳定性；`gates/registry-*.log`：五项 registry 结果。
- `gates/receipt-check.log`：精确 revision、完整范围、依赖及主干漂移复核。
- `merge-883.json`：授权原话、期待的 head/base、合成树、API 回读与 Git 父提交/树核验。原件不存在或任一门禁无结论，不视为已经合入。
- `pr-885-resolution.json`：#885 的 API 状态与其 head 已被合入候选包含的核验；若需关闭，必须先留下 #883 接替指针。

最终计数与合入状态以原件和 PR 回读为准，本文件不预填尚未完成的结果。提交后才跑门禁，跑完只更新树外记录与 PR，避免为写结论改变被测 head。

## 保留与后续

`9a0227986` 的原红收据、#885 红对照和完整绿收据均保留。#75 审计树 `fwp-gate-65-main/finance-workspace-private@da761024e`、原红测试树以及他人仍在使用的 `docs/closeout-workorders-0922` 不移动、不删除；`docs/claim-scope-merge-65` 也不清理。

主干若继续移动，先核对实际合成树与门禁候选，不把无冲突等同于全量通过。合入不等于运行时接入或真实金融验收完成。复用现有门禁与 Gitea 工具，不新增通用框架。
