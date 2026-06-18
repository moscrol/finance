"""Agent-specific evaluation harness (P1+ 评测闸).

Where the existing RAG eval measures *retrieval* (recall@k of the wiki index),
this package measures the **agent's answers**: did it cite only evidence the
tools actually returned (no hallucinated citations), did it ground on the
expected sources, did it surface the expected companies, did it keep the
red-line markers (免责声明 / graph_only / ⚠️过期), and how did the W (wiki dense)
recall behave per theme.

The scorer (:mod:`intelligence.eval.agent_eval`) is a pure, dependency-free
function over a small serializable :class:`TurnInput` view, so it is unit-tested
with hand-built fixtures (no LLM, no KB). The live runner
(:mod:`intelligence.eval.runner`) drives a real :class:`~intelligence.services.agent.AgentSession`
over a golden case set and applies the gate — usable on demand or on a schedule,
not in PR CI (it needs an LLM key + the KB).
"""
