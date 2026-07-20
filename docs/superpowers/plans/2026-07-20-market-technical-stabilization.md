# Market Technical Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让技术位回答只使用已完成日线，正确区分实时价格、确定性成功和证据缺口，并在 8792 切换前通过真实行情 E2E。

**Architecture:** 在 `market_technical.py` 中把行情解析、交易日完成判定、证券解析和技术计算分成明确边界；`ask.py` 只接收结构化结果并选择 `market_technical` 或 `evidence_gap` 展示契约。Controller 与 orchestrator 只负责传递完整裁决和准确 phase，不再让旧模板或 LLM fallback 覆盖确定性结果。

**Tech Stack:** Python 3.11、dataclasses、zoneinfo、pytest、现有 Tencent ifzq adapter、`AnswerSpec`/`EvidenceAtom`、`ProviderTrace`。

---

## 文件地图

- Modify: `intelligence/services/market_technical.py`：行情模型、完成日线筛选、代码解析、技术位计算和 provenance。
- Modify: `intelligence/services/ask.py`：行情成功/缺口的专属 AnswerSpec 构造和短答投影。
- Modify: `intelligence/services/answer_model.py`：专属 presentation kind 和控制面诊断隔离。
- Modify: `intelligence/services/conversation_orchestrator.py`：确定性 phase、LLM fallback 条件、完整 routing envelope 同步。
- Modify: `intelligence/services/turn_controller.py`：controller decision 作为 TurnIntent 单一事实源。
- Modify: `intelligence/services/research_contract.py`：补齐 route envelope 的 subject kind、required outputs 和 research mode 同步字段。
- Test: `intelligence/tests/test_market_technical.py`：新增时间语义、成交量、代码解析和缺口投影回归。
- Test: `intelligence/tests/test_conversation_orchestrator.py`：新增确定性成功不降级和完整 envelope 一致性回归。
- Test: `intelligence/tests/test_turn_controller.py`：新增主体/类型冲突覆盖回归。

## Task 1: 先锁定盘中日线和缺口行为

**Files:**
- Modify: `intelligence/tests/test_market_technical.py`

- [ ] **Step 1: 写失败测试**

```python
def test_intraday_last_bar_is_excluded_from_technical_calculation(monkeypatch):
    monkeypatch.setattr(market_technical, "now_shanghai", lambda: dt("2026-07-20T12:45:00+08:00"))
    series = make_series(last_date="2026-07-20", quote_at="20260720120500")
    result = market_technical.compute_market_technical(series)
    assert result.as_of == "2026-07-17"
    assert result.live_quote.price == Decimal("1712.12")
    assert result.live_bar_used is False

def test_gap_projection_does_not_render_base_finance_sections(monkeypatch):
    result = run_market_answer(provider_error="timeout")
    assert result.answer_spec.presentation_kind == "evidence_gap"
    assert "主要风险" not in result.text
    assert "客户验证" not in result.text
    assert "图谱" not in result.text
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest -q intelligence/tests/test_market_technical.py -k 'intraday or gap_projection'`

Expected: FAIL because the current implementation uses `bars[-1]` and still routes the gap through the generic AnswerSpec.

- [ ] **Step 3: 保留失败测试并提交测试基线**

```bash
git add intelligence/tests/test_market_technical.py
git commit -m "test: define completed-bar and market-gap contracts"
```

## Task 2: 建立完成日线、实时行情和成交量模型

**Files:**
- Modify: `intelligence/services/market_technical.py`
- Test: `intelligence/tests/test_market_technical.py`

- [ ] **Step 1: 增加数据模型**

```python
@dataclass(frozen=True)
class DailyBar:
    date: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None = None

@dataclass(frozen=True)
class LiveQuote:
    price: Decimal
    as_of: str
    source: str

@dataclass(frozen=True)
class MarketSeries:
    instrument: MarketInstrument
    completed_bars: tuple[DailyBar, ...]
    live_bar: DailyBar | None
    live_quote: LiveQuote | None
    source_as_of: str
```

- [ ] **Step 2: 实现交易时段完成判定**

新增纯函数 `split_completed_bars(bars, quote_timestamp, now)`：同日行只有在上海时间 15:05 之后、报价时间不早于 15:00 且日期一致时进入 `completed_bars`；其余同日行进入 `live_bar`。时间戳缺失或矛盾时采用排除策略。

- [ ] **Step 3: 解析 Tencent 行的 volume 和 quote 时间**

