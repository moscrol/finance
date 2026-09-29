# 在途交接归档 · 2026-09-29 夜间盘点

main 上 `docs/handoffs/inflight/` 挂着 20 份交接，对应的分支都没开 PR，最后改动在 08-21~09-24。
这里只归档**代码已确认在 main 上、分支只剩交接文档改动**的 4 份。其余 16 份的分类见 Arena 会话盘点（`finance-repo-triage-0929.md`），需要原作者或用户认领后再处理。分支都保留，没删。

| 交接 | 分支 | 为什么可以归档 | 归档用的版本 |
|---|---|---|---|
| fix-eastmoney-circuit-breaker-0922 | `fix/eastmoney-circuit-breaker-0922` | 文中代码提交 `82ce1bb54` / `b8415a377` / `faa480ec1` 都是 main 的祖先；分支比 merge-base 多出的 2 个提交只改了交接本身 | 分支上的较新版本 |
| fix-local-plan-gate-alignment | `fix/local-plan-gate-alignment` | 代码 `4fbc8c42` 已随 `07d42891c` 进入 main；分支多出的 1 个提交只改交接 | 分支上的较新版本 |
| fix-daily-swap-lock-all-callers | `fix/daily-swap-lock-all-callers` | 文中列的 7 个代码提交（`601db6dd` 等）都在 main；分支多出的 10 个提交只改交接，另外还有一份 `2026-09-14-302132-backfill-prep.md`，一并归档到本目录 | 分支上的较新版本 |
| codex-8792-readiness-closeout-0928 | `codex/8792-readiness-closeout-0928` | 分支已经完全包含在 main 里（0 个独立提交）；文中写明「功能代码经 #948 合入并已部署，此分支只收口文档」 | main 上的版本 |

判断方法：`git merge-base` 之后的 diff 只涉及交接文件，再逐个核对交接里点名的代码提交是否 `--is-ancestor gitea/main`。
