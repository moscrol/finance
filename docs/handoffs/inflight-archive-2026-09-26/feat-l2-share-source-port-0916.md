# feat/l2-share-source-port-0916 · L2 闲鱼日包 / 百度分享源搬进主干

## 这个分支做什么
把主检出树里**已在生产每晚 20:40 跑**的 L2 资金流文件源管线（`baidu-share:xianyu-l2-7z`）从 `salvage/main-tree-20260916` 搬到主干。原作者未知，本单是搬运 + 审读。全景与运维收尾见 `docs/handoffs/2026-09-16-main-tree-salvage-port.md`。

## 决策与被否方案
- L2 代码根 = 本脚本所在树（CODE_ROOT）/ 否运营版的 `$DATA_ROOT` 执行：那是代码不在冻结快照里时的权宜；状态 / 缓存 / Cookie 由 `l2_paths.py` 按 env 与家目录解析（工单 #51）。
- 去掉 `l2-paused.flag` 短路 / 否保留：文件源没有 ClickHouse 断供那种故障形状；`L2_PAUSED=1` 环境变量仍是应急开关。
- `write_to_duckdb.py` 以主干为底叠 `current_source()` / 否整文件覆盖：覆盖会丢 `--repair-pct-chg`。
- `skills/l2-moneyflow/SKILL.md` 取树版 / 否主干版：主干版是 ClickHouse 文案，两边都是新文件无 base。
- 日包解包口径测试迁入本单 / 否留在资金面板单：那边不依赖 `scripts/moneyflow`。

## 当前状态
已提交 7dc17832 + 修正 8b4e1626（守卫先于前置件、代码根认 FINANCE_CODE_ROOT、撞名修复），已推 gitea，**PR #773**（http://127.0.0.1:3300/a77/finance-workspace-private/pulls/773）等用户审；`merge-tree` 对 main 干净；#772 已合入 c29a6401，本单对新主干重探仍干净。全量：ruff 通过，pytest 11141 passed / 0 failed / 81 skipped / 2 xfailed，收据 `~/.finance-runtime/test-receipts/20260916T132429Z-8b4e1626.json`（dirty=false）。第一轮全量 6 红已修并复现验证。

## 已验证
定向 109 通过（test_l2_file_pipeline / non_trading_day_l2_guard / eval_launchd_wiring / pipeline_p0 / method_flywheel）；pre-commit 11 道全过；`build_registry.py scan / check / check-parseability`；`check_path_literals.py` 无新增；`zsh -n` 两个脚本。

## 未验证 / 已知边界
- 没在 CODE_ROOT 执行环境真跑一次 `run_l2_pipeline.sh`（要百度网盘登录态 + 当日日包上架），只有静态断言与解包口径单测。
- 前端 / e2e 叶未跑（未改 webapp）。
- 装机副本 `~/.local/bin/nightly_full_review.sh` 仍是 DATA_ROOT 版，合入本身不改变生产。

## 下一步
用户审 PR → 合入 → 刷新 runtime 快照 + 重跑 launchd 安装脚本 → 观察一晚 `ops_pipeline_run_daily` → 退役主树覆盖层。

## 踩过的坑
`git merge-file` 遇到「两边都是新文件」会产出上百个假冲突；zsh 里 `git add -- $FILES` 整串成一个路径；用户级钩子把同一条命令里的 `push` 与 `merge-tree gitea/main` 拼成「直推 main」。
