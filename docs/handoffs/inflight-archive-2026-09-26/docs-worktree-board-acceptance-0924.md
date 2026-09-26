# #84 看板全量验收交接

## 这个分支做什么
只载 #895 的全量验收报告；底为 main `5bf47a5ae9aa`。实现与受测树仍在 `/Users/a77/fwp-wt-board-hardening-0923`，#895 head 固定 `b26b8711a4826521a43a5a24fb488bdf53aa389e`。不要用本文档树的旧看板冒充候选。

## 决策与被否方案
- 报告另枝，不给 #895 追加文档提交，保住受测 head。
- 去掉验收运行器的全局保留变量后全量重跑；不改断言、不用单例绿覆盖全量红。
- 保留引用未知，不擅修仓外 plist；保持 WIP，不把无冲突当合入许可。
- 展开与收据索引：`docs/handoffs/2026-09-24-worktree-board-acceptance.md`。

## 当前状态
固定候选四叶通过；#895 仍 open/WIP，未合、未部署、未关闭 #812、未重开 K3、未删真实树。本文档分支的收据只签上述候选，不签本文档提交。验收进程已结束。

## 未验证 / 已知边界
- main `5bf47a5ae9aa` 较候选前进 28 提交 / 8 张合并，`--base-drift-max 5` exit 1；仍缺最新 main 集成候选的验收。
- 实机扫描完成，但 335 行均因 `com.kb.disclosure-scout.plist` 的 plistlib 解析失败带引用未知；plutil -lint 却通过，未修配置。
- 12 棵 ownership 树各两项 tracked deletion，保留；#64 完整判据与逐树授权未重验。
- Node 26.0.0（CI 配置 22）；85 个 Python 条件跳过、2X，E2E 两个非 desktop binding 跳过；不代生产库/真实模型/跨仓显式探针验收。

## 下一步
协调资源，在新集成候选前向最新 main 并绑定新收据；取得用户确认才可合入。报告与源码两枝分开，不移签、不关闭 #812、不拆树。

## 踩过的坑
全局 `GATE_KEEP_BASETEMP=1` 会被门禁测试子进程继承，使默认清理用例失败；1F/去变量1P/模块56P已证实。最终直跑全量 pytest + 现有收据校验，不把控制变量送进被测代码。旧红原件保留。

## 已验证
候选 Ruff + pytest 14665P/0F/85S/2X，collected=14752 未收窄；独立身份/范围校验 0；错 SHA 与漂移检查各 1。frontend 120P、E2E 34P/2S、registry 五项 0。所有成功运行首尾干净同 SHA。看板实机 JSON 335 行、288.76 秒、exit 0；未知不是删除许可。证据根 `~/.finance-runtime/reviews/worktree-board-hardening-20260923/`，正式 Python 在 `full-20260924T0024/`，其他叶和首红在 `full-20260923T2346/`。
