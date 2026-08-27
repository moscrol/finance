# Operator Prefetch OS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 空 `manual + []` 不再盖掉历史类比信封；`history_analog` / regime 问句在 Engine A 开场预取必须带**按 as_of 截断的** D10 窗口，或显式 gap。

**Architecture:** 三刀，都不换引擎。第一刀收窄 `turn_controller._deterministic_decision` 的旗标短路。第二刀给 D10 取数加 as_of 截断（**必须先于第三刀**，否则接进来的是带未来数据的块）。第三刀在已有 `collect_prefetch_items` 上按算子追加 D10 / gap，不把 D10 注册成第 13 个 agent 工具。权威设计：`docs/superpowers/specs/2026-08-23-operator-prefetch-os-design.md`。

**Tech Stack:** Python 3.12、pytest、DuckDB 只读、现役 `decide_turn` / `asof_prefetch` / `market_regime_analogs`。

---

## 文件地图

| 文件 | 职责 |
|---|---|
| `intelligence/tests/test_turn_controller.py` | 空 manual / 非空 skill / 取值对照 |
| `intelligence/services/turn_controller.py` | 只认非空 `selected_skill_ids` |
| `intelligence/tests/test_market_regime_analogs.py` | D10 as_of 截断（追加到既有 `LoaderAndBlockTests`） |
| `intelligence/services/market_regime_analogs.py` | 取数层按 as_of 截断，三个函数透传 |
| `intelligence/tests/test_asof_prefetch_regime_analog.py` | D10 正向出块 + gap + 非类比题不注入（新建） |
| `intelligence/services/asof_prefetch.py` | 算子供数：D10 出块或 gap；D8/D11 留 gap |

本 plan **只做 spec P0**。发布层 complete 假绿、类比做法 skill、开关板 n≥10 不在此文件。

冻结题面（全文照抄，禁止改写）：

```text
用spt和风远的结合视角，说一下目前的行情和之前的哪一段历史行情比较相似，个股怎么对标。
```

解释器一律用 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`（本工作树无独立 venv）。所有命令在 `/Users/a77/fwp-wt-operator-prefetch-os` 下执行。

### 施工前必读的三条已核实事实（**不要再探一遍**）

1. 冻结题面上：`parse_regime_intent=True`、`parse_analog_intent=**False**`、`parse_stock_analog_intent=True`。所以本题走 D10 分支 + D11 gap 分支，**不走** D8 分支。
2. `regime_block_for_llm` / `load_market_regime_artifact` / `load_market_regime_vectors` 今日**都没有 as_of 参数**，`load_market_regime_vectors` 的 base 查询无 `where`，`find_regime_analogs` 把「当前窗口」取成**库尾** `z_rows[n-window:]`。
3. `market_regime_analogs.py` 顶部**没有** `from datetime import date`，Task 2 需自行补。
4. `intelligence/tests/test_turn_controller.py` 已有 `_no_llm`（`:15`）与 `decide_turn` import（`:12`），Task 1 的测试直接用，不要重新定义。
5. `test_market_regime_analogs.py` 的 `_make_db` 不使用 `self`，`LoaderAndBlockTests._make_db(None, path, ...)` 可直接跨文件复用（已实测）。`_day(i) = 2025-01-01 + i 天`，故 `_day(120)='2025-05-01'`、`_day(199)='2025-07-19'`。

---

### Task 1: 空 manual 不得盖掉 comparison_analog

**Files:**
- Modify: `intelligence/tests/test_turn_controller.py`
- Modify: `intelligence/services/turn_controller.py:313`
- Test: `intelligence/tests/test_turn_controller.py`

- [ ] **Step 1: Write the failing tests**

在 `intelligence/tests/test_turn_controller.py` 文件末尾、最后一个测试之后追加：

```python
_FROZEN_ANALOG = (
    "用spt和风远的结合视角，说一下目前的行情和之前的哪一段历史行情比较相似，个股怎么对标。"
)


