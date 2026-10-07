"""授课框架标签 → 判定路径的**桥**：保命名空间分离，带身份消费。

## 为什么是桥，不是并库

``teaching_framework.river_objects`` 搬运教学标签，桥把其中已开放的标量
接到情景树、规则 DSL 与判断维护的判定路径。教学标签与供应商标签的定义和来源不同，
所以 ``tf.*`` 保留独立目录，不并入 ``ALL_LABELS`` / ``LABEL_KINDS``：

- ``tf.`` 前缀是强制的、保留的身份标记。去掉前缀的裸名（``above_week_ma``）一律拒绝——
  缺少前缀就无法确认标签属于哪个定义体系。
- 单独一张 ``TEACHING_LABEL_KINDS`` 表，与供应商标签表平行，不合并。
- 每次取值都回对应教学对象的 ``ref``，``teaching_provenance()`` 另给阶段对象的
  ``framework_version`` + ``source_hash``，让收据里能看出「这个 true 是哪一版教学框架在哪天算的」。

## 旁路库没接的时候

``river.build_slice`` 不给 ``teaching_labels_db`` 时切片上就没有 ``teaching_*`` 对象。
这时绑定函数返回 ``(None, [])`` → 判定走 Kleene 三值的 **unknown**，并在读数里留 ``no_observation``。

**不是静默跳过，也不是当 false。** 「这条谓词没原料」和「这条谓词为假」是两回事，
混起来就会让一棵树在旁路库缺席时悄悄走到另一个分枝上，而收据看不出差别。

## SSOT 与防漂移

``TEACHING_LABEL_KINDS`` 与 ``TEACHING_LABELS_WITHHELD`` 的并集必须**恰好等于**
``river_objects`` 搬运的四组标签并集，由 ``assert_teaching_catalog_parity()`` 守。
这样新增教学标签时，要么显式开放、要么显式留置并写理由，不会有标签悄悄漏进或漏出判定路径——
``adapters.SLICE_EVALUABLE_LABELS`` 当年手抄一份四元组导致两处同名不同物，就是这个教训。
"""

from __future__ import annotations

from typing import Any

from intelligence.services.river import RiverObject, RiverSlice
from intelligence.services.river_window_contract import track_objects
from intelligence.services.teaching_framework.river_objects import (
    CYCLE_LABELS,
    SECTOR_ROLE_LABELS,
    STAGE_LABELS,
    STRUCTURE_LABELS,
)

TEACHING_NAMESPACE = "tf."
TEACHING_STAGE_OBJECT = "teaching_stage"
TEACHING_CYCLE_OBJECT = "teaching_cycle"
TEACHING_STRUCTURE_OBJECT = "teaching_structure"
TEACHING_SECTOR_ROLE_OBJECT = "teaching_sector_role"

# 哪个标签挂在哪个河对象上。两个对象而不是一个，是因为阶段对象已接近 payload ≤ 20 键的索引层约束
# （仓里 CAPITAL / BREADTH / NARRATIVE 也是这么分的）。桥对调用方隐藏这个分法：
# 谓词只写 ``tf.xxx``，不需要知道它落在哪个对象里。
_OBJECT_OF_LABEL: dict[str, str] = {
    **{label: TEACHING_STAGE_OBJECT for label in STAGE_LABELS},
    **{label: TEACHING_CYCLE_OBJECT for label in CYCLE_LABELS},
    **{label: TEACHING_STRUCTURE_OBJECT for label in STRUCTURE_LABELS},
    **{label: TEACHING_SECTOR_ROLE_OBJECT for label in SECTOR_ROLE_LABELS},
}

