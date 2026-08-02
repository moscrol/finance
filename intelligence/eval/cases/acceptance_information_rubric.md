# Acceptance information-value rubric v1

Compare the Workbench answer with the eligible frozen reference only on usable
decision information. Factual correctness remains on the independent credibility
axis and must not be silently re-scored here.

Judge these dimensions:

1. **Directness** — answers the case's actual question rather than changing scope.
2. **Usable judgments** — turns evidence into specific rankings, scenarios, causal
   links, invalidation conditions, or next checks.
3. **Coverage** — addresses the important subquestions without padding.
4. **Decision structure** — makes assumptions, conditions, and trade-offs legible.
5. **Unsupported-detail risk** — penalizes untraceable numbers, invented probability,
   temporal leakage, or calculations over incomplete data.

Allowed outcomes:

- `workbench_wins`: Workbench contains materially more usable decision information.
- `tie`: each answer has comparable information value or complementary strengths.
- `knevo_wins`: the frozen Knevo reference contains materially more usable decision
  information.
- `not_evaluated`: available evidence is insufficient for a fair comparison.

Calibration anchors from the manually reviewed ledger:

- Knevo can win on retrieval breadth, historical analogy, and financial granularity.
- Workbench can win on reproducibility, missing-data honesty, and auditable local facts.
- Breadth does not win automatically when it depends on stale, incomplete, or
  untraceable data; auditability does not win automatically when the direct task is
  unanswered.

Return a concise reason plus Workbench-unique information, reference-unique
information, and unsupported-detail risks. Do not infer a winner from answer length.
