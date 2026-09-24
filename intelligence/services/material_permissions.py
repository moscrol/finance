"""E2 frozen read ceiling; only audited runner paths may enter local_only.

This is deliberately not inferred from tool names, cost or freshness. See the
producer seams below; unknown/mixed paths stay out until separately certified.
Model inference for answering is not a data-read capability.
"""
from __future__ import annotations

# Producers: episode_tools.finance_query_runner -> FinanceQuery (read-only DuckDB);
# mainline_runner -> ask_blocks._market_review_mainline_context_block_for_llm;
# agent_research.build_graph_tools._evidence_lookup -> KnowledgeAdapter local JSON;
# episode_tools.memory_lookup_runner -> user_memory local user ledgers.
# Not yet certified: kb_search subprocess/model loading, graph_lookup research_map,
# evidence_search semantic judge, market_data/financial_data external fallbacks.
LOCAL_READ_CAPABILITIES = frozenset({
    "finance_query", "mainline_context", "evidence_lookup", "memory_lookup",
})


# Evidence producer names are not extra capabilities. These two audited paths
# share finance_query permission; save_history_research remains uncertified.
LOCAL_EVIDENCE_PRODUCERS = {
    "history_query": "finance_query",
    "read_history_result": "finance_query",
}


def restrict_read_capabilities(capabilities: tuple[str, ...], data_scope: str | None) -> tuple[str, ...]:
    """Intersect the requested reads with the frozen scope; never add a floor."""
    if data_scope == "material_only":
        return ()
    if data_scope == "local_only":
        return tuple(cap for cap in capabilities if cap in LOCAL_READ_CAPABILITIES)
    if data_scope == "full" or data_scope is None:
        return capabilities
    raise ValueError("unknown material read scope")
