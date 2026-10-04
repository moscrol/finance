"""Material-only author and reviewer share the bounded finance reasoning invariants."""

from intelligence.services.material_answer_authoring import _AUTHOR_RULE
from intelligence.services.material_claim_review import MATERIAL_REVIEW_RULE


_REQUIRED_INVARIANTS = (
    "经营现金流减资本开支不是融资需求的穷尽式定义",
    "资本开支属于投资活动现金流",
    "资产负债表余额变化只是线索",
    "FCFE中的净借款按新增借款减偿还借款计算并加回",
    "净利润不能直接再减现金资本开支",
    "材料未说明不等于事实不存在或不影响",
)


def test_bounded_finance_invariants_reach_both_author_and_semantic_reviewer():
    for invariant in _REQUIRED_INVARIANTS:
        assert invariant in _AUTHOR_RULE
        assert invariant in MATERIAL_REVIEW_RULE
