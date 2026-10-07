# 市场上下文证据合同 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: 使用 `subagent-driven-development`，由主协调者派 fresh 实现 agent，按 A、B 两个独立任务执行，每个任务完成后独立 Spec→Standards 复核。下列 checkbox 每步为一个约 2–5 分钟动作；测试/门禁的等待单独记实际耗时。用户已授权推进，不再提问执行方式。

**Goal:** 让 D4 保全本表主题覆盖、如实区分事实/派生信号/方法，并让原用户的目标日期与资料授权截止从可信输入贯穿实际消费者。

**Architecture:** 在现有 `ask_blocks` 增加不可变结构快照，两个既有 D4 工具适配点消费同一个结构投影。时间合同先从完整原用户消息冻结，再投影到现有 Envelope/Frame/TurnIntent/context；模型分析字段和资料日期不能给自己扩权。A 先完成，B 随后完成，不重做编排。

**Tech Stack:** Python frozen dataclass、DuckDB 聚合与窗口函数、现有 ResearchToolRegistry / FinanceResearchHarness / ContinuousTurnAdapter、pytest；解释器固定 `.venv-workbench/bin/python`。

---

## 执行范围与证据纪律

设计：[2026-10-08-market-context-evidence-design.md](../specs/2026-10-08-market-context-evidence-design.md)。基线 `82de3fb730a4175170b4e6ba472e130e5ef87ab7`。当前独占树 `/Users/a77/.codex/worktrees/knevo-coverage-release-1007/finance-workspace-private`，分支 `codex/market-context-contract-1008`。先 `git status --short && git branch --show-current`；若出现他人改动，依 AGENTS 隔离，不接管它们。本设计/计划提交不代表源码已改、测试已跑、部署或质量已通过。

现役回合 900 秒/120 步、工具能力保持不变。`ASK_SEMANTIC_JUDGE` 保既有 off 选择；`ASK_EVIDENCE_JUDGE` 既有配置/预算不改，本题零调用不能证明关闭。不新增工具、开关、注册表/台账、输出章节、特定中文金融词补丁。provider 的 repair_finalize 截断/40 秒预算不在任务中。

原确定性诊断 CLI 会在脚本自己的 `ROOT` 写 `repro-*.json`，**不能直接在原件目录重跑**。实现前需看原报告与 machine.json；需要复用脚本时复制到一个新的专属目录，设置候选 `DIAG_SOURCE`，保留 inherited `expected_sha=82...` 只是旧见证身份，并另记候选 `git rev-parse HEAD`，不能把旧 expected_sha 当候选收据。原脚本直接调用混合文本→通用转卡路径，A 改后产品路径已变；用下列正式测试重放同夹具、同失败断言，不改通用转换器以求旧诊断全绿，不篡改旧报告。

```bash
git status --short && git branch --show-current
.venv-workbench/bin/python scripts/workspace.py doctor
```

期望：本任务树干净，doctor ready。只读原报告，不读私有用户台账。新测试数据库全部在 pytest `tmp_path`，外呼/模型用抛错替身关闭；fixture 不是生产行情。

## 文件与责任

| 文件 | 实施责任 |
| --- | --- |
| `intelligence/services/ask_blocks.py` | A 的 frozen 类型、同一只读查询快照、有限预览、旧 renderer 与信号语义 |
| `intelligence/services/episode_tools.py` | A 的结构→证据/指导/query_basis 共用投影及 mainline_runner；B 的目标日期消费与 overnight 新闻越界分支 |
| `intelligence/services/ask.py` | 仅迁移 `_generic_mainline_context` 这个同源适配点，不重写引擎 B |
| `intelligence/tests/test_market_context_contract.py`（新） | 原诊断夹具的真实 DuckDB→registry→shared projection 闭环 |
| `intelligence/services/temporal_contract.py`（新） | B 的 pure 类型、共享日期 primitives、来源编译、不可扩权的 context 选择；不得 import runtime |
| `intelligence/services/honesty_gates.py` | 既有截止 parser 的兼容入口与共同控制语法 |
| `intelligence/services/historical_research/intent.py` | 提炼复用日期/直接区间规则，保历史授权语义 |
| `intelligence/services/query_understanding.py` / `task_frame.py` | 合同投影/序列化/新 hash，兼容旧无字段输入 |
| `intelligence/services/research_contract.py` / `turn_controller.py` | TurnIntent/context 类型，模型前冻结，续轮传递 |
| `intelligence/runtime/conversation_orchestrator.py` | 原 user 消息核验与唯一输入权威 Seam，controller 前冻结、后固定投影 |
| `intelligence/services/episode_factory.py` / `intelligence/runtime/continuous_turn_adapter.py` | 消费并核对冻结权限，禁止未指定/无效混淆 |
| `intelligence/services/research_tool_registry.py` | 按现有 typed 资料时点真正扣除未来内容及不安全原观察 |
| `intelligence/tests/test_temporal_contract.py`（新） / 现有测试文件 | 复用原 temporal cases、类型/hash/继承及实际消费者测试 |
| `docs/agent-product-door.md` | 与改 runtime 同提交解释新输入/消费合同及实际限制 |

类型和字段的 SSOT 是以上源码 dataclass/docstring；没有新平行数据规范表。不要改 `market_feature_store/schema.sql` 或数据写入链；A 读取当前 schema 即可。

## Task A：完整 D4 摘要 + 每主题预览 + 角色分离

### A1. 写真实读取与投影的红控制

- [ ] **Step A1.1（2–5 分钟）：建立本地 canonical fixture 与真实 tool 调用。** 创建 `intelligence/tests/test_market_context_contract.py`，使用以下完整辅助代码。`init_db(con)` 初始化的是显式临时连接，不使用默认生产 DB。

```python
from dataclasses import replace
import json
import socket

import duckdb
import pytest

from market_feature_store.db import init_db
from intelligence.services import ask_blocks, episode_tools, reading_baseline
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.query_understanding import understand_query
from intelligence.services.research_harness import FinanceResearchHarness

Q = "复盘2026年9月30日的A股主线强弱，只使用截至当日可见的信息。"

class OfflineKnowledge:
    def __init__(self, root):
        self.root = root
    def relation_path(self, name):
        return self.root / name
    def load_relation(self, _name):
        return {"found": False}

@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def refused(*_args, **_kwargs):
        raise AssertionError("contract test attempted network")
    monkeypatch.setattr(socket.socket, "connect", refused)
    monkeypatch.setattr(socket, "create_connection", refused)
    monkeypatch.setattr(socket, "getaddrinfo", refused)

def write_mainline_fixture(path, dominant_rows=31, extra_themes=0):
    rows = [("AAA", f"a{i:02}", i) for i in range(dominant_rows)]
    rows += [("ZZZ", "z_valid", 0)]
    rows += [(f"BBB{i}", f"b{i}", 0) for i in range(extra_themes)]
    with duckdb.connect(str(path)) as con:
        init_db(con)
        con.execute("INSERT INTO fact_market_daily(trade_date) VALUES ('2026-09-30')")
        con.executemany("""INSERT INTO fact_mainline_sector_daily
          (trade_date,theme_code,theme_name,sector_ts_code,sector_name,sort_no)
          VALUES ('2026-09-30',?,?,?,?,?)""",
          [(theme, theme, code, code, order) for theme, code, order in rows])
        con.executemany("""INSERT INTO fact_sector_daily_generation
          (trade_date,sector_universe_snapshot_id,sector_ts_code,sector_name,
           sw_l1,pct_chg,diff_ratio,amount)
          VALUES ('2026-09-30','legacy',?,?,'fixture',2.0,42.0,1100.0)""",
          [(code, code) for _, code, _ in rows])

def project_d4(path, tmp_path):
    frame = understand_query(Q).task_frame
    assert frame is not None
    context = build_episode_context(frame, task_id="d4-contract", today="2026-09-30",
        latest_data_date="2026-09-30", knowledge=OfflineKnowledge(tmp_path),
        capabilities=("mainline_context",), timeout=10.0)
    registry = episode_tools.build_episode_registry(frame, context,
        finance_root=tmp_path, knowledge_wiki=tmp_path / "empty-wiki",
        l3_runner=None,
        fixture_policy=episode_tools.SealedFixturePolicy(market_db_path=path))
    observed = registry.execute("mainline_context", {}, context=context, step_id="d4")
    projected = FinanceResearchHarness().project_tool_result(observed,
        evidence_so_far=observed.evidence, seen_prose=set())
    return observed, json.loads(projected.model_content)

@pytest.mark.parametrize(("n", "extra", "names"), [
    (31, 0, {"AAA", "ZZZ"}),
    (1, 4, {"AAA", "ZZZ", "BBB0", "BBB1", "BBB2", "BBB3"}),
])
def test_all_table_themes_survive_real_shared_projection(tmp_path, n, extra, names):
    path = tmp_path / "fixture.duckdb"
    write_mainline_fixture(path, n, extra)
    observed, model = project_d4(path, tmp_path)
    assert set(model["query_basis"]["theme_names"]) == names
    groups = {g["theme_name"]: g for g in model["query_basis"]["groups"]}
    assert groups["AAA"]["total_rows"] == n
    assert groups["AAA"]["preview_rows"] == min(n, 8)
    assert groups["AAA"]["omitted_rows"] == max(0, n - 8)
    assert groups["ZZZ"]["preview_rows"] == 1
    assert any("z_valid" in item.detail for item in observed.evidence)
    assert model["query_basis"]["scope"] == "current_table_all_themes"

def test_method_rules_remain_guidance_without_fact_identity(tmp_path):
    path = tmp_path / "fixture.duckdb"
    write_mainline_fixture(path)
    observed, model = project_d4(path, tmp_path)
    for rule in reading_baseline.block_rules("D4_mainline"):
        assert rule.id in observed.observation
        assert rule.source in observed.observation
        assert all(rule.rule not in item.detail for item in observed.evidence)
        assert all(rule.id not in item["detail"] for item in model["evidence"])
    assert all(item.source_date == "2026-09-30" for item in observed.evidence)
```

