"""偏差目录 v1：登记判断时，从台账 + 旁路库**确定性**算出「你可能正在犯哪种过程性错误」。

设计稿 ``docs/superpowers/specs/2026-09-04-methodology-backtest-structured-history-design.md`` §10.2 第一条：
理性 / 非理性按**过程**定义，不按结果定义——一次判断亏了不等于非理性。目录只收能从可证伪点台账
（``checkpoints.jsonl`` / ``verdicts.jsonl``）与旁路库 ``history_labels.duckdb`` 确定性算出的条目；
算不出的（如「锚定」——claim 是自由文本）不进目录。四条：

| code | 一句话 | 数据源 |
|---|---|---|
| ``late_streak``      | 追高 / 末段登记：关联板块在 D0 ``dual_red_streak >= 4``，或热度前三连续 >= 3 日 | 台账 themes → ``dim_sector`` / ``config_theme_sector_link`` → 旁路库标签 |
| ``post_miss_streak`` | 近因：同类判断最近 >= 2 条终态均 miss，且距最后一次 miss <= 3 个交易日 | 只用台账（+ 日历） |
| ``rule_not_firing``  | 偏离自己的规则：带 ``rule_id`` 但规则在 D0 对关联实体未触发（编译器窗口 ``[D0, D0]`` 取事件集） | 规则文件 + 旁路库 |
| ``revenge_reentry``  | 连错再登记：共享标的的上一条判断刚落空（<= 5 个交易日）又登记 | 只用台账（+ 日历） |

三条纪律（与 ``checkpoint_resolvers`` 的降级形状同族）：

1. **只提示不拦截**：``scan`` 只返回 flag，不改判断、不写 verdict；任何异常都被折成 ``*_unverifiable``，
   登记不会因为它失败。
2. **unverifiable ≠ not_applicable**：数据不齐（缺日历 / 缺映射 / 缺标签行 / 库打不开）给
   ``<code>_unverifiable``，``evidence.missing`` 写缺什么；规则不适用（如无 ``rule_id`` 时的 ``rule_not_firing``）
   **不产 flag**——两者混在一起，「无 flag」就没有含义了。
3. **绝不猜**：``themes`` 文本映射不到 ``sector_ts_code`` 就是 unverifiable，不做模糊匹配；旁路库缺失时
   只用台账的两条退化为自然日计数并在 ``evidence.calendar="natural_days"`` 标明，要触库的两条为 unverifiable。

D0 的口径：判断登记时刻 ``ts`` 换成北京时间，收盘（15:00）之后登记取当日、之前取前一日，再落到日历上
最近的一个交易日——确认日语义：D 日的标签只在 D 日收盘后才成立，盘中登记不能用当日标签。
``ts`` 无时区一律按 UTC 解释（``checkpoints._now()`` 写的就是 UTC）。

本模块可 import ``methodology_backtest.*``（同在 services，不触 runtime）；``checkpoints.py`` 保持只用标准库，
所以目录放在这里而不是那里。数据源以可注入 callable 形式传入（``LabelLookup`` / ``EntityLookup`` /
``RuleFireLookup``），单测不连真库；真库实现见 :class:`LedgerDataSources`（全部 ``read_only=True``）。
"""

from __future__ import annotations

import re
from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, time as time_cls, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

from intelligence.services.checkpoints import TERMINAL_VERDICTS

BIAS_CODES = ("late_streak", "post_miss_streak", "rule_not_firing", "revenge_reentry")
UNVERIFIABLE_SUFFIX = "_unverifiable"
SEVERITY_INFO = "info"
SEVERITY_WARN = "warn"
SEVERITIES = (SEVERITY_INFO, SEVERITY_WARN)

# 阈值常量（工单 §2.4 写死；改动请同步设计稿 §10.2 第一条）。
LATE_STREAK_GE = 4
LATE_HEAT_RANK_LE = 3
LATE_HEAT_DAYS = 3
POST_MISS_STREAK_GE = 2
POST_MISS_WITHIN_DAYS = 3
REVENGE_WITHIN_DAYS = 5

# A 股收盘时刻与时区（无夏令时，固定 +08:00）。
MARKET_CLOSE = time_cls(15, 0)
CN_TZ = timezone(timedelta(hours=8))