把响应行的第六列解析成 `Decimal`；解析失败使用 `None`，不伪造 0。把 quote timestamp 映射到 `LiveQuote.as_of`，并保留原始 provider 时间在 `ProviderTrace.detail`。

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 -m pytest -q intelligence/tests/test_market_technical.py -k 'bar or volume or timestamp'`

Expected: PASS，且没有将盘中行放入 `completed_bars`。

- [ ] **Step 5: 提交**

```bash
git add intelligence/services/market_technical.py intelligence/tests/test_market_technical.py
git commit -m "fix: separate completed bars from live market quote"
```

## Task 3: 统一证券解析和 provider 能力登记

**Files:**
- Modify: `intelligence/services/market_technical.py`
- Modify: `intelligence/services/query_understanding.py`
- Test: `intelligence/tests/test_market_technical.py`
- Test: `intelligence/tests/test_query_understanding.py`

- [ ] **Step 1: 写代码映射回归**

```python
def test_beijing_920_code_is_not_misclassified_as_shanghai():
    assert resolve_market_instrument("920022").exchange == "BJ"
    assert resolve_market_instrument("920022.BJ").provider_symbol == "bj920022"

def test_unsupported_alias_is_not_advertised_as_executable():
    capability = capability_for("932000.CSI")
    assert capability.executable is False
    assert capability.reason == "provider_unsupported"
```

- [ ] **Step 2: 实现 `resolve_market_instrument()`**

解析顺序固定为后缀、指数别名、`92xxx → BJ`、已登记股票前缀、无法判断。返回 `instrument_resolution_gap` 而不是猜测交易所。

- [ ] **Step 3: 给别名注册表增加 capability 状态**

每个别名记录 `provider_symbol`、`history_window` 和 `executable`。只有映射存在且实际历史长度达到 60 根时才让 `market_technical` head capability 可执行。

- [ ] **Step 4: 运行路由和代码解析测试**

Run: `python3 -m pytest -q intelligence/tests/test_market_technical.py intelligence/tests/test_query_understanding.py -k 'market_technical or exchange or alias'`

Expected: PASS，`920022` 不再变成 `sh920022`，未支持别名进入明确 gap。

- [ ] **Step 5: 提交**

```bash
git add intelligence/services/market_technical.py intelligence/services/query_understanding.py intelligence/tests/test_market_technical.py intelligence/tests/test_query_understanding.py
git commit -m "fix: make market instrument resolution capability-aware"
```

## Task 4: 让技术位计算只消费 completed bars，并保留计算血缘

**Files:**
- Modify: `intelligence/services/market_technical.py`
- Test: `intelligence/tests/test_market_technical.py`

- [ ] **Step 1: 修改计算函数签名**

```python
def compute_market_technical(series: MarketSeries) -> MarketTechnicalResult:
    bars = series.completed_bars
    if len(bars) < 60:
        return MarketTechnicalResult.gap("insufficient_history", required=60, actual=len(bars))
    return calculate_levels(bars, live_quote=series.live_quote)
```

- [ ] **Step 2: 给每个 level 记录 lineage**

`SupportLevel` 和 `ResistanceLevel` 增加 `bar_dates`, `method`, `inputs`；成交量确认只在所有需要的 `volume` 非空时计算，否则 `volume_confirmation=None`。

- [ ] **Step 3: 编写数值稳定性测试**

```python
def test_support_lineage_uses_only_completed_bar_dates():
    result = compute_market_technical(make_intraday_series())
    assert "2026-07-20" not in result.supports[0].bar_dates
    assert result.supports[0].method in {"ma", "swing_low", "period_low", "gap_cluster"}