- [ ] **Step A1.2（2–5 分钟）：运行红控制并保存准确范围。**

```bash
.venv-workbench/bin/python -m pytest -q intelligence/tests/test_market_context_contract.py
```

期望当前红：覆盖测试缺 `query_basis`/ZZZ；方法测试发现规则变成事实，不能把“新函数不存在”作为唯一见证。这一运行 0 模型、0 网络，只读源码与临时数据库。

### A2. 添加 frozen 数据对象，保 NULL 与来源

- [ ] **Step A2.1（2–5 分钟）：在 `ask_blocks.py` 的 D4 函数前添加以下类型。** `MainlineContextSnapshot` 的 `guidance` 正式类型为 `tuple[reading_baseline.ReadingRule,...]`；不能用方法卡伪装 AgentEvidence。

```python
@dataclass(frozen=True)
class MainlineSectorFact:
    trade_date: str
    theme_code: str | None
    theme_name: str
    sector_ts_code: str
    sector_name: str
    sort_no: int | None
    today_pct: float | None
    limit_up_count: int | None
    net_inflow_1d: float | None
    amount: float | None
    cycle_status: str | None
    cycle_level: str | None
    startup_date_small: str | None
    high_status_label: str | None
    near_breakout_label: str | None
    sector_pct: float | None
    diff_ratio: float | None
    sector_amount: float | None
    sw_l1: str | None
    pct_source: str
    amount_source: str

@dataclass(frozen=True)
class MainlinePriceVolumeSignal:
    trade_date: str
    theme_code: str | None
    theme_name: str
    sector_ts_code: str
    state: str
    strict_double_red: bool | None
    inputs_complete: bool
    missing_inputs: tuple[str, ...]

@dataclass(frozen=True)
class MainlineGroupCoverage:
    theme_name: str
    total_rows: int
    non_null_counts: tuple[tuple[str, int], ...]
    preview_rows: int
    omitted_rows: int

@dataclass(frozen=True)
class MainlineHistoryCoverage:
    theme_name: str
    day_count: int
    first_date: str
    last_date: str
    sector_rows: int
    has_snapshot_day: bool

@dataclass(frozen=True)
class MainlineContextSnapshot:
    status: str
    market_date: str | None
    snapshot_date: str | None
    requested_as_of: str | None
    target_theme: str | None
    total_rows: int = 0
    groups: tuple[MainlineGroupCoverage, ...] = ()
    facts: tuple[MainlineSectorFact, ...] = ()
    signals: tuple[MainlinePriceVolumeSignal, ...] = ()
    history_start: str | None = None
    history_end: str | None = None
    lookback_days: int = 20
    history: tuple[MainlineHistoryCoverage, ...] = ()
    guidance: tuple[reading_baseline.ReadingRule, ...] = ()
    gap_messages: tuple[str, ...] = ()

MAINLINE_PREVIEW_ROWS_PER_THEME = 8
```

字段数值由 DuckDB 原对象映射，不 `value or 0`。日期只在 dataclass 构造前显式 `str(value)`；None 保留。frozen 类型不可原地追加；`non_null_counts` 用 tuple，避免 frozen 外壳内藏可变 dict。

### A3. 用同一个 joined CTE 得到完整摘要和组内预览

- [ ] **Step A3.1（2–5 分钟）：提炼原连接/日期/主题解析为 `_load_mainline_snapshot(con, latest, market_date, target_theme, lookback_days, as_of)`。** 保原 db path、`retrieval_cache.try_connect_readonly`、缺表及 `latest <= as_of` 检查。joined CTE 用下列字段，不查 generation 多版本。

```sql
WITH joined AS (
  SELECT m.trade_date,m.theme_code,m.theme_name,m.sector_ts_code,m.sector_name,
         m.sort_no,m.today_pct,m.limit_up_count,m.net_inflow_1d,m.amount,
         m.cycle_status,m.cycle_level,m.startup_date_small,
         m.high_status_label,m.near_breakout_label,
         COALESCE(s.pct_chg,m.today_pct) AS sector_pct,
         s.diff_ratio,COALESCE(s.amount,m.amount/10000.0) AS sector_amount,s.sw_l1,
         CASE WHEN s.pct_chg IS NOT NULL THEN 'fact_sector_daily.pct_chg'
              WHEN m.today_pct IS NOT NULL THEN 'fact_mainline_sector_daily.today_pct'
              ELSE 'unprovided' END AS pct_source,
         CASE WHEN s.amount IS NOT NULL THEN 'fact_sector_daily.amount'
              WHEN m.amount IS NOT NULL THEN 'fact_mainline_sector_daily.amount/10000'
              ELSE 'unprovided' END AS amount_source
  FROM fact_mainline_sector_daily m
  LEFT JOIN fact_sector_daily s
    ON m.trade_date=s.trade_date AND m.sector_ts_code=s.sector_ts_code
  WHERE m.trade_date=? AND (? IS NULL OR m.theme_name=?)
)
```

参数固定 `[latest,target_theme,target_theme]`。不要把用户文本拼进 SQL。connection 开 `BEGIN TRANSACTION` 后做两次读取，`COMMIT` 后关闭；异常在同一 finally 内 rollback/close、返回 `unavailable` 及无事实，不误记成 empty。

- [ ] **Step A3.2（2–5 分钟）：joined 后接全组聚合与 per-theme 排号查询。** 以下两段分别与同一个 CTE 拼接。`COUNT` 使用原值；不以行数推非空值。

```sql
SELECT theme_name,COUNT(*) AS total_rows,
       COUNT(today_pct) AS today_pct,COUNT(limit_up_count) AS limit_up_count,
       COUNT(net_inflow_1d) AS net_inflow_1d,COUNT(amount) AS amount,
       COUNT(cycle_status) AS cycle_status,COUNT(cycle_level) AS cycle_level,
       COUNT(sector_pct) AS sector_pct,COUNT(diff_ratio) AS diff_ratio,
       COUNT(sector_amount) AS sector_amount,COUNT(sw_l1) AS sw_l1
FROM joined GROUP BY theme_name ORDER BY theme_name
```

```sql
, ranked AS (
  SELECT *,ROW_NUMBER() OVER (
    PARTITION BY theme_name
    ORDER BY sort_no NULLS LAST,sector_name,theme_code,sector_ts_code
  ) AS preview_no
  FROM joined
)
SELECT * EXCLUDE(preview_no) FROM ranked WHERE preview_no <= ?
ORDER BY theme_name,sort_no NULLS LAST,sector_name,theme_code,sector_ts_code
```

后一查询仅多一个 `MAINLINE_PREVIEW_ROWS_PER_THEME` 参数。`con.description` 的字段名映射到上述 dataclass，不保脆弱的 15 元素 tuple 下标。每组 preview/omitted 从实际 `facts` 分组计数与 aggregate total 计算：

```python
preview_counts = Counter(fact.theme_name for fact in facts)
groups = tuple(MainlineGroupCoverage(
    theme_name=name,
    total_rows=total,
    non_null_counts=tuple(zip(metric_names, counts, strict=True)),
    preview_rows=preview_counts[name],
    omitted_rows=total-preview_counts[name],
) for name, total, *counts in aggregate_rows)
```

`metric_names` 按聚合 SELECT 定义为 `("today_pct","limit_up_count","net_inflow_1d","amount","cycle_status","cycle_level","sector_pct","diff_ratio","sector_amount","sw_l1")`，import `Counter`。`facts` 用 `MainlineSectorFact(**row_mapping)` 构造，date 两列转换 ISO，不能随卡预算改变 groups。