def test_empty_manual_does_not_override_comparison_analog() -> None:
    decision = decide_turn(
        _FROZEN_ANALOG,
        skill_mode="manual",
        selected_skill_ids=(),
        llm_complete=_no_llm,
    )
    assert decision.question_type == "comparison_analog"
    assert decision.reason != "用户显式选择了工作流能力"
    assert decision.turn_intent is not None
    assert "history_analog" in decision.turn_intent.operators


def test_nonempty_manual_skill_still_counts_as_explicit_choice() -> None:
    decision = decide_turn(
        _FROZEN_ANALOG,
        skill_mode="manual",
        selected_skill_ids=("daily-agent",),
        llm_complete=_no_llm,
    )
    assert decision.reason == "用户显式选择了工作流能力"


def test_empty_manual_does_not_reroute_quick_fact() -> None:
    decision = decide_turn(
        "宁德时代今天收盘多少",
        skill_mode="manual",
        selected_skill_ids=(),
        llm_complete=_no_llm,
    )
    assert decision.question_type == "quick_fact"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_turn_controller.py::test_empty_manual_does_not_override_comparison_analog \
  intelligence/tests/test_turn_controller.py::test_nonempty_manual_skill_still_counts_as_explicit_choice \
  intelligence/tests/test_turn_controller.py::test_empty_manual_does_not_reroute_quick_fact \
  -q
```

Expected: **2 failed, 1 passed**。三条各自的今日实测值（2026-08-23 @ `90c069cb`，已跑过，不必再探）：

| 测试 | 今日 | 判定 |
|---|---|---|
| `test_empty_manual_does_not_override_comparison_analog` | `question_type='general_finance_qa'`，`reason='用户显式选择了工作流能力'` | FAIL（预期内） |
| `test_empty_manual_does_not_reroute_quick_fact` | `question_type='stock_deep_dive'` | FAIL（预期内） |
| `test_nonempty_manual_skill_still_counts_as_explicit_choice` | `reason='用户显式选择了工作流能力'` | **PASS**（守门用，改完必须仍绿） |

第二条今天就红，是因为空 manual 短路本身把取值题也盖住了——这正是本 Task 要修的同一个洞，不是另一个问题。

- [ ] **Step 3: Write the minimal implementation**

`intelligence/services/turn_controller.py:313` 单行替换：

```python
    if selected_skill_ids or skill_mode == "manual":
```

改成：

```python
    if selected_skill_ids:
```

不要改 reason 文案。不要动 `_fine_grained_route_row`。**本步只改这一行**，其余一字不动。

- [ ] **Step 4: Re-run the three tests**

同一条 pytest 命令。Expected: **3 passed**。

修复后的目标值已实测（走等价的非 manual 路径量得，2026-08-23 @ `90c069cb`）：

```text
宁德时代今天收盘多少   → quick_fact          reason='路由表命中 quick_fact：高置信词面命中细粒度路由'      ops=()
冻结题面              → comparison_analog   reason='路由表命中 comparison_analog：高置信词面命中细粒度路由' ops=('history_analog',)
```

若改完取值题落到 `quick_fact` 以外，是实现过窄，**不得**把断言改成实际值就范。

再跑已有类比路由，防手滑改到解析器：

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_market_regime_analogs.py::WiringTests -q
```

Expected: passed（`WiringTests` 含 `test_regime_query_routes_to_comparison_analog`）。

- [ ] **Step 5: Commit（等用户点头再执行）**

```bash
git add intelligence/tests/test_turn_controller.py intelligence/services/turn_controller.py
git commit -- intelligence/tests/test_turn_controller.py intelligence/services/turn_controller.py
```

Message:

```text
fix(routing): empty manual no longer overrides analog route
```

---

### Task 2: D10 取数按 as_of 截断（**必须在 Task 3 之前完成**）

