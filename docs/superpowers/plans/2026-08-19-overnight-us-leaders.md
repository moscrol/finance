# Overnight US Leader Quotes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]` ) syntax for tracking.

**Goal:** Overnight-hybrid `market_forecast` episodes attach bindable US index + leader quotes (费城半导体 / 英伟达 / 美光 / SK海力士 / 闪迪) so the verifier can keep 费半 −6% / 闪迪 −8% style numbers.

**Architecture:** Reuse Yahoo chart quotes already in `external_market.py`. Do not add a capability or tool slot. When `market_data` runs on a `market_forecast` whose question hits overnight/external markers, append structured quote evidence. Local forecasts stay A-share only. News titles remain non-quotes.

**Tech Stack:** Python, pytest, existing `external_market.resolve` + `build_episode_registry` seams.

**Spec:** `docs/learning/spec-continuous-depth-gap-r1.md` R2 P0-B. Stacked on `feat/overnight-forecast-auth` (P0-A).

**Seams under test:** `overnight_leader_codes` / `format_quote_line` / `resolve_overnight_leaders` in `intelligence/services/external_market.py`; `market_data` execution via `build_episode_registry`. No private helpers in episode tests beyond the existing registry seam.

---

### Task 1: Quote catalog + formatter

**Files:**
- Modify: `intelligence/services/external_market.py`
- Test: `intelligence/tests/test_external_market.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_overnight_leader_codes_are_sox_and_four_names() -> None:
    assert external_market.overnight_leader_codes() == (
        "SOX",
        "NVDA",
        "MU",
        "HYNIX",
        "SNDK",
    )
    assert external_market.requested_symbols("昨天美股的涨跌情况") == (
        "DJI",
        "SPX",
        "IXIC",
    )


def test_format_quote_line_exposes_bound_pct_chg() -> None:
    quote = external_market.ExternalMarketQuote(
        code="SNDK",
        name="闪迪",
        close=80.0,
        pct_chg=-8.0,
        trade_date="2026-08-18",
        source=external_market.YAHOO_PROVIDER,
    )
    line = external_market.format_quote_line(quote)
    assert "闪迪" in line
    assert "-8.00%" in line
    assert "2026-08-18" in line
    assert "新闻标题不作为精确涨跌" in line
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests/test_external_market.py::test_overnight_leader_codes_are_sox_and_four_names intelligence/tests/test_external_market.py::test_format_quote_line_exposes_bound_pct_chg -q`

Expected: FAIL (`overnight_leader_codes` / `format_quote_line` missing)

- [ ] **Step 3: Minimal implementation**

Add NVDA / MU / HYNIX (`000660.KS`) / SNDK to `_SYMBOLS`. Add `overnight_leader_codes()`, `format_quote_line()`, `resolve_overnight_leaders()` that calls `fetch_yahoo_finance_quotes(..., symbols=overnight_leader_codes())`. Do not change `requested_symbols()` defaults.

- [ ] **Step 4: Tests pass**

- [ ] **Step 5: Commit** after the episode hook is also green (one product commit is enough)

---

### Task 2: Hang quotes on overnight `market_data`

**Files:**
- Modify: `intelligence/services/episode_tools.py`
- Modify: `intelligence/services/research_tool_registry.py` (`_TOOL_CONTRACTS["market_data"]`)
- Test: `intelligence/tests/test_episode_tools.py`

- [ ] **Step 1: Failing test**

Fifth-round question + mocked `resolve_overnight_leaders` → `market_data` evidence contains 英伟达 / 美光 / SK海力士 / 闪迪 and a signed pct. Local forecast `"昨天的反弹能持续多久"` does not call the resolver.

- [ ] **Step 2: Implement** in `market_data_runner` after A-share evidence. Skip when `fixture_policy.external_search_enabled` is false. Yahoo failure becomes a gap string, not a hard fail.

- [ ] **Step 3: Existing local-forecast and P0-A auth tests stay green**

---

### Out of scope

- New capability / new tool
- Rebuilding web-access CDP
- Opening news/web for all forecasts
- Changing verification or `memory_gate`
- Cutting 8792
