# 2026-08-24 #352 盘面包链切

用户明示切 8792。#352 合进 main 后，**只切主港**。8796 是解耦树，不合 main、不跟 8792 同 SHA。

## 读数

| 项 | 值 |
|---|---|
| 合入 | #352 merged `af71f048`（含 `5840e537`） |
| 8792 | `af71f048` / dirty=false / match=true；readiness 13/13 |
| 8796 | `76ee1e89`（解耦树 LaunchAgent）。误切到 `af71f048` 后已拨回 |
| 快照 8792 | `~/.finance-runtime/finance-workspace-af71f0480889` |
| 快照 8796 | `~/.finance-runtime/finance-workspace-76ee1e89ed8a` |
| 回滚 8792 | `ln -sfh ~/.finance-runtime/finance-workspace-8688545b9104 /Users/a77/finance-workspace-runtime` + kickstart |
| 回滚 8796 | 启动器 `runtime_tree` 改回 `…/76ee1e89ed8a` + kickstart sidecar（本次已做） |
| 长电（8792） | `run_20260824_102946_149967` completed / 61.6s / degrade=0 / secret=0 |

## 坑

8796 不是临时 sidecar，是 LaunchAgent `com.a77.finance-workbench-capability-sidecar`。启动脚本写死 `runtime_tree`。只 `kill` 会被 KeepAlive 拉回旧 SHA。

**合 main ≠ 两港对齐。** 主港跟主干，对照港跟实验树。

## 未做

未打 `~/backups/gitea-*.tar.gz`（1.3G）。P1 `R-20260824-04` 未做。#343 未合。
