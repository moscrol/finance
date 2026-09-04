# 2026-09-01 工单索引（分发用）

`docs/superpowers/specs/2026-08-28-backlog-workorders-INDEX.md` 当时不在 `gitea/main`。本文件只登记 09-01 起从本基座分发的单。

| # | 工单 | 优先级 | 主仓 | 一句话 |
|---|------|--------|------|--------|
| 20 | `2026-09-01-episode-budget-grant-workorder.md` | **P0** | 金融 | P0/P0.1 已提交。finalize 离线量完：生产 P95=26.9s，20s 地板证伪。P1 仍挂起。 |
| 22 | `2026-09-04-rag-worker-resident-memory-workorder.md` | **P0** | 金融（B 步在 KB 仓） | 生产 RAG worker 在请求间被整个换出（RSS 3.7 MB，机器 swap 14.4/15.4 GB），每次查询先付 20–60s 换入，30s 帽必超时。先量干净 p95，再 keepalive / mmap；预算闸在此之前一律不动。#21 号被 `perf/wiki-hybrid-25s` 与 `docs/finance-agent-bp`（PR #573）两棵未合分支各占一次，故跳到 22。 |