- [ ] **Step A3.3（2–5 分钟）：保历史语义，增加两个结构入口和兼容 renderer。** 从原函数移动同一 `cutoff=latest-timedelta(days=int(lookback_days))` / 双端含边界的历史聚合，删除历史聚合 `LIMIT 8`；每条映射 `MainlineHistoryCoverage(...,has_snapshot_day=last==latest)`。`mainline_context_snapshot(query,theme,market_db_path,lookback_days=20,*,as_of=None)` 保原 latest 与匹配逻辑；`market_review_mainline_context_snapshot(query,theme,market_db_path,*,as_of=None)` 保原 `_market_data_asof` 与同日分支、题材汇总和旧明细 gap。两个旧 str 函数只 render 对应 snapshot，签名不变。

renderer 从 `snapshot.groups/facts/history/guidance/gap_messages` 构造，日期/匹配口径改为“本表当日主题”，明说每组预览数量/省略数；原 `ReadingRule.rule` 原样仍可读，追加 `id/title/source`。保旧主要标题和同日/stale 说明，不回头从渲染文本构造 typed snapshot。`test_ask_compose` 的旧纯文本边界断言仍应通过；依赖旧错误“真正双红/增量启动”的断言改成 canonical 价量资格。

### A4. 量价派生只描述输入可证明的状态

- [ ] **Step A4.1（2–5 分钟）：在 ask_blocks 中用以下纯函数取代旧分类源逻辑。** 旧 `_classify_mainline_volume_state` 保兼容签名，调用同一纯逻辑的 state；`signals` 与 renderer 不各写阈值。

```python
from market_feature_store.signals import is_double_red, DOUBLE_RED_DESCRIPTION

def _classify_mainline_volume_state(pct_chg, diff_ratio, amount):
    pct,diff,amt = _safe_float(pct_chg),_safe_float(diff_ratio),_safe_float(amount)
    strict = is_double_red(pct,diff,amt)
    if strict:
        state = "满足严格双红量价条件"
    elif pct is not None and diff is not None and pct > 0 and diff < 0:
        state = "上涨且成交额环比下降"
    elif pct is not None and diff is not None and pct > 0 and diff >= 0:
        state = "上涨且成交额环比非负，未确认严格双红"
    elif pct is not None and diff is not None and pct < 0 and diff > 0:
        state = "下跌且成交额环比上升"
    else:
        state = "量价输入不足或状态待确认"
    return state

def _mainline_price_volume_signal(fact: MainlineSectorFact) -> MainlinePriceVolumeSignal:
    inputs = {"sector_pct":fact.sector_pct,"diff_ratio":fact.diff_ratio,
              "sector_amount":fact.sector_amount}
    missing = tuple(key for key,value in inputs.items() if value is None)
    strict = None if missing else is_double_red(*inputs.values())
    state = _classify_mainline_volume_state(*inputs.values())
    return MainlinePriceVolumeSignal(fact.trade_date,fact.theme_code,fact.theme_name,fact.sector_ts_code,
        state,strict,not missing,missing)
```

`DOUBLE_RED_DESCRIPTION` 写入 metric_semantics，不手抄门槛。源函数 `market_feature_store/sync/sync_local_sector_daily.py::diff_ratio` 只读确认公式，不修改写库算法。

- [ ] **Step A4.2（2–5 分钟）：追加少量真实行控制。** 在新测试里 parametrized 修改临时行的 amount/diff，再真实读取 snapshot；以下输入的 strict 预期分别 None/False/False/True/False/False。

```python
@pytest.mark.parametrize(("amount","diff","expected"), [
    (None,42,None),(0,42,False),(500,42,False),(501,42,True),
    (501,10,False),(501,-1,False),
])
def test_d4_uses_canonical_signal_qualification(tmp_path,amount,diff,expected):
    path=tmp_path/"fixture.duckdb"
    write_mainline_fixture(path,1)
    with duckdb.connect(str(path)) as con:
        con.execute("UPDATE fact_sector_daily_generation SET amount=?,diff_ratio=?",[amount,diff])
    snapshot=ask_blocks.mainline_context_snapshot(Q,None,path,as_of="2026-09-30")
    assert all(s.strict_double_red is expected for s in snapshot.signals)
    assert all(f.limit_up_count is None for f in snapshot.facts)
    assert all(f.net_inflow_1d is None for f in snapshot.facts)
```

不能据这些 fixture 认证现实主线。method off 控制直接用现有 reading_baseline off fixture；只需证明 guidance 空且真实 facts/coverage 不变。

### A5. 两个适配点复用结构投影，范围跨预算保留

- [ ] **Step A5.1（2–5 分钟）：在 episode_tools 定义 `mainline_snapshot_tool_result(snapshot)`。** 一板块一事实卡，原主线与关联指标分别标字段；不创建 guidance/signal 卡。canonical 来源只由真实 fact 指定。

```python
def mainline_snapshot_tool_result(snapshot):
    def shown(value):
        return "未提供" if value is None else str(value)
    evidence=tuple(agent_research.AgentEvidence(
        tool="mainline_context",
        title=f"{fact.theme_name}｜{fact.sector_name}",
        detail=(f"{fact.trade_date} {fact.theme_name}核心板块 {fact.sector_name}"
                f"；板块代码={fact.sector_ts_code}"
                f"；主线涨幅={shown(fact.today_pct)}；主线涨停={shown(fact.limit_up_count)}"
                f"；主线净流入={shown(fact.net_inflow_1d)}"
                f"；周期={shown(fact.cycle_status)}/{shown(fact.cycle_level)}"
                f"；关联涨幅%={shown(fact.sector_pct)}；成交额环比%={shown(fact.diff_ratio)}"
                f"；关联成交额亿={shown(fact.sector_amount)}"
                f"；涨幅来源={fact.pct_source}；金额来源={fact.amount_source}"),
        source="本地 DuckDB · fact_mainline_sector_daily / fact_sector_daily",
        source_date=fact.trade_date,evidence_tier="L4_structured",
        independent_key=f"d4:{fact.trade_date}:{fact.theme_code}:{fact.sector_ts_code}",
        freshness="current",
    ) for fact in snapshot.facts)
    guidance="\n".join(f"方法指导[{rule.id}] {rule.title}；来源={rule.source}；{rule.rule}"
        for rule in snapshot.guidance)
    observation="\n".join(part for part in (
        guidance,*snapshot.gap_messages,
        "本表主题覆盖完整；板块明细为组内有限预览，范围见 query_basis。"
        if snapshot.groups else "本表没有可交付同日板块事实；不能据此断言市场不存在。",
    ) if part)
    return ToolRunResult(evidence,observation,ProviderTrace(
        provider="agent:mainline_context",capability="mainline_context",
        status=("success" if evidence else "error" if snapshot.status=="unavailable"
                else "stale" if snapshot.status=="stale" else "empty"),result_count=len(evidence),
        requested_date=snapshot.requested_as_of,served_date=snapshot.snapshot_date,
        detail=f"d4_snapshot_status={snapshot.status}"),
        gaps=snapshot.gap_messages,query_basis=mainline_snapshot_query_basis(snapshot))
```

不要在短卡里塞满全部原始字段；未显示的 startup/breakout 原值留 snapshot/审计，若文本旧 renderer 需要则用该对象渲染。长名称可能触发现有 prose 裁剪，完整元数据仍保留。

- [ ] **Step A5.2（2–5 分钟）：定义完整 query_basis 投影并迁移 Episode runner。** 给 `episode_tools` 增加 `asdict` import；`mainline_snapshot_query_basis` 的实现为：

```python
def mainline_snapshot_query_basis(snapshot):
    return {
        "schema":"d4_mainline_snapshot_v1",
        "scope":"current_table_single_theme" if snapshot.target_theme else "current_table_all_themes",
        "status":snapshot.status,"market_date":snapshot.market_date,
        "snapshot_date":snapshot.snapshot_date,"requested_as_of":snapshot.requested_as_of,
        "target_theme":snapshot.target_theme,"theme_names":[g.theme_name for g in snapshot.groups],
        "total_rows":snapshot.total_rows,
        "groups":[{**asdict(g),"non_null_counts":dict(g.non_null_counts)} for g in snapshot.groups],
        "preview_limit_per_theme":ask_blocks.MAINLINE_PREVIEW_ROWS_PER_THEME,
        "ordering":["theme_name","sort_no NULLS LAST","sector_name","theme_code","sector_ts_code"],
        "history_window":{"start":snapshot.history_start,"end":snapshot.history_end,
                          "inclusive":True,"lookback_calendar_days":snapshot.lookback_days},
        "history":[asdict(item) for item in snapshot.history],
        "metric_semantics":{
            "diff_ratio":"(当日成交额-上一交易日成交额)/上一交易日成交额*100；不是净流入",
            "strict_double_red":DOUBLE_RED_DESCRIPTION,
            "scope":"量价条件不证明资金净流入、唯一主线、指数贡献或长期趋势"},
        "price_volume_signals":[asdict(signal) for signal in snapshot.signals],
    }
```

`DOUBLE_RED_DESCRIPTION` 从 canonical signals import。`mainline_runner` 保原取消、deadline 和 stale precheck，后半替换为：