CALENDAR_TRADING = "history_calendar"
CALENDAR_NATURAL = "natural_days"

_RULE_FILE_RE = re.compile(r"\.v(\d+)\.json$")


# --------------------------------------------------------------------------- #
# 数据类与注入点
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class BiasFlag:
    code: str
    severity: str  # info | warn
    reason: str
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def base_code(self) -> str:
        return self.code[: -len(UNVERIFIABLE_SUFFIX)] if self.code.endswith(UNVERIFIABLE_SUFFIX) else self.code

    @property
    def unverifiable(self) -> bool:
        return self.code.endswith(UNVERIFIABLE_SUFFIX)

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "severity": self.severity, "reason": self.reason, "evidence": dict(self.evidence)}


@dataclass(frozen=True)
class RuleFire:
    """某条规则在某个交易日的事件集（编译器窗口 ``[D0, D0]``）。``fired`` 是当日满足全部谓词的实体 id。"""

    rule_ref: str
    entity_type: str
    trade_date: str
    fired: frozenset[str]
    label_version: str | None = None


class LookupUnavailable(Exception):
    """数据源打不开 / 找不到（库被写锁占用、规则文件不存在……）。``scan`` 把它折成 unverifiable，消息进 ``evidence.missing``。"""


# (entity_type, entity_ids, label, trade_dates) -> {(entity_id, trade_date): value_num}；没有那一行就没有那个键。
LabelLookup = Callable[[str, Sequence[str], str, Sequence[str]], dict[tuple[str, str], float | None]]
# themes 文本 -> {theme: [sector_ts_code, ...]}；返回 None 表示映射源不可用（与「查了但没映到」不同）。
EntityLookup = Callable[[Sequence[str]], "dict[str, list[str]] | None"]
# (rule_id, trade_date) -> RuleFire；None 表示规则或旁路库不可用。
RuleFireLookup = Callable[[str, str], "RuleFire | None"]


def _unverifiable(code: str, missing: str, **evidence: Any) -> BiasFlag:
    return BiasFlag(
        code=f"{code}{UNVERIFIABLE_SUFFIX}",
        severity=SEVERITY_INFO,
        reason=f"{code} 无法判定：缺 {missing}",
        evidence={"missing": missing, **evidence},
    )


# --------------------------------------------------------------------------- #
# 时间与日历
# --------------------------------------------------------------------------- #
def parse_ts(value: Any) -> datetime | None:
    """ISO 时间戳 → 带时区的 UTC ``datetime``；无时区按 UTC；解析失败 → None。"""
    s = str(value or "").strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        try:
            dt = datetime.fromisoformat(s[:10])
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def local_date(dt: datetime) -> str:
    """北京时间的日历日 ``YYYY-MM-DD``。"""
    return dt.astimezone(CN_TZ).date().isoformat()


def resolve_d0(ts: datetime, calendar: Sequence[str]) -> tuple[str | None, str]:
    """登记时刻 → 标签成立的交易日 D0 与口径说明。收盘后取当日、收盘前取前一日，再落到最近交易日。"""
    local = ts.astimezone(CN_TZ)
    if local.time() < MARKET_CLOSE:
        cutoff = (local - timedelta(days=1)).date().isoformat()
        basis = "before_close→previous_day"
    else:
        cutoff = local.date().isoformat()
        basis = "after_close→same_day"
    i = bisect_right(list(calendar), cutoff) - 1
    return (str(calendar[i]) if i >= 0 else None), basis


def days_between(calendar: Sequence[str] | None, start: str, end: str) -> tuple[int, str]:
    """``start`` 到 ``end`` 的天数：有日历数 ``(start, end]`` 内的交易日，否则自然日。返回 ``(天数, 口径)``。"""
    if calendar:
        cal = list(calendar)
        n = bisect_right(cal, end) - bisect_right(cal, start)
        return n, CALENDAR_TRADING
    d0 = datetime.fromisoformat(start[:10]).date()
    d1 = datetime.fromisoformat(end[:10]).date()
    return (d1 - d0).days, CALENDAR_NATURAL


