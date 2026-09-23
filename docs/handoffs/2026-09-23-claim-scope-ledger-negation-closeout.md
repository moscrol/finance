# fix/claim-scope-ledger-negation-0923 · #65 后续修复 · 已合入（归档） · 2026-09-23 04:2x（S5）

**终态**：PR #872 → 主干 `bd2290c861419b30b406633b1620d09d30de71e5`（`gitea_pr.py merge --record`，回读三项全过；记录 `~/.finance-runtime/reviews/claim-scope-merge-65-20260922/merge-872.json`，授权原话「你按照最优方案继续推进」2026-09-22T18:12:08Z）。远端与本地分支已删，门禁树已清。

## 改了什么（只改离线判据与测试；`answer_claim_scope` / `check_answer_claims` 仍无生产路径 import，运行时零改动）

1. `scripts/check_answer_claims.py`：证据台账按子句判否定语境（`_ledger_flow_clauses` / `_LEDGER_NEGATION`），「本次未取得主力资金净流入数据」不再让 `fund_flow_evidence=True`；肯定子句（带数字新闻句）仍算；两组子句进 `context_diagnostics.fund_flow_ledger_clauses / _negated_clauses`。
2. `intelligence/services/answer_claim_scope.py`：`_LATEST_DAY_HEDGE_AFTER`，免责紧跟断言短语（同子句 ≤8 字）才放行；「…但成交额无法确认」对别的对象免责仍报（回归钉住）。

来源：`docs/verification/2026-09-22-claim-scope-merge-65/second-party-review.md` 发现 1 / 2。

## 门禁

- 第一轮 head `b058a0a1`：python 14332P/0F、frontend+e2e exit 0、registry 5/5——但跑的 23 分钟里主干合了 6 张，`--base-drift-max 5` 判作废。
- 前向合并 `e728e4a11` → head `0a258a09`：python **14383P/0F/85S/2X**（`gate-n4mE47Sb/pytest.json`，`scope.collected=14470`，可采信漂移 1）、frontend+e2e exit 0（e2e 34P）、registry 5/5、`merge-tree` 对 `99c2ff28b` 干净且零文件重叠。
- 合后两冻结 run 在 `bd2290c86` 重放 PARITY OK（`replay-on-main/`）。

## 未做

接入运行时（设计稿 `docs/superpowers/specs/2026-09-22-claim-scope-runtime-integration-design.md` §5 六条验收，另授权另立单）；召回率；#75 K3 事后审（候选树 `/Users/a77/fwp-gate-65-main`，现 detached @ `bd2290c86`）。