```python
snapshot=ask_blocks.market_review_mainline_context_snapshot(
    frame.raw_question,frame.subject,market_db_path,as_of=_structured_as_of(context))
tool_context.check_cancelled()
return mainline_snapshot_tool_result(snapshot)
```

不修改 `_NON_EVIDENCE_PREFIXES` / 普通 `block_lines_to_evidence`，不加“判读/资金/唯一”词面过滤。registry 已支持 `ToolRunResult`、query_basis，不新增注册结构。

- [ ] **Step A5.3（2–5 分钟）：迁移 ask.py 唯一同源工具适配点。** `_generic_mainline_context` 里局部导入共用投影，返回 typed 结果：

```python
from intelligence.services.episode_tools import mainline_snapshot_tool_result
snapshot=ask_blocks.market_review_mainline_context_snapshot(
    options.query,contract.subject,options.market_db_path,
    as_of=context.information_cutoff.as_of_date.isoformat()
          if context.information_cutoff is not None else None)
result=mainline_snapshot_tool_result(snapshot)
```

`ask.py` 当前导入若为单函数别名，增加 `from intelligence.services import ask_blocks`。原“双红”补充块保原 `market_timeseries.latest_double_red_snapshot_block_for_llm` 的事实路径，仅单独 `block_lines_to_evidence` 转其数值事实，再 `replace(result,evidence=(*extra,*result.evidence),observation=...)`；不能把 D4 guidance 拼回去。让 trace.result_count 同实际卡数。不能重构其他 Owner 或 D 块。追加到 `intelligence/tests/test_ask_compose.py` 的现有 mainline 工具用例，断言 typed producer 的规则没有进入事实卡且 stale 仍无证据。

- [ ] **Step A5.4（2–5 分钟）：补 3 个数据库范围控制并跑绿。** 复用 fixture，在同文件覆盖：单主题 `theme="ZZZ"` 仅单组；同 sort_no/sector_name 的不同行按 theme_code/sector_ts_code 稳定；同日 published 行使 legacy 自动让位。published fixture 操作如下：

```python
with duckdb.connect(str(path)) as con:
    con.execute("""INSERT INTO ops_sector_universe_snapshot_daily
      VALUES ('2026-09-30','published-fixture','fixture',2,0,'published',CURRENT_TIMESTAMP)""")
    con.execute("""INSERT INTO fact_sector_daily_generation
      (trade_date,sector_universe_snapshot_id,sector_ts_code,sector_name,pct_chg,amount,diff_ratio)
      SELECT trade_date,'published-fixture',sector_ts_code,sector_name,3.0,501.0,11.0
      FROM fact_sector_daily_generation WHERE sector_universe_snapshot_id='legacy'""")
snapshot=ask_blocks.mainline_context_snapshot(Q,None,path,as_of="2026-09-30")
assert all(f.sector_amount == 501.0 for f in snapshot.facts)
```

复用 `test_ask_compose` 的 stale/future 主线与历史边界用例，不另铺大矩阵。添加历史起点 9/10、9/9 与终点 9/30/10/1 临时行，默认 20 自然日只计 9/10–9/30；在 query_basis 完整 history 上断言，不用 renderer preview 判全集。相关命令：

```bash
.venv-workbench/bin/python -m pytest -q intelligence/tests/test_market_context_contract.py intelligence/tests/test_ask_compose.py intelligence/tests/test_episode_tools.py intelligence/tests/test_reading_baseline.py intelligence/tests/test_tool_result_budget.py intelligence/tests/test_research_harness.py
.venv-workbench/bin/python -m ruff check intelligence/services/ask_blocks.py intelligence/services/episode_tools.py intelligence/services/ask.py intelligence/tests/test_market_context_contract.py
```

期望本范围全绿；shared model query_basis 有全部主题，method 0 张事实卡，旧非 D4 转卡行为无改变。fixture观察 prose 超预算时 metadata 仍完整，加入 `replace(observed,observation=observed.observation+"x"*5000)` 再过真实 project_tool_result 验一次。不要调整 4000/800 常量来通过。

- [ ] **Step A5.5（2–5 分钟）：更新门页并提交 A。** `docs/agent-product-door.md` 数据块小节写上述结构覆盖/预览/指导三角色与范围，不宣称全市场齐全；与源码同提交。只 pathspec：

```bash
git add -- intelligence/services/ask_blocks.py intelligence/services/episode_tools.py intelligence/services/ask.py intelligence/tests/test_market_context_contract.py intelligence/tests/test_ask_compose.py docs/agent-product-door.md
git commit -m "fix: preserve D4 theme coverage and evidence roles" -- intelligence/services/ask_blocks.py intelligence/services/episode_tools.py intelligence/services/ask.py intelligence/tests/test_market_context_contract.py intelligence/tests/test_ask_compose.py docs/agent-product-door.md
```

独立复核通过后再进入 Task B。A 只解决 producer/角色合同，不签回答语义通过。

## Task B：可信输入冻结时间合同，续轮/恢复/消费者实际守界

### B1. 先把原时点案例走实际 context 与消费者

- [ ] **Step B1.1（2–5 分钟）：创建 `intelligence/tests/test_temporal_contract.py`，复用原诊断的 9 个 temporal cases。** 以下首个端到端红控制不 mock parser、context 或 future gate；fake model 只禁外呼。

```python
from dataclasses import replace
from datetime import date
import json
import pytest

from intelligence.runtime.turn_control_core import project_turn_decision
from intelligence.services.turn_controller import decide_turn
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.research_tool_registry import ResearchToolRegistry,ToolSpec,ToolRunResult

NOW="2026-10-07"
Q="请复盘2026年9月30日的A股，只使用截至当日可见的信息。"

def controlled_context(question=Q,previous=None):
    decision=decide_turn(question,previous_intent=previous,
        llm_complete=lambda *_a,**_k:(None,None,"disabled"))
    assert decision.task_frame is not None
    control=project_turn_decision(decision,task_frame=decision.task_frame)
    context=build_episode_context(control.task_frame,task_id="temporal-contract",today=NOW,
        latest_data_date="2026-09-30",capabilities=("market_data",))
    return decision,control,context

def make_sentinel_registry():
    card=AgentEvidence(tool="market_data",title="未来资料哨兵",
        detail="FUTURE_PAYLOAD_1001=987654.321；本地测试资料",
        source="synthetic availability fixture",source_date="2026-10-01",
        evidence_tier="L4_structured")
    return ResearchToolRegistry((ToolSpec(name="market_data",capability="market_data",
        description="local availability sentinel",cost="local",freshness="current",
        query_scope="episode",runner=lambda _q,_c:ToolRunResult((card,),card.detail,
            ProviderTrace(provider="local:fixture",capability="market_data",status="success"),
            query_basis={"preview":"FUTURE_PAYLOAD_1001=987654.321"})),))

def future_projection(context,registry=None):
    registry=registry or make_sentinel_registry()
    observed=registry.execute("market_data",{},context=context,step_id="future-sentinel")
    projection=FinanceResearchHarness().project_tool_result(observed,
        evidence_so_far=observed.evidence,seen_prose=set())
    return observed,projection

def test_user_relative_cutoff_reaches_actual_registry_and_model():
    decision,control,context=controlled_context()
    assert context.information_cutoff.as_of_date == date(2026,9,30)
    observed,projection=future_projection(context)
    assert observed.trace.status == "future_of_cutoff"
    assert observed.evidence == ()
    assert "FUTURE_PAYLOAD_1001" not in projection.model_content
    assert "987654.321" not in projection.model_content
    assert "不是源里没有" in observed.observation
```

第一拍不传新参数，factory 固定 NOW，观察 cutoff10/7/future正文确红。B5 增加 keyword-only 信任运行日参数之后，在这行明确补 `today=date.fromisoformat(NOW)`，固定编译时点，不依赖实际测试墙钟。

- [ ] **Step B1.2（2–5 分钟）：运行红控制，并先独立固定现有显式截止负控。**

```bash
.venv-workbench/bin/python -m pytest -q intelligence/tests/test_temporal_contract.py
```

期望当前 cutoff 错为10/7；另将 context replace 为显式9/30，仍可暴露当前 registry “标注后交付”未来正文。这两处是不同层的红，不能相加计为两个质量提升样本。

### B2. 定义最小 schema 与共享日历 primitives

- [ ] **Step B2.1（2–5 分钟）：在新 `temporal_contract.py` 加 frozen 类型。** 类型模块顶层只 import stdlib；`user_task/honesty_gates` 在 compiler 内 lazy import，避免 `TaskFrame→temporal→honesty→research_contract` 循环。