def _terms(values: Any) -> list[str]:
    out: list[str] = []
    for v in values or []:
        s = str(v).strip()
        if s and s not in out:
            out.append(s)
    return out


def _norm(text: Any) -> str:
    return re.sub(r"\s+", "", str(text or "")).lower()


def _terminal_before(verdicts: list[dict[str, Any]], before: datetime) -> dict[str, dict[str, Any]]:
    """登记时刻 ``before`` 之前**已知**的终态打分，每个 id 取最后一条（同 ``checkpoints._latest_terminal_verdicts`` 口径）。

    只看 ``checked_at <= before`` 的：过程条件只能用登记当时可得的信息，之后才出的结果不算。
    """
    out: dict[str, dict[str, Any]] = {}
    for v in verdicts:
        if v.get("verdict") not in TERMINAL_VERDICTS or not v.get("id"):
            continue
        checked = parse_ts(v.get("checked_at"))
        if checked is None or checked > before:
            continue
        out[str(v["id"])] = v
    return out


def _map_themes(
    themes: list[str], entity_lookup: EntityLookup | None
) -> tuple[list[str], list[str], str | None]:
    """themes → 去重的 sector_ts_code 列表。返回 ``(codes, unmapped, missing)``；``missing`` 非 None 即该判 unverifiable。"""
    if entity_lookup is None:
        return [], list(themes), "sector_ts_code 映射（未提供 dim_sector / config_theme_sector_link 查询）"
    mapping = entity_lookup(themes)
    if mapping is None:
        return [], list(themes), "sector_ts_code 映射源（主库不可用）"
    codes: list[str] = []
    unmapped: list[str] = []
    for name in themes:
        hits = [str(c) for c in (mapping.get(name) or []) if str(c).strip()]
        if not hits:
            unmapped.append(name)
        for c in hits:
            if c not in codes:
                codes.append(c)
    if not codes:
        return [], unmapped, f"sector_ts_code 映射（{unmapped} 不在 dim_sector / config_theme_sector_link）"
    return codes, unmapped, None


# --------------------------------------------------------------------------- #
# 四条目录项（各自纯函数：给数据就算，缺数据就说缺什么）
# --------------------------------------------------------------------------- #
def check_late_streak(
    checkpoint: dict[str, Any],
    *,
    label_lookup: LabelLookup | None,
    entity_lookup: EntityLookup | None,
    calendar: Sequence[str] | None,
) -> BiasFlag | None:
    code = "late_streak"
    themes = _terms(checkpoint.get("themes"))
    if not themes:
        return _unverifiable(code, "themes（判断没关联任何板块 / 题材）")
    ts = parse_ts(checkpoint.get("ts"))
    if ts is None:
        return _unverifiable(code, "ts（登记时刻缺失或不可解析）")
    if not calendar:
        return _unverifiable(code, "history_calendar（旁路库缺失，交易日 D0 无法确定）")
    d0, basis = resolve_d0(ts, calendar)
    if d0 is None:
        return _unverifiable(code, "D0（登记时刻早于旁路库日历起点）", d0_basis=basis)
    codes, unmapped, missing = _map_themes(themes, entity_lookup)
    if missing:
        return _unverifiable(code, missing, d0=d0, themes=themes)
    if label_lookup is None:
        return _unverifiable(code, "history_labels（旁路库缺失）", d0=d0, codes=codes)

    cal = list(calendar)
    i = cal.index(d0)
    heat_days = cal[max(0, i - (LATE_HEAT_DAYS - 1)) : i + 1]
    streaks = label_lookup("sector", codes, "dual_red_streak", [d0])
    ranks = label_lookup("theme", codes, "limit_heat_rank", heat_days)
    streak_vals = {c: float(v) for (c, d), v in streaks.items() if v is not None and d == d0}
    rank_vals = {(c, d): float(v) for (c, d), v in ranks.items() if v is not None}
    if not streak_vals and not rank_vals:
        return _unverifiable(
            code,
            f"D0={d0} 上 {codes} 没有 dual_red_streak / limit_heat_rank 标签行（旁路库未覆盖该日或该代码）",
            d0=d0,
            d0_basis=basis,
            codes=codes,
            unmapped_themes=unmapped,
        )
    streak_hits = {c: v for c, v in streak_vals.items() if v >= LATE_STREAK_GE}
    heat_hits = [
        c
        for c in codes
        if len(heat_days) == LATE_HEAT_DAYS
        and all(rank_vals.get((c, d)) is not None and rank_vals[(c, d)] <= LATE_HEAT_RANK_LE for d in heat_days)
    ]
    evidence = {
        "d0": d0,
        "d0_basis": basis,
        "codes": codes,
        "unmapped_themes": unmapped,
        "dual_red_streak": streak_vals,
        "limit_heat_rank": {f"{c}@{d}": v for (c, d), v in sorted(rank_vals.items())},
        "heat_days": heat_days,
        "thresholds": {"dual_red_streak_ge": LATE_STREAK_GE, "heat_rank_le": LATE_HEAT_RANK_LE, "heat_days": LATE_HEAT_DAYS},
    }
    if streak_hits or heat_hits:
        parts = []
        if streak_hits:
            parts.append("双红连板 " + "、".join(f"{c}={int(v)}" for c, v in streak_hits.items()))
        if heat_hits:
            parts.append(f"热度前 {LATE_HEAT_RANK_LE} 连续 {LATE_HEAT_DAYS} 日 {heat_hits}")
        return BiasFlag(
            code=code,
            severity=SEVERITY_WARN,
            reason=f"追高 / 末段登记：D0={d0} 关联板块 " + "；".join(parts) + "——这是在一段已经走了很久的行情末端下判断",
            evidence=evidence,
        )
    return None