# 同名不同物是本仓踩过的坑（见模块 docstring 末段）。一个标签名只能属于一个对象：
# 教学标签现在横跨 market / sector 两个实体层，``tf.mainline_volume_top3`` 就同时存在于
# 市场级 CYCLE_LABELS 与板块级 SECTOR_LABELS（含义不同）。碰撞必须在导入时就炸，
# 不能等到某天一条谓词悄悄绑到了另一层的读数上——那种错不会报错，只会给出错的答案。
_LABEL_GROUPS = (
    ("STAGE_LABELS", STAGE_LABELS), ("CYCLE_LABELS", CYCLE_LABELS),
    ("STRUCTURE_LABELS", STRUCTURE_LABELS), ("SECTOR_ROLE_LABELS", SECTOR_ROLE_LABELS),
)
_seen: dict[str, str] = {}
for _group_name, _group in _LABEL_GROUPS:
    for _label in _group:
        if _label in _seen:
            raise AssertionError(
                f"教学标签 {_label!r} 同时出现在 {_seen[_label]} 与 {_group_name}。"
                "一个名字只能属于一个河对象，否则谓词会绑到哪一层取决于字典插入顺序——"
                "静默给出另一层的读数。请改名或在搬运侧剔除其中一个（并写明理由）。"
            )
        _seen[_label] = _group_name
_BRIDGED_LABELS = frozenset(_seen)
del _seen, _group_name, _group, _label

# ---------------------------------------------------------------------------
# 跨子系统同名守卫
#
# 上面那道断言只看桥**自己**的四组，看不见别的子系统。2026-10-07 的补证包
# (FINDINGS §3) 指出一处它拦不住的重名：
#
#   ``index_stage.STRUCTURE_EVENTS`` 里的 ``macd_bottom_div_observe`` 等名字量的是
#   **上证日线**（市场级）；桥上开放的同名标签量的是**板块 / 个股**
#   （``entity_type='sector'/'stock'``，见 ``river_objects.STRUCTURE_LABELS``）。
#   同一个名字，两个实体，两个子系统。
#
# 更要紧的是市场级那一份**已经在给段位打分**——``stage_rules.py:300``：底背离的
# 观察 / 确认日给「缩量右底」与「共建主线」各记一分。所以一棵树里同时写
# ``tf.stage_coarse == "共建主线"`` 和 ``tf.macd_bottom_div_confirm == True``，
# 两个谓词**不独立**：前者部分由上证背离打分得来，后者是板块的背离。不是严格循环
# （实体不同），但相关，而且读的人多半以为是同一件事。
#
# 这里**不**改名——改名要动已落库的历史行，是另一件事，得单独定。只做两件：
#   1. 已知的重名逐个在 ``_CROSS_SUBSYSTEM_REUSE`` 里写明「桥上这份是谁」；
#   2. 任何**新增**的意外重名在导入期就炸，而不是等某棵树悄悄绑到另一层。
#
# 哪天把市场级那批也搬上河，第一道断言会先炸（同名跨组），这道是第二层。
_CROSS_SUBSYSTEM_REUSE: dict[str, str] = {
    "tf.macd_bottom_div_observe": "桥上这份是板块 / 个股；index_stage 同名那份量上证日线且已进段位计分",
    "tf.macd_bottom_div_confirm": "桥上这份是板块 / 个股；index_stage 同名那份量上证日线且已进段位计分",
    "tf.macd_bottom_div_failed": "桥上这份是板块 / 个股；index_stage 同名那份量上证日线",
    "tf.macd_top_div": "桥上这份是板块 / 个股；index_stage 同名那份量上证日线",
}


