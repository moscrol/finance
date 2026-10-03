# Workspace evaluation recovery — 2026-10-03

## Recovered scope

Base: `bd0be25db7b5ed04d12a86ed6f726aaf4fda3e04`, subsequently merged through PR #24.

- Integrate the PR #18–23 chain: bounded evaluation deadlines, frozen scorer compatibility, offline conversation preflight, and propagation of already granted planning time to the actual tool boundary. Preserve the unsuccessful model experiments and their original denominators.
- Select only PR #17's catalog request view and experiment records. The model-specific semantic policy from its earlier base is not imported. The wrapper is evaluation-only and disabled by default. The current native GLM composition already omits duplicate catalog descriptions; the wrapper correctly leaves that request unchanged, with complete native tool definitions intact.
- Recover the deterministic content-correctness evaluator, strict paired-score comparator, route paraphrase probe and tool-description size report. These do not call a model. The comparator can report FAIL or INCONCLUSIVE, never acceptance of general model benefit.
- Recover three independent read-only audits: physical data consumption, stock-day/captured-quote reconciliation, and declared-versus-requested tool usage. No historical user run manifests or private measurement reports are included. Tool usage classification is now explicit input and its default output lives outside Git.
- Recover `d279a4ba8`'s list-label parser fix: a leading decimal or numeric range retains its full quantity instead of losing the part before a dot or hyphen.

The consumption audit's original CLI could overwrite its input database through `--output`, including symbolic/hard-link aliases. Four counterexamples failed before the fix; exclusive creation now refuses existing output files and leaves the database unchanged.

## Explicit release rejection

Do not integrate `b244bb8b3`'s short-date mask change. The joint candidate passed synthetic cases but introduced two incorrect public “quantity not found” notes during replay. Both quantities had bound evidence: two endpoints of a stock-price transition, and a negative percentage displayed as a decrease. Correct support requires evidence identity and units; widening numeric field-name exceptions or matching arbitrary endpoints would violate the existing matching policy. The original source commit and failing replay are retained.

Replay scope was 966 archived episode files: 955 rebuilt successfully; 11 older contracts could not be rebuilt because `required_outputs` was not a list. The rejected joint candidate added two notes and removed none. Replaying the accepted list-label-only change produced zero additions and zero removals in the 955 supported files. These are replay coverage results, not a claim about the 11 unprocessed files or all possible answers.

Other rejected semantic-routing policies, unvalidated schema slimming, the frozen A7 fixture edit, and the explicitly archived FinArena product remain outside this release. Pi's active output-provenance and plan-ownership work is preserved separately.

## Validation before review

Ruff passed. The recovered and changed evaluation/audit test files passed 254 tests; the content-correctness and paired-score software selftests passed. The real-loop catalog seam verifies the production GLM no-op as well as projection on the two full-catalog loops. These are targeted checks; full Python, frontend/E2E, registry, independent review and GitHub checks remain release prerequisites.

Private source identity records, original failures and replay evidence are retained under `~/.finance-runtime/reviews/workspace-closeout-1003/`. The original source trees were not modified.