def check_post_miss_streak(
    checkpoint: dict[str, Any],
    *,
    checkpoints: list[dict[str, Any]],
    verdicts: list[dict[str, Any]],
    calendar: Sequence[str] | None,
) -> BiasFlag | None:
    code = "post_miss_streak"
    category = str(checkpoint.get("category") or "").strip()
    if not category:
        return _unverifiable(code, "category（判断没有类别，找不到「同类」）")
    ts = parse_ts(checkpoint.get("ts"))
    if ts is None:
        return _unverifiable(code, "ts（登记时刻缺失或不可解析）")
    cid = str(checkpoint.get("id") or "")
    known = _terminal_before(verdicts, ts)
    history: list[tuple[datetime, dict[str, Any]]] = []
    for c in checkpoints:
        if str(c.get("id") or "") == cid or str(c.get("category") or "").strip() != category:
            continue
        v = known.get(str(c.get("id") or ""))
        if v is None:
            continue
        checked = parse_ts(v.get("checked_at"))
        if checked is not None:
            history.append((checked, v))
    history.sort(key=lambda item: item[0])
    streak = 0
    for _checked, v in reversed(history):
        if v.get("verdict") != "miss":
            break
        streak += 1
    if streak < POST_MISS_STREAK_GE:
        return None
    last_checked, last = history[-1]
    gap, cal_kind = days_between(calendar, local_date(last_checked), local_date(ts))
    if gap > POST_MISS_WITHIN_DAYS:
        return None
    return BiasFlag(
        code=code,
        severity=SEVERITY_WARN,
        reason=(
            f"近因：「{category}」最近 {streak} 条终态判定全部落空，最后一次落空（{local_date(last_checked)}）"
            f"距本次登记 {gap} 个{'交易日' if cal_kind == CALENDAR_TRADING else '自然日'}——刚连错就再登记同类判断，先看看是不是在补偿"
        ),
        evidence={
            "category": category,
            "miss_streak": streak,
            # 只留最近几条 id 作线索；真台账上连错 50 条时全列出来没人读。
            "recent_miss_ids": [v.get("id") for _c, v in history[-min(streak, 5) :]],
            "last_miss_checked_at": last.get("checked_at"),
            "gap_days": gap,
            "calendar": cal_kind,
            "thresholds": {"streak_ge": POST_MISS_STREAK_GE, "within_days": POST_MISS_WITHIN_DAYS},
        },
    )


