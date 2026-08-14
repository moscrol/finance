"""把展开成一家一行的句子，改绑到那家公司自己的 claim，而不是删掉它们。

registry 里常同时存在聚合 claim 和逐家 claim。实测 run_20260731_103917_565944
（中际旭创深挖）：``gap:1``「12 家公司仅有间接或候选证据，未达到公司级硬证据门槛」，
另有 ``gap:6``「华灿光电 证据 2026-06-04 已超 45 天…」等逐家条目，以及 12 条
company_table。composer 把聚合展开成 8 行「**华灿光电**：产业链映射为 G3 候选层级…」，
却把 8 行全绑回 ``gap:1``，于是每行判 ``cross_subject``「混入未绑定主体」，repair 再
把这 8 行删掉——删掉的正好是 chain_mapping 这个必需输出要的内容。

8 条里 6 条是这种绑错（公司的 claim 就在 registry 里），2 条（易天股份、智立方）
registry 里根本没有，是真的凭空添加，必须继续照报。
"""
from __future__ import annotations

from intelligence.services import answer_model as am

AGGREGATE = "12 家公司仅有间接或候选证据，未达到公司级硬证据门槛，不得升级为核心受益。"


def _claim(claim_id: str, text: str, company: str | None = None) -> am.Claim:
    return am.make_claim(
        claim_id=claim_id,
        text=text,
        claim_type="evidence_gap" if claim_id.startswith("gap") else "supporting_fact",
        theme="中际旭创",
        status=am.ClaimStatus.CANDIDATE,
        company=company,
    )


def _spec() -> am.AnswerSpec:
    return am.AnswerSpec(
        research_spec=am.resolve_answer_profile("中际旭创怎么看", "中际旭创", "deep_dive"),
        summary=(),
        verified_facts=(
            _claim("company:1", "华灿光电，产业链候选层级。", company="华灿光电"),
            _claim("company:2", "卓胜微，产业链候选层级。", company="卓胜微"),
        ),
        company_table=(),
        counter_evidence=(),
        gaps=(
            _claim("gap:1", AGGREGATE),
            # 同一家公司也出现在这条时效 gap 的文本里——绑定该落在 company:1。
            _claim("gap:6", "华灿光电 证据 2026-06-04 已超 45 天，需复核。"),
        ),
        triggers=(),
        candidate_facts=(),
        next_actions=(),
        sources=(),
        system_notices=(),
    )


def _line(text: str, claim_id: str) -> str:
    return f"{text} <!-- claim_ids={claim_id}; evidence_atom_ids=; claim_type=gap -->"


def _bound_claim(answer: str, company: str) -> str:
    import re

    for line in answer.splitlines():
        if company in line:
            match = re.search(r"claim_ids=([^;]+)", line)
            if match is not None:
                return match.group(1).strip()
    return ""


def test_a_row_expanded_from_the_aggregate_is_rebound_to_its_own_company() -> None:
    answer = "\n".join(
        (
            _line("**华灿光电**：产业链映射为候选层级。", "gap:1"),
            _line("**卓胜微**：产业链映射为候选层级。", "gap:1"),
        )
    )

    rebound = am.rebind_entity_claim_ids(answer, _spec())

    assert _bound_claim(rebound, "华灿光电") == "company:1"
    assert _bound_claim(rebound, "卓胜微") == "company:2"


def test_the_explicit_company_claim_beats_an_incidental_mention() -> None:
    """华灿光电 也出现在 gap:6 的文本里；带 company 字段的那条优先。"""
    answer = _line("**华灿光电**：产业链映射为候选层级。", "gap:1")

    rebound = am.rebind_entity_claim_ids(answer, _spec())

    assert _bound_claim(rebound, "华灿光电") == "company:1"


def test_a_company_absent_from_the_registry_is_left_alone() -> None:
    """易天股份 registry 里没有，不能凭空给它找个 claim——仍旧照报。"""
    answer = _line("**易天股份**：产业链映射为候选层级。", "gap:1")

    rebound = am.rebind_entity_claim_ids(answer, _spec())

    assert _bound_claim(rebound, "易天股份") == "gap:1"


def test_a_sentence_naming_two_companies_is_not_rebound() -> None:
    """一句提到多个主体时无法确定该绑哪个，不猜。"""
    answer = _line("华灿光电与卓胜微同属候选层级。", "gap:1")

    rebound = am.rebind_entity_claim_ids(answer, _spec())

    assert _bound_claim(rebound, "华灿光电") == "gap:1"


def test_an_already_correct_binding_is_untouched() -> None:
    answer = _line("**华灿光电**：产业链映射为候选层级。", "company:1")

    assert am.rebind_entity_claim_ids(answer, _spec()) == answer


def test_the_aggregate_sentence_itself_keeps_its_binding() -> None:
    """聚合句没有点名任何一家公司，不该被改绑。"""
    answer = _line(AGGREGATE, "gap:1")

    assert am.rebind_entity_claim_ids(answer, _spec()) == answer
