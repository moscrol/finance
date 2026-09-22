# fix/claim-scope-ledger-negation-0923 · #65 后续：口径越界 lint 两处判据缺陷 · 2026-09-23 凌晨（S5）

**边界**：只改离线判据（`intelligence/services/answer_claim_scope.py`、`scripts/check_answer_claims.py`）与其测试；两者仍无任何生产路径 import，运行时行为零改动；零 live；不动 8792。

## 改了什么

1. **证据台账正则不辨否定语境（fail-open，中）**：`check_answer_claims._ledger_has_fund_flow` 原对整份 `outcome.evidence` 子串匹配，工具回包一句「本次未取得主力资金净流入数据」就让 `fund_flow_evidence=True`，答案里的「资金集中流入」被放行。现改为按子句判（`_ledger_flow_clauses`）：资金流名词落在否定 / 缺失子句（`_LEDGER_NEGATION`）不算，肯定子句（带数字的新闻句）仍算；两组子句进 `context_diagnostics.fund_flow_ledger_clauses / _negated_clauses` 供人核（L5 条件卡 3b 要求人读原文，现在原文直接在收据里）。
2. **「无法确认」免责句误报（低）**：`_latest_trading_day_issue` 新增 `_LATEST_DAY_HEDGE_AFTER`——免责（无法 / 无从 / 不能 / 难以 + 确认 / 核验 / 核实 / 确定 / 判断 / 验证 / 核对）**紧跟断言短语、同一子句内 ≤8 字**才放行；刻意不进句级词表，否则「X 为最近一个已收盘交易日，但成交额无法确认」会静默（回归钉住）。

来源：`docs/verification/2026-09-22-claim-scope-merge-65/second-party-review.md` 发现 1 / 2，探针原句作夹具。

## 读数（写于动作完成之后）

- ruff 0；定向 `test_answer_claim_scope / test_check_answer_claims / test_date_claim_jurisdiction` 全绿（新增 4 条）。
- 两冻结 run（材料 1 / 行情 3，`--scope-total 20`）裁决与合前逐字段一致（`~/.finance-runtime/reviews/claim-scope-merge-65-20260922/fix-parity/`）。
- 变异：stash 掉两处源码改动，三条新测试必红；还原后绿。
- 四叶：见 PR 评论（python 全量需等机器准入：load ≤ 10、pytest ≤ 3、free ≥ 8G）。

## 同批文档

`docs/handoffs/inflight/docs-claim-scope-65-design.md` → 归档为 `docs/handoffs/2026-09-23-claim-scope-65-closeout.md`（#65 已合入，分支已删）。

## 不做

不改四条规则的语义与接口；不接入运行时（设计稿 `2026-09-22-claim-scope-runtime-integration-design.md` §5 六条验收，另授权另立单）；不给召回率。
