# Native Daily Reports Design

## 1. Goal

Turn Daily Agent and Daily Review into the first native, public-friendly Workbench reports. The migration moves information and user tasks into a consistent product language; it does not transplant legacy HTML pages into the main experience.

## 2. Product Principles

- A general reader can understand the page without knowing internal field names, workflow commands, or repository paths.
- The first screen answers three questions: what happened, why it matters, and what needs attention next.
- Professional detail remains available through progressive disclosure instead of dominating the default view.
- Every conclusion keeps its date, evidence boundary, missing evidence, and canonical source.
- Legacy HTML is a secondary comparison surface labelled `Original report`. It is never the default Daily Agent or Daily Review view.
- Existing canonical writers and ledger ownership remain unchanged.

## 3. Scope

### In scope

- Native Daily Agent projection from its canonical JSON.
- Native Daily Review projection from canonical Markdown.
- A compatibility projection for historical Daily Review artifacts whose Markdown is missing. It extracts only known sections from registered HTML and identifies the source mode as `legacy_html_projection`.
- A shared React report surface and Workbench visual language.
- Safe access to registered legacy companion assets for the secondary original-report viewer.
- Navigation race, scroll restoration, SSE replay deduplication, mobile accessible names, and CI reproducibility fixes found during PR review.

### Out of scope

- Native migration of strategy matrices, forecast ledgers, cockpit pages, or every Artifact Registry category.
- Changes to Daily Review, ledger, or knowledge-base canonical writers beyond preserving the Markdown output already declared by the workflow.
- New trading recommendations or personalized transaction instructions.

## 4. Architecture

```text
Daily Agent JSON -----------+
                            |
Daily Review Markdown ------+--> DailyReportProjection --> React DailyReportView
                            |
Historical registered HTML -+    compatibility only

Registered HTML + sibling assets --> sandboxed Original report
```

The backend owns normalization because source schemas and provenance are domain contracts. The frontend receives one stable projection and owns presentation only. This is an anti-corruption layer: old output formats can change without leaking their structure into the product UI.

### 4.1 Projection contract

`DailyReportProjection` contains:

- `report_type`, `title`, `date`, and `source_mode`.
- `plain_summary`: up to three short conclusions written from deterministic source fields.
- `metrics`: a small set of labelled values with optional context and tone.
- `sections`: ordered groups of actionable items.
- `glossary`: short explanations for unavoidable research terms.
- `provenance`: canonical path, rendered path, warnings, and whether the original report is available.

Sections use a shared item contract with `title`, `summary`, `badges`, `meta`, `next_action`, and optional structured details. Unknown fields are not dumped into the main interface.

## 5. Daily Agent Presentation

The adapter maps canonical JSON into:

1. `Three things to know`: deterministic counts and the highest-priority validated or unconfirmed signal.
2. `Research workload`: IMA, official evidence, market validation, and downgrade/watch counts.
3. `Worth attention`: top candidates with lifecycle, evidence status, representative stocks, and the reason they matter.
4. `What to do today`: actionable queues ordered by existing priority.
5. `Evidence boundary`: missing L2/L3 layers, warnings, source mode, and generation time.

Internal keys such as `old_logic_wakeup` are translated to reader-facing Chinese labels. L1-L4 remains available, with a glossary explaining each level.

## 6. Daily Review Presentation

The canonical Markdown path is preferred. The adapter parses headings and Markdown tables with a bounded parser and projects:

1. `Three things to know`: market nature/stage, dominant direction, and risk or validation boundary.
2. `Market temperature`: index, turnover, breadth, limit-up/down, concentration, and strength.
3. `Main directions`: double-red themes, new-high directions, and limit-up themes.
4. `Risk and verification`: market assessment, coverage warnings, and the next-session validation focus.
5. `Professional data`: selected source sections and the link to the canonical Markdown.

For historical HTML without Markdown, a compatibility parser reads only `Core dashboard` and `Market environment assessment`. It never reuses legacy CSS, scripts, navigation, or layout. The UI displays a provenance warning so compatibility output cannot be mistaken for a complete canonical projection.

## 7. Frontend Experience

- `ArtifactViewer` requests a projection for supported daily categories and renders `DailyReportView`.
- The shared report uses the existing Workbench palette, spacing, typography, status badges, and responsive breakpoints.
- Dense data is presented as unframed sections, compact metric strips, rows, and disclosures. It does not introduce a marketing hero or nested cards.
- `Original report` is a secondary action and disclosure below the native report.
- Navigation clears stale data immediately, ignores late responses, deduplicates replayed trace steps, and resets document scroll on surface changes.
- Mobile icon-only controls always retain explicit accessible names.

## 8. Legacy Asset Compatibility

The API may serve a relative companion asset only when:

- the parent artifact is registered;
- the resolved asset remains inside the registered artifact's directory;
- the target is a regular file; and
- the request cannot escape through `..` or symlinks.

The original HTML remains sandboxed. Companion-asset support exists for accurate archival comparison, not as the native rendering mechanism.

## 9. Errors And Degradation

- Missing or invalid projection source: show a native error state and retain the original-report action when available.
- Missing canonical Markdown with valid historical HTML: use compatibility projection and show its warning.
- Invalid Daily Agent JSON: do not fall back to raw JSON as a public report; expose the registered source and recovery message.
- Late navigation response: discard it without changing the current surface.
- SSE reconnect/replay: replace a trace step with the same `step_id` instead of appending duplicates.

## 10. Testing And Release Gate

- Backend tests cover Daily Agent projection, Daily Review Markdown projection, legacy compatibility projection, malformed inputs, and companion-asset traversal.
- Component tests cover reader-facing labels, glossary, degradation, original-report disclosure, and mobile accessible names.
- E2E covers native Daily Agent and Daily Review flows at desktop, tablet, and mobile widths, scroll reset, and failed navigation isolation.
- CI runs the 817-test intelligence suite, lint, TypeScript, component tests, production build, and Playwright using a discoverable Python executable.
- Real local verification opens current artifacts rather than relying only on mocked HTML.

## 11. Acceptance Criteria

- Daily Agent and Daily Review open as native Workbench reports by default.
- Their first viewport communicates conclusions and next actions without internal schema knowledge.
- The two report types share one visual and interaction system.
- The original HTML is clearly secondary and its registered relative image loads successfully.
- Switching runs or artifacts never leaves old content under a new selection.
- All automated checks pass from a clean checkout without a manually created `.venv` symlink.
