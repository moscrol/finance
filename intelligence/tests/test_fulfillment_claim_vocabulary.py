"""任务契约门禁必须认识研究 owner 实际发出的 claim_id 命名空间。

原先的 exact 判定是 `output_id in claim_id`，方向反了：owner 发 `counter:1`，
而 `"counterpoint" in "counter:1"` 恒为假。direct_assessment 那条分支又只认
`generic:summary` 或 claim_type in {summary, cause_attribution}，而 owner 发的是
`summary:market` + claim_type=fact，且它在候选为空时直接 return，走不到后面的兜底。

后果：题材类问题的三个必需输出一条候选都取不到，全判 missing/partial，
fail_closed 把整份答案换成 190 字的「请补充数据源」。实测被丢弃的是一份 905 字、
带 claim_ids 与 evidence_atom_ids 内联绑定的完整答案。
"""
from __future__ import annotations

import pytest

from intelligence.services import answer_model as am
from intelligence.services.task_fulfillment import _claim_candidates


def _claim(claim_id: str, text: str, claim_type: str = "fact") -> am.Claim:
    return am.make_claim(
        claim_id=claim_id,
        text=text,
        claim_type=claim_type,
        theme="固态电池",
        status=am.ClaimStatus.VERIFIED,
        evidence_ids=("S1",),
    )


OWNER_CLAIMS = (
    _claim("summary:market", "盘面信号全面转强"),
    _claim("summary:company-gap", "公司层面无可回查证据"),
    _claim("counter:1", "资金行为不能替代基本面"),
    _claim("trigger:1", "关注量产落地"),
    _claim("market:S1", "涨幅 1.59%"),
)


@pytest.mark.parametrize(
    "output_id,expected",
    [
        ("direct_assessment", ["summary:market", "summary:company-gap"]),
        ("counterpoint", ["counter:1"]),
        ("counter_evidence", ["counter:1"]),
    ],
)
def test_owner_claim_namespaces_bind_to_required_outputs(
    output_id: str, expected: list[str]
) -> None:
    assert [c.claim_id for c in _claim_candidates(output_id, OWNER_CLAIMS)] == expected


def test_legacy_generic_convention_still_wins() -> None:
    """旧约定不能因为加了命名空间映射而失效。"""
    legacy = (_claim("generic:summary", "结论", "summary"),)

    assert [c.claim_id for c in _claim_candidates("direct_assessment", legacy)] == [
        "generic:summary"
    ]


def test_chain_mapping_stays_unbound_without_chain_claims() -> None:
    """没有产业链/公司 claim 时就该判缺——这条不能靠放宽命名来假装满足。

    固态电池那次的 chain_mapping 确实没产出：company_table 是 0 项。真正的问题在
    上游（owner 没读知识库的 12 条公司暴露），不是在这里放行。
    """
    assert _claim_candidates("chain_mapping", OWNER_CLAIMS) == ()


def test_chain_mapping_binds_when_the_owner_does_map_companies() -> None:
    with_chain = (*OWNER_CLAIMS, _claim("company:东方锆业", "材料环节核心标的"))

    assert [c.claim_id for c in _claim_candidates("chain_mapping", with_chain)] == [
        "company:东方锆业"
    ]
