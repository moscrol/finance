# feat/judge-pending-review

## 这个分支做什么
W2 Phase 1：判官降级诚实化 + 后验复核台账。叠在 W1 `5af29bb1`，不合 W3。规格 §W2。

## 当前状态
**已实现、未推、未合。** 分类名与 W3 兼容：`judge_unavailable` / `content_degraded`。`not_applicable` 不进判官桶。半窗不足一次完整尝试不发独立判官。pending 标记进产物；索引默认 `~/.finance-runtime/rejudge-pending/index.jsonl`（`FINANCE_REJUDGE_PENDING_INDEX` 可改）。`scripts/rejudge_pending.py` 只写 `*-rejudge` 收据，不改已发布答案。

## 已验证
- 解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`
- 定向：degrade / rejudge / semantic / live_probe / smoke / adapter **294 passed**；相邻 237 passed。
- 全量 **5624 passed / 16 failed / 12 skipped**，收据 `~/.finance-runtime/test-receipts/20260819T0838*Z-5af29bb1.json`（dirty）。16F = ceiling/wiki-export 环境项，与 W1 同形。本单 +14（5610→5624）。
- 今日 live 目录 `~/fwp-wt-live-verify/state/live-verify/20260819T06*` **不存在**，未做 live 事后复核（W7 已报缺失）。夹具 `intelligence/eval/fixtures/rejudge-unavailable-run.json` 走出 confirm。

## 关键行为
- `judge_status=unavailable` → `judge_unavailable`（有无 timeout/exc 都算）；其余 degrade → `content_degraded`。
- 独立 `judge_provider` 路径：`remaining < complete_judge_attempt_seconds`（默认约 25s）→ 不调用 provider，issue=`semantic judge leftover window below one complete attempt`。
- 不放大 `semantic_judge_window_seconds` / `DEFAULT_JUDGE_TIMEOUT`。
- 翻案率：confirm=事后通过，overturn=事后否决/收窄。两者都可表示。

## 下一步 / Phase 2
1. 用户确认后开 PR；不合并 main、不推除非另嘱。
2. Phase 2（发布后可见批注）**未做**，等翻案率数据另立 spec。
3. 与 W3 合时：`gate_receipt` 计数应复用 `classify_degrade_counts`，勿再写一套规则。

## 踩过的坑
半窗闸只拦独立 provider，不拦 `judge_fn` / `primary_judge`。否则仓内大量 5s deadline 单测会全部 skip 判官。
