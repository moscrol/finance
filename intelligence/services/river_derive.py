"""区间派生对象（工单 #35 刀 2；09-06 spec §4.4）：从 ``RiverWindow`` 的切片序列算出可拆回到天与行的对象。

五类 ``object_type``（§4.4 钦定）：

| 类 | 定义 | 本模块 |
|---|---|---|
| ``streak`` | 连续 N 日满足某注册标签 | ``derive_streak`` |
| ``transition`` | 阶段 / 标签从 a 到 b 的跃迁日 | ``derive_transitions`` |
| ``cumulative`` | 区间累计 | ``river_window_contract.cumulative_object``（包 ``range_aggregate``，不重写） |
| ``first_event`` | 区间内首次出现 | ``derive_first_event`` |
| ``signature`` | 六维 z-score 签名 | ``derive_signature``（包 ``river_window.window_features``，不重写） |

每条派生对象必带：``derivation_rule{name, version}``、``member_refs[]``（指回哪些天的哪些对象 ref）、
``validity_kind=range``、``valid_from=start / valid_to=end``、``pit_grade``（所依赖切片的 min）、
``gap_policy`` 与 ``gaps_applied[]``（缺了哪几天、按哪条策略处理）。

**gap_policy 三值**（挂在派生规则上，不是全局）：

- ``unverifiable``（默认）：区间内任一天所需轨为 gap → 对象标 unverifiable 并写明缺哪天；缺一天不是零，也不是跳过继续数。
- ``break``：缺天中断连续计数（对 streak 语义正确，对累计量不对）。
- ``skip``：累计时跳过并在 coverage 里报（对累计量可接受，对连续量不可接受）。

**标签谓词只能引用 ``methodology_backtest.labels.ALL_LABELS``**——不新造标签名（G-16 红线提前守住）。
切片里放的是原料字段不是编译后的标签值，所以这里有一层「标签绑定」把注册标签落到 payload 上：
只收单日切片能判的那些（``SLICE_EVALUABLE_LABELS``），阈值 ``from labels import``，不复制数字。
需要历史的标签（``dual_red_streak / diff_ratio_turn_up / ma5_*``）由本模块的 streak / transition 派生表达，不做单日绑定。

**白名单是整条河的表达力上限**：情景树的分枝条件、规则 DSL、研究演化的可判观测，
三者都只认这张表里的名字（``scenario_trees.py`` 与 ``research_evolution.adapters``
直接 import 它）。白名单有几个词，这条河就只能说出几种话——所以每新接一个**已注册**
标签，不是加一列数据，是给判读多一个可用的概念。2026-10-07 从 4 个扩到 7 个：
补上的 ``multi_period_resonance / opinion_stage / lifecycle_stage`` 全都是切片里
**本来就算好了、只是没接线**的值，口径一个字没改，``LABEL_VERSION`` 不动。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable

from intelligence.services.methodology_backtest.labels import (
    ALL_LABELS,
    DUAL_RED_AMOUNT_GT,
    DUAL_RED_DIFF_RATIO_GT,
    LABEL_VERSION,
)
from intelligence.services.river import RiverObject, RiverSlice
from intelligence.services.river_window_contract import RiverWindow, track_objects
from market_feature_store.analysis.turning_points import VOLUME_SURGE_PCT

GAP_POLICIES = ("unverifiable", "break", "skip")


class LabelNotSliceEvaluable(ValueError):
    """标签不在单日切片可判的白名单里（或根本不是注册标签）。"""


# --------------------------------------------------------------------------- #
# 标签绑定：注册标签 → 单日切片上的取值（True / False / None=缺原料）
# --------------------------------------------------------------------------- #
def _first(objs: list[RiverObject], object_type: str) -> RiverObject | None:
    for o in objs:
        if o.object_type == object_type:
            return o
    return None


def _num(v: Any) -> float | None:
    if isinstance(v, bool) or v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _sector_quote(sl: RiverSlice) -> RiverObject | None:
    """盘面轨里那条来自 ``fact_sector_daily`` 的量价行。

    盘面轨同时发两个 ``object_type="label"``：量价行与涨停热度行（``source_view="limit_heat"``）。
    按出现顺序取第一个在量价行存在时恰好对；但**量价行缺、热度行在**的那一天，
    ``_first(..., "label")`` 取到的是热度行——它没有 ``pct_chg`` 等键，``.get`` 全返回 None，
    于是结果「碰巧」仍是「缺原料」。碰巧对的代价是：热度表哪天多出一个同名列，绑定就会
    静默读错一张表且不报错。这里按 ``sector_ts_code`` 存在与否显式选行，把巧合变成约定。
    """
    for o in track_objects(sl, "market"):
        if o.object_type == "label" and o.payload.get("source_view") != "limit_heat":
            if "sector_ts_code" in o.payload or "pct_chg" in o.payload:
                return o
    return None


def _bind_dual_red_strict(sl: RiverSlice) -> tuple[bool | None, list[str]]:
    """与 ``labels.py`` 的 ``dual_red_strict`` **同一套三值逻辑**：任一已知条件为假即 False，
    只有「已知的都为真、却有输入缺失」才是 None。

    两边必须逐格一致：同名同版本的标签在标签层与河的绑定层给出两种判断，而派生对象照样
    标 ``label_version``，情景树的分枝条件又用的是这条绑定——不一致会让「同一个标签」在
    两条路径上得到不同的真值，且没有任何地方会报错（09-12 复核抓到：pct=1 / diff=NULL /
    amount=100 时标签层判 0、这里判未知）。一致性由 ``test_river_derive_matches_labels_layer`` 钉住。
    """
    o = _sector_quote(sl)
    if o is None:
        return None, []
    p = o.payload
    pct, diff, amt = _num(p.get("pct_chg")), _num(p.get("diff_ratio")), _num(p.get("amount"))
    known_false = (
        (pct is not None and pct <= 0)
        or (diff is not None and diff <= DUAL_RED_DIFF_RATIO_GT)
        or (amt is not None and amt <= DUAL_RED_AMOUNT_GT)
    )
    if known_false:
        return False, [o.ref]
    if pct is None or diff is None or amt is None:
        return None, [o.ref]
    return True, [o.ref]


def _bind_volume_surge(sl: RiverSlice) -> tuple[bool | None, list[str]]:
    o = _first(track_objects(sl, "market"), "stage")
    if o is None:
        return None, []
    v = _num(o.payload.get("amount_vs_yesterday_pct"))
    return (None if v is None else bool(v > VOLUME_SURGE_PCT)), [o.ref]


def _bind_market_stage(sl: RiverSlice) -> tuple[str | None, list[str]]:
    """河切片里的 ``market_stage`` 是供应商原值（可能带「阶段」后缀）；绑定到注册标签要走 G-05 的归一函数，
    否则 ``in ["底部横盘"]`` 对着「底部横盘阶段」永远不命中——旁路库 v3 已归一，切片这边必须同口径。"""
    from intelligence.services.market_stage import normalize_market_stage

    o = _first(track_objects(sl, "market"), "stage")
    if o is None:
        return None, []
    v = normalize_market_stage(o.payload.get("market_stage"))
    return (v if v not in (None, "") else None), [o.ref]


def _bind_limit_heat_rank(sl: RiverSlice) -> tuple[float | None, list[str]]:
    for o in track_objects(sl, "market"):
        if o.object_type == "label" and o.payload.get("source_view") == "limit_heat":
            return _num(o.payload.get("rank")), [o.ref]
    return None, []


def _bind_multi_period_resonance(sl: RiverSlice) -> tuple[bool | None, list[str]]:
    """``fact_sector_daily.multi_period_resonance`` 的直接投影。

    标签层是 ``CASE WHEN multi_period_resonance IS NULL THEN NULL WHEN … THEN 1 ELSE 0 END``
    （labels.py 的布尔列投影），没有阈值、没有派生，所以这里也只做三值映射：
    缺列 / 缺行 / 列为 NULL → None，其余按 Python 真值判。

    不写 ``bool(v)`` 兜底任意类型：该列在 schema 里是 BOOLEAN，真库若哪天变成 0/1 整数或
    'Y'/'N' 字符串，``bool("N")`` 会判成 True 而且不报错。只认 bool，其余交给下面的显式分支。
    """
    o = _sector_quote(sl)
    if o is None:
        return None, []
    v = o.payload.get("multi_period_resonance")
    if v is None:
        return None, [o.ref]
    if isinstance(v, bool):
        return v, [o.ref]
    n = _num(v)
    if n is not None:  # 整数 0/1 列：真库换型时仍可判，且口径与 SQL 的 CASE 一致
        return bool(n != 0), [o.ref]
    raise LabelNotSliceEvaluable(
        f"multi_period_resonance 读到非布尔非数值的 {type(v).__name__} 值 {v!r}；"
        " 上游列型变了，绑定层拒绝猜——改口径请同时改 labels.py 的投影并升 LABEL_VERSION"
    )


def _bind_opinion_stage(sl: RiverSlice) -> tuple[str | None, list[str]]:
    """舆论生命周期段（萌芽 / 扩散 / 拥挤 / 退热 / 证伪 / unverifiable）。

    切片的舆论轨已经调过 ``opinion_stage.derive_stage(hits, as_of, knowledge_cutoff=as_of)``
    并把结果发成 ``object_type="stage"``；标签层 ``_build_opinion_stage_labels`` 调的是
    **同一个函数、同一组参数**。所以这里不重算，只取那个对象的 ``stage`` ——重算等于把
    同一口径实现两遍，正是 parity 测试要防的东西。

    该板块名从未被研报 tag 命中的日子，舆论轨整条是 ``Gap("opinion","no_data")``，
    这里返回 None，与标签层的「不落行 = NULL」对上。

    ⚠ 一处**已知且故意保留**的不对称：标签层按 ``sector_ts_code`` 归并该代码历史上的
    全部曾用名再取命中并集（实测 990380.FP 有两个名字），河这边只用当前切片的
    ``entity_name`` 一个名字匹配。改过名的板块在改名前后会出现两层口径不同的日子。
    不在这里偷偷补：河的实体归一走 ``resolve_entity`` / ``config_sector_alias``，
    那才是该修的地方（实测该表 0 行，见质检 P2）。此处只把差异写明，避免下游以为两边恒等。
    """
    o = _first(track_objects(sl, "opinion"), "stage")
    if o is None:
        return None, []
    v = o.payload.get("stage")
    return (v if isinstance(v, str) and v else None), [o.ref]


def _bind_lifecycle_stage(sl: RiverSlice) -> tuple[str | None, list[str]]:
    """题材生命周期七段（酝酿 / 首发 / 发酵 / 主升 / 分歧 / 退潮 / 回流）的当日读数。

    题材轨的 ``theme_lifecycle_stage_object`` 与标签层的 ``_build_lifecycle_stage_labels``
    是同一台状态机（``theme_lifecycle_timeline.derive_stages`` 的 ``daily=`` 逐日态），
    labels.py 的 docstring 已写明「随机抽 30 格两边逐字节相等（测试钉住）」。这里同样只取不算。

    取的是 ``payload["stage"]``（站在当天的读数），**不是**
    ``payload["segment_hindsight"]["stage"]`` —— 后者是段落表的事后视角（起点回溯、短段合并），
    两者可以不同，而 PIT 下只有前者可用。段外（首个盘面信号之前 / 段间空档）题材轨不发
    stage 对象，这里返回 None，对应标签层的 NULL；那是 gap，不是「酝酿」。
    """
    for o in track_objects(sl, "theme"):
        if o.object_type == "stage" and o.payload.get("mapping_version"):
            v = o.payload.get("stage")
            return (v if isinstance(v, str) and v else None), [o.ref]
    return None, []


# 白名单：单日切片能判的注册标签 → 绑定函数。值域：bool（谓词）或标量（stage / rank，用于 transition）。
#
# 只收 ``ALL_LABELS`` 里已登记的名字（``bind`` 会先查），这里扩的是「已注册但还没接线」的那部分，
# 不新造标签名、不动任何阈值、不升 ``LABEL_VERSION``——口径一个字没改，只是河这边原本能判却没判。
SLICE_EVALUABLE_LABELS: dict[str, Callable[[RiverSlice], tuple[Any, list[str]]]] = {
    "dual_red_strict": _bind_dual_red_strict,
    "volume_surge": _bind_volume_surge,
    "market_stage": _bind_market_stage,
    "limit_heat_rank": _bind_limit_heat_rank,
    "multi_period_resonance": _bind_multi_period_resonance,
    "opinion_stage": _bind_opinion_stage,
    "lifecycle_stage": _bind_lifecycle_stage,
}

# 为什么剩下 10 个注册标签仍然不在上面（写下来，省得下次有人重新判断一遍）：
#   amount_rank_top10        切片只有本实体的 amount，没有当日 published 名单的横截面，排名算不出来
#   mainline_flag            fact_mainline_sector_daily 不在六轨任何一轨的取数范围内
#   limit_heat_rank_jump     要前一交易日的名次 → 用 derive_transitions(limit_heat_rank) 表达
#   dual_red_streak          就是 derive_streak("dual_red_strict") 本身，重复绑定等于两处口径
#   diff_ratio_turn_up       要相邻前一日 → 区间派生，不是单日
#   ma5_peak_confirmed       SignalDetector 要全程 fact_market_daily 序列
#   ma5_valley_confirmed     同上
#   limit_up / first_board / new_high_1y
#                            个股级标签。河的实体是板块，个股轨给的是成员列表；
#                            在板块切片上「绑定」它们只能绑成某种聚合（几只涨停 / 占比），
#                            而那是**另一个标签**，需要新名字 + LABEL_VERSION，踩 G-16 红线。


def bind(label: str, sl: RiverSlice) -> tuple[Any, list[str]]:
    """注册标签在一片切片上的值与所用对象 ref。不在白名单 → 抛错（不猜、不静默 None）。

    ``tf.*`` 走教学桥（``river_teaching_bridge``）：命名空间不合并，缺旁路库返回 ``(None, [])`` → unknown。
    """
    from intelligence.services import river_teaching_bridge as _bridge

    if _bridge.is_teaching_label(label):
        return _bridge.bind_teaching(label, sl)
    if label not in ALL_LABELS:
        raise LabelNotSliceEvaluable(f"{label!r} 不是注册标签（ALL_LABELS @ {LABEL_VERSION}）")
    fn = SLICE_EVALUABLE_LABELS.get(label)
    if fn is None:
        raise LabelNotSliceEvaluable(
            f"{label!r} 需要历史或个股级原料，单日切片判不了；用 streak / transition 派生表达，或等更多绑定"
        )
    return fn(sl)


# --------------------------------------------------------------------------- #
# 派生对象的公共外壳
# --------------------------------------------------------------------------- #
def _hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _pit_of(slices: list[RiverSlice], hindsight: bool) -> str:
    if hindsight or not slices:
        return "trade_date_only"
    return "strict" if all(s.pit_grade == "strict" for s in slices) else "trade_date_only"


def _derived(
    win: RiverWindow,
    *,
    track: str,
    object_type: str,
    rule: dict[str, str],
    status: str,
    member_refs: list[str],
    gap_policy: str,
    gaps_applied: list[str],
    body: dict[str, Any],
    used_slices: list[RiverSlice],
) -> RiverObject:
    if gap_policy not in GAP_POLICIES:
        raise ValueError(f"gap_policy 只能是 {GAP_POLICIES}")
    payload = {
        "derivation_rule": rule,
        "label_version": LABEL_VERSION,
        "status": status,
        "gap_policy": gap_policy,
        "gaps_applied": gaps_applied,
        "member_refs": member_refs,
        "pit_grade": _pit_of(used_slices, win.hindsight),
        **body,
    }
    return RiverObject(
        track=track,  # type: ignore[arg-type]
        entity_id=win.entity_id,
        object_type=object_type,
        ref=f"{object_type}:{rule['name']}:{win.entity_id}:{win.start}:{win.end}",
        source_hash=_hash({"rule": rule, "status": status, "body": body, "members": member_refs}),
        valid_from=win.start,
        valid_to=win.end,
        recorded_at=None,
        payload=payload,
        validity_kind="range",
        derivation="deterministic",
    )


@dataclass(frozen=True)
class DayValue:
    day: str
    value: Any  # None = 缺原料
    refs: tuple[str, ...]


def _values(win: RiverWindow, label: str) -> list[DayValue]:
    out: list[DayValue] = []
    for sl in win.slices:
        v, refs = bind(label, sl)
        out.append(DayValue(sl.as_of, v, tuple(refs)))
    return out


def _require_boolean(label: str, vals: list[DayValue]) -> None:
    """``streak`` 只对**布尔谓词**有意义；非布尔标签必须抛错，不得静默算成 0。

    为什么要这道门：``derive_streak`` 的内层循环是 ``if d.value is True``，分类标签
    （``market_stage`` 取 '震荡'/'主升'…）或数值标签（``limit_heat_rank``）永远走不进
    这个分支，于是返回 ``longest=0, current=0`` 且 ``status="ok"``——**一个看着完全
    正常的读数**，调用方没有任何线索知道它问错了问题。注册标签里只有少数是布尔，
    传错的概率不低，而错了之后拿到的是假零不是异常，正是本仓反复强调的那类
    「看起来完全合理、足以支撑一次错误归属分析」的数字。

    连续段语义对分类标签不是没有，而是**另一个对象**：某个取值连续出现几天，
    要先把标签投影成谓词（``market_stage == '主升'``）再数。那是调用方的建模决定，
    本函数不替它猜一个取值。
    """
    bad = [d for d in vals if d.value is not None and not isinstance(d.value, bool)]
    if not bad:
        return
    sample = bad[0]
    kinds = sorted({type(d.value).__name__ for d in bad})
    raise LabelNotSliceEvaluable(
        f"streak 只接布尔谓词，{label!r} 在区间内取到 {kinds} 值"
        f"（如 {sample.day}={sample.value!r}）。"
        " 分类/数值标签请先投影成谓词再数连续段——直接传进来会得到 longest=0 的假零读数。"
    )


# --------------------------------------------------------------------------- #
# streak：连续 N 日谓词为真
# --------------------------------------------------------------------------- #
def derive_streak(win: RiverWindow, label: str, *, gap_policy: str = "unverifiable") -> RiverObject:
    """区间内该谓词**最长连续为真**的天数与落在区间尾的当前连续数。

    ``unverifiable``：任一天缺原料 → 整条 unverifiable（写明缺哪天）；
    ``break``：缺天当作中断（计数归零、继续往后数）——对「连续」语义成立，理由写在 gaps_applied；
    ``skip`` 对连续量不成立，拒绝。
    """
    if gap_policy == "skip":
        raise ValueError("streak 是连续量：缺天跳过继续数等于把「不知道」当成「连着」，不接受 skip")
    vals = _values(win, label)
    _require_boolean(label, vals)
    missing = [d.day for d in vals if d.value is None]
    refs = [r for d in vals for r in d.refs]
    rule = {"name": f"streak:{label}", "version": "v1"}
    if missing and gap_policy == "unverifiable":
        return _derived(win, track="market", object_type="streak", rule=rule, status="unverifiable",
                        member_refs=refs, gap_policy=gap_policy, gaps_applied=[f"missing:{d}" for d in missing],
                        body={"label": label}, used_slices=list(win.slices))
    best = cur = 0
    best_end: str | None = None
    for d in vals:
        if d.value is True:
            cur += 1
            if cur > best:
                best, best_end = cur, d.day
        else:  # False 或（break 策略下的）None
            cur = 0
    return _derived(win, track="market", object_type="streak", rule=rule, status="ok",
                    member_refs=refs, gap_policy=gap_policy,
                    gaps_applied=[f"break:{d}" for d in missing],
                    body={"label": label, "longest": best, "longest_end": best_end, "current": cur, "days": len(vals)},
                    used_slices=list(win.slices))


# --------------------------------------------------------------------------- #
# transition：标量标签从 a 到 b 的跃迁日
# --------------------------------------------------------------------------- #
def derive_transitions(win: RiverWindow, label: str, *, gap_policy: str = "unverifiable") -> RiverObject:
    """相邻两天取值不同的那一天（后一天）记一次跃迁 ``{day, from, to}``。

    缺原料日：``unverifiable`` → 整条 unverifiable；``break`` → 缺天两侧不比（缺天前后即便变了也不算跃迁，
    因为不知道是哪天变的）；``skip`` 不接受（跨过缺天比较会把两天的变化算成一天）。
    """
    if gap_policy == "skip":
        raise ValueError("transition 跨缺天比较会把多天的变化算成一天，不接受 skip")
    vals = _values(win, label)
    missing = [d.day for d in vals if d.value is None]
    refs = [r for d in vals for r in d.refs]
    rule = {"name": f"transition:{label}", "version": "v1"}
    if missing and gap_policy == "unverifiable":
        return _derived(win, track="market", object_type="transition", rule=rule, status="unverifiable",
                        member_refs=refs, gap_policy=gap_policy, gaps_applied=[f"missing:{d}" for d in missing],
                        body={"label": label}, used_slices=list(win.slices))
    trans: list[dict[str, Any]] = []
    prev: DayValue | None = None
    for d in vals:
        if d.value is None:
            prev = None  # break：缺天断开比较链
            continue
        if prev is not None and prev.value != d.value:
            trans.append({"day": d.day, "from": prev.value, "to": d.value, "refs": list(prev.refs) + list(d.refs)})
        prev = d
    return _derived(win, track="market", object_type="transition", rule=rule, status="ok",
                    member_refs=refs, gap_policy=gap_policy,
                    gaps_applied=[f"break:{d}" for d in missing],
                    body={"label": label, "transitions": trans, "count": len(trans)},
                    used_slices=list(win.slices))


# --------------------------------------------------------------------------- #
# first_event：区间内某轨某类事件首次出现
# --------------------------------------------------------------------------- #
def derive_first_event(win: RiverWindow, track: str, object_type: str, *, gap_policy: str = "unverifiable") -> RiverObject:
    """区间内 ``track`` 上第一条 ``object_type`` 对象出现的那天。

    该轨在首次出现之前若有缺口日（gap 不是空列表），``unverifiable`` 下整条 unverifiable——
    「首次」可能落在看不见的那天；``break`` 不适用（首次没有连续可断）；``skip`` 下把缺口日
    写进 gaps_applied 并照常报「可见范围内的首次」。
    """
    if gap_policy == "break":
        raise ValueError("first_event 没有连续计数可断，不接受 break")
    rule = {"name": f"first_event:{track}:{object_type}", "version": "v1"}
    gap_days: list[str] = []
    for sl in win.slices:
        v = sl.tracks.get(track)  # type: ignore[arg-type]
        if not isinstance(v, list):
            gap_days.append(sl.as_of)
            continue
        hit = [o for o in v if o.object_type == object_type]
        if hit:
            if gap_days and gap_policy == "unverifiable":
                return _derived(win, track=track, object_type="first_event", rule=rule, status="unverifiable",
                                member_refs=[o.ref for o in hit], gap_policy=gap_policy,
                                gaps_applied=[f"missing:{d}" for d in gap_days],
                                body={"first_visible_day": sl.as_of}, used_slices=list(win.slices))
            return _derived(win, track=track, object_type="first_event", rule=rule, status="ok",
                            member_refs=[o.ref for o in hit], gap_policy=gap_policy,
                            gaps_applied=[f"skip:{d}" for d in gap_days],
                            body={"first_day": sl.as_of, "count_on_day": len(hit)}, used_slices=list(win.slices))
    status = "unverifiable" if (gap_days and gap_policy == "unverifiable") else "ok"
    return _derived(win, track=track, object_type="first_event", rule=rule, status=status,
                    member_refs=[], gap_policy=gap_policy,
                    gaps_applied=[f"{'missing' if status == 'unverifiable' else 'skip'}:{d}" for d in gap_days],
                    body={"first_day": None, "note": "区间内未出现"}, used_slices=list(win.slices))


# --------------------------------------------------------------------------- #
# signature：六维 z-score 签名（包 river_window.window_features，不重写）
# --------------------------------------------------------------------------- #
def derive_signature(win: RiverWindow, daily: list[dict[str, Any]], *, z_rows: list[dict[str, float | None]] | None = None) -> RiverObject:
    """把 ``river_window.build_daily_vectors(knowledge_cutoff=C)`` 的逐日向量折成区间签名对象。

    ``daily`` 必须是带 C 算出来的（本单 刀 3 让 ``build_daily_vectors`` 必填 ``knowledge_cutoff``），
    这里再核一遍：任何一行 ``d > C`` 直接拒绝——签名对象绝不能从看得见未来的向量算。
    缺维按覆盖率惩罚而不是补零（``window_features`` 既有行为），``gap_policy=unverifiable`` 只在区间内无交易日时触发。
    """
    from intelligence.services import river_window as rw

    late = [str(r.get("trade_date")) for r in daily if str(r.get("trade_date")) > win.knowledge_cutoff]
    if late:
        raise ValueError(f"daily 向量含晚于 knowledge_cutoff={win.knowledge_cutoff} 的行（如 {late[:3]}）：前视泄漏，拒绝")
    rule = {"name": "signature:river_window.window_features", "version": "v1"}
    feat = rw.window_features(daily, win.start, win.end, label=f"{win.entity_id}:{win.start}~{win.end}", z_rows=z_rows)
    member_refs = [f"fact_market_daily:{r.get('trade_date')}" for r in daily if win.start <= str(r.get("trade_date")) <= win.end]
    if feat is None:
        return _derived(win, track="market", object_type="signature", rule=rule, status="unverifiable",
                        member_refs=member_refs, gap_policy="unverifiable", gaps_applied=["no trading days in range"],
                        body={}, used_slices=list(win.slices))
    body = feat.to_dict() if hasattr(feat, "to_dict") else {"features": getattr(feat, "features", None)}
    return _derived(win, track="market", object_type="signature", rule=rule, status="ok",
                    member_refs=member_refs, gap_policy="unverifiable", gaps_applied=[],
                    body=body, used_slices=list(win.slices))