```python
from dataclasses import dataclass,asdict,replace
from datetime import date
import hashlib
import re

@dataclass(frozen=True)
class TemporalSource:
    message_id: str | None
    message_sha256: str
    excerpt: str

    def __post_init__(self):
        if self.message_id is not None and (not isinstance(self.message_id,str) or not self.message_id):
            raise ValueError("invalid temporal message id")
        if not isinstance(self.message_sha256,str) or not re.fullmatch(r"[a-f0-9]{64}",self.message_sha256):
            raise ValueError("invalid temporal message digest")
        if not isinstance(self.excerpt,str):
            raise ValueError("invalid temporal excerpt")

@dataclass(frozen=True)
class ResearchDateWindow:
    start: str
    end: str
    source: TemporalSource

@dataclass(frozen=True)
class TemporalContract:
    market_target: ResearchDateWindow | None = None
    information_cutoff: str | None = None
    cutoff_origin: str = "none"
    cutoff_source: TemporalSource | None = None
    relative_anchor_sha256: str | None = None
    errors: tuple[str,...] = ()

    def __post_init__(self):
        if self.cutoff_origin not in {"none","explicit_user","relative_target",
                "runtime_relative","inherited_user","legacy_user"}:
            raise ValueError("invalid temporal cutoff origin")
        if self.cutoff_origin == "none" and self.information_cutoff is not None:
            raise ValueError("unattributed temporal permission")
        if not isinstance(self.errors,tuple) or any(not isinstance(e,str) for e in self.errors):
            raise ValueError("invalid temporal errors")
        if self.information_cutoff is not None:
            if not isinstance(self.information_cutoff,str):
                raise ValueError("invalid temporal cutoff date")
            date.fromisoformat(self.information_cutoff)
        if self.market_target is not None:
            date.fromisoformat(self.market_target.start)
            date.fromisoformat(self.market_target.end)
            if self.market_target.start > self.market_target.end:
                raise ValueError("reversed market target window")
        sources=(self.cutoff_source,self.market_target.source if self.market_target else None)
        for source in sources:
            if source is not None and not re.fullmatch(r"[a-f0-9]{64}",source.message_sha256):
                raise ValueError("invalid temporal source digest")
        if self.cutoff_origin == "relative_target" and (
                self.market_target is None or self.relative_anchor_sha256 != self.market_target.source.message_sha256):
            raise ValueError("relative cutoff lacks trusted target anchor")
        if self.cutoff_origin != "none" and (self.information_cutoff is None or self.cutoff_source is None):
            raise ValueError("incomplete temporal permission")

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls,value):
        if not isinstance(value,dict) or set(value) != {
                "market_target","information_cutoff","cutoff_origin","cutoff_source",
                "relative_anchor_sha256","errors"}:
            raise ValueError("invalid temporal contract schema")
        def source(raw):
            if not isinstance(raw,dict) or set(raw) != {"message_id","message_sha256","excerpt"}:
                raise ValueError("invalid temporal source schema")
            return TemporalSource(**raw)
        target=value["market_target"]
        if target is not None:
            if not isinstance(target,dict) or set(target) != {"start","end","source"}:
                raise ValueError("invalid market target schema")
            target=ResearchDateWindow(target["start"],target["end"],source(target["source"]))
        errors=value["errors"]
        if not isinstance(errors,(list,tuple)) or any(not isinstance(e,str) for e in errors):
            raise ValueError("invalid temporal errors")
        return cls(target,value["information_cutoff"],value["cutoff_origin"],
            source(value["cutoff_source"]) if value["cutoff_source"] is not None else None,
            value["relative_anchor_sha256"],tuple(errors))
```

`ResearchDateWindow.__post_init__` 同样检查 start/end 为 str、`date.fromisoformat` 合法且 start<=end、source 为 TemporalSource；以上 parent 的校验不能替代直接类型构造检查。`relative_anchor_sha256` 非None时必须为合法digest且与所指目标source一致。保持固定键 schema，不吃半截对象后默默回 default。

- [ ] **Step B2.2（2–5 分钟）：提炼现有日期 primitives，保持原 parser 正控。** 将 `query_understanding.py::_FULL_DATE_RE/_YEARLESS_DATE_RE` 移到 `temporal_contract.py`，原位置 import alias；将 `historical_research.intent::_SHORT_RANGE_END` 的直接连接规则移到同一 pure Module，旧 history parser import 使用。共享函数接口如下；函数体使用旧 `market_review_requested_date` 的年解析/合法日期逻辑与旧 history 的短端点逻辑，不调用 LLM。

```python
def calendar_date_tokens(text: str, *, today: date) -> tuple[tuple[int,int,date|None],...]:
    tokens=[]
    occupied=[]
    for match in _FULL_DATE_RE.finditer(text):
        try:
            value=date(*(int(v) for v in match.groups()))
        except ValueError:
            value=None
        tokens.append((match.start(),match.end(),value))
        occupied.append((match.start(),match.end()))
    for match in _YEARLESS_DATE_RE.finditer(text):
        if any(a <= match.start() < b for a,b in occupied):
            continue
        if _YEARLESS_QUANTITY_PREFIX_RE.search(text[:match.start()]):
            continue
        value=None
        for year in (today.year,today.year-1):
            try:
                candidate=date(year,int(match[1]),int(match[2]))
            except ValueError:
                continue
            if candidate <= today:
                value=candidate
                break
        tokens.append((match.start(),match.end(),value))
    return tuple(sorted(tokens))

def market_target_window(text: str, *, today: date, source: TemporalSource):
    tokens=calendar_date_tokens(text,today=today)
    if any(value is None for _,_,value in tokens):
        return None,"市场目标日期无效，请明确有效日期"
    if not tokens:
        return None,None
    a,b,start=tokens[0]
    if len(tokens)==2 and re.fullmatch(r"\s*(?:到|至|~|～|—|-)\s*",text[b:tokens[1][0]]):
        end=tokens[1][2]
        if end >= start:
            return ResearchDateWindow(start.isoformat(),end.isoformat(),source),None
        return None,"市场目标窗口顺序相反，请明确完整窗口"
    short=_SHORT_RANGE_END.match(text,b)
    if short is not None:
        try:
            end=date(start.year,int(short["month"]) if short["month"] else start.month,
                     int(short["day"] or short["same_month_day"]))
        except ValueError:
            return None,"市场目标窗口终点无效，请明确完整起止日期"
        if end < start or any(offset >= short.end() for offset,_,_ in tokens[1:]):
            return None,"市场目标窗口不唯一或跨年不明，请明确完整窗口"
        return ResearchDateWindow(start.isoformat(),end.isoformat(),source),None
    if len(tokens)==1:
        return ResearchDateWindow(start.isoformat(),start.isoformat(),source),None
    return None,"市场目标日期不唯一，请明确相对截止引用哪个日期或窗口"
```

`_YEARLESS_QUANTITY_PREFIX_RE` 沿用 `query_understanding.py` 原声明，必须同样移/import alias，不能把“涨幅7.16%”认日期。上述代码先识别完整第二端点的连接，再识别压缩短端点；短端点内部的 yearless token 不作为第三锚。`_SHORT_RANGE_END` 沿用旧语法，不扩大研究模式正则。原 `market_review_requested_date` 通过首个 token 投影保旧行为，history discovery/purpose 不跟日期 primitives 合并。

### B3. 编译资料许可，分清未指定与解析失败

- [ ] **Step B3.1（2–5 分钟）：提炼已有截止解析为只读 legacy helper。** 将 `honesty_gates.requested_information_cutoff` 原 body 改名 `_legacy_requested_information_cutoff`（逻辑不变），新同名 public wrapper 返回 `compile_temporal_contract(query,today=runtime_date)` 的 cutoff；errors 非空返回 None 给旧只读调用方，factory/入口必须消费 typed errors 并澄清，不能据 None 回 default。`explicit_information_cutoff_dates` / `_explicit_cutoff_candidates` 仍是唯一绝对许可/否定/日期角色规范。

相对许可只增加日期角色语法：`截至/截止到 + 今天/当日/该日/该区间结束日/区间结束日`。在既有 `_explicit_cutoff_candidates` 的逐 clause 否定/角色检查处提炼 `cutoff_instruction_clauses(query)`，返回原 clause、绝对匹配 span、相对 token；引文保护用既有 `top_level_message_text`，不能另做引号过滤。相对 token 必须在非否定的 permission clause 中；多个冲突 token 返回错误。

- [ ] **Step B3.2（2–5 分钟）：写 `compile_temporal_contract` 与固定 frame 投影。** 接口与权限选择如下；`cutoff_instruction_clauses` 是上一小步在 honesty_gates 定义的 helper，goal_text 是将明确 cutoff 日期 span 等长置空后的顶层文本（不整句删掉目标日期）。