def check_rule_not_firing(
    checkpoint: dict[str, Any],
    *,
    rule_fire_lookup: RuleFireLookup | None,
    entity_lookup: EntityLookup | None,
    calendar: Sequence[str] | None,
) -> BiasFlag | None:
    code = "rule_not_firing"
    rule_id = str(checkpoint.get("rule_id") or "").strip()
    if not rule_id:
        return None  # 不适用：没引用规则，谈不上偏离
    ts = parse_ts(checkpoint.get("ts"))
    if ts is None:
        return _unverifiable(code, "ts（登记时刻缺失或不可解析）", rule_id=rule_id)
    if not calendar:
        return _unverifiable(code, "history_calendar（旁路库缺失，交易日 D0 无法确定）", rule_id=rule_id)
    d0, basis = resolve_d0(ts, calendar)
    if d0 is None:
        return _unverifiable(code, "D0（登记时刻早于旁路库日历起点）", rule_id=rule_id, d0_basis=basis)
    if rule_fire_lookup is None:
        return _unverifiable(code, "规则事件集（未提供 rule_fire_lookup：规则编译 / 旁路库不可用）", rule_id=rule_id, d0=d0)
    fire = rule_fire_lookup(rule_id, d0)
    if fire is None:
        return _unverifiable(code, f"规则 {rule_id} 的事件集（规则文件或旁路库不可用）", rule_id=rule_id, d0=d0)
    if fire.entity_type == "stock":
        return _unverifiable(
            code,
            "stock_ts_code 映射（v1 只映射 themes → sector_ts_code，个股规则的实体对照未实现）",
            rule_id=rule_id,
            rule_ref=fire.rule_ref,
            d0=d0,
            stocks=_terms(checkpoint.get("stocks")),
        )
    themes = _terms(checkpoint.get("themes"))
    if not themes:
        return _unverifiable(code, "themes（判断没关联任何板块 / 题材，无法对照规则实体）", rule_id=rule_id, d0=d0)
    codes, unmapped, missing = _map_themes(themes, entity_lookup)
    if missing:
        return _unverifiable(code, missing, rule_id=rule_id, rule_ref=fire.rule_ref, d0=d0, themes=themes)
    fired_here = [c for c in codes if c in fire.fired]
    evidence = {
        "rule_id": rule_id,
        "rule_ref": fire.rule_ref,
        "d0": d0,
        "d0_basis": basis,
        "entity_type": fire.entity_type,
        "codes": codes,
        "unmapped_themes": unmapped,
        "fired_here": fired_here,
        "fired_count": len(fire.fired),
        "label_version": fire.label_version,
    }
    if fired_here:
        return None
    return BiasFlag(
        code=code,
        severity=SEVERITY_WARN,
        reason=(
            f"偏离自己的规则：{fire.rule_ref} 在 D0={d0} 对 {codes} 未触发（当日事件集 {len(fire.fired)} 个实体）"
            "——你引用了这条规则，但按它今天并不该出这个判断"
        ),
        evidence=evidence,
    )


def check_revenge_reentry(
    checkpoint: dict[str, Any],
    *,
    checkpoints: list[dict[str, Any]],
    verdicts: list[dict[str, Any]],
    calendar: Sequence[str] | None,
) -> BiasFlag | None:
    code = "revenge_reentry"
    own_terms = _terms(checkpoint.get("themes")) + _terms(checkpoint.get("stocks"))
    own = {_norm(t) for t in own_terms}
    if not own:
        return _unverifiable(code, "themes / stocks（判断没关联任何标的）")
    ts = parse_ts(checkpoint.get("ts"))
    if ts is None:
        return _unverifiable(code, "ts（登记时刻缺失或不可解析）")
    cid = str(checkpoint.get("id") or "")
    known = _terminal_before(verdicts, ts)
    candidates: list[tuple[datetime, dict[str, Any], dict[str, Any], list[str]]] = []
    for c in checkpoints:
        if str(c.get("id") or "") == cid:
            continue
        c_ts = parse_ts(c.get("ts"))
        if c_ts is None or c_ts >= ts:
            continue
        other_terms = _terms(c.get("themes")) + _terms(c.get("stocks"))
        shared = [t for t in other_terms if _norm(t) in own]
        if not shared:
            continue
        v = known.get(str(c.get("id") or ""))
        if v is None:
            continue
        checked = parse_ts(v.get("checked_at"))
        if checked is not None:
            candidates.append((checked, c, v, shared))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    checked, prev, v, shared = candidates[-1]
    if v.get("verdict") != "miss":
        return None
    gap, cal_kind = days_between(calendar, local_date(checked), local_date(ts))
    if gap > REVENGE_WITHIN_DAYS:
        return None
    return BiasFlag(
        code=code,
        severity=SEVERITY_WARN,
        reason=(
            f"连错再登记：与本条共享 {shared} 的上一条判断 {prev.get('id')} 于 {local_date(checked)} 判为落空，"
            f"距本次登记 {gap} 个{'交易日' if cal_kind == CALENDAR_TRADING else '自然日'}——刚在这个标的上错过，再来一次前先问变量变了没有"
        ),
        evidence={
            "shared_terms": shared,
            "previous_id": prev.get("id"),
            "previous_claim": str(prev.get("claim") or "")[:60],
            "previous_checked_at": v.get("checked_at"),
            "gap_days": gap,
            "calendar": cal_kind,
            "thresholds": {"within_days": REVENGE_WITHIN_DAYS},
        },
    )


