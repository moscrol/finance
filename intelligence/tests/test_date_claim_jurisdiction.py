"""日期类判定的管辖边界：两条规则各管一半，不许互相漂。

仓里现在有两处碰「日期标注对不对」：

- `output_review._check_stale_mislabel`：**有真值可比**时的事实核对。块层带着
  真实扫描日，答案却把 19 天前的榜单写成「当日」→ 报。它比的是 date A vs date B。
- `answer_claim_scope.latest_trading_day_unverified`：**无真值可比**时的口径越界。
  没有日历数据源可查（`finance_query` 没有日历 dataset），答案却断言某日是
  「最近一个已收盘交易日」→ 报。它比的是 claim vs evidence。

两者都在往「日期标注正确性」长，最容易各自漂：同一句话两条规则给出矛盾裁决，
或者都以为对方管了、于是都不管。下面的差分测试把界钉住——谁越界谁红，
届时必须显式决定合并还是分工，而不是无声漂移。
"""

from __future__ import annotations

import unittest

from intelligence.services.answer_claim_scope import (
    RULE_LATEST_TRADING_DAY,
    ClaimEvidenceContext,
    review_answer_claims,
)
from intelligence.services.output_review import WARN, _check_stale_mislabel

# blk-d9 实测原形状：块层扫描日 2026-08-07，答案写成 08-26 当日
STALE_HINTS = (("大单扫描", "2026-08-07", "2026-08-26"),)
STALE_SENTENCE = "以下为 2026-08-26 当日的大单净流入扫描榜单。"

# K3 首跑实测原形状：断言某日是最近一个已收盘交易日，但无从核验
UNVERIFIED_SENTENCE = "**数据日期：2026-09-18（最近一个已收盘交易日）**"


def _claim_rules(text: str) -> list[str]:
    context = ClaimEvidenceContext(question="", evidence_dates=("2026-09-18",))
    return [issue.rule for issue in review_answer_claims(text, context).issues]


def _stale_mislabels(text: str) -> bool:
    """只看「疑似当日化错标」那种裁决。

    `_check_stale_mislabel` 会发两种 WARN：错标（把旧数据写成当日）与
    出处缺失（正文根本没写扫描日）。后者对任何不提扫描日的答案都会响，
    与口径规则的管辖无关——拿状态当语义会把两件事混为一谈。
    """

    return any(
        check.status == WARN and "疑似把" in check.note
        for check in _check_stale_mislabel(text, STALE_HINTS)
    )


class JurisdictionTests(unittest.TestCase):
    def test_stale_mislabel_owns_the_ground_truth_comparison(self) -> None:
        # 有真值（扫描日）可比 → 时点错标管；口径规则不该插手：它没有真值，
        # 「当日」也不是它要抓的断言形状。
        self.assertTrue(_stale_mislabels(STALE_SENTENCE))
        self.assertEqual([], _claim_rules(STALE_SENTENCE))

    def test_claim_scope_owns_the_unverifiable_assertion(self) -> None:
        # 没有真值可比 → 口径规则管；时点错标无从判断，不该报。
        self.assertEqual([RULE_LATEST_TRADING_DAY], _claim_rules(UNVERIFIED_SENTENCE))
        self.assertFalse(_stale_mislabels(UNVERIFIED_SENTENCE))

    def test_scan_date_present_clears_stale_but_not_the_bare_claim(self) -> None:
        # 答案带上真实扫描日 → 时点错标放行；但若同时又断言「最新交易日」，
        # 口径规则仍然要管。两条规则的触发条件互不替代。
        text = "2026-08-07 扫描的大单净流入榜单如下，该日为最近一个已收盘交易日。"
        self.assertFalse(_stale_mislabels(text))
        self.assertEqual([RULE_LATEST_TRADING_DAY], _claim_rules(text))


if __name__ == "__main__":
    unittest.main()