def _assert_no_undeclared_cross_subsystem_reuse() -> None:
    """桥上的名字若与 ``index_stage`` 的市场级结构事件重名，必须已在上表登记。"""

    from .teaching_framework.index_stage import STRUCTURE_EVENTS

    market_level = {f"{TEACHING_NAMESPACE}{name}" for name in STRUCTURE_EVENTS}
    undeclared = sorted((_BRIDGED_LABELS & market_level) - set(_CROSS_SUBSYSTEM_REUSE))
    if undeclared:
        raise AssertionError(
            f"教学标签 {undeclared} 在桥上开放，同名的另一份在 index_stage 量的是**上证日线**"
            "（市场级），且其中一部分已参与段位计分。同名不同实体不会被第一道断言发现——"
            "情景树拿到的是桥这一份（板块 / 个股），写树的人多半以为是上证那一份。"
            "请在 _CROSS_SUBSYSTEM_REUSE 里写明桥上这份是谁，或改名。"
        )
    stale = sorted(set(_CROSS_SUBSYSTEM_REUSE) - _BRIDGED_LABELS)
    if stale:
        raise AssertionError(
            f"_CROSS_SUBSYSTEM_REUSE 登记了 {stale}，但桥上已经没有这些标签了。"
            "登记表留着过期条目会让下一个人以为重名还在——请删掉。"
        )


_assert_no_undeclared_cross_subsystem_reuse()

# 对象挂在哪条轨上。市场级那批挂 ``__market__`` 的盘面轨；结构事件是**实体级**的，
# 挂切片自己那个实体的轨（板块 → theme）。写死 "market" 会让实体级标签永远绑不到值，
# 而且是静默的 unknown —— 看不出是「没接旁路库」还是「找错了轨」。
_TRACK_OF_OBJECT: dict[str, str] = {
    TEACHING_STAGE_OBJECT: "market",
    TEACHING_CYCLE_OBJECT: "market",
    TEACHING_STRUCTURE_OBJECT: "theme",
    TEACHING_SECTOR_ROLE_OBJECT: "theme",
}


class TeachingLabelNotBridged(ValueError):
    """``tf.*`` 标签没有开放给判定路径；消息里带留置理由，不静默。"""


# 开放给判定路径的教学标签 → 值域类型。只开放四组教学对象搬上来的那批；
# capital / narrative / briefing / breadth 几个对象是本轮未纳入的扩展面（见模块末 FUTURE）。
TEACHING_LABEL_KINDS: dict[str, str] = {
    # —— 大盘周期 ——
    "tf.stage_coarse": "text",
    "tf.stage_fine": "text",
    "tf.above_week_ma": "bool",          # 收盘相对周均线的位置
    "tf.cross_below_kind": "text",       # 首次下穿 / 再次下穿
    "tf.below_ma_cycle_day": "num",      # 周均线下方第几天
    "tf.deviation_band": "text",         # 偏离度分档
    "tf.turn_up": "bool",
    "tf.turn_top": "bool",
    "tf.turn_down": "bool",
    # —— 市场情绪 ——
    "tf.money_losing_day": "bool",       # 亏钱日
    "tf.money_losing_streak": "num",     # 连续亏钱日数
    "tf.limit_premium_ma5_pct": "num",
    # —— 量（见顶量价时空）——
    "tf.amount_vs_ma20_pct": "num",      # 成交额相对 20 日均值
    "tf.new_high_1y_count": "num",
    # —— 周期位置：旁路库早就算了、此前从未搬上河的那批（teaching_cycle 对象）——
    "tf.gap_down_open": "bool",          # 低开缺口
    "tf.cross_above_week_ma": "bool",    # 上穿周均线
    "tf.deviation_narrowing": "bool",    # 偏离度收敛
    "tf.shrink_day": "bool",             # 缩量日
    "tf.volume_shrink_streak": "num",    # 连续缩量天数
    "tf.double_volume_day": "bool",      # 倍量日
    "tf.mainline_volume_top3": "bool",   # 市场级主线量能标记
    "tf.mainline_share_trend_up": "bool",  # 主线成交占比上行
    "tf.max_boards": "num",              # 最高连板高度
    # ── 结构事件（板块级）。这组是事件标签：只落事件日，
    # 「今天没事件」与「旁路库没接」在读数上长得一样，所以能写「出现底背离确认」，
    # 写不出「没有顶背离」—— 后者需要旁路库先落一条覆盖行，不在本次范围。
    "tf.macd_bottom_div_observe": "bool",   # 两低：后低收盘更低而 DIF 更高
    "tf.macd_bottom_div_confirm": "bool",   # 三低：收盘递降、DIF 递升
    "tf.macd_bottom_div_failed": "bool",    # 失效：fail_horizon 内收盘跌破锚点低点
    "tf.macd_top_div": "bool",              # 顶背离：两高收盘更高而 DIF 更低
    # ── 板块角色（C 类），口径以 sector_roles 为准，桥不重算。
    "tf.role_volume_top3": "bool",          # 量能角色
    "tf.role_price_top10": "bool",          # 价格角色
    "tf.role_sharpness_top10": "bool",      # 锐度前 10
    "tf.role_breadth_top_l1": "bool",       # 宽度第一的申万一级
    "tf.mainline_vendor": "bool",           # 供应商口径的主线板块
    "tf.dual_red_strict": "bool",           # 双红：pct>0 ∧ diff_ratio>10 ∧ amount>500（回测层同一口径）
    "tf.rps_3d_rank": "num",                # 板块级短期 RPS 名次
    "tf.rps_5d_rank": "num",
    "tf.rps_10d_rank": "num",
    "tf.limit_up_count": "num",             # 板块内涨停家数
    "tf.sharpness_limit_rank": "num",       # 锐度分量一：涨停家数名次
    "tf.sharpness_rank_mean": "num",        # 锐度分量二：区间涨幅名次均值（两列都出，合成方式待定）
    # 赚钱效应保留五种独立口径，桥不合成总分。
    "tf.money_effect.limit_top10": "bool",
    "tf.money_effect.dual_red": "bool",
    "tf.money_effect.rps5_top10": "bool",
    "tf.money_effect.rank_mean_top10": "bool",
    "tf.money_effect.kmeans_hot": "bool",
}