# --------------------------------------------------------------------------- #
# 总入口
# --------------------------------------------------------------------------- #
def scan(
    checkpoint: dict[str, Any],
    *,
    checkpoints: list[dict[str, Any]],
    verdicts: list[dict[str, Any]],
    label_lookup: LabelLookup | None,
    rule_fire_lookup: RuleFireLookup | None,
    entity_lookup: EntityLookup | None = None,
    calendar: Sequence[str] | None = None,
) -> list[BiasFlag]:
    """对一条判断跑完四条目录，返回 flag 列表（命中 + unverifiable；不适用的不出现）。

    任一条抛异常（库锁、规则文件损坏……）都折成该条的 ``*_unverifiable``，``evidence.missing`` 带异常文本——
    偏差扫描是提示层，永远不能让登记失败。
    """
    checks: list[tuple[str, Callable[[], BiasFlag | None]]] = [
        (
            "late_streak",
            lambda: check_late_streak(
                checkpoint, label_lookup=label_lookup, entity_lookup=entity_lookup, calendar=calendar
            ),
        ),
        (
            "post_miss_streak",
            lambda: check_post_miss_streak(checkpoint, checkpoints=checkpoints, verdicts=verdicts, calendar=calendar),
        ),
        (
            "rule_not_firing",
            lambda: check_rule_not_firing(
                checkpoint, rule_fire_lookup=rule_fire_lookup, entity_lookup=entity_lookup, calendar=calendar
            ),
        ),
        (
            "revenge_reentry",
            lambda: check_revenge_reentry(checkpoint, checkpoints=checkpoints, verdicts=verdicts, calendar=calendar),
        ),
    ]
    flags: list[BiasFlag] = []
    for code, fn in checks:
        try:
            flag = fn()
        except LookupUnavailable as exc:
            flag = _unverifiable(code, str(exc))
        except Exception as exc:  # noqa: BLE001 - 提示层：任何失败都只能是「判不了」，不能是「登记失败」
            flag = _unverifiable(code, f"扫描异常 {type(exc).__name__}: {exc}")
        if flag is not None:
            flags.append(flag)
    return flags


def classify(checkpoint: dict[str, Any], flags: Sequence[BiasFlag]) -> dict[str, str]:
    """每条目录项对这条判断的状态：``flagged`` / ``unverifiable`` / ``clean`` / ``not_applicable``。"""
    by_code = {f.code: f for f in flags}
    out: dict[str, str] = {}
    for code in BIAS_CODES:
        if code == "rule_not_firing" and not str(checkpoint.get("rule_id") or "").strip():
            out[code] = "not_applicable"
        elif code in by_code:
            out[code] = "flagged"
        elif f"{code}{UNVERIFIABLE_SUFFIX}" in by_code:
            out[code] = "unverifiable"
        else:
            out[code] = "clean"
    return out