**为什么先做：** 今日 D10 读全库、把「当前窗口」取成库尾、并用**全历史**算 z 标准化系数。直接把它接进 as_of-aware 的预取层，等于给历史截止日的问句喂未来数据。本仓已为同一失败形状留过测试（`test_asof_prefetch_dual_red.py::test_fermentation_query_cutoff_is_requested_as_of_not_current`），不能开倒车。

**一刀解四处：** 只在**取数层**加 `where trade_date <= as_of`，下游全部自动被截断——
当前窗口（`z_rows[n-window:]`）、z 标准化系数（`standardize_vectors(vectors)`）、
候选窗口枚举、后续 5/10/20 日事实（`_forward_facts(vectors[end:], h)`）都只消费 `vectors`。

**Files:**
- Modify: `intelligence/tests/test_market_regime_analogs.py`
- Modify: `intelligence/services/market_regime_analogs.py`
- Test: `intelligence/tests/test_market_regime_analogs.py`

- [ ] **Step 1: Write the failing tests**

在 `intelligence/tests/test_market_regime_analogs.py` 的 **`LoaderAndBlockTests` 类内部**、最后一个方法之后追加两个方法（放这个类里是为了直接复用它的 `self._make_db`，不另建第二份建表 SQL）：

```python
    def test_loader_respects_as_of(self) -> None:
        """取数层是唯一截断点：as_of 之后的行不得进入向量序列。"""
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db, n=200, hot_ranges=[(40, 60), (180, 200)])
            con = duckdb.connect(str(db), read_only=True)
            cut_vectors, _ = load_market_regime_vectors(con, as_of=_day(120))
            all_vectors, _ = load_market_regime_vectors(con)
            con.close()
        self.assertEqual(len(cut_vectors), 121)
        self.assertEqual(str(cut_vectors[-1]["trade_date"]), _day(120))
        self.assertEqual(len(all_vectors), 200)

    def test_analog_windows_never_cross_as_of(self) -> None:
        """历史窗口与其后续事实都不得跨过问句截止日。"""
        cut = _day(120)
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db, n=200, hot_ranges=[(40, 60), (180, 200)])
            artifact = load_market_regime_artifact(db, as_of=cut)
            cut_block = regime_block_for_llm(db, as_of=cut)
            full_block = regime_block_for_llm(db)
        self.assertTrue(artifact.available)
        for a in artifact.analogs:
            self.assertLessEqual(str(a["end_date"]), cut)
        self.assertIn("[D10]", cut_block)
        # 库尾 180~200 是涨停潮、101~120 是缩量弱势；截断若失效两块会一模一样
        self.assertNotEqual(cut_block, full_block)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_market_regime_analogs.py::LoaderAndBlockTests -q
```

Expected: 两条新测试 FAIL，报 `TypeError: ... unexpected keyword argument 'as_of'`。既有方法仍全绿。

- [ ] **Step 3: Write the minimal implementation**

改 `intelligence/services/market_regime_analogs.py`，共四处。

**3a. 顶部 import 区**（`from dataclasses import dataclass` 之后）新增一行：

```python
from datetime import date
```

**3b. `load_market_regime_vectors`（`:327`）加参数并在 base 查询上截断。** 把函数签名与 base 查询这一段：

```python
def load_market_regime_vectors(con: Any) -> tuple[list[dict[str, Any]], list[str]]:
    """从只读连接拼每日情绪向量。返回 (升序向量列表, 缺失特征名列表)。"""
    try:
        base = con.execute(
            "select trade_date, total_amount, advancers, limit_up, limit_down, "
            "sh_deviation_pct, sh_index_pct_chg "
            "from fact_market_daily order by trade_date asc"
        ).fetchall()
    except Exception:
        return [], list(FEATURES)
```

替换为：