# 显式留置：算得出、进了河，但**不开放给判定**。每条必须有理由，理由必须可追到记录。
TEACHING_LABELS_WITHHELD: dict[str, str] = {
    "tf.volume_band": (
        "volume_band 维持只写出、不进计分"
        "（依据 docs/learning/teaching-framework/00-concept-label-skeleton.md §1.5）。"
        "判定路径上的谓词就是计分，所以这里留置；要开放需用户重新裁定。"
    ),
    "tf.stage_evidence": "JSON 结构（命中/缺项/领先分），不是标量谓词值；要用请取其中具体字段另立标签。",
}


def assert_teaching_catalog_parity() -> None:
    """开放表 ∪ 留置表 必须恰好等于河上真实搬运的那批教学标签。偏了就抛。"""
    declared = set(TEACHING_LABEL_KINDS) | set(TEACHING_LABELS_WITHHELD)
    actual = set(STAGE_LABELS) | set(CYCLE_LABELS) | set(STRUCTURE_LABELS) | set(SECTOR_ROLE_LABELS)
    missing = sorted(actual - declared)
    extra = sorted(declared - actual)
    if missing or extra:
        raise TeachingLabelNotBridged(
            "教学标签目录与 teaching_framework.river_objects.STAGE_LABELS 漂移："
            f"未表态 {missing}；表里有但河上没有 {extra}。"
            "新增教学标签必须显式开放或显式留置（带理由），不接受默认。"
        )


def is_teaching_label(label: str) -> bool:
    return isinstance(label, str) and label.startswith(TEACHING_NAMESPACE)