def summarize(results: Sequence[tuple[dict[str, Any], Sequence[BiasFlag]]]) -> dict[str, Any]:
    """``bias-scan`` 的汇总：每条目录项四类计数 + 命中 id + unverifiable 原因分布。"""
    per_code: dict[str, dict[str, Any]] = {
        code: {
            "flagged": 0,
            "unverifiable": 0,
            "clean": 0,
            "not_applicable": 0,
            "flagged_ids": [],
            "unverifiable_reasons": Counter(),
        }
        for code in BIAS_CODES
    }
    for checkpoint, flags in results:
        status = classify(checkpoint, flags)
        for code, st in status.items():
            per_code[code][st] += 1
        for f in flags:
            if f.unverifiable:
                per_code[f.base_code]["unverifiable_reasons"][str(f.evidence.get("missing") or "")] += 1
            else:
                per_code[f.code]["flagged_ids"].append(str(checkpoint.get("id") or ""))
    for bucket in per_code.values():
        bucket["unverifiable_reasons"] = dict(bucket["unverifiable_reasons"].most_common())
    return {"scanned": len(results), "by_code": per_code}


def render_flag_lines(flags: Sequence[BiasFlag]) -> list[str]:
    """CLI 回显：warn 用 ⚠，unverifiable 用 ·。"""
    lines: list[str] = []
    for f in flags:
        mark = "⚠" if f.severity == SEVERITY_WARN else "·"
        lines.append(f"{mark} {f.code}：{f.reason}")
    return lines


# --------------------------------------------------------------------------- #
# 真库数据源（全部只读）。CLI 用；单测用上面的可注入 callable。
# --------------------------------------------------------------------------- #
def latest_rule_file(rules_dir: str | Path, rule_id: str) -> Path | None:
    """``<rules_dir>/<rule_id>.v<n>.json`` 里版本号最大的那份；没有 → None。"""
    base = Path(rules_dir).expanduser()
    if not base.is_dir():
        return None
    best: tuple[int, Path] | None = None
    for path in base.glob(f"{rule_id}.v*.json"):
        m = _RULE_FILE_RE.search(path.name)
        if not m:
            continue
        key = (int(m.group(1)), path)
        if best is None or key > best:
            best = key
    return best[1] if best else None


