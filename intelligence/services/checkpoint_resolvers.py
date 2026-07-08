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


def _unverifiable(data_source: str, reason: str, observed: dict[str, Any] | None = None) -> ResolveOutcome:
    return ResolveOutcome(
        verdict="unverifiable",
        score=None,
        data_source=data_source,
        reason=reason,
        observed=observed or {},
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
            return _unverifiable("market", "无关联个股，无法机检区间涨幅")
        try:
            target = float(metric["target"])
            op = str(metric.get("op") or ">=")
        except (KeyError, TypeError, ValueError):
            return _unverifiable("market", "metric 缺少有效 op/target")
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
            return _unverifiable("market", "区间内查无个股行情（停牌/未上市/名称不匹配）", observed)
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
            return _unverifiable("market", "market_daily 缺 conditions，无法机检")
        trade_date = str(metric.get("trade_date") or "") or checkpoints._parse_date(checkpoint.get("due"))
        fn = self.row_fn or self._default_row
        try:
            row = fn(trade_date)
        except Exception as exc:  # 无 duckdb / 无 db / 查询失败 → 降级
            return _unverifiable(
                "market",
                f"盘面数据不可用（{type(exc).__name__}）：本机有 DuckDB 时重跑 recheck 即可判定",
                {"trade_date": trade_date},
            )
        if not row:
            return _unverifiable(
                "market",
                f"fact_market_daily 查无 {trade_date} 行（未同步/非交易日）",
                {"trade_date": trade_date},
            )
        observed: dict[str, Any] = {"trade_date": trade_date, "conditions": []}
        passed_all = True
        for cond in conditions:
            field_name = str(cond.get("field") or "")
            op = str(cond.get("op") or ">=")
            try:
                target = float(cond.get("target"))
            except (TypeError, ValueError):
                return _unverifiable("market", f"条件 {field_name} 缺有效 target，无法机检", observed)
            value = row.get(field_name)
            if value is None:
                return _unverifiable("market", f"字段 {field_name} 当日无值/不存在，无法机检", observed)
            try:
                value_f = float(value)
            except (TypeError, ValueError):
                return _unverifiable("market", f"字段 {field_name} 非数值（{value!r}），无法机检", observed)
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
            return _unverifiable("knowledge", "无 target_name/themes/stocks，无法定位证据")
        try:
            threshold = int(float(metric.get("target", 1)))
        except (TypeError, ValueError):
            threshold = 1
        since = str(checkpoint.get("ts") or "")[:10]
        try:
            adapter = self._get_adapter()
            result = adapter.get_evidence(target, limit=500)
        except Exception as exc:  # 知识库缺失/读失败 → 降级
            return _unverifiable("knowledge", f"知识库不可用（{type(exc).__name__}）", {"target": target})
        if not result.get("found") and result.get("errors"):
            return _unverifiable("knowledge", "证据库读取失败", {"target": target, "errors": result.get("errors")})
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
    )