```python
def load_market_regime_vectors(
    con: Any, as_of: date | str | None = None
) -> tuple[list[dict[str, Any]], list[str]]:
    """从只读连接拼每日情绪向量。返回 (升序向量列表, 缺失特征名列表)。

    ``as_of`` 非空时只取 ``trade_date <= as_of``。这是 D10 唯一的截断点：
    当前窗口签名、z 标准化系数、候选窗口、后续 5/10/20 日事实全部只消费本函数
    的返回值，因此截在这里即可杜绝未来数据。辅表不必再加同一条件——辅表值按
    日期键回查 base 行，as_of 之后的辅表行不可达。
    """
    base_sql = (
        "select trade_date, total_amount, advancers, limit_up, limit_down, "
        "sh_deviation_pct, sh_index_pct_chg "
        "from fact_market_daily"
    )
    params: list[Any] = []
    if as_of is not None:
        base_sql += " where trade_date <= ?"
        params.append(str(as_of))
    base_sql += " order by trade_date asc"
    try:
        base = con.execute(base_sql, params).fetchall()
    except Exception:
        return [], list(FEATURES)
```

函数其余部分（`if not base:` 起到 return）**一字不动**。

**3c. `load_market_regime_artifact`（`:368`）透传。** 签名：

```python
def load_market_regime_artifact(
    market_db_path: str | Path | None,
    window: int = DEFAULT_WINDOW,
) -> MarketRegimeArtifact:
```

改成：

```python
def load_market_regime_artifact(
    market_db_path: str | Path | None,
    window: int = DEFAULT_WINDOW,
    as_of: date | str | None = None,
) -> MarketRegimeArtifact:
```

并把函数体内唯一一处调用：

```python
        vectors, missing = load_market_regime_vectors(con)
```

改成：

```python
        vectors, missing = load_market_regime_vectors(con, as_of=as_of)
```

**3d. `regime_block_for_llm`（`:459`）透传。** 签名：

```python
def regime_block_for_llm(
    market_db_path: str | Path | None,
    window: int = DEFAULT_WINDOW,
) -> str:
```

改成：

```python
def regime_block_for_llm(
    market_db_path: str | Path | None,
    window: int = DEFAULT_WINDOW,
    as_of: date | str | None = None,
) -> str:
```

并把：

```python
    artifact = load_market_regime_artifact(market_db_path, window=window)
```

改成：

```python
    artifact = load_market_regime_artifact(market_db_path, window=window, as_of=as_of)
```

**默认 `as_of=None` = 保持今日行为。** Engine B 唯一调用点 `ask.py:3986` 不传该参数，行为不变；本单不动 Engine B。

- [ ] **Step 4: Re-run**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_market_regime_analogs.py -q
```

Expected: 全 passed（新增 2 条 + 既有全部）。若既有 `test_loader_assembles_vectors` / `test_block_renders_with_citation_and_discipline` 变红，说明默认路径被改动，回退重做——本步不允许改变 `as_of=None` 时的任何行为。

- [ ] **Step 5: Commit（等用户点头再执行）**

```bash
git add intelligence/tests/test_market_regime_analogs.py intelligence/services/market_regime_analogs.py
git commit -- intelligence/tests/test_market_regime_analogs.py intelligence/services/market_regime_analogs.py
```

Message:

```text
fix(d10): truncate regime analog inputs at as_of
```

---

### Task 3: 算子命中时预取 D10 或 gap

**Files:**
- Create: `intelligence/tests/test_asof_prefetch_regime_analog.py`
- Modify: `intelligence/services/asof_prefetch.py`
- Test: `intelligence/tests/test_asof_prefetch_regime_analog.py`

- [ ] **Step 1: Write the failing tests**

新建 `intelligence/tests/test_asof_prefetch_regime_analog.py`，全文如下：

```python
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from intelligence.services.asof_prefetch import collect_prefetch_items
from intelligence.services.market_regime_analogs import parse_regime_intent
from intelligence.tests.test_market_regime_analogs import LoaderAndBlockTests, _day

try:
    import duckdb
except Exception:  # pragma: no cover
    duckdb = None

_FROZEN_ANALOG = (
    "用spt和风远的结合视角，说一下目前的行情和之前的哪一段历史行情比较相似，个股怎么对标。"
)