class LedgerDataSources:
    """把旁路库 / 主库 / 规则目录包成 ``scan`` 需要的三个 callable + 日历。全部 ``read_only=True``，用完 ``close()``。

    任一源打不开都不抛：对应 callable 置 None（→ 该条 unverifiable），原因记在 ``notes`` 里给 CLI 打印。
    """

    def __init__(
        self,
        *,
        labels_db: str | Path | None,
        market_db: str | Path | None,
        rules_dir: str | Path | None,
    ) -> None:
        import duckdb

        self.notes: list[str] = []
        self.labels_db = Path(labels_db).expanduser() if labels_db else None
        self.market_db = Path(market_db).expanduser() if market_db else None
        self.rules_dir = Path(rules_dir).expanduser() if rules_dir else None
        self._labels_con = None
        self._market_con = None
        self.calendar: list[str] | None = None
        self.label_version: str | None = None

        if self.labels_db is None or not self.labels_db.is_file():
            self.notes.append(f"旁路库不存在：{self.labels_db}（late_streak / rule_not_firing 为 unverifiable，其余按自然日）")
        else:
            try:
                self._labels_con = duckdb.connect(str(self.labels_db), read_only=True)
                rows = self._labels_con.execute("SELECT trade_date FROM history_calendar ORDER BY trade_date").fetchall()
                self.calendar = [str(r[0]) for r in rows] or None
                meta = self._labels_con.execute(
                    "SELECT label_version FROM history_build_meta WHERE build_kind = 'labels'"
                ).fetchone()
                self.label_version = str(meta[0]) if meta else None
            except duckdb.Error as exc:
                self.notes.append(f"旁路库打不开（{type(exc).__name__}）：{exc}")
                self._labels_con = None
                self.calendar = None
        if self.market_db is None or not self.market_db.is_file():
            self.notes.append(f"主库不存在：{self.market_db}（themes → sector_ts_code 映射不可用）")
        else:
            try:
                self._market_con = duckdb.connect(str(self.market_db), read_only=True)
            except duckdb.Error as exc:
                self.notes.append(f"主库只读打开失败（{type(exc).__name__}，可能被写进程独占）：{exc}")
                self._market_con = None
        if self.rules_dir is None or not self.rules_dir.is_dir():
            self.notes.append(f"规则目录不存在：{self.rules_dir}")

    def close(self) -> None:
        for con in (self._labels_con, self._market_con):
            if con is not None:
                try:
                    con.close()
                except Exception:  # noqa: BLE001 - 关连接失败没有可做的事
                    pass
        self._labels_con = self._market_con = None

    def __enter__(self) -> "LedgerDataSources":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def availability(self) -> dict[str, Any]:
        return {
            "labels_db": str(self.labels_db) if self.labels_db else None,
            "labels_db_ok": self._labels_con is not None,
            "calendar_days": len(self.calendar) if self.calendar else 0,
            "calendar_end": self.calendar[-1] if self.calendar else None,
            "label_version": self.label_version,
            "market_db": str(self.market_db) if self.market_db else None,
            "market_db_ok": self._market_con is not None,
            "rules_dir": str(self.rules_dir) if self.rules_dir else None,
            "rules_dir_ok": bool(self.rules_dir and self.rules_dir.is_dir()),
            "notes": list(self.notes),
        }

    # -- 三个 callable（属性形式：不可用时为 None，scan 会给出对应 unverifiable） -------------------- #
    @property
    def label_lookup(self) -> LabelLookup | None:
        if self._labels_con is None:
            return None

        def lookup(entity_type: str, entity_ids: Sequence[str], label: str, trade_dates: Sequence[str]):
            ids = [str(x) for x in entity_ids]
            days = [str(d) for d in trade_dates]
            if not ids or not days:
                return {}
            sql = (
                "SELECT entity_id, trade_date, value_num FROM history_labels "
                "WHERE entity_type = ? AND label = ? "
                f"AND entity_id IN ({', '.join('?' for _ in ids)}) "
                f"AND trade_date IN ({', '.join('?' for _ in days)})"
            )
            rows = self._labels_con.execute(sql, [entity_type, label, *ids, *days]).fetchall()
            return {(str(e), str(d)): (float(v) if v is not None else None) for e, d, v in rows}

        return lookup

    @property
    def entity_lookup(self) -> EntityLookup | None:
        if self._market_con is None:
            return None

        def lookup(themes: Sequence[str]):
            names = [str(t).strip() for t in themes if str(t).strip()]
            if not names:
                return {}
            placeholders = ", ".join("?" for _ in names)
            rows = self._market_con.execute(
                f"SELECT sector_name, sector_ts_code FROM dim_sector WHERE sector_name IN ({placeholders}) "
                "UNION ALL "
                f"SELECT theme, sector_ts_code FROM config_theme_sector_link WHERE theme IN ({placeholders})",
                [*names, *names],
            ).fetchall()
            out: dict[str, list[str]] = {n: [] for n in names}
            for name, code in rows:
                if name in out and code and str(code) not in out[name]:
                    out[name].append(str(code))
            return out

        return lookup

    @property
    def rule_fire_lookup(self) -> RuleFireLookup | None:
        if self._labels_con is None or self.rules_dir is None or not self.rules_dir.is_dir():
            return None

        def lookup(rule_id: str, trade_date: str) -> RuleFire | None:
            from intelligence.services.methodology_backtest.compiler import compile_rule
            from intelligence.services.methodology_backtest.rules import load_rule

            path = latest_rule_file(self.rules_dir, rule_id)
            if path is None:
                raise LookupUnavailable(f"规则文件 {self.rules_dir}/{rule_id}.v*.json（不存在）")
            rule = load_rule(path)
            # runner.execute_compiled 只保留 12 条样例，这里要的是完整事件集，直接跑同一份编译出的事件查询。
            compiled = compile_rule(rule, start=trade_date, end=trade_date)
            rows = self._labels_con.execute(compiled.events.sql, list(compiled.events.params)).fetchall()
            return RuleFire(
                rule_ref=rule.ref,
                entity_type=rule.entity_type,
                trade_date=trade_date,
                fired=frozenset(str(r[0]) for r in rows),
                label_version=self.label_version,
            )

        return lookup