```python
def compile_temporal_contract(query, *, today, message_id=None, previous=None, continuing=False):
    from intelligence.services.user_task import top_level_message_text
    from intelligence.services.honesty_gates import (
        explicit_information_cutoff_dates,cutoff_instruction_clauses,
        _legacy_requested_information_cutoff,
    )
    raw=str(query or "").replace("\r\n","\n").replace("\r","\n")
    visible,uncertain=top_level_message_text(raw)
    base=previous if continuing and previous is not None else TemporalContract()
    if uncertain:
        return replace(base,errors=("无法确定原用户时间指令边界，请明确本轮日期与资料范围",))
    source=TemporalSource(message_id,hashlib.sha256(raw.encode()).hexdigest(),raw)
    goal_text,relative=cutoff_instruction_clauses(raw)
    target,target_error=market_target_window(goal_text,today=today,source=source)
    if target is None and target_error is None and continuing:
        target=base.market_target
    explicit=set(explicit_information_cutoff_dates(raw))
    if None in explicit or len(explicit)>1 or len(set(relative))>1:
        return replace(base,market_target=target,errors=("资料截止无效或不唯一，请明确有效许可",))
    standing=_legacy_requested_information_cutoff(raw,today=today.isoformat())
    until=next(iter(explicit),None)
    origin="explicit_user"
    anchor=None
    if relative:
        token=relative[0]
        if token == "今天":
            relative_date=today
            origin="runtime_relative"
        elif target is None or (token in {"当日","该日"} and target.start != target.end):
            return replace(base,market_target=target,errors=(target_error or "相对截止缺少唯一目标日期",))
        else:
            relative_date=date.fromisoformat(target.end)
            origin="relative_target"
            anchor=target.source.message_sha256
        if until is not None and until != relative_date:
            return replace(base,market_target=target,errors=("绝对与相对资料许可冲突，请明确截止日期",))
        until=relative_date
    elif until is None and standing is not None:
        until=standing.as_of_date
    if target_error and not relative:
        # Multi-target comparison may have an explicit independent information bound.
        # It has no single market_target; never guess the max date as a relative anchor.
        if target_error != "市场目标日期不唯一，请明确相对截止引用哪个日期或窗口":
            return replace(base,market_target=target,errors=(target_error,))
    if until is not None:
        return TemporalContract(target,min(until,today).isoformat(),origin,source,anchor)
    if continuing and base.information_cutoff is not None:
        return replace(base,market_target=target,cutoff_origin="inherited_user",errors=())
    return TemporalContract(market_target=target)
```

`cutoff_instruction_clauses` 的返回签名必须为 `tuple[str,tuple[str,...]]`：第一项可作日期角色分析的顶层 goal text；第二项相对许可 token。它调用既有绝对 cutoff regex/span/negation 检查，仅对 permission 角色日期置空；材料保护后的文本不可拿来伪造原 source digest。source 中存原全文用于追溯，公开投影不含它。多锚且相对许可缺唯一目标不得进入 research；多锚纯比较可沿现有框架处理，不能伪造单一 target。

在 `task_frame.py` 定义共享代码拥有的投影：

```python
def pin_temporal_contract(frame, temporal_contract):
    errors=temporal_contract.errors
    return replace(frame,temporal_contract=temporal_contract,
        ambiguities=_merge_strings(frame.ambiguities,errors),
        clarification_question=(errors[0] if errors else frame.clarification_question))
```

这不是新入口门，只是 existing frame 的投影；所有模型 alignment/rebase 保同一个合同。`InformationCutoff.source` 的旧三值闭集不用加新值，权限具体来源在 TemporalContract。

### B4. 序列化、hash 与续轮兼容

- [ ] **Step B4.1（2–5 分钟）：四个类型尾部加 optional field，精确控制旧 hash。** 修改 `QueryEnvelope/TaskFrame/TurnIntent/ResearchRunContext`，`temporal_contract: TemporalContract|None=None`；前3个 to_dict/_payload：

```python
if self.temporal_contract is None:
    payload.pop("temporal_contract",None)
else:
    payload["temporal_contract"]=self.temporal_contract.to_dict()
```

`TaskFrame/TurnIntent` 的既有 from_dict 对缺键读 None；存在键就 `TemporalContract.from_dict(value["temporal_contract"])`，异常沿既有无效 frame/intent 错误返回，不吞成None。QueryEnvelope/context 无既有 from_dict，不为此增加反序列化入口。`project_task_frame/envelope_from_task_frame` 显式映射同一 field；`_attach_turn_intent` 对 intent replace 同一合同并更新 frame hash；`rebase_task_frame/align_task_frame` 不从模型生成新 temporal field。新合同参与 TaskFrame._payload 原 SHA256，无字段的旧 payload/hash 原样不变。

- [ ] **Step B4.2（2–5 分钟）：在现有 `test_task_frame.py` 加兼容 round-trip 控制。**

```python
legacy=frame.to_dict()
legacy.pop("temporal_contract",None)
restored=TaskFrame.from_dict(legacy)
assert restored is not None
assert restored.task_frame_hash == legacy["task_frame_hash"]
typed=pin_temporal_contract(restored,contract)
assert TaskFrame.from_dict(typed.to_dict()) == typed
assert typed.task_frame_hash != restored.task_frame_hash
assert replace(typed,timeframe="2026-10-07").temporal_contract == contract
```

使用该文件已有 frame fixture 与本 Task 编译的 contract；合同内 source 摘要变化导致 hash 变化。`TurnIntent.from_dict` legacy 缺字段仍读取成功，新无效半截 contract 拒绝；不声称新 hash 与旧 artifact 可互换。

### B5. 原输入权威 Seam、controller 前冻结与 continuation

- [ ] **Step B5.1（2–5 分钟）：修改直接理解入口与 controller。** `understand_query` 增加 keyword-only `today: date|None=None, temporal_contract: TemporalContract|None=None`；在 routing/inner envelope 之前编译（若 supplied 则使用 supplied），inner frame creation 后 pin，并投影 envelope。`build_task_frame` 尾部增加同一 optional kwargs，compiler 在 optional LLM 前运行；`decide_turn` 增加 `today` 与 `temporal_contract` 参数，在 resolver 前冻结，并把合同传到所有 `build_task_frame` / pending恢复路径。任何已有早返 material/personal-recall 不增加检索，仅带合同或按错误澄清。

```python
trusted_temporal = temporal_contract or compile_temporal_contract(query,today=today or date.today())
# At the existing inherit_subject/history_followup decision, only merge trusted prior state.
if temporal_contract is None and previous_intent is not None and (inherit_subject or history_followup is not None):
    trusted_temporal = compile_temporal_contract(query,today=today or date.today(),
        previous=previous_intent.temporal_contract,continuing=True)
```

resolver 前先冻结当前原指令；resolver 后的继承判定只能接合 **旧合同** 中原用户已经授予的上界，不能重读模型提供的 timeframe 作为许可。生产入口 supplied 合同不在 controller 重编译；最终由入口核对 prior-turn 指针来定继承。当前显式授权优先；pending source complete 才恢复旧合同。没有新权限指令的真 continuation，资料 cutoff 不随本轮今天变化。

- [ ] **Step B5.2（2–5 分钟）：在 production orchestrator 调 controller 前核对完整 user 记录。** 不改新会话入口/存储 schema；已有 `conversation_messages` 的 message id/run/role 就是权威。

```python
current_users=[m for m in conversation_messages if m.role=="user" and m.run_id==run_id]
if len(current_users)!=1 or current_users[0].content != query:
    raise ValueError("current user message identity does not match run query")
trusted_temporal=compile_temporal_contract(query,today=date.today(),
    message_id=current_users[0].message_id,
    previous=inherited_intent.temporal_contract if inherited_intent else None,
    continuing=history_continuation or bool(turn_continuation))
```

实际 production 中已有可信 today 注入时复用它，禁止由模型提供 today。一般代词 follow-up 的继承标记在 controller 返回后可用 `decision.turn_intent.inherited_from_turn` 确认，只用原 current_users 和旧 frozen合同合并；入口允许 controller 判“正在延续哪项研究”，不允许它授新 cutoff。默认 controller 直接传 `temporal_contract`；injected legacy controllers 依现有 inspect.signature 兼容，不认识新 kwargs 就不传，返回后无条件 `pin_temporal_contract`。controller.trace/raw QueryEnvelope、TurnControlResult 与 adapter 必须看到同一合同；不能仅写 trace。

旧持久化 intent 缺新字段时，从现有有界完整 user 消息集合恢复被继承那轮的原问句与许可（用 existing prior-turn 指针与 message run，而不是 summary/assistant正文）。恢复 source message id/digest，标 legacy_user；缺原记录/被截断则放入 errors，clarification 不发工具。新当前明确许可不因旧恢复失败被阻止；无新许可的continuation不得放宽。

- [ ] **Step B5.3（2–5 分钟）：加真入口 pin 测试与继承控制。** 在 `test_conversation_orchestrator.py` 使用已有 `_prepare_turn`、临时 ConversationStore/RunStore 与 injected controller fixture。controller 故意返回 `replace(frame,timeframe="2026-10-07",user_goal="使用10/7资料")`；capture adapter/frame 断言 temporal cutoff仍9/30，并运行 `future_projection(context)`，两种日期字符串都不能扩权。再以同一临时消息链测“继续讲反证”无新许可继承9/30；当前用户“资料范围改为截至2026-10-07”得到10/7；引用同一句不扩权，缺 legacy 原记录澄清。不要只用 TurnIntent 造一张 fake 权限卡当恢复证据。