```

- [ ] **Step 4: 运行技术计算回归**

Run: `python3 -m pytest -q intelligence/tests/test_market_technical.py`

Expected: PASS，已有 12 项回归和新增 lineage/volume 测试全部通过。

- [ ] **Step 5: 提交**

```bash
git add intelligence/services/market_technical.py intelligence/tests/test_market_technical.py
git commit -m "fix: bind technical levels to completed-bar lineage"
```

## Task 5: 接入专属 AnswerSpec 和正确的 orchestrator phase

**Files:**
- Modify: `intelligence/services/ask.py`
- Modify: `intelligence/services/answer_model.py`
- Modify: `intelligence/services/conversation_orchestrator.py`
- Test: `intelligence/tests/test_market_technical.py`
- Test: `intelligence/tests/test_conversation_orchestrator.py`

- [ ] **Step 1: 构造 `market_technical` 和 `evidence_gap` AnswerSpec**

成功结果写入收盘口径、盘中参考价、点位、方法、失效条件和 evidence ids；失败结果只写 `gap` claim、当前可得字段、缺口类型和验证条件。

- [ ] **Step 2: 修复 template fallback 条件**

把 `conversation_orchestrator.py` 中的 fallback 条件改为：只有 `decision.needs_template is True` 且合成与 owner 都没有输出时，才增加 `llm_unavailable_template_answer`；确定性 `market_technical` 走 `deterministic_verified`。

- [ ] **Step 3: 隔离原始 quality diagnostics**

`render_answer_spec()` 的 fail-closed 分支只输出业务化缺口；原始 `QualityIssue.code/detail` 通过 `ProviderTrace` 或 Inspector payload 返回，不拼进用户正文。

- [ ] **Step 4: 运行展示回归**

Run: `python3 -m pytest -q intelligence/tests/test_market_technical.py intelligence/tests/test_conversation_orchestrator.py -k 'market_technical or deterministic or quality or template'`

Expected: PASS；缺口正文不含“主要风险/客户验证/图谱”，确定性成功不含 `llm_unavailable_template_answer`。

- [ ] **Step 5: 提交**

```bash
git add intelligence/services/ask.py intelligence/services/answer_model.py intelligence/services/conversation_orchestrator.py intelligence/tests/test_market_technical.py intelligence/tests/test_conversation_orchestrator.py
git commit -m "fix: use typed market technical and evidence gap presentations"
```

## Task 6: 统一 controller decision 与 routing envelope

**Files:**
- Modify: `intelligence/services/turn_controller.py`
- Modify: `intelligence/services/conversation_orchestrator.py`
- Modify: `intelligence/services/research_contract.py`
- Test: `intelligence/tests/test_turn_controller.py`
- Test: `intelligence/tests/test_conversation_orchestrator.py`

- [ ] **Step 1: 写主体冲突回归**

```python
def test_controller_subject_wins_when_question_type_is_unchanged():
    decision = decision_with_subject("科创50", subject_kind="index")
    old_intent = intent_with_subject("半导体", question_type=decision.question_type)
    merged = _attach_turn_intent(decision, old_intent)
    assert merged.subject == "科创50"
    assert merged.subject_kind == "index"
```

- [ ] **Step 2: 实现完整字段同步**

继承型追问只保留显式允许继承的字段；普通 turn 用 decision 整体生成 `TurnIntent`，orchestrator 的 `routing_envelope` 使用同一对象的 question type、subject、subject kind、owner、required outputs 和 research mode。

- [ ] **Step 3: 运行 controller/orchestrator 回归**

Run: `python3 -m pytest -q intelligence/tests/test_turn_controller.py intelligence/tests/test_conversation_orchestrator.py -k 'intent or envelope or subject'`

Expected: PASS，类型相同但主体不同的旧 intent 不再覆盖 controller。

- [ ] **Step 4: 提交**

```bash
git add intelligence/services/turn_controller.py intelligence/services/conversation_orchestrator.py intelligence/services/research_contract.py intelligence/tests/test_turn_controller.py intelligence/tests/test_conversation_orchestrator.py
git commit -m "fix: keep controller decision as routing source of truth"
```

## Task 7: 分层回归和真实行情验收

**Files:**
- Test: `intelligence/tests/test_market_technical.py`
- Test: `intelligence/tests/test_conversation_orchestrator.py`
- Modify: `docs/superpowers/plans/2026-07-20-market-technical-stabilization.md`

- [ ] **Step 1: 运行定向测试**

Run: `python3 -m pytest -q intelligence/tests/test_market_technical.py intelligence/tests/test_turn_controller.py intelligence/tests/test_query_understanding.py intelligence/tests/test_conversation_orchestrator.py`

Expected: 全部通过。

- [ ] **Step 2: 运行静态检查**

Run: `python3 -m compileall -q intelligence/services/market_technical.py intelligence/services/ask.py intelligence/services/answer_model.py intelligence/services/conversation_orchestrator.py intelligence/services/turn_controller.py && git diff --check`

Expected: 无编译错误、无 whitespace error。

- [ ] **Step 3: 运行全量 intelligence 测试**

Run: `python3 -m pytest -q intelligence/tests`

Expected: 新增失败为 0；既有 userspace/subconscious 宿主路径失败必须单独与 baseline 对照，不得伪装成全绿。

- [ ] **Step 4: 运行临时端口 E2E**

依次提交“科创50的支撑点位在哪”“沪深300压力位在哪里”“920022支撑位在哪”“北证50支撑位在哪”和 provider 失败注入，保存正文、AnswerSpec、phase、degrades、trace、as-of 与耗时。

- [ ] **Step 5: 提交验收记录**

```bash
git add docs/superpowers/plans/2026-07-20-market-technical-stabilization.md
git commit -m "docs: record market technical stabilization verification"
```

