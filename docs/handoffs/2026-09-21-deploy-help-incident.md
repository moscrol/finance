# 2026-09-21 部署入口事故与恢复记录

## 背景

本轮验收期间需要确认部署入口是否安全。旧版 `scripts/deploy_workbench_runtime.sh` 没有参数解析：传入 `--help` 不会显示帮助，而会继续执行默认部署流程。2026-09-21 20:59 左右，本轮助手执行了：

```text
zsh /Users/a77/finance-workspace-private/scripts/deploy_workbench_runtime.sh --help 2>&1 | head -80
```

这不是只读探测，而是真实执行了 rsync 和 launchd 重启。此前关于“未执行部署”的记述不正确，责任属于本轮执行者，不能归咎并发 agent。

## 发现顺序与处置

1. 8792 无法连接，启动日志出现 `TypeError: Run.__init__() got an unexpected keyword argument 'maintenance_launch'`；原运行目录的源码被覆盖。
2. 先保留事故现场：运行目录的 tracked diff、status、启动错误日志、launchd 状态均保存到 `~/.finance-runtime/reviews/release-831-20260921/incident-8792/`。没有恢复覆盖原目录，也没有手改用户数据。
3. 从已知 `adcda94b5e401158f1c3aa51f210e1e8d0f0b713` 新建干净恢复快照 `finance-workspace-adcda94b5e40-recovery-20260921`，切换 `/Users/a77/finance-workspace-runtime` 软链，记录 switch 账本并重新 bootstrap。
4. 恢复后 health 为 `healthy`，`source_dirty=false`，`code_matches_repo=true`，加载根在 recovery 快照；部署账本检查通过。
5. readiness 保留真实失败：数据库最新交易日为 `2026-09-18`，快照日期为 `2026-09-21`，唯一失败 `market_data_consistency`。没有为了过门禁改行情数据。
6. 真实 episode 探针 `run_20260921_213139_441392` 完成；`degrade_count=0`、`content_degraded_count=0`、`judge_unavailable_count=0`，secret/public scan 均为 0。判官修复了一个内部过程表述泄露，事实口径含 `fact_stock_daily` 等。

## 修复决策

- `--help` / `-h` 在环境检查和任何副作用之前退出；空参数、未知参数和组合错误拒绝。
- 真实执行必须同时具备 `--apply`、完整 40 位小写 `--expect-revision`、显式 `WORKBENCH_REPO_ROOT`。
- 源树必须是干净 Git 工作树且 revision 精确匹配；运行目标必须是 standalone 目录。
- 拒绝覆盖 `.git` 文件、目录、悬空链接、Git 工作树，以及 `intelligence/` 软链，避免沿软链覆盖版本快照。
- 保留 `rsync` 形态只服务旧式 standalone 目标；版本化 Git 快照只能新建并切换运行软链，按 `docs/workflows/acceptance-workflow.md` 操作。

没有选择“只在文档里提醒不要传 `--help`”，因为事故已经证明人工约定不能覆盖危险入口；也没有直接改生产快照来验证修复，因为那会销毁事故证据并重新扩大副作用面。

## 验证与证据

修复分支 `fix/deploy-help-fail-closed-0921`，提交 `4f9a2af56` 已推送，PR #846 保持 WIP。基础防护干净收据为 `~/.finance-runtime/test-receipts/20260921T135024Z-4f9a2af5.json`，对应 `57 passed`；加入 `intelligence/` 软链拒绝后，改动树定向收据为 `~/.finance-runtime/test-receipts/20260921T135920Z-4f9a2af5.json`，对应 `59 passed`，不是该基础提交的干净认证。软链补丁的语法、定向 Ruff 通过；全仓 Ruff 的通过记录属于基础版本。最终提交的复验以 PR 评论及在途交接为准。

前两轮变异在专用修复工作树中串行执行并恢复：移除版本/脏源检查后 3 个测试失败；移除帮助/Git 快照检查后 6 个测试失败。两轮失败收据分别为 `20260921T134201Z-028a251a.json`、`20260921T134243Z-028a251a.json`。第三轮在树外副本 `~/.finance-runtime/reviews/release-831-20260921/deploy-link-mutation/` 中移除 `intelligence/` 软链检查，2 个测试失败；该副本保留变异，不可用于部署。所有测试均使用临时源/目标、伪造 Python、记录型 rsync/launchctl，不触生产。

事故证据：

- `~/.finance-runtime/reviews/release-831-20260921/incident-8792/old-status.txt`
- `~/.finance-runtime/reviews/release-831-20260921/incident-8792/old-tracked.diff`
- `~/.finance-runtime/reviews/release-831-20260921/incident-8792/startup-error-before.log`
- `~/.finance-runtime/reviews/release-831-20260921/incident-8792/health-final.json`
- `~/.finance-runtime/reviews/release-831-20260921/incident-8792/readiness-final.json`
- `~/.finance-runtime/reviews/release-831-20260921/incident-8792/grounded-smoke.json`

## 未完成与禁止事项

- #846 尚未独立验收、解除 WIP 或合并；当前修复不代表已部署。
- #831 旧生产基线候选 `165038afaeb899af3c93e808136176a8dcd2fd84` 的通过结果不能替代 main `028a251a1b2ca98245326a6b59376f4f7f8e5e81` 与原 head `ea5c3a94618a15e37f914c8b1a13e271875e4337` 的合流树 `c4ebdbd4d725a73588fe5990cedfc47a9702c265` 验收。该合流只确认无冲突，未测。候选 Python 收据 `20260921T131501Z-165038af.json` 为 12446 passed/85 skipped/2 xfailed；前端规范收据 `~/.finance-runtime/reviews/release-831-20260921/frontend-receipt/frontend.json` 六步全绿、身份稳定且干净，110 单测、E2E 34 passed/2 skipped；同根 registry 目录保留五项通过日志。不得据此代签当前合流树。#831 仅测试夹具和代码地图工具，无须重启生产；最新 main 含已回滚 K3 变更，不可直接部署。
- 包装器失败保留：`run_main_gate.sh` 的变量邻接全角字符导致 unbound variable；registry 留证壳首次因旧 Bash 空数组展开报错；前端最初目录错误、宿主解释器缺 uvicorn。后续正确环境复验不抹去原失败。
- 原被覆盖目录是 `~/.finance-runtime/finance-workspace-adcda94b5e40`，不在 incident 证据目录内，不再作为回滚目标。事故原始会话 `~/.pi/agent/sessions/--Users-a77-finance-workspace-private--/2026-09-21T12-42-38-633Z_01a0c3fd-64a8-7216-baa4-fde82fbbb078.jsonl` 在 `2026-09-21T12:59:50.886Z` 记录了误执行；证据与回滚材料均不清理。
- 工具沉淀复用实际脚本和正式回归，不另造部署器；跨项目方法写入记忆。`~/harness-reference` 当时 ahead 1 且 BUILD.md 有他人改动，本轮不写，通用件索引回填留待该树归属澄清。
- readiness 的行情日期差需要由数据链路负责人确认；不要关闭检查或补写数据制造全绿。
- 旧主树中的危险脚本在 #846 合并前仍不可执行，尤其不能运行其 `--help`。