### B6. factory/adapter/日期消费者真消费合同

- [ ] **Step B6.1（2–5 分钟）：让 factory 只在真正未指定时默认，adapter 固定有效合同。** 在 `build_episode_context` 原 cutoff 位置替换：

```python
temporal=frame.temporal_contract
if temporal is None:
    # Legacy direct service callers: authority is raw user question, never timeframe/goal.
    temporal=compile_temporal_contract(frame.raw_question,today=date.fromisoformat(today[:10])
        if today else date.today())
if temporal.errors:
    raise ValueError(temporal.errors[0])
cutoff=(InformationCutoff(date.fromisoformat(temporal.information_cutoff),"requested")
        if temporal.information_cutoff else _default_information_cutoff(
            today=today,latest_data_date=latest_data_date))
if information_cutoff is not None:
    cutoff=InformationCutoff(min(cutoff.as_of_date,information_cutoff.as_of_date),cutoff.source)
```

保原 history information_cutoff/strict-window 的额外 min，不允许更晚字段覆盖。构造 `ResearchRunContext(...,temporal_contract=temporal)`。在 `ContinuousTurnAdapter.handle` 默认/context_factory 结果后无条件给相同 contract，并把返回的 information_cutoff 与冻结边界 min；errors 禁止进入 runtime。注入式 factory 的错误晚 cutoff 也不能扩权；legacy 无字段仅前述原问句恢复，不能从 factory latest_date 再猜。

- [ ] **Step B6.2（2–5 分钟）：让结构日期消费者使用目标与权限两种角色。** 修改 `episode_tools._structured_freshness_floor` 及 `_structured_as_of` 共用同一个上界函数，防止同日9/30目标被10/7 freshnessfloor误拒 stale。

```python
def _structured_freshness_floor(context):
    upper=context.information_cutoff.as_of_date
    temporal=context.temporal_contract
    if temporal and temporal.market_target:
        upper=min(upper,date.fromisoformat(temporal.market_target.end))
    snapshot_date=_iso_date(context.latest_data_date)
    return min(snapshot_date,upper) if snapshot_date is not None else None

def _structured_as_of(context):
    floor=_structured_freshness_floor(context)
    if floor is not None:
        return floor.isoformat()
    temporal=context.temporal_contract
    target=date.fromisoformat(temporal.market_target.end) if temporal and temporal.market_target else context.information_cutoff.as_of_date
    return min(target,context.information_cutoff.as_of_date).isoformat()
```

`news_search/evidence_search` 的 max仍用 InformationCutoff，各自事件解释窗可再收紧；不把9/30目标自动变成所有资料上界。正控：目标9/30、资料截至10/7，mainline query as_of9/30而 context信息上界10/7。负控：资料截至9/29，不能为9/30生产当日事实。

### B7. 真实消费者不送未来资料，保提前已知的未来日程

- [ ] **Step B7.1（2–5 分钟）：删掉 registry 全未来“贴标签后交付”分支。** 在 `ResearchToolRegistry.execute` 现有 `filter_future_dated` 之后，仅保合法卡：

```python
if rejected:
    if evidence:
        observation="；".join(f"{item.title}：{item.detail}" for item in evidence)
    else:
        observation="已检索但内容晚于信息截止日，未交付；不是源里没有。"
        gaps=(*gaps,observation)
    # A producer's original metadata may carry the same rejected previews.
    run_result=replace(run_result,query_basis={})
```

不恢复 rejected evidence、不重复 minted hash；trace 保既有 future_of_cutoff / count逻辑。无卡且 provider 来源可见时点晚于边界时也重写观察并清 query_basis；不是对正文里任意日期匹配。`_overnight_news_evidence` 返回 `result.items`，其 `after_cutoff_items` 仅诊断，不以晚于日标题构造证据。未来标题/数值/摘要不得流入 observation 或 query_basis，private原provider trace仍可审计。

- [ ] **Step B7.2（2–5 分钟）：加未来资料反控与未来事件正控走真实 registry。** 先跑 B1 的哨兵，另测混合合法/未来两卡只保合法值、全未来且 history_intent=None 不交内容。事件正控复用 `test_finance_query.py::test_event_daily_allows_scheduled_dates_beyond_cutoff` / `_write_event_daily` 的临时 fixture：`event_daily.allow_future_time_range=True, cutoff_column=updated_at` 不变。

```python
arguments={"dataset":"event_daily","metrics":["importance"],
    "dimensions":["event_date","title","is_future"],
    "time_range":{"start":"2026-08-24","end":"2026-08-28"},
    "order_by":[{"field":"event_date","direction":"asc"}],"limit":20}
# The existing fixture has 8/26 and 8/27 events known by 8/21,
# plus an 8/28 event inserted on 8/24. Run through the real episode registry.
observed=registry.execute("finance_query",arguments,context=context,step_id="event-time-role")
projection=FinanceResearchHarness().project_tool_result(observed,
    evidence_so_far=observed.evidence,seen_prose=set())
assert "英伟达2026Q2财报" in projection.model_content
assert "杰克逊霍尔全球央行年会" in projection.model_content
assert "事后才知道的事件" not in projection.model_content
assert {item.source_date for item in observed.evidence} == {"2026-08-21"}
```

在现有 `test_episode_tools.py` 建 sealed fixture registry/context（cutoff8/21），不是仅调用 FinanceQuery helper。日程发生日允许未来是有类型的已存在权限；不添加“event”关键词豁免或全局日期删除，不把 updated_at 说成严格官方发布时间。

- [ ] **Step B7.3（2–5 分钟）：把 consumer 红控制走 ContinuousTurnAdapter。** 在 `test_continuous_turn_adapter.py` 用真实 `build_episode_context`、B1 真实 sentinel registry；只用 local runtime 替身在 `run(task_frame,context,registry)` 内执行真 registry/project并捕获，再主动抛测试专用异常停止到 semantic/model 前。该替身不伪造 cutoff/filter/project。

```python
captured=[]
sentinel_registry=make_sentinel_registry()

class ProbeRuntime:
    def run(self,*,task_frame,context,registry):
        observed,projection=future_projection(context,registry)
        captured.append((task_frame.temporal_contract,context.information_cutoff,
                         observed,projection.model_content))
        raise RuntimeError("offline consumer probe complete")

adapter=ContinuousTurnAdapter(runtime=ProbeRuntime(),runtime_name="local-probe",mode="on",
    today=NOW,latest_data_date="2026-09-30",
    context_factory=build_episode_context,registry_factory=lambda *_a,**_k:sentinel_registry)
adapter.handle(frame=control.task_frame,control=control)
assert captured[0][1].as_of_date == date(2026,9,30)
assert captured[0][2].evidence == ()
assert "FUTURE_PAYLOAD_1001" not in captured[0][3]
```

B1 已定义 `make_sentinel_registry()` 与使用入参 registry 的 projection，ProbeRuntime 真执行 `registry` 参数；不能另建一个 registry 假装 adapter 已消费。复用本文件已有 runtime失败捕获/assert形式，不把故意停止冒充发布成功。另 injected factory 返回10/7 context仍被adapter收紧到9/30。

### B8. 控制回归、提交与独立验收

- [ ] **Step B8.1（2–5 分钟）：复用诊断 temporal cases，保独立信息许可优先。** 测以下期望，所有 cases通过 `decide_turn → project_turn_decision → factory`，其中原题与事件/哨兵还过adapter→registry→model。

| 输入控制 | 目标角色 | 信息许可预期 |
| --- | --- | --- |
| 原题及8/12“截至当日” | 唯一目标日 | 对应目标日 |
| 9/28至9/30“截至区间结束日” | 明确窗口末端 | 9/30 |
| 复盘9/30，明确截至9/29 | 9/30 | 9/29 |
| 复盘9/30，结合截至今天 | 9/30 | NOW |
| 公司只用截至今天 | 不假造市场目标 | NOW |
| ISO站在9/30收盘/无年份9月30日 | 9/30 | 对应站立日/相对目标 |
| 引文/否定中的截止 | 不作为权限来源 | 无新许可，当前默认或继承旧许可 |
| 多锚“当日”、2/30、冲突截止 | 不猜max/不吞错误 | clarification，0工具 |
| continuation无新许可 / 当前明确新许可 | 保/更新用户目标 | 继承旧 / 用新明确截止 |
| legacy恢复原user可得 / 不完整 | 校验原source与digest | 重建旧 / clarification |

新 schema 不存在仍保旧无字段 hash；存在但坏 schema不能退回默认。不要为单独公司/市场题再加另一权限 parser。

- [ ] **Step B8.2（2–5 分钟）：运行有明确 scope 的定向绿检查。**

