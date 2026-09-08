"""区间契约 ``river.window``（工单 #35 / roadmap G-02c；契约正文 09-06 统一 spec §4.4）。

单点切片 ``river.slice_river(T, C)`` 回答「这一天是什么」；**区间**回答「这一段怎么走过来的」。
两者同级、同一套时钟，联立不降级——区间不是把每条轨压成一个数再求均值，而是**保留对象身份的
切片序列**加上**可拆回到天与行的派生对象**（派生见 ``river_derive``）。

    window(start, end, entity, knowledge_cutoff=C, ...) -> RiverWindow
      start / end          按交易日历（fact_market_daily 有行的日子），不按自然日
      knowledge_cutoff     整段一个 C；默认 C = end；C > end → hindsight=true；C < end → ValueError
      slices[]             [start, end] 内每个交易日一片 RiverSlice，各自带 pit_grade
      derived[]            区间派生对象（validity_kind=range）；本模块只挂 cumulative（包 range_aggregate）
      coverage{track: 有对象天数 / 区间天数}
      pit_grade            = min(slices.pit_grade)：任一天 trade_date_only 整段 trade_date_only
      hindsight / alias_applied   任一天为真整段为真

**每一片必须与 ``slice_river(day, C)`` 逐字节相同**（``to_dict()`` 比）。允许 provider 日后加按区间批量取数的
快路径，但快路径的正确性靠这条断言守，不靠信任——``window()`` 今天就是逐日调 ``slice_river``。

为什么 C 对整段只有一个：区间读数要回答「站在 C 那天回看这段路」。若每天各用自己那天当 cutoff，
就成了「每天只知道当天」的拼接——那是回放里的另一种问法（逐日重放），不是区间。

⚠ 模块名不叫 ``river/window.py``：``intelligence/services/river.py`` 是模块，同名目录会把它遮掉。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from intelligence.services import river_query
from intelligence.services.river import (
    DEFAULT_DB,
    TRACKS,
    Gap,
    PitGrade,
    RiverObject,
    RiverSlice,
    slice_river,
)

DERIVATION_RULE_CUMULATIVE = {"name": "range_aggregate", "version": "v1"}


@dataclass(frozen=True)
class RiverWindow:
    start: str
    end: str
    entity_id: str
    entity_name: str
    knowledge_cutoff: str
    slices: tuple[RiverSlice, ...]
    derived: tuple[RiverObject, ...] = ()
    hindsight: bool = False

    @property
    def days(self) -> tuple[str, ...]:
        return tuple(s.as_of for s in self.slices)

    @property
    def pit_grade(self) -> PitGrade:
        """任一天降档整段降档（污点传播：一个事后才知道的数就够污染一段读数）。空区间 fail closed。"""
        if self.hindsight or not self.slices:
            return "trade_date_only"
        return "strict" if all(s.pit_grade == "strict" for s in self.slices) else "trade_date_only"

    @property
    def alias_applied(self) -> bool:
        return any(s.alias_applied for s in self.slices)

    @property
    def coverage(self) -> dict[str, dict[str, int]]:
        """每轨「有对象的天数 / 区间天数」。gap 与空列表都算没有。"""
        total = len(self.slices)
        out: dict[str, dict[str, int]] = {}
        for track in TRACKS:
            n = sum(
                1
                for s in self.slices
                if isinstance(s.tracks.get(track), list) and s.tracks.get(track)
            )
            out[track] = {"days_with_objects": n, "days": total}
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "knowledge_cutoff": self.knowledge_cutoff,
            "pit_grade": self.pit_grade,
            "hindsight": self.hindsight,
            "alias_applied": self.alias_applied,
            "coverage": self.coverage,
            "days": list(self.days),
            "slices": [s.to_dict() for s in self.slices],
            "derived": [o.to_dict() for o in self.derived],
        }


def _resolve_days(start: str, end: str, db: Path) -> list[str]:
    import duckdb

    con = duckdb.connect(str(db), read_only=True)
    try:
        return river_query.trading_days(con, start, end)
    finally:
        con.close()


def cumulative_object(agg: river_query.RangeAggregate, *, entity_id: str, start: str, end: str, member_refs: list[str], pit_grade: str) -> RiverObject:
    """把 ``range_aggregate`` 的结果装成 ``cumulative`` 类派生对象——纳入而不重写（§4.4 原文）。

    覆盖不完整 → 对象标 ``unverifiable`` 且**不给数**；``gap_policy=skip`` 是 range_aggregate 的既有语义
    （跳过缺天并在 coverage 里如实报），这里原样带出来，不换策略。
    """
    data = agg.to_dict()
    payload: dict[str, Any] = {
        "derivation_rule": DERIVATION_RULE_CUMULATIVE,
        "gap_policy": "skip",
        "method": data.get("method"),
        "coverage": data.get("coverage"),
        "codes_seen": data.get("codes_seen"),
        "caveats": data.get("caveats"),
        "pit_grade": pit_grade,
        "member_refs": member_refs,
    }
    if agg.trustworthy:
        payload["values"] = data.get("values")
        payload["peak_date"] = data.get("peak_date")
        payload["status"] = "ok"
    else:
        # 不给数：偏低但不知道偏多少的累计量比没有更坏（range_aggregate 模块注释原话）。
        payload["status"] = "unverifiable"
        payload["gaps_applied"] = list(data.get("caveats") or []) + [f"missing_dates={data.get('coverage', {}).get('missing_dates')}"]
    return RiverObject(
        track="market",
        entity_id=entity_id,
        object_type="cumulative",
        ref=f"range_aggregate:{entity_id}:{start}:{end}",
        source_hash=_hash({"start": start, "end": end, "entity": entity_id, "values": payload.get("values"), "status": payload["status"]}),
        valid_from=start,
        valid_to=end,
        recorded_at=None,
        payload=payload,
        validity_kind="range",
        derivation="deterministic",
    )


def _hash(payload: Any) -> str:
    import hashlib
    import json

    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:16]


def window(
    start: str,
    end: str,
    entity: str,
    *,
    knowledge_cutoff: str | None = None,
    require_strict: bool = False,
    allow_hindsight: bool = False,
    with_cumulative: bool = True,
    db_path: str | Path | None = None,
    checkpoints_path: str | Path | None = None,
) -> RiverWindow:
    """``[start, end]`` 上 ``entity`` 的区间：切片序列 + cumulative 派生对象。

    ``knowledge_cutoff`` 缺省 = ``end``。``C < end`` 直接拒绝：区间没走完就没有这段区间。
    ``C > end`` 是事后视角，必须 ``allow_hindsight=True``，整段 ``hindsight=True`` 且 ``pit_grade`` 永远不是 strict。
    """
    if start > end:
        raise ValueError(f"start={start!r} 晚于 end={end!r}")
    cutoff = knowledge_cutoff or end
    if cutoff < end:
        raise ValueError(
            f"knowledge_cutoff={cutoff!r} 早于 end={end!r}：区间没走完就没有这段区间。要看「截至 C 的那一段」，把 end 改成 C。"
        )
    hindsight = cutoff > end
    if hindsight and not allow_hindsight:
        raise ValueError(
            f"knowledge_cutoff={cutoff!r} 晚于 end={end!r}：那是事后视角。人工复核确需如此就显式传 allow_hindsight=True"
            "（整段 pit_grade 永远不是 strict，且不得进入校准与方法有效性统计）。"
        )
    if hindsight and require_strict:
        raise ValueError("allow_hindsight 与 require_strict 互斥")

    db = Path(db_path or os.environ.get("MARKET_FEATURE_STORE_DB", DEFAULT_DB)).expanduser()
    if not db.exists():
        raise FileNotFoundError(f"数据库不存在：{db}（不自动创建）")
    days = _resolve_days(start, end, db)

    slices: list[RiverSlice] = []
    for day in days:
        # 区间里每一天都用同一个 C 读。对 day < end 的天，C > day 在单点语义里叫 hindsight，
        # 但在区间语义里它就是「站在 C 回看」——所以 allow_hindsight=True 取片，再把 hindsight 标记
        # 改成**区间级**的（C > end 才算）。pit_grade 仍按 recorded_at ≤ C 逐对象判，不受这个标记影响。
        sl = slice_river(
            day,
            entity,
            knowledge_cutoff=cutoff,
            require_strict=require_strict,
            allow_hindsight=True,
            db_path=db,
            checkpoints_path=checkpoints_path,
        )
        slices.append(replace(sl, hindsight=hindsight))

    entity_id = slices[0].entity_id if slices else entity
    entity_name = slices[0].entity_name if slices else entity
    derived: list[RiverObject] = []
    if with_cumulative and slices:
        # 只有实体解析成功（任一天任一轨不是 entity_unresolved）才有累计量可算。
        unresolved = all(
            all(isinstance(v, Gap) and v.reason == "entity_unresolved" for v in s.tracks.values()) for s in slices
        )
        if not unresolved:
            try:
                agg = river_query.range_aggregate(
                    start, end, entity, db_path=db, require_complete=True, knowledge_cutoff=cutoff
                )
            except Exception as exc:  # 累计量算不出来 → 缺口对象，不让整段区间报错
                derived.append(
                    RiverObject(
                        track="market",
                        entity_id=entity_id,
                        object_type="cumulative",
                        ref=f"range_aggregate:{entity_id}:{start}:{end}",
                        source_hash=_hash({"error": type(exc).__name__}),
                        valid_from=start,
                        valid_to=end,
                        recorded_at=None,
                        payload={
                            "derivation_rule": DERIVATION_RULE_CUMULATIVE,
                            "status": "unverifiable",
                            "gaps_applied": [f"{type(exc).__name__}: {exc}"[:200]],
                            "pit_grade": "trade_date_only",
                        },
                        validity_kind="range",
                    )
                )
            else:
                member_refs = [
                    o.ref
                    for s in slices
                    for o in (s.tracks.get("market") if isinstance(s.tracks.get("market"), list) else [])
                ]
                pit = "strict" if all(s.pit_grade == "strict" for s in slices) and not hindsight else "trade_date_only"
                derived.append(
                    cumulative_object(agg, entity_id=entity_id, start=start, end=end, member_refs=member_refs, pit_grade=pit)
                )

    return RiverWindow(
        start=start,
        end=end,
        entity_id=entity_id,
        entity_name=entity_name,
        knowledge_cutoff=cutoff,
        slices=tuple(slices),
        derived=tuple(derived),
        hindsight=hindsight,
    )


def render(win: RiverWindow) -> str:
    lines = [
        f"window {win.start} → {win.end}  entity={win.entity_id} {win.entity_name}  cutoff={win.knowledge_cutoff}"
        f"  pit_grade={win.pit_grade}  days={len(win.slices)}"
        + ("  ⚠ hindsight=true" if win.hindsight else "")
        + ("  alias_applied" if win.alias_applied else ""),
        "",
        "  覆盖（有对象天数 / 区间天数）：",
    ]
    for track, c in win.coverage.items():
        lines.append(f"    {track:<9} {c['days_with_objects']:>3} / {c['days']}")
    lines += ["", "  逐日 pit_grade："]
    for s in win.slices:
        lines.append(f"    {s.as_of}  {s.pit_grade}")
    lines += ["", f"  派生对象 {len(win.derived)} 条："]
    for o in win.derived:
        lines.append(f"    {o.object_type:<12} {o.payload.get('status')}  ref={o.ref}")
    return "\n".join(lines)


# 供 river_derive 复用：区间的一天里某轨对象
def track_objects(sl: RiverSlice, track: str) -> list[RiverObject]:
    v = sl.tracks.get(track)  # type: ignore[arg-type]
    return list(v) if isinstance(v, list) else []


__all__ = ["RiverWindow", "window", "render", "cumulative_object", "track_objects"]
