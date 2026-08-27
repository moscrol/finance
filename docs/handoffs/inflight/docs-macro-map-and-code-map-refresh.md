# 在途交接 · docs/macro-map-and-code-map-refresh

更新：2026-08-27 20:30 CST

## 这个分支做什么

宏观理解补强两件（元资产盘点 Phase A 的仓内落点，路线图全文在 agent-memory
`00_inbox/2026-08-27-meta-asset-inventory-and-bootstrap-roadmap.md`）：
① AGENTS.md 代码地图节加「五层地图路由表」；② `scripts/install_code_map_refresh.py`
——code map 夜间刷新的 launchd 安装器 + 无人值守运行器。

## 决策与被否方案

- 选 launchd 夜跑（04:25）／否 commit 钩子——build 走 uvx，全量分钟级，拖慢每次提交；
  否 SessionStart 懒重建——拖慢开工且并发会话可能同时写 graph.db。实测增量 update 仅
  11s，但首次/全量仍慢，夜跑口径不变。
- 路由表只加 AGENTS.md 一处／否 CLAUDE.md 同步复制——两份清单必漂（BUILD 模式 6）。
- `run` 在 status exit=3 时不 build、退出 3／否「无脑重建」——错误状态上重建会掩盖真问题
  （fail closed）。
- plist 用 stdlib plistlib 生成 + plutil -lint／否 sed 模板——多字节路径不可靠
  （沿用 checkpoint-recheck-mac-setup 的既有结论）。

## 当前状态

- 已验证 [实测 2026-08-27]：`install`（plutil -lint 过、launchctl bootstrap gui 域成功、
  calendarinterval 已注册）；`run` 两分支——stale→build exit 0（n=19771 @fea0633、
  增量 11s）、fresh→skip。ruff 过。
- launchd 挂载是**本机系统状态**，已生效、与分支合并与否无关。回滚：
  `python3 scripts/install_code_map_refresh.py uninstall`。
- 本分支基 gitea/main=fea0633e，单提交含本文档；合 main 等用户确认。
- 未做（原因见路线图待办节）：harness-reference KIT/BUILD 回写一行——其本地树有他人在途
  改动（BUILD/KIT/PLAYBOOK/TOOLKIT 四份带 M）；`agent-run-review` 迁共享仓。

## 坑

- launchd 域 PATH 不含 homebrew，uvx 找不到会让夜跑静默失败——安装器已在生成 plist 时把
  `dirname(uvx)` 注入 EnvironmentVariables.PATH；**换机/换 python 后要重跑 install**。
- plist 钉住安装时所在的树与解释器路径；只在主检出树上安装，别在临时 worktree。
