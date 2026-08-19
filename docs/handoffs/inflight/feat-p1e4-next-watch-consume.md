# feat/p1e4-next-watch-consume

## 这个分支做什么
P1-E4：跟踪题「下期关注」写入既有 `checkpoints.jsonl`（`source=track_next_watch`），次日 foresight 强制对照。ask 与 continuous 都登记。

## 当前状态
HEAD `4dd56941`，树 `~/fwp-wt-p1e4-next-watch`。PR #229。**r3 live 过，可合。未合 main，不切 8792。** 轨道 C 同改 `conversation_orchestrator`，合完再开。

## 未验证 / 已知边界
- 从未切生产。合入后的 8792 部署按 acceptance-workflow，不在本单。
- Q2 episode E=21，略低于历史地板 23；两发复核超时（R-06），不挡 E4。
- 全量 `workbench-check` 本树未跑（定向 53P 独立收据在案）。

## 下一步
1. 用户确认后合 #229（pathspec，勿 `git add -A`）。
2. 合完再开轨道 C（E2）。不要因 A #227「B 可链切」就切 8792。

## 踩过的坑
- 真 `theme_track` 只在会话口；`live_probe ask` 会落到 `general_finance_qa` / `theme_analysis`。
- parse 绿 ≠ 入账：ingest 曾只挂 legacy ask-compose，live 走 `_complete_continuous_turn`。helper 在 pytest 下是 no-op，接线要用 spy 钉调用。
- 变异前先提交：sidecar health 看 `source_revision`，脏树 live 对不上 commit。

## 已验证
r3 `:8812` @ `4dd56941` dirty=false：Q1 入账 1 / Q2 入账 3。读数 `docs/verification/2026-08-19-p1e4-next-watch-live.md`。收据 `~/.finance-runtime/test-receipts/20260819T080415Z-4dd56941.json`。
