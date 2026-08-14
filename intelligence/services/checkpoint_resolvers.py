"""可证伪点回检引擎：到期把判断交给对应数据源核对，产出 verdict（优雅降级）。

按 ``checkpoint.metric.type`` 路由到不同 resolver：

- ``stock_return`` → :class:`MarketResolver`：拉个股区间涨幅（DuckDB），对比 ``op``/``target``。
  **本机有 DuckDB 才跑真数**；云端/CI 无 duckdb 或 ``db/market.duckdb`` 缺失时
  →返回 ``unverifiable``（绝不编造），下次有数据环境再判。
- ``kb_evidence`` → :class:`KnowledgeResolver`：查注册后是否出现新证据（``wiki/relations``，
  云端也在仓里，随处可跑）。
- ``market_daily`` → :class:`MarketDailyResolver`：拉 ``fact_market_daily`` 到期日整行，
  逐条比较 ``conditions``（全部达标=hit，任一不达标=miss，查无当日行=unverifiable）。
  市场路径类 claim（涨家/涨停/成交额阈值）用它机检，不再落 manual。
- 其他 / 无 metric → 走人工：返回 ``unverifiable``，等 ``checkpoint score`` 人工打分。

**红线**：缺数、报错、连不上一律降级为 ``unverifiable``，永不臆造 hit/miss。
本模块顶层不 import duckdb / market 适配器（保持 CLI 在无 duckdb 环境可用），
真正用到时才惰性导入。

**降级不等于沉默**：每个 ``unverifiable`` 出口都要交出 :class:`ResolveOutcome.degradation`
——试过哪些源及其返回状态 / 缺口是什么 / 对判断有什么影响 / 走了什么 fallback /
待补证清单。可信度降低的时候透明度必须提高，否则夜间 recheck 只留一句"数据不可用"，
半年后没人知道当时卡在哪、要补什么才能判。这几项是**必填关键字参数**，
新增降级出口漏写会直接 TypeError，不会静默产出半个披露。
口径来源见 ``docs/learning/knevo-distill/q13-拒答与降级纪律.md``。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as date_cls, timedelta
from typing import Any, Callable

from intelligence.services import checkpoints

# 给 MarketResolver 注入的「区间涨幅」函数签名（便于离线单测，不依赖真 DuckDB）：
# (stocks, start, end) -> {名称或代码: {"interval_gain": float, ...}}
ReturnsFn = Callable[[list[str], str, str], dict[str, dict[str, Any]]]


@dataclass
class ResolveOutcome:
    verdict: str  # hit | miss | partial | unverifiable
    score: float | None
    data_source: str
    reason: str
    observed: dict[str, Any] = field(default_factory=dict)
    # 仅 unverifiable 时有值；hit/miss 拿到了真数，不需要降级披露。
    degradation: dict[str, Any] | None = None


# 降级披露的必填项（缺一项即视为降级不合格）。
DEGRADE_FIELDS = ("attempted", "gap", "impact", "fallback", "todo")

# 影响口径是统一的：unverifiable 不是"判错"，是"这条还不能判"。
DEFAULT_IMPACT = "不计入命中率分母，仍留在到期队列；数据到位后重跑 recheck 即可判定"

# q13 的 7 项里有 2 项落在答案生成层、不在机检 resolver 层，这里显式记下来，
# 免得后来的人以为是漏了：resolver 只做「查得到就判、查不到就降级」，
# 它不产出推断也不断言历史基线，硬塞这两个字段只会得到两个空壳。
NOT_APPLICABLE_HERE = {
    "fact_inference_assumption_split": "resolver 不产出推断，只回报查到/查不到，三分法归答案生成层",
    "baseline_vs_current_split": "resolver 不断言历史基线，基线分离归答案生成层",
}


def _unverifiable(
    data_source: str,
    reason: str,
    observed: dict[str, Any] | None = None,
    *,
    attempted: list[dict[str, str]],
    gap: str,
    fallback: str,
    todo: list[str],
    owed_source: str | None = None,
    impact: str = DEFAULT_IMPACT,
) -> ResolveOutcome:
    """降级出口：除"标注缺口"外，还要交出试过什么 / 影响 / fallback / 待补证。

    ``attempted`` 每项形如 ``{"source": "duckdb:fact_market_daily", "status": "..."}``；
    规格不全时一次查询都没发出，此处为空列表 —— 空本身就是信息，别拿假条目填。
    ``owed_source`` 是"本该由谁判"，降级不改写它：这条是 q13「来源标注不降级」，
    这样看板上能区分"市场数据该判但没数"和"本来就只能人工判"。
    """
    return ResolveOutcome(
        verdict="unverifiable",
        score=None,
        data_source=data_source,
        reason=reason,
        observed=observed or {},
        degradation={
            "attempted": list(attempted),
            "gap": gap,
            "impact": impact,
            "fallback": fallback,
            "todo": list(todo),
            "owed_source": owed_source or data_source,
            "not_applicable": dict(NOT_APPLICABLE_HERE),
        },
    )


def _spec_gap(
    data_source: str,
    reason: str,
    *,
    missing: str,
    observed: dict[str, Any] | None = None,
) -> ResolveOutcome:
    """规格不全：checkpoint 自己没写清，一次外部查询都没发出，补规格才有救。"""
    return _unverifiable(
        data_source,
        reason,
        observed,
        attempted=[],
        gap=f"checkpoint 规格缺 {missing}",
        fallback="无 fallback：规格补全前任何数据源都判不了",
        todo=[f"补 {missing}，再 `checkpoint recheck --id <id>`"],
    )


def _compare(value: float, op: str, target: float) -> bool:
    if op == ">=":
        return value >= target
    if op == ">":
        return value > target
    if op == "<=":
        return value <= target
    if op == "<":
        return value < target
    return abs(value - target) < 1e-9


# --------------------------------------------------------------------------- #
# 盘面 resolver：个股区间涨幅 vs 阈值（DuckDB，缺则 unverifiable）。
# --------------------------------------------------------------------------- #
@dataclass
class MarketResolver:
    db_path: str | None = None
    returns_fn: ReturnsFn | None = None  # 注入则用之（单测）；否则惰性接 MarketAdapter

    def _default_returns(self, stocks: list[str], start: str, end: str) -> dict[str, dict[str, Any]]:
        # 惰性导入：无 duckdb / 无 db 文件时抛错，由 resolve() 捕获→unverifiable。
        from intelligence.adapters.market import MarketAdapter

        adapter = MarketAdapter(db_path=self.db_path)
        return adapter.interval_returns(stocks, start, end)

    def resolve(self, checkpoint: dict[str, Any]) -> ResolveOutcome:
        metric = checkpoint.get("metric") or {}
        stocks = checkpoints._clean_terms(checkpoint.get("stocks"))
        if metric.get("target_name"):
            stocks = [str(metric["target_name"]).strip()] + [s for s in stocks if s != metric["target_name"]]
        if not stocks:
            return _spec_gap("market", "无关联个股，无法机检区间涨幅", missing="stocks/metric.target_name")
        try:
            target = float(metric["target"])
            op = str(metric.get("op") or ">=")
        except (KeyError, TypeError, ValueError):
            return _spec_gap("market", "metric 缺少有效 op/target", missing="metric.op/metric.target")
        window = int(metric.get("window_days") or checkpoints.DEFAULT_WINDOW_DAYS)
        end = checkpoints._parse_date(checkpoint.get("due"))
        start = (date_cls.fromisoformat(end) - timedelta(days=window)).isoformat()
        fn = self.returns_fn or self._default_returns
        try:
            returns = fn(stocks, start, end)
        except Exception as exc:  # 无 duckdb / 无 db / 查询失败 → 降级
            return _unverifiable(
                "market",
                f"盘面数据不可用（{type(exc).__name__}）：本机有 DuckDB 时重跑 recheck 即可判定",
                {"window": [start, end], "stocks": stocks},
                attempted=[{"source": "duckdb:interval_returns", "status": f"{type(exc).__name__}: {exc}"[:200]}],
                gap=f"取不到 {start}~{end} 区间涨幅（{type(exc).__name__}）",
                fallback="无替代源：本模块只认 DuckDB 真数，不用估算值顶替",
                todo=[f"在有 db/market_feature_store.duckdb 的机器上重跑 `checkpoint recheck --id <id>`（窗口 {start}~{end}）"],
            )
        # 取命中的个股（任一关联个股达标即算 hit；都不达标算 miss；查无数据算 unverifiable）。
        observed: dict[str, Any] = {"window": [start, end], "op": op, "target": target, "returns": {}}
        found = False
        passed = False
        for name in stocks:
            row = returns.get(name)
            if not row or row.get("interval_gain") is None:
                continue
            found = True
            gain = float(row["interval_gain"])
            observed["returns"][name] = round(gain, 2)
            if _compare(gain, op, target):
                passed = True
        if not found:
            return _unverifiable(
                "market",
                "区间内查无个股行情（停牌/未上市/名称不匹配）",
                observed,
                attempted=[{"source": "duckdb:interval_returns", "status": f"查询成功但 {len(stocks)} 只均无行情行"}],
                gap=f"{stocks} 在 {start}~{end} 无行情：停牌、未上市，或名称/代码对不上库里的写法",
                fallback="无 fallback：名称没对上时猜代码只会判错对象",
                todo=[
                    f"确认 {stocks} 在库中的实际写法（`dim_sector`/`fact_stock_daily` 名称与代码两路查）",
                    "确认区间内是否整段停牌；若是则该 checkpoint 本身要改窗口",
                ],
            )
        verdict = "hit" if passed else "miss"
        reason = (
            f"区间 {start}~{end} 涨幅 {observed['returns']} {op} {target}"
            f"{'：达标' if passed else '：未达标'}"
        )
        return ResolveOutcome(verdict, checkpoints.SCORE_MAP[verdict], "market", reason, observed)


# --------------------------------------------------------------------------- #
# 盘面 resolver：fact_market_daily 当日多条件阈值（DuckDB，缺则 unverifiable）。
# --------------------------------------------------------------------------- #
# 给 MarketDailyResolver 注入的「当日行」函数签名（便于离线单测）：date -> row dict | None
MarketDailyRowFn = Callable[[str], "dict[str, Any] | None"]


@dataclass
class MarketDailyResolver:
    db_path: str | None = None
    row_fn: MarketDailyRowFn | None = None

    def _default_row(self, date: str) -> dict[str, Any] | None:
        from intelligence.adapters.market import MarketAdapter

        return MarketAdapter(db_path=self.db_path).market_daily_row(date)

    def resolve(self, checkpoint: dict[str, Any]) -> ResolveOutcome:
        metric = checkpoint.get("metric") or {}
        conditions = metric.get("conditions") or []
        if not conditions:
            return _spec_gap("market", "market_daily 缺 conditions，无法机检", missing="metric.conditions")
        trade_date = str(metric.get("trade_date") or "") or checkpoints._parse_date(checkpoint.get("due"))
        fn = self.row_fn or self._default_row
        try:
            row = fn(trade_date)
        except Exception as exc:  # 无 duckdb / 无 db / 查询失败 → 降级
            return _unverifiable(
                "market",
                f"盘面数据不可用（{type(exc).__name__}）：本机有 DuckDB 时重跑 recheck 即可判定",
                {"trade_date": trade_date},
                attempted=[{"source": "duckdb:fact_market_daily", "status": f"{type(exc).__name__}: {exc}"[:200]}],
                gap=f"取不到 {trade_date} 的 fact_market_daily 整行（{type(exc).__name__}）",
                fallback="无替代源：条件全是阈值比较，缺一个字段就不能判",
                todo=[f"在有 DuckDB 的机器上重跑 `checkpoint recheck --id <id>`（{trade_date}）"],
            )
        if not row:
            return _unverifiable(
                "market",
                f"fact_market_daily 查无 {trade_date} 行（未同步/非交易日）",
                {"trade_date": trade_date},
                attempted=[{"source": "duckdb:fact_market_daily", "status": "查询成功，无该日行"}],
                gap=f"{trade_date} 在 fact_market_daily 无行：当日未同步，或本就不是交易日",
                fallback="无 fallback：不拿相邻交易日顶替当日（那是换了个题目在答）",
                todo=[
                    f"先分清是未同步还是非交易日；未同步则 `daily-full --trade-date {trade_date}` 补，非交易日则改 checkpoint 的 due",
                ],
            )
        observed: dict[str, Any] = {"trade_date": trade_date, "conditions": []}
        passed_all = True
        for cond in conditions:
            field_name = str(cond.get("field") or "")
            op = str(cond.get("op") or ">=")
            try:
                target = float(cond.get("target"))
            except (TypeError, ValueError):
                return _spec_gap(
                    "market", f"条件 {field_name} 缺有效 target，无法机检",
                    missing=f"conditions[{field_name}].target", observed=observed,
                )
            value = row.get(field_name)
            if value is None:
                return _unverifiable(
                    "market", f"字段 {field_name} 当日无值/不存在，无法机检", observed,
                    attempted=[{"source": "duckdb:fact_market_daily", "status": f"取到 {trade_date} 行，但 {field_name} 为空/无此列"}],
                    gap=f"{field_name} 在 {trade_date} 无值：该列未回填，或字段名和 schema 对不上",
                    fallback="无 fallback：拿 0 当缺失值会把没达标和没数据混成一件事",
                    todo=[f"核对 {field_name} 是否在 schema.sql 里；在则回填 {trade_date}，不在则修 checkpoint 的字段名"],
                )
            try:
                value_f = float(value)
            except (TypeError, ValueError):
                return _unverifiable(
                    "market", f"字段 {field_name} 非数值（{value!r}），无法机检", observed,
                    attempted=[{"source": "duckdb:fact_market_daily", "status": f"取到值但非数值：{value!r}"[:200]}],
                    gap=f"{field_name}={value!r} 不能转成数，阈值比较无从下手",
                    fallback="无 fallback：不猜解析规则",
                    todo=[f"查 {field_name} 的写入端为什么落了非数值（单位串/占位符？），修数据或改 checkpoint 口径"],
                )
            ok = _compare(value_f, op, target)
            observed["conditions"].append({"field": field_name, "op": op, "target": target, "value": value_f, "pass": ok})
            if not ok:
                passed_all = False
        verdict = "hit" if passed_all else "miss"
        detail = "，".join(
            f"{c['field']}={c['value']}{'✓' if c['pass'] else '✗'}({c['op']}{c['target']})"
            for c in observed["conditions"]
        )
        reason = f"{trade_date} 盘面：{detail}：{'全部达标' if passed_all else '未全部达标'}"
        return ResolveOutcome(verdict, checkpoints.SCORE_MAP[verdict], "market", reason, observed)


# --------------------------------------------------------------------------- #
# 知识库 resolver：注册后是否出现新证据（relations/evidence_index.json）。
# --------------------------------------------------------------------------- #
@dataclass
class KnowledgeResolver:
    wiki_root: str | None = None
    adapter: Any | None = None  # 注入则用之（单测）；否则惰性接 KnowledgeAdapter

    def _get_adapter(self) -> Any:
        if self.adapter is not None:
            return self.adapter
        from intelligence.adapters.knowledge import KnowledgeAdapter

        return KnowledgeAdapter(wiki_root=self.wiki_root)

    def resolve(self, checkpoint: dict[str, Any]) -> ResolveOutcome:
        metric = checkpoint.get("metric") or {}
        target = str(metric.get("target_name") or "").strip()
        if not target:
            cand = checkpoints._clean_terms(checkpoint.get("themes")) + checkpoints._clean_terms(checkpoint.get("stocks"))
            target = cand[0] if cand else ""
        if not target:
            return _spec_gap(
                "knowledge", "无 target_name/themes/stocks，无法定位证据",
                missing="metric.target_name 或 themes/stocks",
            )
        try:
            threshold = int(float(metric.get("target", 1)))
        except (TypeError, ValueError):
            threshold = 1
        since = str(checkpoint.get("ts") or "")[:10]
        try:
            adapter = self._get_adapter()
            result = adapter.get_evidence(target, limit=500)
        except Exception as exc:  # 知识库缺失/读失败 → 降级
            return _unverifiable(
                "knowledge", f"知识库不可用（{type(exc).__name__}）", {"target": target},
                attempted=[{"source": "wiki:get_evidence", "status": f"{type(exc).__name__}: {exc}"[:200]}],
                gap=f"打不开知识库，取不到 {target} 的证据列表",
                fallback="无替代源：证据数是判据本身，没有近似值可用",
                todo=[f"确认 wiki_root 指向存在的知识库，再 `checkpoint recheck --id <id>`（target={target}）"],
            )
        if not result.get("found") and result.get("errors"):
            return _unverifiable(
                "knowledge", "证据库读取失败", {"target": target, "errors": result.get("errors")},
                attempted=[{"source": "wiki:get_evidence", "status": f"返回 found=false + errors={result.get('errors')}"[:200]}],
                gap=f"{target} 的证据索引读失败（不是「没有新证据」，是「没读到」）",
                fallback="无 fallback：读失败当成 0 条新证据就会把它误判成 miss",
                todo=["按 errors 修 relations/evidence_index.json 后重跑"],
            )
        items = result.get("items") or []
        new_items = [
            it for it in items
            if isinstance(it, dict) and str(it.get("source_date") or "")[:10] >= since and str(it.get("source_date") or "").strip()
        ]
        observed = {"target": target, "since": since, "new_evidence": len(new_items), "total_evidence": len(items), "threshold": threshold}
        verdict = "hit" if len(new_items) >= threshold else "miss"
        reason = (
            f"{target} 注册（{since}）后新增证据 {len(new_items)} 条（阈值 {threshold}）"
            f"{'：兑现' if verdict == 'hit' else '：未见新证据'}"
        )
        return ResolveOutcome(verdict, checkpoints.SCORE_MAP[verdict], "knowledge", reason, observed)


def resolve_checkpoint(
    checkpoint: dict[str, Any],
    *,
    db_path: str | None = None,
    wiki_root: str | None = None,
    market_returns_fn: ReturnsFn | None = None,
    knowledge_adapter: Any | None = None,
) -> ResolveOutcome:
    """按 metric.type 路由到对应 resolver；无机检规格 → 人工（unverifiable）。"""
    metric = checkpoint.get("metric") or {}
    mtype = str(metric.get("type") or "").strip()
    if mtype == "stock_return":
        return MarketResolver(db_path=db_path, returns_fn=market_returns_fn).resolve(checkpoint)
    if mtype == "kb_evidence":
        return KnowledgeResolver(wiki_root=wiki_root, adapter=knowledge_adapter).resolve(checkpoint)
    if mtype == "market_daily":
        return MarketDailyResolver(db_path=db_path).resolve(checkpoint)
    return _unverifiable(
        "manual",
        "无机检规格（manual）：用 `checkpoint score --id <id> --verdict hit|miss|partial` 人工打分",
        attempted=[],
        gap=f"metric.type={mtype or '(空)'} 没有对应 resolver，机器判不了",
        impact="不计入命中率分母；等人工打分，不会因为没人打分而变成 miss",
        fallback="人工打分：`checkpoint score --id <id> --verdict hit|miss|partial`",
        todo=[
            "人工判定后 `checkpoint score`",
            "若这类 claim 反复出现，考虑给它写 metric 规格（stock_return / market_daily / kb_evidence）转成机检",
        ],
        owed_source="manual",
    )