def teaching_kind(label: str) -> str:
    """教学标签的值域类型；未开放 → 抛（带留置理由）。裸名不认。"""
    if not is_teaching_label(label):
        raise TeachingLabelNotBridged(
            f"{label!r} 没有 {TEACHING_NAMESPACE!r} 前缀。教学标签必须带命名空间前缀引用"
            "；供应商与教学命名空间不可混用。"
        )
    kind = TEACHING_LABEL_KINDS.get(label)
    if kind is not None:
        return kind
    reason = TEACHING_LABELS_WITHHELD.get(label)
    if reason is not None:
        raise TeachingLabelNotBridged(f"{label!r} 已留置，不开放给判定路径：{reason}")
    raise TeachingLabelNotBridged(
        f"{label!r} 不在教学标签开放表里（开放 {len(TEACHING_LABEL_KINDS)} 个，"
        f"留置 {len(TEACHING_LABELS_WITHHELD)} 个）；若旁路库新增了它，先在 TEACHING_LABEL_KINDS 表态。"
    )


def _object_for(sl: RiverSlice, object_type: str) -> RiverObject | None:
    for o in track_objects(sl, _TRACK_OF_OBJECT.get(object_type, "market")):
        if o.object_type == object_type:
            return o
    return None


def _stage_object(sl: RiverSlice) -> RiverObject | None:
    return _object_for(sl, TEACHING_STAGE_OBJECT)


def _coerce(raw: Any, kind: str) -> Any | None:
    """旁路库把 bool 存成 0/1 的 value_num，取回来要按声明的值域还原。

    ``0`` 不是缺失——``above_week_ma = 0`` 是「在周均线下方」这个**确定的假**，
    不能和「没这条读数」混成同一个 None。
    """
    if raw is None:
        return None
    if kind == "bool":
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, (int, float)):
            return bool(raw)
        return None
    if kind == "num":
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            return None
        return float(raw)
    if kind == "text":
        if not isinstance(raw, str) or not raw.strip():
            return None
        return raw
    return None


def bind_teaching(label: str, sl: RiverSlice) -> tuple[Any, list[str]]:
    """教学标签在一片切片上的值与 ref。

    返回 ``(None, [])`` 的三种情形，判定路径一律当 **unknown**，不当 false：
    旁路库没接（切片上没有 teaching_stage 对象）／当天这条标签没读数／值的类型与声明不符。
    """
    kind = teaching_kind(label)
    obj = _object_for(sl, _OBJECT_OF_LABEL[label])
    if obj is None:
        return None, []
    key = label.removeprefix(TEACHING_NAMESPACE)
    if key not in obj.payload:
        return None, []
    value = _coerce(obj.payload.get(key), kind)
    if value is None:
        return None, []
    return value, [obj.ref]


def teaching_provenance(sl: RiverSlice) -> dict[str, Any] | None:
    """这片切片上教学读数的身份：哪一版框架、哪条 ref、内容指纹。没接旁路库 → None。

    收据里必须带上它——否则一个 ``tf.above_week_ma = false`` 看不出是哪一版教学框架算的，
    ``recorded_at`` 取对象成员最晚的 ``first_known_at``；任一缺戳则整体未知。
    """
    obj = _stage_object(sl)
    if obj is None:
        return None
    return {
        "namespace": "teaching",
        "ref": obj.ref,
        "source_hash": obj.source_hash,
        "framework_version": obj.payload.get("framework_version"),
        "recorded_at": obj.recorded_at,
    }


# FUTURE：teaching_capital / teaching_narrative / teaching_briefing / teaching_breadth 四个对象
# 另有 ~30 个市场级数值标签（龙虎榜、封单、竞价、广度、叙事覆盖）。本轮不开放，原因是它们还没有
# 对应到已开放的判据目录；开放前先确认定义、类型及 PIT 证据，避免仅因已有数值就加入判定。
# 其他结构事件也按同样流程处理，已开放集合以 TEACHING_LABEL_KINDS 为准。
__all__ = [
    "TEACHING_NAMESPACE",
    "TEACHING_LABEL_KINDS",
    "TEACHING_LABELS_WITHHELD",
    "TeachingLabelNotBridged",
    "assert_teaching_catalog_parity",
    "bind_teaching",
    "is_teaching_label",
    "teaching_kind",
    "teaching_provenance",
]