def _make_market_db(path: Path, n: int = 200) -> None:
    """复用 D10 既有夹具，避免第二份建表 SQL 漂移；_make_db 不使用 self。"""
    LoaderAndBlockTests._make_db(None, path, n=n, hot_ranges=[(40, 60), (180, 200)])


def _blob(items) -> str:
    return "\n".join(f"{item.title}\n{item.detail}" for item in items)


def test_frozen_question_is_regime_analog() -> None:
    assert parse_regime_intent(_FROZEN_ANALOG)


def test_missing_db_still_emits_historical_analog_gap(tmp_path: Path) -> None:
    items = collect_prefetch_items(
        question=_FROZEN_ANALOG,
        question_type="general_finance_qa",
        subject="",
        as_of=date(2026, 8, 21),
        market_db_path=tmp_path / "missing.duckdb",
    )
    assert items
    blob = _blob(items)
    assert "historical_analogs" in blob
    assert "gap" in blob.lower()


def test_frozen_question_also_marks_stock_analog_gap(tmp_path: Path) -> None:
    """题面含「个股怎么对标」：D11 未接 Engine A，必须留 gap，不得静默无证据。"""
    items = collect_prefetch_items(
        question=_FROZEN_ANALOG,
        question_type="general_finance_qa",
        subject="",
        as_of=date(2026, 8, 21),
        market_db_path=tmp_path / "missing.duckdb",
    )
    blob = _blob(items)
    assert "D11" in blob


@pytest.mark.skipif(duckdb is None, reason="duckdb 不可用")
def test_regime_question_with_data_emits_real_d10_block(tmp_path: Path) -> None:
    """有数据时必须真的出 D10 块——否则「永远返回 gap」的实现也能全绿。"""
    db = tmp_path / "m.duckdb"
    _make_market_db(db)
    items = collect_prefetch_items(
        question=_FROZEN_ANALOG,
        question_type="general_finance_qa",
        subject="",
        as_of=date.fromisoformat(_day(120)),
        market_db_path=db,
    )
    blob = _blob(items)
    assert "[D10]" in blob
    assert "历史相似窗口" in blob
    assert "后续5日" in blob


@pytest.mark.skipif(duckdb is None, reason="duckdb 不可用")
def test_d10_prefetch_honours_as_of(tmp_path: Path) -> None:
    """两个不同 as_of 必须给出不同的块；相同即说明 as_of 被忽略。"""
    db = tmp_path / "m.duckdb"
    _make_market_db(db)

    def _run(cut: str) -> str:
        return _blob(
            collect_prefetch_items(
                question=_FROZEN_ANALOG,
                question_type="general_finance_qa",
                subject="",
                as_of=date.fromisoformat(cut),
                market_db_path=db,
            )
        )

    early = _run(_day(120))
    late = _run(_day(199))
    assert "[D10]" in early and "[D10]" in late
    assert early != late


