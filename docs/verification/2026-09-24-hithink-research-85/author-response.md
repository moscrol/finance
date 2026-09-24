# Author Response To Previous Quality M1 (Not A Verdict)

The previous REPORT.md and parsed.json remain unmodified. This follow-up may uphold, withdraw, or split M1. Please decide from the original contract and independently observed behavior, not from the new author assertions.

The pre-review contract is preserved byte-for-byte at ROOT/inputs/original-claims.md. The current C1-C6 text is unchanged; only candidate identity changed. Since the previous candidate, source.diff has four new author regression cases and no implementation change (check inputs/since-last-review.diff).

Original C2: "Ordinary API/network/parse errors are not reclassified as rate-limit gaps".
Original C3: "a typed 429 exhaustion ... continues remaining requests ... Other errors still fail closed."

Previous M1 input: three business-4001 responses, one HTTP 429, then URLError, with retries=4 and rate_limit_budget_seconds=300. Previous probes establish that this ends as plain HithinkAPIError and aborts remaining research requests. They do not establish that either 429 bound was exhausted. The original fake sleep only records sleeps and does not advance monotonic time; please use a controlled clock if testing the time-bound distinction.

Competing interpretations:
A. Ordinary retry exhaustion stays ordinary even after a historical 429. A 429 count/time exhaustion is a different stopping condition and remains typed. The author believes A follows C2/C3.
B. Once any 429 has occurred, the rest of that request is permanently owned by rate-limit recovery, including later ordinary retry exhaustion. Previous M1 invokes this rule to exclude C2. Identify the primary contract text supporting B if upholding it; do not assume the interpretation merely because the prior report states it.

Questions for independent adjudication:
- Which stopping condition actually fires for M1? Is either 429 bound exhausted?
- Compare the ordinary exhaustion with and without an intervening 429, and compare genuine typed 429 exhaustion.
- Does changing this sequence to HithinkRateLimitError satisfy or violate C2/C3?
- Is there any different, reproducible product defect in the inspected paths?

The added author cases live in tests/test_hithink_stock_daily.py::test_429_does_not_reclassify_later_ordinary_failure (three terminal error types) and tests/test_hithink_research.py::test_ordinary_failure_after_rate_limit_gap_still_aborts. They are not independent evidence; build/reuse reviewer-owned probes and retain the observed first result. The original low-priority observations must remain visible with their existing verification limits unless you independently resolve them.
