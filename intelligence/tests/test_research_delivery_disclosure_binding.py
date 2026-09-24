"""What makes an absence claim legitimate: the channel, not the venue's name.

Two shapes escaped the older checks, both for the same reason as the ratio bug:
the rule was written as a list of strings the model happens to produce.

- '本期无任何披露文件' was not in the absence phrase list, so it shipped, while the
  synonymous '零披露' was caught.
- '深交所互动易显示…[E2]' was not in the attributed-venue list, so a sentence that
  cited its own source was deleted along with the invalid inference next to it.

Absence is now a negator crossed with a disclosure noun (two closed classes),
and attribution asks whether the episode actually holds evidence from the
disclosure channel - a question the prose cannot fake.
"""

import pytest

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_delivery_checks import (
    disclosure_absence_findings,
    remove_findings,
)

FAILED_LOOKUP = ProviderTrace(
    provider="agent:l3_lookup",
    capability="l3_lookup",
    status="request_error",
    detail="private-path secret-token",
)
INVALID = "因此公司没有公告"
CITED_VENUE = "深交所互动易显示本期没有公告[E2]"
DRAFT = f"收入可核[E1]，查询返回空白，{INVALID}，{CITED_VENUE}。"


def _evidence(tool):
    return (AgentEvidence(tool=tool, title="披露来源", detail="本期没有公告",
                          source="fixture", content_hash="venue-fixture"),)


@pytest.mark.parametrize(
    "claim",
    [
        "收入可核[E1]，查询返回空白，因此本期无任何披露文件。",
        "收入可核[E1]，查询返回空白，因此本期为零披露。",
        "收入可核[E1]，查询返回空白，因此本期没有公告。",
        "收入可核[E1]，查询返回空白，因此期内不存在披露记录。",
        "收入可核[E1]，查询返回空白，因此公告数量为 0。",
    ],
)
def test_absence_is_a_negator_crossed_with_a_disclosure_noun(claim):
    """Synonyms of 'nothing was disclosed' are open-ended; the classes are not."""
    findings = disclosure_absence_findings(claim, (FAILED_LOOKUP,))
    assert findings
    kept = remove_findings(claim, findings)
    assert kept == "收入可核[E1]，查询返回空白。"


def test_a_venue_we_never_listed_keeps_its_sentence_and_its_citation():
    findings = disclosure_absence_findings(DRAFT, (FAILED_LOOKUP,), _evidence("l3_lookup"))
    kept = remove_findings(DRAFT, findings)
    assert INVALID not in kept
    assert CITED_VENUE in kept and "收入可核[E1]" in kept


def test_a_citation_from_another_channel_cannot_launder_the_same_sentence():
    """Control: without disclosure-channel evidence, [E2] is borrowed."""
    findings = disclosure_absence_findings(DRAFT, (FAILED_LOOKUP,), _evidence("news_search"))
    kept = remove_findings(DRAFT, findings)
    assert INVALID not in kept and CITED_VENUE not in kept
    assert kept == "收入可核[E1]，查询返回空白。"


@pytest.mark.parametrize(
    "claim",
    [
        "查询返回空白，因此改用互动易核对公告清单。",
        "不能据此断言公司没有公告或尚未兑现。",
        "查询失败不代表没有公告。",
        "窗口内存在两份已核实公告，但查询并不完整。",
        "若公司确实无新公告，则研究重点转向已披露信息。",
        "无法完整查询本期公告。",
    ],
)
def test_honest_gaps_and_next_steps_are_not_absence_claims(claim):
    """A wider absence rule must not start eating gap admissions or plans."""
    assert disclosure_absence_findings(claim, (FAILED_LOOKUP,), _evidence("l3_lookup")) == ()
