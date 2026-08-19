# Overnight News Hang Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When overnight-hybrid `market_forecast` already executes `market_data`, hang Eastmoney news evidence with `tool=news_search` so the model sees bindable overnight headlines without waiting for a second tool call.

**Architecture:** Mirror `_should_attach_overnight_leaders` / `_overnight_leader_evidence`. Same exception as P0-B Yahoo leaders: not pre-execution of tools (spec #215 vetoed that). Gate on `news_search` in allowed capabilities, overnight external premise, and `fixture_policy.external_search_enabled`. Do not open news for all `market_forecast`. Empty fetch does not fail `market_data`.

**Tech Stack:** Python, pytest, existing `market_news.fetch_eastmoney_news_result` + `build_episode_registry` / `market_data` execute seam.

**Spec:** `docs/learning/spec-continuous-depth-gap-r1.md` sixth-round Knevo gap. Stacked on P0-A/B + P1-C. Not P1-D.

**Seams under test:** `market_data` execution via `build_episode_registry` in `intelligence/tests/test_episode_tools.py`. Stub `episode_tools.market_news.fetch_eastmoney_news_result`. Reuse `_overnight_hybrid_forecast_frame()` and `_market_forecast_frame()`. Do not test private helpers as a public API.

**Out of scope:** new capability / tool slot / required output; episode-instruction string literals; `verification` / `memory_gate` / `route_table` / `build_default_tools` / `_RUNTIME_CAPABILITY_FLOOR`; `requested_symbols()` defaults; P1-D; 8792 cutover; `live_probe ask` / `POST /api/runs`.

---

### Task 1: Failing tests for overnight news hang

**Files:**
- Modify: `intelligence/tests/test_episode_tools.py` (after `test_local_forecast_market_data_does_not_fetch_us_leaders`, ~1109)
- Create: `docs/superpowers/plans/2026-08-19-overnight-news-hang.md` (this file)

- [ ] **Step 1: Write the three failing tests**

```python
def test_overnight_hybrid_market_data_attaches_eastmoney_news(
    tmp_path,
    monkeypatch,
) -> None:
    from intelligence.services.market_news import NewsFetchResult, NewsItem

    frame = _overnight_hybrid_forecast_frame()
    context = build_episode_context(
        frame,
        task_id="overnight-news",
        capabilities=("market_data", "news_search"),
        timeout=30.0,
        latest_data_date="2026-08-18",
    )
    monkeypatch.setattr(
        episode_tools,
        "_market_block",
        lambda *_args: (
            "全市场成交额：24006.36 亿元",
            "本地 DuckDB · 预测盘面窗口",
            "market_forecast_window",
        ),
    )
    monkeypatch.setattr(
        episode_tools.ask_blocks,
        "_market_data_asof",
        lambda *_args, **_kwargs: "2026-08-18",
    )

    def empty_leaders(*_args, **_kwargs):
        return episode_tools.external_market.ExternalMarketResult(
            target_trade_date="2026-08-18",
            source_trade_date="2026-08-18",
            selected_provider=episode_tools.external_market.YAHOO_PROVIDER,
            quotes=(),
            provider_traces=(),
        )

    monkeypatch.setattr(
        episode_tools.external_market,
        "resolve_overnight_leaders",
        empty_leaders,
    )
    called: dict[str, object] = {"n": 0, "keyword": None}

    def fake_news(keyword: str, **_kwargs):
        called["n"] = int(called["n"]) + 1
        called["keyword"] = keyword
        return NewsFetchResult(
            (
                NewsItem(
                    "2026-08-18 22:00:00",
                    "证券时报",
                    "费城半导体指数大跌，存储链领跌",
                    "http://eastmoney.test/sox-1",
                ),
                NewsItem(
                    "2026-08-18 23:00:00",
                    "财联社",
                    "存储周期担忧升温，海力士闪迪齐跌",
                    "http://eastmoney.test/memory-2",
                ),
            ),
            ProviderTrace(
                provider="eastmoney",
                capability="directional_news",
                status="success",
                result_count=2,
            ),
        )

    monkeypatch.setattr(
        episode_tools.market_news,
        "fetch_eastmoney_news_result",
        fake_news,
    )
    registry = build_episode_registry(
        frame,
        context,
        finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
    )
    observation = registry.execute(
        "market_data",
        {},
        context=context,
        step_id="overnight-news:1",
    )
    blob = " ".join(
        f"{item.title} {item.detail}" for item in observation.evidence
    )
    assert called["n"] == 1
    assert called["keyword"] == "美股科技"
    assert any(item.tool == "news_search" for item in observation.evidence)
    assert "费城半导体" in blob
    assert "存储" in blob


def test_local_forecast_market_data_does_not_fetch_overnight_news(
    tmp_path,
    monkeypatch,
) -> None:
    frame = _market_forecast_frame()
    context = build_episode_context(
        frame,
        task_id="local-no-news",
        capabilities=("market_data", "news_search"),
        timeout=30.0,
        latest_data_date="2026-07-23",
    )
    monkeypatch.setattr(
        episode_tools,
        "_market_block",
        lambda *_args: (
            "当前成交额21949亿元",
            "本地 DuckDB · 预测盘面窗口",
            "market_forecast_window",
        ),
    )
    monkeypatch.setattr(
        episode_tools.ask_blocks,
        "_market_data_asof",
        lambda *_args, **_kwargs: "2026-07-23",
    )

    def fail_news(*_args, **_kwargs):
        raise AssertionError("local forecast must not fetch overnight news")

    monkeypatch.setattr(
        episode_tools.market_news,
        "fetch_eastmoney_news_result",
        fail_news,
    )
    registry = build_episode_registry(
        frame,
        context,
        finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
    )
    observation = registry.execute(
        "market_data",
        {},
        context=context,
        step_id="local-no-news:1",
    )
    assert not any(item.tool == "news_search" for item in observation.evidence)


def test_overnight_hybrid_skips_news_when_external_search_disabled(
    tmp_path,
    monkeypatch,
) -> None:
    frame = _overnight_hybrid_forecast_frame()
    context = build_episode_context(
        frame,
        task_id="overnight-news-sealed",
        capabilities=("market_data", "news_search"),
        timeout=30.0,
        latest_data_date="2026-08-18",
    )
    monkeypatch.setattr(
        episode_tools,
        "_market_block",
        lambda *_args: (
            "全市场成交额：24006.36 亿元",
            "本地 DuckDB · 预测盘面窗口",
            "market_forecast_window",
        ),
    )
    monkeypatch.setattr(
        episode_tools.ask_blocks,
        "_market_data_asof",
        lambda *_args, **_kwargs: "2026-08-18",
    )

    def fail_news(*_args, **_kwargs):
        raise AssertionError("sealed fixture must not fetch overnight news")

    monkeypatch.setattr(
        episode_tools.market_news,
        "fetch_eastmoney_news_result",
        fail_news,
    )
    registry = build_episode_registry(
        frame,
        context,
        finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
        fixture_policy=episode_tools.SealedFixturePolicy(),
    )
    observation = registry.execute(
        "market_data",
        {},
        context=context,
        step_id="overnight-news-sealed:1",
    )
    assert not any(item.tool == "news_search" for item in observation.evidence)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_episode_tools.py \
  -k "overnight or local_forecast_market_data" \
  -q --tb=short
```

Expected: `test_overnight_hybrid_market_data_attaches_eastmoney_news` FAIL (no `news_search` evidence / fetch not called). The two skip tests may PASS vacuously until the hang exists — that is acceptable; the attach test is the red bar. Existing leader tests must stay green (they authorize `market_data` only).

---

### Task 2: Hang Eastmoney news on overnight `market_data`

**Files:**
- Modify: `intelligence/services/episode_tools.py` (~215–249 helpers; ~731–745 `market_data_runner`)

- [ ] **Step 1: Add helpers next to the leader helpers**

```python
_OVERNIGHT_NEWS_QUERY = "美股科技"


def _should_attach_overnight_news(
    frame: TaskFrame,
    fixture_policy: SealedFixturePolicy | None,
    allowed_capabilities,
) -> bool:
    if "news_search" not in allowed_capabilities:
        return False
    if frame.question_type != "market_forecast":
        return False
    if fixture_policy is not None and not fixture_policy.external_search_enabled:
        return False
    return evidence_capabilities._has_overnight_external_premise(frame.raw_question)


def _overnight_news_evidence(*, as_of, timeout) -> tuple[list[AgentEvidence], str]:
    result = market_news.fetch_eastmoney_news_result(
        _OVERNIGHT_NEWS_QUERY,
        timeout=timeout,
        as_of=as_of,
    )
    evidence = [
        agent_research.AgentEvidence(
            tool="news_search",
            title=item.title,
            detail=f"{item.date} {item.source}",
            source=item.url,
            source_date=item.date[:10] or None,
            evidence_tier="news",
            independent_key=item.url,
        )
        for item in result.items[:6]
    ]
    evidence = [
        replace(item, content_hash=agent_research.evidence_content_hash(item))
        for item in evidence
    ]
    observation = "；".join(f"{item.detail}《{item.title}》" for item in evidence)
    return evidence, observation
```

Use `agent_research.AgentEvidence` (already the local import style), not a bare `AgentEvidence` unless imported.

- [ ] **Step 2: Call after the overnight-leaders block, before the return**

```python
        if _should_attach_overnight_news(
            frame,
            fixture_policy,
            context.contract.allowed_capabilities,
        ) and not any(item.tool == "news_search" for item in evidence):
            news_timeout = tool_context.deadline.stage_timeout(8.0)
            if news_timeout > 0.001:
                news_evidence, news_obs = _overnight_news_evidence(
                    as_of=served_date,
                    timeout=news_timeout,
                )
                if news_evidence:
                    evidence.extend(news_evidence)
                    if news_obs:
                        observation = "；".join(
                            part for part in (observation, news_obs) if part
                        )
```

Empty fetch: do not fail `market_data`. Do not duplicate if `news_search` is already in the evidence list.

- [ ] **Step 3: Re-run the same pytest -k filter. All overnight + local_forecast_market_data tests pass, including the two existing leader tests.**

---

### Task 3: Sixth-round docs

**Files:**
- Create: `docs/verification/2026-08-19-sixth-round-live.md` (copy `~/.finance-runtime/sixth-round-live/2026-08-19-sixth-round-live.md`; light path edits only)
- Modify: `docs/learning/spec-continuous-depth-gap-r1.md`

- [ ] **Step 1: Copy sixth-round live note into the repo**

- [ ] **Step 2: Update spec status line** to include sixth-round live + this knife

- [ ] **Step 3: Update §四.3** — P1-C closed and later landed on 8792 via `15510ad7`; do not recut for docs. Drop stale 「不合、不切 8792」.

- [ ] **Step 4: Add §四.4 sixth-round live addendum**

  - Primary `run_20260819_105845_919694` @ `15510ad7`: spec 1–5 pass; Yahoo all five bound including HYNIX −8.51% on 2026-08-18; 【互斥因果假说】A 存储见顶 vs B 情绪回吐, lean B; news authorized unused; no invented 2.2万亿/60/27% on primary.
  - Control `run_20260819_110003_775678`: no news/web auth (item 6 pass); public invented 「约2.2万亿」.
  - This knife (overnight news hang) is the remaining Knevo gap; not P1-D.

Do not recut 8792 for docs-only.

---

### Task 4: Commit + Gitea PR (no merge)

- [ ] **Step 1: Commit on `feat/overnight-news-hang`** with a 1–2 sentence why (HEREDOC)

- [ ] **Step 2: `git push -u gitea feat/overnight-news-hang`**

- [ ] **Step 3: POST Gitea PR** `http://127.0.0.1:3300/api/v1/repos/a77/finance-workspace-private/pulls`

Title: 挂隔夜混合预测的东财新闻（P0-B 同形）

Body: summary + test plan. Mention: no merge, no 8792 cut, sixth-round docs included.

Do NOT merge.

---

### Hard constraints (do not violate)

- No new capability / tool slot / required output
- No episode-instruction string literals
- Do not open news for all `market_forecast`
- Do not treat bare 「今晚」 as a trigger (`_has_overnight_external_premise` already)
- Do not relax verification
- Do not change `requested_symbols()` defaults
- Gate `news_search` not in allowed so existing overnight leader tests stay green
- Skip when `fixture_policy.external_search_enabled` is False
- Skip local A-share forecast 「昨天的反弹能持续多久」
- If fetch returns empty, do not fail `market_data`
- Do not duplicate if `news_search` already in the evidence list
- Do not edit `/Users/a77/finance-workspace-private` dirty main
- Do not print secrets
- Do not use `live_probe ask` / `POST /api/runs`
- Do not start P1-D
- Do not change `verification`, `memory_gate`, `route_table`, `build_default_tools`, or `_RUNTIME_CAPABILITY_FLOOR`
