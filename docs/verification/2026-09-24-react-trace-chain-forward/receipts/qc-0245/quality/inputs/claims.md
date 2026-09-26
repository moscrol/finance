# #81 / PR #832 engineering claims

Candidate f7d525ca0bdc33df2bbbed96bdb8a8af3b58ddf0; baseline 3bb81b9638f97b4773ce0f338df3a505b7c0162f. Claims are author statements to challenge, not verdicts.
C1. Evidence ordinals such as E1 are not numeric facts; actual unsupported numeric claims remain checked. Owner: intelligence/services/episode_protocol.py strip_evidence_ordinals and episode_semantic_verifier.py.
C2. finance_query validation errors return safe structured diagnostics, not arbitrary text, paths, or fabricated observations. Owner: finance_query.py and episode_tools.py.
C3. A local tool validation failure can feed back into the same Episode and continue without losing existing evidence or extending tool/cancellation budgets. Relevant tests: test_finance_query_repair_feedback.py, test_agent_episode_progress.py.
C4. Frozen nested Mapping tool parameters can record research progress without mutation; unknown objects remain rejected. Owner: intelligence/runtime/research_progress.py.
C5. History read pages retain absolute row/sample identity, offset/next_offset, final-page truncation and selected-window hints; projection failure must not register a successful history read. Owner: intelligence/services/historical_research/episode.py; tests/test_history_model_projection.py.
C6. Numeric-condition repair only removes dangling count references whose definition was actually removed in this repair and has no surviving definition. It preserves unrelated prose, bullets and line breaks, and is wired into the real repair exit without relaxing the numeric gate. Owner: episode_semantic_verifier.py; test_condition_reference_seams.py.

Against baseline, C1-C4 product implementations have no diff; C5/C6 retain product increments. Independently verify the new head, including interactions; do not transplant old reviewer verdicts. inputs/source.diff is the exact baseline-to-candidate product/test diff. No natural-finance claims, merge or deployment authority. Old refresh E2E timing failures remain unexplained; no performance conclusion is claimed here.
