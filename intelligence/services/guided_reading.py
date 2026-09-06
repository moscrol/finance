"""带读模式（roadmap G-03 第 2 件）：把一片 as-of 河切片渲染成「今日带读」，并给出可登记的观察剧本骨架。

终局 spec §2.1「今日带读」工作面、§3.1 每日闭环、§4.3「事实 / 推断 / 反证 / 缺口」。

## v0 只出三段，**判读段留空**

``授课框架 v0``（G-01）的内容必须由创始人写，agent 只能搭骨架——这是 08-19 定下的红线。
所以本模块渲染的是：

1. **事实**：逐轨列出切片里的对象（``object_type`` + payload 键值 + ``ref``），只搬不解释；
2. **限制**：``pit_grade`` 降档、``alias_applied`` 跨供应商换源这类会影响可比性的标记；
3. **缺口**：哪条轨读不出来、为什么——缺轨不用别的轨补（spec §4.3 硬规矩）。

**没有第四段「推断」**：那一段的内容属于授课框架，框架母本没写完之前生成它，等于 agent
替创始人给判读。留空 + 写明原因，比生成一段没有出处的话诚实。对外也一律不能称
「授课框架带读」——G-01 未过验收前只能说「带读管线跑通」。

## 默认状态：新用户开、老用户关（用户 2026-09-06 拍板）

判据是**有没有历史台账**，不是注册日期：老用户的现有输出一个字节都不该因为本模块变化。
本模块因此是纯附加的——关闭时 ``run`` 直接返回 ``None``，不读盘、不写盘、不登记。

⚠ 「关掉后逐字节不变」这条验收，在带读接进 ``market_watch_pack`` / ``exports/<date>-daily-agent.md``
之前是**平凡成立**的（没人调用它）。本刀故意不接那条线：接线要改每日复盘的产物，得单独
一刀带自己的 diff 收据。别把平凡成立的绿灯当成接线后的保证。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from intelligence.services import compliance_gate, observation_script

ENV_FLAG = "FORESIGHT_GUIDED_READING"

# 「有历史」的判据台账。只要其中任何一条有内容，就是老用户 → 默认关。
_HISTORY_LEDGERS = ("checkpoints_path", "judgments_path", "interactions_path")

# 每条轨的观察变量与放弃条件骨架：按 (track, object_type) 给句式，不碰 payload 语义。
# 句式里不许出现方向词 / 时点词——它们要过 observation_script 的同一道硬门。
_TRACK_VARIABLES: dict[str, str] = {
    "market": "盘面轨：指数阶段、成交与边际量是否延续",
    "theme": "题材轨：题材所处阶段是否推进",
    "opinion": "舆论轨：卖方覆盖密度与逻辑版本是否更新",
    "capital": "资金轨：板块 / 题材资金流是否延续",
    "stock": "个股轨：公告、订单、财报节点是否新增（只看节点，不出名单）",
    "judgment": "判断轨：已登记的可证伪点是否到期",
}
_TRACK_ABANDON: dict[str, str] = {
    "market": "盘面轨该实体的量价对象消失或转为缺口",
    "theme": "题材轨阶段标签回退或转为缺口",
    "opinion": "舆论轨连续无新增覆盖事件",
    "capital": "资金轨转为缺口（无可靠来源时不填零）",
    "stock": "个股轨无新增节点",
    "judgment": "判断轨该实体无未到期的可证伪点",
}

# 每个对象最多摊开几个 payload 键：切片是给人读的，不是导出全量。
_PAYLOAD_KEYS = 6


@dataclass(frozen=True)
class GuidedReading:
    as_of: str
    entity_id: str
    entity_name: str
    knowledge_cutoff: str
    pit_grade: str
    facts: dict[str, list[str]] = field(default_factory=dict)
    limits: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    draft: observation_script.ObservationScript | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of,
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "knowledge_cutoff": self.knowledge_cutoff,
            "pit_grade": self.pit_grade,
            "facts": self.facts,
            "limits": self.limits,
            "gaps": self.gaps,
            "draft": self.draft.to_dict() if self.draft else None,
        }


# --------------------------------------------------------------------------- #
# 开关
# --------------------------------------------------------------------------- #
def is_new_user(us: Any) -> bool:
    """零历史 = 三条台账全空或全不存在。文件存在但零行也算零历史。"""
    for attr in _HISTORY_LEDGERS:
        path = getattr(us, attr, None)
        if not isinstance(path, Path) or not path.exists():
            continue
        try:
            if any(line.strip() for line in path.read_text(encoding="utf-8").splitlines()):
                return False
        except OSError:  # pragma: no cover - 读不动就当没历史，不阻断带读
            continue
    return True


def resolve_enabled(us: Any, *, override: bool | None = None) -> tuple[bool, str]:
    """返回 ``(是否开启, 理由)``。优先级：显式参数 > 环境变量 > 新用户判据。

    理由要跟着读数走——「带读怎么没出来」这类问题，答案通常是三个来源里的某一个，
    只返回布尔值会让人去猜。
    """
    if override is not None:
        return bool(override), "显式参数"
    env = str(os.environ.get(ENV_FLAG) or "").strip().lower()
    if env in {"on", "1", "true", "yes"}:
        return True, f"环境变量 {ENV_FLAG}={env}"
    if env in {"off", "0", "false", "no"}:
        return False, f"环境变量 {ENV_FLAG}={env}"
    if is_new_user(us):
        return True, "零历史用户默认开"
    return False, "已有历史台账的用户默认关"


# --------------------------------------------------------------------------- #
# 渲染
# --------------------------------------------------------------------------- #
def _fact_line(obj: dict[str, Any]) -> str:
    payload = obj.get("payload") or {}
    keys = sorted(k for k in payload if payload[k] is not None)[:_PAYLOAD_KEYS]
    body = "，".join(f"{k}={payload[k]}" for k in keys)
    return f"{obj.get('object_type')}｜{body}｜ref={obj.get('ref')}｜hash={obj.get('source_hash')}"


def _is_stock_node(obj: dict[str, Any]) -> bool:
    """这个对象是不是「一只个股的一条记录」。

    判据按**对象形状**，不按轨名：题材轨也会发个股涨停节点
    （``fact_theme_limit_stock_daily``），个股轨更不用说。按轨名收边界，
    下一个 provider 一接进来就漏。
    """
    payload = obj.get("payload") or {}
    return bool(payload.get("stock_ts_code")) or compliance_gate.is_stock_entity(str(obj.get("ref") or ""))


def _collapse_stock_nodes(objs: list[dict[str, Any]]) -> list[str]:
    """个股级对象在带读里只出**计数与标签**，不出名单。

    数据层把它们叫「节点」（``river._stock_track`` 原文：不是推荐名单），这在 river
    那个查询面上成立——那是给操作者的数据出口。但带读是**小白产品面**：十条按成交额
    降序、带涨幅的个股行渲染出来，读者看到的就是一张名单，无论我们管它叫什么。
    边界得产品面自己收住，不能指望读者理解「这不是推荐」。明细留在 river 切片里。
    """
    labels: dict[str, int] = {}
    for obj in objs:
        payload = obj.get("payload") or {}
        for key in ("high_status_label", "limit_status", "up_stat"):
            label = str(payload.get(key) or "").strip()
            if label:
                labels[label] = labels.get(label, 0) + 1
    tail = "，".join(f"{k}×{v}" for k, v in sorted(labels.items())) or "无特征标签"
    return [f"个股级节点 {len(objs)} 条（{tail}）；明细见 river 切片，带读不出名单"]


def _fact_lines(objs: list[dict[str, Any]]) -> list[str]:
    """非个股级对象逐条摊开；个股级对象折叠成一行计数。"""
    stock_nodes = [o for o in objs if _is_stock_node(o)]
    lines = [_fact_line(o) for o in objs if not _is_stock_node(o)]
    if stock_nodes:
        lines += _collapse_stock_nodes(stock_nodes)
    return lines


def build(
    slice_dict: dict[str, Any],
    *,
    alias_applied: bool | None = None,
    framework_version: str | None = None,
) -> GuidedReading:
    """河切片 → 带读对象。纯函数：不读盘、不调模型、同一输入同一输出。

    入参是 ``RiverSlice.to_dict()`` 的形状，不直接吃 ``RiverSlice``——带读要能被
    回放器喂历史 JSON，绑死对象会把「从收据重建当日带读」这条路堵死。
    """
    tracks = slice_dict.get("tracks") or {}
    facts: dict[str, list[str]] = {}
    gaps: list[str] = []
    present: list[str] = []

    for track in sorted(tracks):
        value = tracks[track]
        if isinstance(value, dict) and value.get("gap"):
            detail = str(value.get("detail") or "").strip()
            gaps.append(f"{track}：{value.get('reason')}" + (f"（{detail}）" if detail else ""))
            continue
        objs = value if isinstance(value, list) else []
        if not objs:
            gaps.append(f"{track}：empty（读取面返回空列表，按缺口处理，不当作「没变化」）")
            continue
        facts[track] = _fact_lines(objs)
        present.append(track)

    pit_grade = str(slice_dict.get("pit_grade") or "trade_date_only")
    limits: list[str] = []
    if pit_grade != "strict":
        limits.append(
            f"pit_grade={pit_grade}：切片里有对象缺 recorded_at，可用于当日带读，"
            "但不能进回放与方法校准"
        )
    # 缺省从切片自己读：调用方漏传就丢掉换源警告，是「限定语被静默吃掉」的老形状。
    if alias_applied if alias_applied is not None else bool(slice_dict.get("alias_applied")):
        limits.append("alias_applied=true：实体身份跨供应商归一过，跨换源日的数值不可直接比较")
    if not present:
        limits.append("六轨全缺：本日无可读对象，带读只报缺口")

    draft = _draft_script(slice_dict, present, framework_version=framework_version) if present else None
    return GuidedReading(
        as_of=str(slice_dict.get("as_of") or ""),
        entity_id=str(slice_dict.get("entity_id") or ""),
        entity_name=str(slice_dict.get("entity_name") or ""),
        knowledge_cutoff=str(slice_dict.get("knowledge_cutoff") or ""),
        pit_grade=pit_grade,
        facts=facts,
        limits=limits,
        gaps=gaps,
        draft=draft,
    )


def _draft_script(
    slice_dict: dict[str, Any], present: list[str], *, framework_version: str | None
) -> observation_script.ObservationScript:
    """按「哪几条轨读得出来」生成剧本骨架，状态 ``drafted``。

    骨架不是判读：变量与放弃条件只说「哪条轨的什么对象要复看」，不说该怎么做。
    用户确认前它没有任何效力——``drafted`` 不进回检队列、不进校准。
    """
    entity_id = str(slice_dict.get("entity_id") or "")
    scope = "index" if entity_id.upper().startswith("SH0") or entity_id in {"上证指数", "全市场"} else "theme"
    variables = [_TRACK_VARIABLES[t] for t in present if t in _TRACK_VARIABLES]
    abandon = [_TRACK_ABANDON[t] for t in present if t in _TRACK_ABANDON]
    return observation_script.make(
        as_of=str(slice_dict.get("as_of") or ""),
        scope=scope,
        entity_ids=[slice_dict.get("entity_name") or entity_id],
        variables=variables,
        downgrade_or_abandon_conditions=abandon,
        evidence_refs=[
            o.get("ref")
            for track in present
            for o in (slice_dict.get("tracks") or {}).get(track, [])
            if isinstance(o, dict) and o.get("ref")
        ],
        knowledge_cutoff=str(slice_dict.get("knowledge_cutoff") or "") or None,
        framework_version=framework_version,
        scope_note="由数据面派生的骨架，待用户改写；未经授课框架判读",
        status="drafted",
    )


def render(gr: GuidedReading) -> str:
    """人类可读带读。段序固定：事实 → 限制 → 缺口 → 待确认剧本。"""
    lines = [
        f"# 今日带读｜{gr.entity_name or gr.entity_id}｜{gr.as_of}",
        f"（knowledge_cutoff={gr.knowledge_cutoff}｜pit_grade={gr.pit_grade}）",
        "",
        "## 事实（逐轨，只搬不解释）",
    ]
    if gr.facts:
        for track in sorted(gr.facts):
            lines.append(f"- **{track}**")
            lines += [f"  - {line}" for line in gr.facts[track]]
    else:
        lines.append("- （无）")

    lines += ["", "## 判读", "- 待授课框架 v0（G-01）落地；母本由人写，此处不生成推断。"]
    lines += ["", "## 限制"]
    lines += [f"- {x}" for x in gr.limits] or ["- （无）"]
    lines += ["", "## 缺口（缺轨不用别的轨补）"]
    lines += [f"- {x}" for x in gr.gaps] or ["- （无）"]

    lines += ["", "## 明天要看什么（待你确认 / 修改 / 跳过）"]
    if gr.draft:
        lines += [f"- 变量：{v}" for v in gr.draft.variables]
        lines += [f"- 降级或放弃：{c}" for c in gr.draft.downgrade_or_abandon_conditions]
        lines.append(f"- {observation_script.DISCLAIMER}")
    else:
        lines.append("- 本日无可读对象，不生成剧本骨架。")
    return "\n".join(lines)


def run(
    us: Any,
    slice_dict: dict[str, Any],
    *,
    override: bool | None = None,
    alias_applied: bool | None = None,
    framework_version: str | None = None,
) -> tuple[GuidedReading | None, str]:
    """开关 + 构建。关闭时返回 ``(None, 理由)``，**不做任何读写**。"""
    enabled, reason = resolve_enabled(us, override=override)
    if not enabled:
        return None, reason
    return build(slice_dict, alias_applied=alias_applied, framework_version=framework_version), reason


def lint_output(text: str) -> list[compliance_gate.Hit]:
    """带读产物的用词 lint（G-12a）：产品语言里不许出现「策略」「第二天的方向」等。"""
    return compliance_gate.scan(
        text, codes=compliance_gate.OBSERVATION_SCRIPT_CODES + (compliance_gate.E_STRATEGY_WORD,)
    )
