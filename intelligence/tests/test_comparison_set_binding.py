from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import OutputEvidenceBinding
from intelligence.services.episode_protocol import (
    expand_comparison_set_bindings,
    expand_episode_snapshot_bindings,
)
from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolSpec


def _row(
    content_hash: str,
    title: str,
    detail: str,
    *,
    tool: str = "finance_query",
    source_date: str = "2026-08-14",
) -> AgentEvidence:
    return AgentEvidence(
        tool=tool,
        title=title,
        detail=detail,
        source="本地行情",
        source_date=source_date,
        content_hash=content_hash,
    )


def _ranking_ledger() -> tuple[AgentEvidence, ...]:
    return (
        _row("h-mkt", "市场日频总览（2026-08-14）", "底部横盘，正常量能"),
        _row("h-rare", "主线板块日频结构（2026-08-14）", "稀有金属 强度2544 净流入居前"),
        _row("h-cu", "主线板块日频结构（2026-08-14）", "铜 强度1685"),
        _row("h-au", "主线板块日频结构（2026-08-14）", "黄金 强度1062"),
        _row("h-cpo", "板块日频行情（2026-08-14）", "CPO 边际量为负"),
        _row("h-elec", "板块日频行情（2026-08-14）", "电子 另一行"),
    )


def _binding(*hashes: str) -> OutputEvidenceBinding:
    return OutputEvidenceBinding("direct_answer", hashes)


def test_comparative_claim_binds_same_title_ranking_cohort() -> None:
    expanded = expand_comparison_set_bindings(
        bindings=(_binding("h-rare", "h-mkt"),),
        evidence=_ranking_ledger(),
        draft="稀有金属涨幅、强度变化和净流入均居前。",
    )

    assert expanded[0].evidence_hashes == ("h-rare", "h-mkt", "h-cu", "h-au")


def test_non_comparative_numeric_sentence_does_not_expand() -> None:
    expanded = expand_comparison_set_bindings(
        bindings=(_binding("h-rare"),),
        evidence=_ranking_ledger(),
        draft="稀有金属强度变化 2544。",
    )

    assert expanded[0].evidence_hashes == ("h-rare",)


def test_comparative_claim_does_not_pull_a_different_observation() -> None:
    expanded = expand_comparison_set_bindings(
        bindings=(_binding("h-cpo"),),
        evidence=_ranking_ledger(),
        draft="CPO 当日成交边际变化为负，板块日频行情里该方向并不居前。",
    )

    assert expanded[0].evidence_hashes == ("h-cpo", "h-elec")
    assert "h-rare" not in expanded[0].evidence_hashes


def test_expansion_is_idempotent() -> None:
    once = expand_comparison_set_bindings(
        bindings=(_binding("h-rare"),),
        evidence=_ranking_ledger(),
        draft="强度变化均居前。",
    )
    twice = expand_comparison_set_bindings(
        bindings=once,
        evidence=_ranking_ledger(),
        draft="强度变化均居前。",
    )

    assert once[0].evidence_hashes == ("h-rare", "h-cu", "h-au")
    assert twice == once


def test_query_scoped_snapshot_path_still_needs_draft_to_expand() -> None:
    def _runner(query: str, context: object) -> object:
        del query, context
        raise AssertionError("registry is only resolved, not executed")

    registry = ResearchToolRegistry(
        (
            ToolSpec(
                "finance_query",
                "market_data",
                "查询型行情",
                "local",
                "current",
                _runner,
                query_scope="query",
            ),
        )
    )
    evidence = _ranking_ledger()
    bindings = (_binding("h-rare"),)

    assert expand_episode_snapshot_bindings(
        bindings=bindings,
        evidence=evidence,
        registry=registry,
    )[0].evidence_hashes == ("h-rare",)
    assert expand_episode_snapshot_bindings(
        bindings=bindings,
        evidence=evidence,
        registry=registry,
        draft="稀有金属涨幅、强度变化和净流入均居前。",
    )[0].evidence_hashes == ("h-rare", "h-cu", "h-au")
