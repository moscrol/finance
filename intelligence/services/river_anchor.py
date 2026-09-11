"""事件锚点回溯（工单 #35 / 09-06 spec §4.6）：``slice`` + ``window`` 的组合，不另写第三套。

    anchor_windows(anchor_label, before, after | until, knowledge_cutoff, entity, ...)
      → list[AnchorRecord]

每个锚点日一条记录：

- ``context``：``slice(anchor_as_of, C)``——锚点那天的世界
- ``forward``：``window(anchor_as_of, forward_end, C)``——前瞻区间派生
- ``lookback``：对 forward 里命中的实体，``window(emerge−m, emerge, C)``（v0 只做定长前瞻，
  lookback 留给事件到事件模式；本刀返回空列表占位）
- ``pit_grade``：各段取最差
- ``gaps``：任一段所需轨 / 标签缺失 → 整条 unverifiable

硬规矩（§4.6）：

1. ``anchor_label`` 必须 ∈ ``ALL_LABELS`` 或已注册派生规则，否则 ``ValueError``
2. ``knowledge_cutoff`` 至少是 ``forward_end``；回放时不得晚于此
3. 输出只报事实，N < 10 写样本不足——本模块不报「下次也会这样」
4. ``windows_around`` / ``cohort_compare`` 是原型，契约把三段合成一条记录

第一个消费方：``teaching_framework.leader_succession``——把锚点日的 river 切片挂进
``context_break`` / ``context_birth``，教学标签字段原样保留（handoff 读数逐字节不变）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from intelligence.services.methodology_backtest.labels import ALL_LABELS
from intelligence.services.river import RiverSlice, slice_river
from intelligence.services.river_derive import LabelNotSliceEvaluable, bind
from intelligence.services.river_window_contract import RiverWindow, window


@dataclass(frozen=True)
class AnchorRecord:
    anchor_as_of: str
    entity_id: str
    entity_name: str
    knowledge_cutoff: str
    context: RiverSlice
    forward: RiverWindow
    lookback: tuple[RiverWindow, ...] = ()
    context_target: RiverSlice | None = None
    gaps: tuple[str, ...] = ()
    status: str = "ok"  # ok | unverifiable | open

    @property
    def pit_grade(self) -> str:
        grades = [self.context.pit_grade, self.forward.pit_grade]
        if self.context_target is not None:
            grades.append(self.context_target.pit_grade)
        grades.extend(w.pit_grade for w in self.lookback)
        if self.context.hindsight or self.forward.hindsight:
            return "trade_date_only"
        return "strict" if all(g == "strict" for g in grades) else "trade_date_only"

    def to_dict(self) -> dict[str, Any]:
        return {
            "anchor_as_of": self.anchor_as_of,
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "knowledge_cutoff": self.knowledge_cutoff,
            "pit_grade": self.pit_grade,
            "status": self.status,
            "gaps": list(self.gaps),
            "context": self.context.to_dict(),
            "forward": self.forward.to_dict(),
            "lookback": [w.to_dict() for w in self.lookback],
            "context_target": self.context_target.to_dict() if self.context_target else None,
        }


def _trading_days_before(days: list[str], anchor: str, n: int) -> str | None:
    """锚点前第 n 个交易日；不够则 None。"""
    if anchor not in days:
        return None
    i = days.index(anchor)
    return days[i - n] if i >= n else None


def _trading_days_after(days: list[str], anchor: str, n: int) -> str | None:
    if anchor not in days:
        return None
    i = days.index(anchor)
    return days[i + n] if i + n < len(days) else None


def _calendar(db_path: str | Path | None) -> list[str]:
    import duckdb
    import os
    from intelligence.services.river import DEFAULT_DB

    db = Path(db_path or os.environ.get("MARKET_FEATURE_STORE_DB", DEFAULT_DB)).expanduser()
    con = duckdb.connect(str(db), read_only=True)
    try:
        rows = con.execute(
            "SELECT DISTINCT CAST(trade_date AS DATE) d FROM fact_market_daily ORDER BY d"
        ).fetchall()
        return [str(r[0]) for r in rows]
    finally:
        con.close()


def find_anchor_days(
    entity: str,
    label: str,
    *,
    start: str | None = None,
    end: str | None = None,
    knowledge_cutoff: str,
    db_path: str | Path | None = None,
    checkpoints_path: str | Path | None = None,
) -> list[str]:
    """在 ``[start, end]``（默认全历史到 cutoff）里找 ``label`` 为真的交易日。

    标签必须能在单日切片上判定（``SLICE_EVALUABLE_LABELS``）；否则抛 ``LabelNotSliceEvaluable``。
    """
    if label not in ALL_LABELS:
        raise ValueError(f"anchor_label={label!r} 不是注册标签（ALL_LABELS）")
    days = _calendar(db_path)
    if not days:
        return []
    lo = start or days[0]
    hi = end or knowledge_cutoff
    out: list[str] = []
    for day in days:
        if day < lo or day > hi or day > knowledge_cutoff:
            continue
        sl = slice_river(day, entity, knowledge_cutoff=knowledge_cutoff, db_path=db_path, checkpoints_path=checkpoints_path)
        try:
            value, _ = bind(label, sl)
        except LabelNotSliceEvaluable:
            raise
        if value is True:
            out.append(day)
    return out


def anchor_windows(
    entity: str,
    anchor_label: str,
    *,
    before: int = 0,
    after: int = 5,
    until_label: str | None = None,
    knowledge_cutoff: str,
    anchors: list[str] | None = None,
    db_path: str | Path | None = None,
    checkpoints_path: str | Path | None = None,
) -> list[AnchorRecord]:
    """锚点日 → 上下文切片 + 前瞻窗。定长 ``after`` 与事件到事件 ``until_label`` 二选一。

    ``anchors`` 非空时跳过扫描，直接用给定锚点日（消费方已有断板日列表时用）。
    """
    if until_label is not None and after != 5:
        # after 默认值被显式改过同时又给了 until——语义冲突，拒绝猜。
        raise ValueError("until_label 与显式 after 不能同时用：事件到事件模式的前瞻窗长度由目标事件决定")
    if anchor_label not in ALL_LABELS:
        raise ValueError(f"anchor_label={anchor_label!r} 不是注册标签（ALL_LABELS）")
    if until_label is not None and until_label not in ALL_LABELS:
        raise ValueError(f"until_label={until_label!r} 不是注册标签（ALL_LABELS）")

    days = _calendar(db_path)
    if anchors is None:
        anchors = find_anchor_days(
            entity, anchor_label, knowledge_cutoff=knowledge_cutoff, db_path=db_path, checkpoints_path=checkpoints_path
        )

    records: list[AnchorRecord] = []
    for anchor in anchors:
        if anchor > knowledge_cutoff:
            continue
        gaps: list[str] = []
        context = slice_river(
            anchor, entity, knowledge_cutoff=knowledge_cutoff, db_path=db_path, checkpoints_path=checkpoints_path
        )

        forward_end: str | None
        status = "ok"
        context_target: RiverSlice | None = None
        if until_label is not None:
            # 事件到事件：从锚点次日往后找目标标签首次为真的日子。
            forward_end = None
            for day in days:
                if day <= anchor or day > knowledge_cutoff:
                    continue
                sl = slice_river(day, entity, knowledge_cutoff=knowledge_cutoff, db_path=db_path, checkpoints_path=checkpoints_path)
                try:
                    value, _ = bind(until_label, sl)
                except LabelNotSliceEvaluable:
                    raise
                if value is True:
                    forward_end = day
                    context_target = sl
                    break
            if forward_end is None:
                status = "open"  # 历史尾部没有目标事件，不进 N
                records.append(
                    AnchorRecord(
                        anchor_as_of=anchor,
                        entity_id=context.entity_id,
                        entity_name=context.entity_name,
                        knowledge_cutoff=knowledge_cutoff,
                        context=context,
                        forward=window(anchor, anchor, entity, knowledge_cutoff=knowledge_cutoff, with_cumulative=False, db_path=db_path, checkpoints_path=checkpoints_path),
                        gaps=("until_label not observed by knowledge_cutoff",),
                        status=status,
                    )
                )
                continue
        else:
            forward_end = _trading_days_after(days, anchor, after)
            if forward_end is None:
                status = "open"
                gaps.append(f"not enough trading days after anchor for after={after}")
                forward_end = knowledge_cutoff if knowledge_cutoff >= anchor else anchor

        if forward_end > knowledge_cutoff:
            raise ValueError(
                f"forward_end={forward_end} 晚于 knowledge_cutoff={knowledge_cutoff}："
                "前瞻窗没走完就没有这条记录（§4.6 硬规矩 2）"
            )

        fwd = window(
            anchor,
            forward_end,
            entity,
            knowledge_cutoff=knowledge_cutoff,
            db_path=db_path,
            checkpoints_path=checkpoints_path,
        )
        # v0 lookback：定长模式下对锚点本身做 before 窗（若 before>0）；事件到事件模式留给后续。
        lookbacks: list[RiverWindow] = []
        if before > 0 and until_label is None:
            look_start = _trading_days_before(days, anchor, before)
            if look_start is None:
                gaps.append(f"not enough trading days before anchor for before={before}")
            else:
                lookbacks.append(
                    window(look_start, anchor, entity, knowledge_cutoff=knowledge_cutoff, db_path=db_path, checkpoints_path=checkpoints_path)
                )

        if status == "ok" and gaps:
            status = "unverifiable"
        records.append(
            AnchorRecord(
                anchor_as_of=anchor,
                entity_id=context.entity_id,
                entity_name=context.entity_name,
                knowledge_cutoff=knowledge_cutoff,
                context=context,
                forward=fwd,
                lookback=tuple(lookbacks),
                context_target=context_target,
                gaps=tuple(gaps),
                status=status,
            )
        )
    return records


def river_context_dict(sl: RiverSlice) -> dict[str, Any]:
    """把一片河切片折成可挂进 ``context_break`` / ``context_birth`` 的字典。

    只搬事实：as_of / pit_grade / 各轨对象摘要。教学标签（stage_coarse 等）不在这里——
    那些仍由 ``_read_context(labels_db)`` 提供，本函数**合并进去**而不是替换。
    """
    from intelligence.services.river import Gap

    tracks: dict[str, Any] = {}
    for name, result in sl.tracks.items():
        if isinstance(result, Gap):
            tracks[name] = {"gap": True, "reason": result.reason, "detail": result.detail}
        else:
            tracks[name] = [
                {"object_type": o.object_type, "ref": o.ref, "source_hash": o.source_hash} for o in result
            ]
    return {
        "anchor_as_of": sl.as_of,
        "knowledge_cutoff": sl.knowledge_cutoff,
        "pit_grade": sl.pit_grade,
        "entity_id": sl.entity_id,
        "entity_name": sl.entity_name,
        "river_tracks": tracks,
        "source": "river.slice",
    }
