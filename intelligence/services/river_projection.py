"""上下文投影（工单 #34 / roadmap G-14；契约见 09-06 统一 spec §4.5）。

从一片 as-of 河切片到「读者 / 模型看到的那几段」，中间今天是写死的截断：``guided_reading``
每个对象取字母序前 6 个 payload 键、个股节点折成一行、轨按字母序排——确定，但**没有一层
可哈希的「看到了什么」**。本模块把这一层做成纯函数：

    project(source, framework_version=..., task=..., budget=...) -> ContextProjection

- **选了什么**：有序 ``blocks``，每块是 ``(track, object_type, derivation)`` 下的一组对象 ref；
- **按什么选**：每块带 ``selected_by``（框架规则号 | ``default``）；
- **省了什么**：``omitted{track: count}`` + ``omitted_refs``——按块整体省略，**不在对象中间截断**；
- **边界条件**：``limits`` / ``gaps`` 是强制块，永远进上下文且排在事实块之前；
- **哈希**：``projection_hash = hash(有序 blocks 的 refs + framework_version + projection_version
  + budget + source_ref)``（§4.5 原文）；``rendered_text`` **不进哈希**——文案改了哈希不变，
  同一对象被重发布改了数值（``source_hash`` 变）哈希才变。

默认序（框架无规则时，§4.5 原文）：轨按 ``river.TRACKS``；轨内 硬度降序 → ``recorded_at`` 升序
→ ``ref`` 字典序；``frozen_llm`` 派生的对象排在同轨 ``deterministic`` 之后。

**不落库、不缓存**（终局 §9 / F4）：投影由 ``(source_ref, framework_version, task, budget,
projection_version, label_version)`` 重算，哈希是回放钥匙不是存储键。

本模块**不写任何授课框架判读规则**：``SelectionRule`` 只是协议，这里只有 ``DefaultRule``
（个股级对象折叠成计数块，其余全选）与测试用 ``TopNRule``。G-01 母本落地后框架规则接在
``rules=`` 上，块上 ``selected_by`` 就会从 ``default`` 变成规则号。

⚠ 与 ``episode_projection.project_durable_events`` 同名不同物：那是运行底座的 **durable 事件
投影**（episode 事件 → workbench trace），本模块是 **上下文投影**（河切片 → 读者上下文）。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Protocol

from intelligence.services import compliance_gate
from intelligence.services.methodology_backtest.labels import LABEL_VERSION
from intelligence.services.river import TRACKS

PROJECTION_VERSION = "cp-v0"
HASH_PREFIX = "cp:"
SELECTED_BY_DEFAULT = "default"

# 每个对象在 rendered_text 里最多摊开几个 payload 键——这是**渲染**上限，不是选择：
# 被省的键只影响文案，投影里对象是整条在的，哈希不变。
RENDER_KEYS = 6

# 硬度：payload 里可选的 ``hardness``（L1–L4，数字越大越硬；``frozen_llm`` 封顶 L1）。
# v0 的 RiverObject 没有这个字段，所以今天全部平局、落到 recorded_at 与 ref 上。
_HARDNESS_RANK = {"L4": 4, "L3": 3, "L2": 2, "L1": 1}
DERIVATION_DETERMINISTIC = "deterministic"
DERIVATION_FROZEN_LLM = "frozen_llm"


# --------------------------------------------------------------------------- #
# 对象
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ProjectedBlock:
    track: str
    object_type: str
    object_refs: tuple[tuple[str, str], ...]  # (ref, source_hash)，有序
    hardness: str  # 块内最高硬度；无 → "n/a"
    derivation: str  # deterministic | frozen_llm
    selected_by: str  # "default" | "framework:<framework_version>:<rule_id>"
    rendered_text: str  # 消费方渲染用；不进哈希
    kind: str = "facts"  # facts | collapsed（个股级对象只出计数，不出名单）
    collapsed_count: int = 0

    def hashed_dict(self) -> dict[str, Any]:
        return {
            "track": self.track,
            "object_type": self.object_type,
            "object_refs": [list(x) for x in self.object_refs],
            "hardness": self.hardness,
            "derivation": self.derivation,
            "selected_by": self.selected_by,
            "kind": self.kind,
            "collapsed_count": self.collapsed_count,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.hashed_dict(), "rendered_text": self.rendered_text}


@dataclass(frozen=True)
class ContextProjection:
    projection_version: str
    framework_version: str | None
    task: str
    source_ref: dict[str, Any]
    blocks: tuple[ProjectedBlock, ...]
    omitted: dict[str, int]
    omitted_refs: dict[str, tuple[str, ...]]
    limits: tuple[str, ...]
    gaps: tuple[str, ...]
    budget: dict[str, Any]
    label_version: str = LABEL_VERSION

    # 四块强制存在（§4.5：省略要可见、gap 与 limits 不可省略、预算要报）。
    # dataclass 字段本身保证「在」，这里守的是「不是 None」——None 是「没填」不是「空」。
    _REQUIRED = ("omitted", "omitted_refs", "limits", "gaps", "budget")

    def canonical_json(self) -> str:
        for name in self._REQUIRED:
            if getattr(self, name) is None:
                raise ValueError(f"ContextProjection.{name} 不能为 None：强制块可以为空，不可缺席")
        body = {
            "projection_version": self.projection_version,
            "framework_version": self.framework_version,
            "task": self.task,
            "source_ref": self.source_ref,
            "blocks": [b.hashed_dict() for b in self.blocks],
            "omitted": self.omitted,
            "omitted_refs": {k: list(v) for k, v in self.omitted_refs.items()},
            "limits": list(self.limits),
            "gaps": list(self.gaps),
            "budget": self.budget,
            "label_version": self.label_version,
        }
        return json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

    @property
    def projection_hash(self) -> str:
        return HASH_PREFIX + hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()[:16]

    @property
    def selected_refs(self) -> tuple[str, ...]:
        """进了上下文的对象 ref（含折叠块里的），有序去重。"""
        out: list[str] = []
        for b in self.blocks:
            for ref, _ in b.object_refs:
                if ref not in out:
                    out.append(ref)
        return tuple(out)

    def to_dict(self) -> dict[str, Any]:
        return {
            "projection_hash": self.projection_hash,
            "projection_version": self.projection_version,
            "framework_version": self.framework_version,
            "task": self.task,
            "source_ref": self.source_ref,
            "blocks": [b.to_dict() for b in self.blocks],
            "omitted": self.omitted,
            "omitted_refs": {k: list(v) for k, v in self.omitted_refs.items()},
            "limits": list(self.limits),
            "gaps": list(self.gaps),
            "budget": self.budget,
            "label_version": self.label_version,
        }


# --------------------------------------------------------------------------- #
# 选择规则协议
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Selection:
    selected: tuple[dict[str, Any], ...]
    collapsed: tuple[dict[str, Any], ...]
    omitted: tuple[dict[str, Any], ...]
    selected_by: str


class SelectionRule(Protocol):
    """一条轨的对象 → (选中, 折叠, 省略, 规则号)。实现必须是纯函数。"""

    def select(self, track: str, objects: list[dict[str, Any]], budget_left: int | None) -> Selection: ...


def is_stock_node(obj: dict[str, Any]) -> bool:
    """「一只个股的一条记录」按对象形状判，不按轨名（题材轨也发个股涨停节点）。"""
    payload = obj.get("payload") or {}
    return bool(payload.get("stock_ts_code")) or compliance_gate.is_stock_entity(str(obj.get("ref") or ""))


class DefaultRule:
    """框架无规则时的默认：个股级对象折叠成计数块，其余全选；预算不够按块整体省略。"""

    def select(self, track: str, objects: list[dict[str, Any]], budget_left: int | None) -> Selection:
        stock = [o for o in objects if is_stock_node(o)]
        rest = [o for o in objects if not is_stock_node(o)]
        return Selection(selected=tuple(rest), collapsed=tuple(stock), omitted=(), selected_by=SELECTED_BY_DEFAULT)


class TopNRule:
    """测试用：每轨只留默认序前 N 条非个股对象，其余进 omitted。"""

    def __init__(self, n: int, *, rule_id: str = "top_n") -> None:
        self.n = int(n)
        self.rule_id = rule_id

    def select(self, track: str, objects: list[dict[str, Any]], budget_left: int | None) -> Selection:
        stock = [o for o in objects if is_stock_node(o)]
        rest = [o for o in objects if not is_stock_node(o)]
        return Selection(
            selected=tuple(rest[: self.n]),
            collapsed=tuple(stock),
            omitted=tuple(rest[self.n :]),
            selected_by=f"framework:test:{self.rule_id}",
        )


# --------------------------------------------------------------------------- #
# 默认序
# --------------------------------------------------------------------------- #
def hardness_of(obj: dict[str, Any]) -> str:
    h = str((obj.get("payload") or {}).get("hardness") or obj.get("hardness") or "").strip()
    return h if h in _HARDNESS_RANK else "n/a"


def derivation_of(obj: dict[str, Any]) -> str:
    d = str((obj.get("payload") or {}).get("derivation") or obj.get("derivation") or "").strip()
    return DERIVATION_FROZEN_LLM if d == DERIVATION_FROZEN_LLM else DERIVATION_DETERMINISTIC


def default_sort_key(obj: dict[str, Any]) -> tuple[Any, ...]:
    """硬度降序 → recorded_at 升序（None 最后）→ ref 字典序。§4.5 原文，不是字母序。"""
    rec = obj.get("recorded_at")
    return (
        -_HARDNESS_RANK.get(hardness_of(obj), 0),
        1 if rec is None else 0,
        str(rec or ""),
        str(obj.get("ref") or ""),
    )


def _max_hardness(objs: list[dict[str, Any]]) -> str:
    ranked = sorted((hardness_of(o) for o in objs), key=lambda h: -_HARDNESS_RANK.get(h, 0))
    return ranked[0] if ranked else "n/a"


# --------------------------------------------------------------------------- #
# 渲染（不进哈希）
# --------------------------------------------------------------------------- #
def render_object(obj: dict[str, Any], *, keys: int | None = None) -> str:
    """一条对象一行：object_type｜前 N 键（provider 序，不是字母序）｜ref｜hash［另有 M 键］。"""
    payload = obj.get("payload") or {}
    present = [k for k in payload if payload[k] is not None]
    shown = present[: (RENDER_KEYS if keys is None else keys)]
    body = "，".join(f"{k}={payload[k]}" for k in shown)
    more = len(present) - len(shown)
    tail = f"｜另有 {more} 键未显示（投影已含）" if more > 0 else ""
    return f"{obj.get('object_type')}｜{body}｜ref={obj.get('ref')}｜hash={obj.get('source_hash')}{tail}"


def render_collapsed(objs: list[dict[str, Any]]) -> str:
    """个股级对象只出**计数与标签**，不出名单（带读是小白产品面，名单就是推荐）。"""
    labels: dict[str, int] = {}
    for obj in objs:
        payload = obj.get("payload") or {}
        for key in ("high_status_label", "limit_status", "up_stat"):
            label = str(payload.get(key) or "").strip()
            if label:
                labels[label] = labels.get(label, 0) + 1
    tail = "，".join(f"{k}×{v}" for k, v in sorted(labels.items())) or "无特征标签"
    return f"个股级节点 {len(objs)} 条（{tail}）；明细见 river 切片，带读不出名单"


# --------------------------------------------------------------------------- #
# 限制与缺口（从切片自己读，不靠调用方转述）
# --------------------------------------------------------------------------- #
def limits_of(source: dict[str, Any], *, present_tracks: list[str]) -> tuple[str, ...]:
    pit_grade = str(source.get("pit_grade") or "trade_date_only")
    limits: list[str] = []
    if source.get("hindsight"):
        limits.append(
            "hindsight=true：本片的 knowledge_cutoff 晚于 as_of，看得见后来才被记录的对象。"
            "只可人工复核；由它派生的观察剧本不会进入方法校准"
        )
    if pit_grade != "strict":
        limits.append(
            f"pit_grade={pit_grade}：切片里有对象缺 recorded_at，可用于当日带读，但不能进回放与方法校准"
        )
    if source.get("alias_applied"):
        limits.append("alias_applied=true：实体身份跨供应商归一过，跨换源日的数值不可直接比较")
    if not present_tracks:
        limits.append("六轨全缺：本日无可读对象，带读只报缺口")
    return tuple(limits)


def gaps_of(tracks: dict[str, Any]) -> tuple[str, ...]:
    """按 ``TRACKS`` 序列出缺轨；空列表也是缺口，不当作「没变化」。"""
    gaps: list[str] = []
    for track in TRACKS:
        if track not in tracks:
            continue
        value = tracks[track]
        if isinstance(value, dict) and value.get("gap"):
            detail = str(value.get("detail") or "").strip()
            gaps.append(f"{track}：{value.get('reason')}" + (f"（{detail}）" if detail else ""))
        elif not value:
            gaps.append(f"{track}：empty（读取面返回空列表，按缺口处理，不当作「没变化」）")
    return tuple(gaps)


def present_tracks_of(tracks: dict[str, Any]) -> list[str]:
    return [t for t in TRACKS if isinstance(tracks.get(t), list) and tracks[t]]


# --------------------------------------------------------------------------- #
# 主函数
# --------------------------------------------------------------------------- #
def source_ref_of(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "as_of": str(source.get("as_of") or ""),
        "entity_id": str(source.get("entity_id") or ""),
        "entity_name": str(source.get("entity_name") or ""),
        "knowledge_cutoff": str(source.get("knowledge_cutoff") or ""),
        "pit_grade": str(source.get("pit_grade") or "trade_date_only"),
        "hindsight": bool(source.get("hindsight")),
        "alias_applied": bool(source.get("alias_applied")),
    }


def project(
    source: dict[str, Any],
    *,
    framework_version: str | None,
    task: str,
    budget: int | None = None,
    rules: dict[str, SelectionRule] | None = None,
) -> ContextProjection:
    """河切片（``RiverSlice.to_dict()`` 形状）→ 上下文投影。纯函数：不读盘、不调模型。

    ``rules`` 按轨名给选择规则，没给的轨走 ``DefaultRule``。``budget`` 是进上下文的**块数**上限
    （None = 不限）：装不下的块整块进 ``omitted``，``limits`` / ``gaps`` 不占预算。
    """
    task_norm = str(task or "").strip()
    if not task_norm:
        raise ValueError("task 不能为空：投影要知道是给谁看的（guided_reading / ask_synthesis / …）")
    if budget is not None and int(budget) < 0:
        raise ValueError("budget 不能为负")

    tracks = source.get("tracks") or {}
    present = present_tracks_of(tracks)
    rules = rules or {}
    default_rule = DefaultRule()

    blocks: list[ProjectedBlock] = []
    omitted: dict[str, int] = {}
    omitted_refs: dict[str, list[str]] = {}
    budget_left: int | None = None if budget is None else int(budget)

    def _omit(track: str, objs: list[dict[str, Any]]) -> None:
        if not objs:
            return
        omitted[track] = omitted.get(track, 0) + len(objs)
        omitted_refs.setdefault(track, []).extend(str(o.get("ref") or "") for o in objs)

    for track in present:
        objs = sorted((o for o in tracks[track] if isinstance(o, dict)), key=default_sort_key)
        rule = rules.get(track, default_rule)
        sel = rule.select(track, objs, budget_left)
        _omit(track, list(sel.omitted))

        # 块 = (object_type, derivation)；deterministic 先于 frozen_llm，再按块内最高硬度降序、类型名。
        groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for o in sel.selected:
            groups.setdefault((str(o.get("object_type") or ""), derivation_of(o)), []).append(o)
        ordered = sorted(
            groups.items(),
            key=lambda kv: (
                0 if kv[0][1] == DERIVATION_DETERMINISTIC else 1,
                -_HARDNESS_RANK.get(_max_hardness(kv[1]), 0),
                kv[0][0],
            ),
        )
        for (otype, deriv), members in ordered:
            members = sorted(members, key=default_sort_key)
            if budget_left is not None and budget_left <= 0:
                _omit(track, members)
                continue
            blocks.append(
                ProjectedBlock(
                    track=track,
                    object_type=otype,
                    object_refs=tuple((str(o.get("ref") or ""), str(o.get("source_hash") or "")) for o in members),
                    hardness=_max_hardness(members),
                    derivation=deriv,
                    selected_by=sel.selected_by,
                    rendered_text="\n".join(render_object(o) for o in members),
                )
            )
            if budget_left is not None:
                budget_left -= 1

        if sel.collapsed:
            members = sorted(sel.collapsed, key=default_sort_key)
            if budget_left is not None and budget_left <= 0:
                _omit(track, members)
            else:
                blocks.append(
                    ProjectedBlock(
                        track=track,
                        object_type="stock_node",
                        object_refs=tuple(
                            (str(o.get("ref") or ""), str(o.get("source_hash") or "")) for o in members
                        ),
                        hardness=_max_hardness(members),
                        derivation=DERIVATION_DETERMINISTIC,
                        selected_by=sel.selected_by,
                        rendered_text=render_collapsed(members),
                        kind="collapsed",
                        collapsed_count=len(members),
                    )
                )
                if budget_left is not None:
                    budget_left -= 1

    used = len(blocks)
    return ContextProjection(
        projection_version=PROJECTION_VERSION,
        framework_version=(str(framework_version).strip() or None) if framework_version else None,
        task=task_norm,
        source_ref=source_ref_of(source),
        blocks=tuple(blocks),
        omitted=dict(sorted(omitted.items())),
        omitted_refs={k: tuple(v) for k, v in sorted(omitted_refs.items())},
        limits=limits_of(source, present_tracks=present),
        gaps=gaps_of(tracks),
        budget={"limit": budget, "used": used},
    )


def render(cp: ContextProjection) -> str:
    """人读投影。段序固定：限制 → 缺口 → 事实块（§4.5：边界条件排在事实之前）→ 省略。"""
    lines = [
        f"# 上下文投影｜{cp.source_ref.get('entity_name') or cp.source_ref.get('entity_id')}｜{cp.source_ref.get('as_of')}",
        f"（{cp.projection_hash}｜{cp.projection_version}｜task={cp.task}｜framework={cp.framework_version or 'none'}"
        f"｜labels={cp.label_version}｜budget={cp.budget['limit']}/{cp.budget['used']}）",
        "",
        "## 限制",
        *([f"- {x}" for x in cp.limits] or ["- （无）"]),
        "",
        "## 缺口（缺轨不用别的轨补）",
        *([f"- {x}" for x in cp.gaps] or ["- （无）"]),
        "",
        "## 事实块（有序）",
    ]
    if cp.blocks:
        for b in cp.blocks:
            lines.append(f"- **{b.track} / {b.object_type}**（{b.derivation}｜hardness={b.hardness}｜selected_by={b.selected_by}）")
            lines += [f"  - {line}" for line in b.rendered_text.split("\n") if line]
    else:
        lines.append("- （无）")
    lines += ["", "## 省略（按块整体省略，不截断）"]
    if cp.omitted:
        for track, n in cp.omitted.items():
            lines.append(f"- {track}：{n} 条未进上下文")
    else:
        lines.append("- （无）")
    return "\n".join(lines)
