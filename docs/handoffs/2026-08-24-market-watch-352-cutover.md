# 2026-08-24 #352 盘面包链切

用户明示切端口。先合 Gitea #352，再把 8792 / 8796 钉到同一 SHA。

## 读数

| 项 | 值 |
|---|---|
| 合入 | #352 merged `af71f048`（含 `5840e537`） |
| 快照 | `~/.finance-runtime/finance-workspace-af71f0480889` |
| 回滚 8792 | `ln -sfh ~/.finance-runtime/finance-workspace-8688545b9104 /Users/a77/finance-workspace-runtime` + kickstart |
| 回滚 8796 | 启动器 `runtime_tree` 改回 `…/finance-workspace-76ee1e89ed8a` + kickstart sidecar |
| 8792 health | `rev=af71f0480889 / dirty=false / match=true`；readiness 13/13、`missing_critical=[]` |
| 8796 health | 同 SHA；用户目录仍是 `finance-workbench-capability-sidecar/users` |
| 长电 | `run_20260824_102946_149967` completed / 61.6s / degrade=0 / secret=0 / glm-5.2@zhipu；`fact_stock_daily`×4、`dataset=stock_daily`×16；无「没有连接本地市场数据」。个股检索超时，稿走条件化判断——不是切失败 |

## 坑

8796 不是临时 sidecar，是 LaunchAgent `com.a77.finance-workbench-capability-sidecar`。启动脚本把 `runtime_tree` **写死**。只 `kill` 旧进程会被 KeepAlive 拉回旧 SHA，账本会记成假切。

## 未做

未打 `~/backups/gitea-*.tar.gz`（1.3G）。P1 `R-20260824-04` 未做。#343 未合。