def test_non_analog_question_does_not_grow_d10(tmp_path: Path) -> None:
    items = collect_prefetch_items(
        question="宁德时代今天收盘多少",
        question_type="quick_fact",
        subject="宁德时代",
        as_of=date(2026, 8, 21),
        market_db_path=tmp_path / "missing.duckdb",
    )
    blob = _blob(items)
    assert "D10" not in blob
    assert "historical_analogs" not in blob
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_asof_prefetch_regime_analog.py -q
```

Expected: `test_frozen_question_is_regime_analog` 与 `test_non_analog_question_does_not_grow_d10` PASS；其余四条 FAIL（今日 `con is None` 直接 `return ()`，有库时也没有 D10 分支）。

- [ ] **Step 3: Write the minimal implementation**

**这是锚点式编辑，不重写整个函数。** 现有的 `market_forecast` / 发酵两段（约 60 行）一个字都不要重打。

**3a. 在 `intelligence/services/asof_prefetch.py` 顶部 import 区**，紧接现有 `from intelligence.services.theme_lifecycle_timeline import (...)` 块之后新增：

```python
from intelligence.services.market_analogs import parse_analog_intent
from intelligence.services.market_regime_analogs import (
    parse_regime_intent,
    regime_block_for_llm,
)
from intelligence.services.stock_analogs import parse_stock_analog_intent
```

**3b. 在 `def collect_prefetch_items(` （`:367`）这一行之前**新增下面这个模块级私有函数：

```python
def _history_analog_items(
    question: str,
    as_of: date,
    as_of_iso: str,
    db_path: Path,
) -> list[PrefetchItem]:
    """算子命中即供数：D10 出块或 gap；D8 / D11 在 P0 只留 gap。

    不变量：D10 取数按 as_of 截断（见 market_regime_analogs.load_market_regime_vectors），
    禁止把问句截止日之后的行情写进历史窗口。
    """
    items: list[PrefetchItem] = []
    wants_regime = parse_regime_intent(question)
    wants_theme_analog = parse_analog_intent(question) and not wants_regime
    if wants_regime:
        block = regime_block_for_llm(db_path, as_of=as_of)
        if str(block or "").strip():
            items.append(
                PrefetchItem(
                    tool="market_data",
                    title="市场情绪环境类比 [D10]",
                    detail=block,
                    source="本地 DuckDB · D10",
                    source_date=as_of_iso,
                )
            )
        else:
            items.append(
                PrefetchItem(
                    tool="market_data",
                    title="historical_analogs gap（D10 不可用）",
                    detail=(
                        "D10 市场情绪类比不可用（库缺失、历史不足或无可比窗口）。"
                        "historical_analogs 必须标 gap，禁止用画像或框架原文冒充历史窗口。"
                    ),
                    source="本地 DuckDB · D10",
                    source_date=as_of_iso,
                )
            )
    elif wants_theme_analog:
        items.append(
            PrefetchItem(
                tool="market_data",
                title="historical_analogs gap（D8 未预取）",
                detail=(
                    "本题命中题材级历史类比算子，D10 市场环境块不适用；"
                    "D8 未在 Engine A 开场预取接线。historical_analogs 标 gap，"
                    "禁止编造未注册的历史阶段。"
                ),
                source="本地 DuckDB · D8 未预取",
                source_date=as_of_iso,
            )
        )
    if parse_stock_analog_intent(question):
        items.append(
            PrefetchItem(
                tool="market_data",
                title="个股对标 gap（D11 未预取）",
                detail=(
                    "本题含个股对标词面。D11 个股走势类比只在 Engine B 接线，"
                    "且当前实现不按 as_of 截断，P0 不接入 Engine A 预取。"
                    "个股对标必须标 gap，禁止用画像或题材原文冒充个股历史窗口。"
                ),
                source="D11 未预取",
                source_date=as_of_iso,
            )
        )
    return items
```

**3c. 在 `collect_prefetch_items` 内部做唯一一处替换。** 找到这**连续 6 行**：

```python
    con = _connect(db_path)
    if con is None:
        return ()
    items: list[PrefetchItem] = []
    as_of_iso = as_of.isoformat()
    try:
```

替换为：

```python
    items: list[PrefetchItem] = []
    as_of_iso = as_of.isoformat()
    items.extend(_history_analog_items(question, as_of, as_of_iso, db_path))
    con = _connect(db_path)
    if con is None:
        return tuple(items)
    try:
```

函数其余部分（`if question_type == "market_forecast":` 起、发酵段、`finally`、结尾 `return tuple(items)`）**完全不动**。改完确认 `git diff intelligence/services/asof_prefetch.py` 只有 import 块、新函数、这 6→7 行三处。

- [ ] **Step 4: Re-run prefetch tests**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_asof_prefetch_regime_analog.py \
  intelligence/tests/test_asof_prefetch_dual_red.py \
  intelligence/tests/test_prefetch_slot_numbers.py \
  intelligence/tests/test_prefetch_evidence_ordinal.py \
  -q
```

Expected: 全 passed。`test_asof_prefetch_dual_red.py` / `test_prefetch_slot_numbers.py` / `test_prefetch_evidence_ordinal.py` 是双红与发酵两段的回归网——它们变红即说明 3c 的替换越界了。

**不要**把「本机真实库必须有窗口」写成 CI 硬断言，`db/market_feature_store.duckdb` 不在 CI 里。

- [ ] **Step 5: Commit（等用户点头再执行）**

```bash
git add intelligence/tests/test_asof_prefetch_regime_analog.py intelligence/services/asof_prefetch.py
git commit -- intelligence/tests/test_asof_prefetch_regime_analog.py intelligence/services/asof_prefetch.py
```

Message:

```text
fix(prefetch): bind history_analog to an as_of-truncated D10 or an explicit gap
```

---

### Task 4: 定向回归与全量门禁

**Files:**
- 不改生产配置

- [ ] **Step 1: 定向集**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_turn_controller.py \
  intelligence/tests/test_market_regime_analogs.py \
  intelligence/tests/test_asof_prefetch_regime_analog.py \
  intelligence/tests/test_asof_prefetch_dual_red.py \
  intelligence/tests/test_prefetch_slot_numbers.py \
  intelligence/tests/test_prefetch_evidence_ordinal.py \
  intelligence/tests/test_workbench_skill_router.py \
  -q
```

基线：施工前同一组为 **172 passed @ `90c069cb`**。Expected: 172 + 新增条数，0 failed。

`test_workbench_skill_router.py` 锁的是「显式 daily-agent / 今天研究什么」；若空 manual 收窄后有红，读失败断言再决定是测试依赖了错误语义，还是实现过窄——**不得**为了变绿恢复 `or skill_mode == "manual"`（spec §10）。

- [ ] **Step 2: ruff**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check \
  intelligence/services/turn_controller.py \
  intelligence/services/market_regime_analogs.py \
  intelligence/services/asof_prefetch.py \
  intelligence/tests/test_turn_controller.py \
  intelligence/tests/test_market_regime_analogs.py \
  intelligence/tests/test_asof_prefetch_regime_analog.py
```

Expected: 无输出。

- [ ] **Step 3: 全量 pytest 并与 main 对照**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q 2>&1 | tail -20
```

**判据不是「全绿」，是「不比 `gitea/main@90c069cb` 多红」。** 出现失败时，先在干净的 `gitea/main` 检出上跑同一条命令比对；同名同因的失败属存量红，记进本 plan 末尾即可，不得为它改本单代码。

- [ ] **Step 4: 回写账本一行（可选，pathspec）**

若用户要求把 P0 验收记进 `docs/prediction-ledger.md`，新增一行 pending：`空 manual + 冻结类比题 → comparison_analog 且预取含按 as_of 截断的 D10/gap`。不要改三臂旧行的 outcome。

---

## Spec 覆盖自检

| Spec 条款 | Task |
|---|---|
| §2.1 / §5.2 规则 1–2 空 manual | Task 1 |
| §2.1 D10 按 as_of 截断（不变量） | Task 2 |
| §2.1 / §5.2 规则 3–5 D10 或 gap | Task 3 |
| §2.1 「个股对标词面 → D11 或 gap」 | Task 3（gap 侧） |
| §2.1 「analog 无环境词 → D8 至少 gap」 | Task 3（gap 侧） |
| §5.3 取值对照 | Task 1 第三条 |
| §5.3 预取正向（有数据出 D10） | Task 3 |
| §7 不改 route_table capabilities | 全 plan 未列该文件 |
| §8 发布层 / n≥10 | 明确不做 |
| §9 P1 skill/OS、Engine B 传 as_of、D11 接线 | 明确不做 |

无 TBD、无 `保持原实现` 占位符。所有 commit 步默认等用户确认。

## 存量红登记

（Task 4 Step 3 若发现 main 同样失败的用例，写在这里，附同名同因证据。）