```bash
.venv-workbench/bin/python -m pytest -q intelligence/tests/test_temporal_contract.py intelligence/tests/test_honesty_gates.py intelligence/tests/test_query_understanding.py intelligence/tests/test_task_frame.py intelligence/tests/test_turn_controller.py intelligence/tests/test_episode_factory.py intelligence/tests/test_conversation_orchestrator.py intelligence/tests/test_continuous_turn_adapter.py intelligence/tests/test_episode_tools.py intelligence/tests/test_finance_query.py intelligence/tests/test_market_context_contract.py
.venv-workbench/bin/python -m ruff check intelligence/services/temporal_contract.py intelligence/services/honesty_gates.py intelligence/services/historical_research/intent.py intelligence/services/query_understanding.py intelligence/services/task_frame.py intelligence/services/research_contract.py intelligence/services/turn_controller.py intelligence/services/episode_factory.py intelligence/services/episode_tools.py intelligence/services/research_tool_registry.py intelligence/runtime/conversation_orchestrator.py intelligence/runtime/continuous_turn_adapter.py intelligence/tests/test_temporal_contract.py
```

期望：本范围全绿，0外呼；不能把该定向收据说成全量绿。若只测 helper 通过而 sentinel/public projection失败，B未完成。

- [ ] **Step B8.3（2–5 分钟）：更新门页并 pathspec 提交 B。** 门页写时间角色、trusted原user消息权威位置、继承/legacy拒绝条件与未来日程例外。再 `git diff --check`，提交只点名本 Task 文件（包含新增测试与确实改过的旧测试）。不 `git add -A` / 裸 commit；不顺手提交他人的索引。

```bash
git add -- intelligence/services/temporal_contract.py intelligence/services/honesty_gates.py intelligence/services/historical_research/intent.py intelligence/services/query_understanding.py intelligence/services/task_frame.py intelligence/services/research_contract.py intelligence/services/turn_controller.py intelligence/services/episode_factory.py intelligence/services/episode_tools.py intelligence/services/research_tool_registry.py intelligence/runtime/conversation_orchestrator.py intelligence/runtime/continuous_turn_adapter.py intelligence/tests/test_temporal_contract.py intelligence/tests/test_task_frame.py intelligence/tests/test_conversation_orchestrator.py intelligence/tests/test_continuous_turn_adapter.py intelligence/tests/test_episode_tools.py docs/agent-product-door.md
git commit -m "fix: freeze trusted temporal authority before research" -- intelligence/services/temporal_contract.py intelligence/services/honesty_gates.py intelligence/services/historical_research/intent.py intelligence/services/query_understanding.py intelligence/services/task_frame.py intelligence/services/research_contract.py intelligence/services/turn_controller.py intelligence/services/episode_factory.py intelligence/services/episode_tools.py intelligence/services/research_tool_registry.py intelligence/runtime/conversation_orchestrator.py intelligence/runtime/continuous_turn_adapter.py intelligence/tests/test_temporal_contract.py intelligence/tests/test_task_frame.py intelligence/tests/test_conversation_orchestrator.py intelligence/tests/test_continuous_turn_adapter.py intelligence/tests/test_episode_tools.py docs/agent-product-door.md
```

## 实施后放行顺序与真实首答 QA

- [ ] **Step V1（2–5 分钟准备，检查另记实际耗时）：固定两个实现提交，独立 Spec→Standards。** 审查 A 的完整覆盖/角色，B 的唯一输入权威Seam/实际消费者/事件正控及hash兼容；每条引用同 SHA。缺口修好再复核，工程测试不是内容批准。

- [ ] **Step V2（2–5 分钟启动，门禁另记实际耗时）：在纯候选树跑本机等价 CI。**

```bash
.venv-workbench/bin/python -m ruff check .
.venv-workbench/bin/python -m pytest -q
```

前端按 AGENTS 既有等价 CI 四项 `pnpm lint/typecheck/test/build`，e2e/registry-check 走现有主干门禁与 GitHub Actions；无前端改动也不得把聚合红忽略为“无关”。`data-quality-check` 按路径触发，这轮未触发其条件不能虚报已通过或缺结论。测试收据必须运行：

```bash
contract_receipt_path=$(.venv-workbench/bin/python -c 'from pathlib import Path; from scripts.check_test_receipt import latest_pointer; print(latest_pointer(Path.cwd()))')
.venv-workbench/bin/python scripts/check_test_receipt.py "$contract_receipt_path" --expect-revision "$(git rev-parse HEAD)" --require-full-scope
```

这里按脚本的本树 latest 指针定位，并要求它与实际 HEAD 全等，不填旧收据；`--ignore/-k/-m/--deselect` 有任一项都不是全量收据。严格记录 collected与读数。门禁临时树/basetemp绿后依现有脚本清理，不复制整份DB备份。

- [ ] **Step V3（2–5 分钟准备，真实运行另记实际耗时）：合法发布后新首次答卷验收。** 沿用户既有上线授权、仓库PR/Actions/合入确认流程执行。固定部署 identity、现役模型、semantic judge off 与其余 judge 实际模式、实际根预算；新 run、新目录保存原题首发 API message/prod event/snapshot与完整证据投影，0覆写旧产物，不重开旧批。沿现有真实入口问原题，只一次首答，不把未提交修订流稿顶成首答。

独立内容审查必须逐主张看：本表覆盖与预览是否被当全集；量价是否升净流入/唯一/长期趋势；重叠题材标签是否误当独立分散；同一时间同一命题的反证是否成立；新输入授权是否实际传到日期消费者；是否回应用户原问题。先记录 PASS/NOT_PASSED 及证据，再讲有限收益。不能据一次新跑签假胜率、严格同输入A/B、一般速度/成本或长期记忆。

provider finish 超时若再出现，保失败和首稿原件，交独立provider任务；不临时增预算或跳过质量标准。本计划的完成是两项结构合同真实落地与工程/内容各自有结论，不承诺模型一定给出某个市场判断。

## 文档自审映射

| 设计约束 | 实施步骤 |
| --- | --- |
| 全主题、组内8、全组非空/省略/排序/历史/published/coalesce | A1–A3、A5.4 |
| 事实/派生量价/ReadingRule来源分离、canonical NULL/零/严格阈值 | A4–A5 |
| 两个真实适配点、query_basis跨共享预算 | A5.1–A5.4 |
| 双角色、完整原user身份、相对锚、controller前冻结 | B2–B5 |
| 旧hash/字段缺失兼容、坏字段拒绝、续轮许可继承 | B4–B5、B8.1 |
| factory/adapter实际消费、目标/许可分别守界 | B6、B7.3 |
| 真未来资料不交内容、提前已知未来事件保留 | B7.1–B7.2 |
| 独立审查、准确全量scope、原件保留、新首答有限QA | V1–V3 |

## Task A 独立 Spec 实证补接缝（2026-10-08）

`c2ea27b73` 的独立复核为21P/3F：真实 `complete` 请求表明，两种主线预取及动态调用
都在 registry 之后丢失 `query_basis`；只在 typed runner 边界验收不足以证明模型实际收到。
原提交、RED、报告与历史设计保持原件；这一接缝补足 A 的两个真实消费者合同，不进入 B 的时间任务。

只传 registry 已批准的公共结构元数据，不从 prose 重建、不追加事实/E号/日期/floor，
不加编排、状态机、持久化字段或预算。预取与动态结果汇入同一个 loop-owned 通道并深拷贝；
非空时每次模型请求单独投影 JSON 消息，空时原消息及旧三元 runner/序列化行为保留。

| 文件责任 | 最小动作与验证 |
| --- | --- |
| `intelligence/services/ask.py` | 两种 D4 预取保存原 `query_basis`，与事实和指导分开传递 |
| `intelligence/services/generic_research_owner.py` | 转交预取元数据；动态 wrapper 保留 typed metadata，不降为仅 prose tuple |
| `intelligence/services/agent_research.py` | 兼容旧 runner；同一 loop 取得元数据副本并在每次请求独立投影，不修改 AgentStep/AgentLoopResult 持久化合同 |
| `intelligence/tests/test_generic_research_owner.py` | 实际模型入口验证两种预取、一次动态 D4 后两个步骤仍有全组/非空/历史/信号；原4000/240裁剪对照，禁止网络与真模型 |
| `intelligence/tests/test_agent_research.py` | 空元数据完整消息字节/旧 tuple/序列化兼容，嵌套元数据 owned-copy，不授予新证据 |
| `docs/agent-product-door.md` | 同提交记录模型透传与现有预算、方法和资格边界 |

修复收据另存 `task-A/fix-model-context-1008/`，复用独立脚本的三项实际模型 RED→GREEN，
不覆写 `spec-c2ea27b73`。随后定向相关回归、ruff、diff-check、自审与 pathspec 提交，
再交同一 Spec 独立复验及 Standards；工程与结构通过均不替代首答语义质量结论。
