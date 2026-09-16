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
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from intelligence.services import (
    compliance_gate,
    observation_extraction as extraction,
    observation_script,
    river_projection,
)

ENV_FLAG = "FORESIGHT_GUIDED_READING"
# 授课框架旁路库（scripts/teaching_framework.py 的 --labels-db）。给了才读教学标签、才出「授课框架读数」
# 一段与上证卡片；不给 = 现状，逐字节不变（G-03 (d)、G-01 (b)）。显式参数 > 环境变量 > 不接。
ENV_TEACHING_DB = "FORESIGHT_TEACHING_LABELS_DB"
TEACHING_CARD_SUFFIX = "-teaching-card.svg"

# 带读是投影的一个消费方（工单 #34 / 09-06 spec §4.5）：选什么、省什么、限制与缺口全部由
# ``river_projection.project`` 决定并哈希，本模块只渲染。``task`` 是投影的输入之一——同一切片
# 给不同任务投影得到不同哈希，是设计不是 bug。v0 不限块数：带读今天渲染全部对象，只在
# 每对象显示键数上做渲染层的省略（不影响哈希）。
PROJECTION_TASK = "guided_reading"
PROJECTION_BUDGET: int | None = None
# 数据面派生的骨架没有模型参与；台账要 model_id 时填这个，不填空——空会被当成「忘了」。
DETERMINISTIC_MODEL_ID = "deterministic"

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
    # 这份带读是从哪一片投影渲染出来的。回放时用它重算投影、对账「当时看到了什么」。
    projection_hash: str | None = None
    omitted: dict[str, int] = field(default_factory=dict)
    # 授课框架读数（只摆读数不下结论，不出名单）与上证卡片的相对路径；没接旁路库时都是空。
    # 它们不进投影块（v0 的投影只收六轨事实对象；G-01 规则成为选择器后再进 blocks 并标 selected_by）。
    teaching: list[str] = field(default_factory=list)
    teaching_card: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of,
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "knowledge_cutoff": self.knowledge_cutoff,
            "pit_grade": self.pit_grade,
            "projection_hash": self.projection_hash,
            "omitted": self.omitted,
            "facts": self.facts,
            "limits": self.limits,
            "gaps": self.gaps,
            "draft": self.draft.to_dict() if self.draft else None,
            "teaching": self.teaching,
            "teaching_card": self.teaching_card,
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


def resolve_teaching_db(override: str | Path | None = None) -> Path | None:
    """授课框架旁路库：显式参数 > 环境变量 > None（不接）。路径不存在按没接处理，不抛——带读不该因它崩。"""
    raw = str(override or os.environ.get(ENV_TEACHING_DB) or "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    return path if path.is_file() else None


# --------------------------------------------------------------------------- #
# 构建：切片 → 投影 → 带读
# --------------------------------------------------------------------------- #
def project_slice(
    slice_dict: dict[str, Any], *, framework_version: str | None = None
) -> river_projection.ContextProjection:
    """带读用的投影。参数钉死（task / budget），保证同一切片两次得到同一个哈希。"""
    return river_projection.project(
        slice_dict,
        framework_version=framework_version,
        task=PROJECTION_TASK,
        budget=PROJECTION_BUDGET,
    )


def _is_teaching(obj: dict[str, Any]) -> bool:
    return str(obj.get("object_type") or "").startswith("teaching_")


def build(
    slice_dict: dict[str, Any],
    *,
    alias_applied: bool | None = None,
    framework_version: str | None = None,
    teaching_card: str | None = None,
) -> GuidedReading:
    """河切片 → 带读对象。纯函数：不读盘、不调模型、同一输入同一输出。

    入参是 ``RiverSlice.to_dict()`` 的形状，不直接吃 ``RiverSlice``——带读要能被
    回放器喂历史 JSON，绑死对象会把「从收据重建当日带读」这条路堵死。

    选什么、省什么、限制与缺口由投影决定；本函数只把投影块按轨归拢成可渲染的行。

    切片里若有 ``teaching_*`` 对象（``slice_river`` 接了授课框架旁路库才有），它们不进逐轨事实、
    不进投影（v0 投影只收六轨事实对象），单独换成「授课框架读数」的句子（只摆读数、不出名单）；
    没有就没有这一段，其余逐字节同前。
    """
    tracks = slice_dict.get("tracks") or {}
    teaching_objs: list[dict[str, Any]] = []
    market = tracks.get("market")
    if isinstance(market, list) and any(_is_teaching(o) for o in market):
        teaching_objs = [o for o in market if _is_teaching(o)]
        tracks = {**tracks, "market": [o for o in market if not _is_teaching(o)]}
    teaching: list[str] = []
    if teaching_objs:
        from intelligence.services.teaching_framework.reading import teaching_lines

        teaching = teaching_lines(teaching_objs)

    # 缺省从切片自己读：调用方漏传就丢掉换源警告，是「限定语被静默吃掉」的老形状。
    # 显式传了就以显式为准——投影读的是切片，所以这里把显式值写回切片副本再投影。
    source = {**slice_dict, "tracks": tracks}
    if alias_applied is not None:
        source["alias_applied"] = bool(alias_applied)
    cp = project_slice(source, framework_version=framework_version)

    facts: dict[str, list[str]] = {}
    for block in cp.blocks:
        facts.setdefault(block.track, []).extend(line for line in block.rendered_text.split("\n") if line)
    present = [t for t in facts]

    draft = _draft_script(source, present, cp, framework_version=framework_version) if present else None
    return GuidedReading(
        as_of=str(source.get("as_of") or ""),
        entity_id=str(source.get("entity_id") or ""),
        entity_name=str(source.get("entity_name") or ""),
        knowledge_cutoff=str(source.get("knowledge_cutoff") or ""),
        pit_grade=str(source.get("pit_grade") or "trade_date_only"),
        facts=facts,
        limits=list(cp.limits),
        gaps=list(cp.gaps),
        draft=draft,
        projection_hash=cp.projection_hash,
        omitted=dict(cp.omitted),
        teaching=teaching,
        teaching_card=teaching_card if teaching else None,
    )


def _draft_script(
    slice_dict: dict[str, Any],
    present: list[str],
    cp: river_projection.ContextProjection,
    *,
    framework_version: str | None,
) -> observation_script.ObservationScript:
    """按「哪几条轨读得出来」生成剧本骨架，状态 ``drafted``。

    骨架不是判读：变量与放弃条件只说「哪条轨的什么对象要复看」，不说该怎么做。
    用户确认前它没有任何效力——``drafted`` 不进回检队列、不进校准。

    ``evidence_refs`` 取**投影选中的** ref 而不是切片里的全部 ref：骨架引用的证据就是
    读者当时看到的那些，两者一旦分叉，``projection_hash`` 对账就对不上。
    """
    entity_id = str(slice_dict.get("entity_id") or "")
    # 作用域推导与提取关联键共用同一个函数：两处各写一遍，迟早一处改了另一处没改，
    # 而漂了的那天表现是「你写的草稿凭空不见了」，不是报错。
    scope = extraction.scope_for(entity_id)
    variables = [_TRACK_VARIABLES[t] for t in present if t in _TRACK_VARIABLES]
    abandon = [_TRACK_ABANDON[t] for t in present if t in _TRACK_ABANDON]
    return observation_script.make(
        as_of=str(slice_dict.get("as_of") or ""),
        scope=scope,
        entity_ids=[slice_dict.get("entity_name") or entity_id],
        variables=variables,
        downgrade_or_abandon_conditions=abandon,
        evidence_refs=list(cp.selected_refs),
        knowledge_cutoff=str(slice_dict.get("knowledge_cutoff") or "") or None,
        framework_version=framework_version,
        scope_note="由数据面派生的骨架，待用户改写；未经授课框架判读",
        status="drafted",
        # 从切片继承：事后视角的切片派生出的剧本，同样不得进校准（spec §4.1）。
        # 这一跳断了，下游 checkpoint 与 calibrate 就再也看不到这个事实。
        hindsight=bool(slice_dict.get("hindsight")),
        projection_hash=cp.projection_hash,
        model_id=DETERMINISTIC_MODEL_ID,
    )


def render(gr: GuidedReading, *, diff_lines: list[str] | None = None) -> str:
    """人类可读带读。段序固定：限制 → 缺口 → 事实 → 判读 → 待确认剧本 → 字段差异。

    限制与缺口排在事实之前是 09-06 spec §4.5 第 2 条：缺口是判读的边界条件，不是脚注。

    ``diff_lines`` 给了就在末尾追加「你写的 vs 系统列的」一段（工单 #53 §2.5）。
    差异排在**最后**：它是对照，不是判读——放前面会让人以为系统那份是标准答案。
    """
    lines = [
        f"# 今日带读｜{gr.entity_name or gr.entity_id}｜{gr.as_of}",
        f"（knowledge_cutoff={gr.knowledge_cutoff}｜pit_grade={gr.pit_grade}｜projection={gr.projection_hash or 'none'}）",
        "",
        "## 限制",
    ]
    lines += [f"- {x}" for x in gr.limits] or ["- （无）"]
    lines += ["", "## 缺口（缺轨不用别的轨补）"]
    lines += [f"- {x}" for x in gr.gaps] or ["- （无）"]

    lines += ["", "## 事实（逐轨，只搬不解释；轨序 = 盘面 → 题材 → 舆论 → 资金 → 个股 → 判断）"]
    if gr.facts:
        for track, fact_lines in gr.facts.items():
            lines.append(f"- **{track}**")
            lines += [f"  - {line}" for line in fact_lines]
    else:
        lines.append("- （无）")
    if gr.omitted:
        lines.append("- 未进上下文（按块整体省略，不截断）：" + "，".join(f"{t}×{n}" for t, n in gr.omitted.items()))

    if gr.teaching:
        lines += ["", "## 授课框架读数（只摆读数，不下结论；不出名单）"]
        lines += [f"- {x}" for x in gr.teaching]
        if gr.teaching_card:
            lines.append(f"- 卡片：![上证指数 · 授课框架读数]({gr.teaching_card})")

    lines += ["", "## 判读", "- 待授课框架 v0（G-01）落地；母本由人写，此处不生成推断。"]

    lines += ["", "## 明天要看什么（待你确认 / 修改 / 跳过）"]
    if gr.draft:
        lines += [f"- 变量：{v}" for v in gr.draft.variables]
        lines += [f"- 降级或放弃：{c}" for c in gr.draft.downgrade_or_abandon_conditions]
        lines.append(f"- {observation_script.DISCLAIMER}")
    else:
        lines.append("- 本日无可读对象，不生成剧本骨架。")
    if diff_lines is not None:
        lines += ["", DIFF_SECTION_TITLE]
        lines += list(diff_lines)
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


# --------------------------------------------------------------------------- #
# 提取前置：先收用户自己的剧本，再披露系统骨架（工单 #53）
# --------------------------------------------------------------------------- #
DIFF_SECTION_TITLE = "## 你写的 vs 系统列的（只列字段差异；不评分、不判谁对）"
# 日报里「无草稿」时放的入口提示。它替代整段带读，所以自己也得过用词 lint
# （测试锁死）——提示语里出现方向词，等于在提示位置把产品红线破了。
EXTRACTION_HINT_LINES = (
    "- 今天先写下**你自己**要看什么，再看系统那份；系统这份不是标准答案，只用来对照你漏了什么。",
    "- 提交：`python3 -m intelligence.cli observation draft --as-of <交易日> --entity <板块或题材>"
    " --variable <要观察的变量> --abandon <降级或放弃条件>`",
    "- 写完再跑一次本日报，这里会出现带读与字段差异。",
    "- 确实不想写：`observation read --as-of <交易日> --entity <板块或题材> --skip-draft`——"
    "跳过是有效行为，不计失败。",
)


@dataclass(frozen=True)
class GatedReading:
    """一次「提取门 + 带读」的完整结果。门没过时 ``guided`` 是 ``None``。"""

    decision: extraction.Decision
    reason: str
    guided: GuidedReading | None = None
    diff: list[dict[str, Any]] = field(default_factory=list)
    # 有没有可比较的系统骨架。``comparable=False`` 时差异恒为 ``[]``，
    # 渲染成「本次无可比较剧本」而**不是**「完全一致」——没得比不等于一致。
    comparable: bool = False
    system_script_ref: str | None = None

    @property
    def diff_lines(self) -> list[str]:
        return extraction.render_diff(self.diff, comparable=self.comparable)

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.decision.to_dict(),
            "reason": self.reason,
            "comparable": self.comparable,
            "system_script_ref": self.system_script_ref,
            "diff": self.diff,
        }


def gated(
    us: Any,
    slice_dict: dict[str, Any],
    *,
    key: extraction.ExtractionKey,
    override: bool | None = None,
    skip_draft: bool = False,
    records: list[dict[str, Any]] | None = None,
    alias_applied: bool | None = None,
    framework_version: str | None = None,
    teaching_card: str | None = None,
    on_skip: Callable[[], None] | None = None,
) -> GatedReading:
    """**共用入口门**：开关 → 提取资格 → 构建 → 差异。CLI 与日报都走这一条。

    门没过时 ``build`` 根本不会被调用——系统骨架不生成、不输出、不登记。

    本函数自己不写台账；``on_skip`` 是调用方传进来的落盘动作，**在 ``build`` 之前**
    被调用。把这个顺序放进共用门而不是交给每个调用方自觉：「先记跳过、再生成骨架」
    一旦靠约定维持，总有一个入口会把两行写反，而写反了从输出上看不出来。

    为什么门要放在 ``build`` 之前而不是渲染之前：``build`` 出来的对象已经是系统的
    答案，只要它存在，任何一个 ``--json`` 分支、日志或异常回显都可能把它漏出去。
    不生成，才是真的不泄漏。
    """
    enabled, enabled_reason = resolve_enabled(us, override=override)
    raw = records if records is not None else observation_script.load_raw(
        getattr(us, "observation_scripts_path", "")
    )
    draft = observation_script.latest_user_draft(raw, key=key)
    decision = extraction.decide(
        enabled=enabled, enabled_reason=enabled_reason, draft=draft, skip_draft=skip_draft
    )
    if not decision.allowed:
        return GatedReading(decision=decision, reason=decision.reason)
    if decision.needs_skip_event and on_skip is not None:
        on_skip()

    gr = build(
        slice_dict,
        alias_applied=alias_applied,
        framework_version=framework_version,
        teaching_card=teaching_card,
    )
    system = gr.draft.to_dict() if gr.draft else None
    return GatedReading(
        decision=decision,
        reason=f"{decision.reason}（{enabled_reason}）",
        guided=gr,
        diff=extraction.diff_scripts(decision.draft, system),
        comparable=system is not None and decision.draft is not None,
        system_script_ref=extraction.system_script_ref(system, key=key),
    )


# --------------------------------------------------------------------------- #
# 接进每日复盘
# --------------------------------------------------------------------------- #
DAILY_SECTION_TITLE = "## 今日带读"


def pick_entity(report: dict[str, Any]) -> str | None:
    """从 daily-agent report 里确定性地挑出「今天带读读哪个题材」。

    取 ``logic_batch.results`` 里 ``priority_score`` 最高的那条的题材名；
    同分按名字升序断连——**排序键必须确定**，否则同一份 report 两次渲染出不同的带读，
    「同一切片两次读取结构化结果一致」那条验收就会假绿。

    挑不出来返回 ``None``：宁可不出这一段，也不要随便找个题材凑数。
    """
    results = ((report or {}).get("logic_batch") or {}).get("results") or []
    cands: list[tuple[float, str]] = []
    for r in results:
        if not isinstance(r, dict):
            continue
        name = str(r.get("market_theme") or r.get("matched_theme") or "").strip()
        if not name:
            continue
        try:
            score = float(r.get("priority_score") or 0)
        except (TypeError, ValueError):
            score = 0.0
        cands.append((score, name))
    if not cands:
        return None
    return sorted(cands, key=lambda x: (-x[0], x[1]))[0][1]


def merge_into_daily_review(
    text: str,
    gr: GuidedReading | None,
    *,
    hint: bool = False,
    diff_lines: list[str] | None = None,
) -> str:
    """把带读并进每日复盘正文。**关闭时原样返回同一个对象**。

    这条 ``is`` 级别的等价是刻意的：spec / roadmap 要求「关掉带读 = 现有行为逐字节不变」。
    只做 ``==`` 相等还留着「重新拼一遍恰好拼回原样」的余地，那种实现一旦哪天多加一个
    换行，验收就悄悄不成立了。返回同一个对象，改动无处藏身。

    ``hint=True``（带读开着、但用户今天还没写自己的剧本）时，在**带读原本那个位置**
    放一段入口提示，其余正文一字不动：夜跑不能等 stdin，也不能替用户记跳过 / 离开。
    ``gr is None and not hint`` 仍然返回同一个对象——带读关闭那条验收不受影响。
    """
    if gr is None and not hint:
        return text
    body = text or ""
    section = (
        "\n".join([DAILY_SECTION_TITLE, *EXTRACTION_HINT_LINES])
        if gr is None
        else render(gr, diff_lines=diff_lines)
    )
    if section in body:  # 幂等：重复合并不叠加
        return body
    return (body.rstrip("\n") + "\n\n" + section + "\n") if body else section + "\n"


@dataclass(frozen=True)
class DailySection:
    """每日复盘「今日带读」那个位置该放什么。

    三种可能：整段带读（``guided``）、一段入口提示（``hint``）、什么都不放。
    第三种必须存在——带读关闭时那一段连提示都不该出现，否则「逐字节不变」就破了。
    """

    guided: GuidedReading | None
    reason: str
    hint: bool = False
    gate: GatedReading | None = None

    @property
    def diff_lines(self) -> list[str] | None:
        return self.gate.diff_lines if (self.gate and self.guided) else None


def daily_section(
    report: dict[str, Any],
    us: Any,
    *,
    override: bool | None = None,
    db_path: str | Path | None = None,
    teaching_labels_db: str | Path | None = None,
    card_dir: str | Path | None = None,
) -> DailySection:
    """每日复盘的带读接缝，**走同一道提取门**。

    ``import river`` 放函数里：本模块其余部分不碰数据库，保持可离线单测。

    ``teaching_labels_db`` 给了（经 ``resolve_teaching_db`` 解析）才接授课框架：切片多出 ``teaching_*``
    对象、带读多一段读数；再给 ``card_dir`` 就把上证卡片写成 ``<as_of>-teaching-card.svg``——这是本函数
    唯一的写盘，且只在带读开启且旁路库接上时发生。两者都不给 = 现状。

    顺序是「先取切片、再过提取门」而不是反过来：取切片是读事实，不是生成系统骨架；
    而身份要从切片里读（切片已经做过跨供应商归一），提前解析等于开两次库。
    """
    enabled, reason = resolve_enabled(us, override=override)
    if not enabled:
        return DailySection(None, reason)
    entity = pick_entity(report)
    if not entity:
        return DailySection(None, "report 里挑不出可带读的题材（logic_batch.results 为空或无题材名）")
    as_of = str((report or {}).get("date") or "").strip()
    if not as_of:
        return DailySection(None, "report 没有 date，无法定 as_of")

    from intelligence.services import river

    teaching_db = resolve_teaching_db(teaching_labels_db)
    try:
        sl = river.slice_river(
            as_of, entity, db_path=db_path, checkpoints_path=us.checkpoints_path, teaching_labels_db=teaching_db,
        )
    except Exception as exc:  # 读不到就不出这一段，不让带读把整份复盘带崩
        return DailySection(None, f"切片读取失败：{type(exc).__name__}: {exc}")
    slice_dict = sl.to_dict()
    canonical = extraction.identity_from_slice(slice_dict)
    if canonical is None:
        return DailySection(None, f"「{entity}」在 {as_of} 解析不出实体身份，不出这一段")
    card_name: str | None = None
    if teaching_db is not None and card_dir is not None:
        card_name = write_teaching_card(teaching_db, as_of, slice_dict, Path(card_dir) / f"{as_of}{TEACHING_CARD_SUFFIX}")
    tail = "，授课框架读数已接" if teaching_db is not None else ""

    gate = gated(
        us,
        slice_dict,
        key=extraction.make_key(getattr(us, "user_id", "default"), as_of, canonical),
        override=override,
        # 日报是无人值守的后台产物：**不能替用户跳过**。没有草稿就放入口提示，
        # 不写任何事件、不创建尝试——后台跑过一次不证明用户进过这个页面。
        skip_draft=False,
        teaching_card=card_name,
    )
    if gate.guided is None:
        return DailySection(None, f"带读 {entity} 未披露（{gate.reason}）", hint=True, gate=gate)
    return DailySection(gate.guided, f"带读 {entity}（{reason}{tail}）", gate=gate)


def build_for_daily_review(
    report: dict[str, Any],
    us: Any,
    *,
    override: bool | None = None,
    db_path: str | Path | None = None,
    teaching_labels_db: str | Path | None = None,
    card_dir: str | Path | None = None,
) -> tuple[GuidedReading | None, str]:
    """``daily_section`` 的 ``(带读 | None, 理由)`` 视图（既有调用方与回归测试用）。

    新代码请用 ``daily_section``：入口提示与字段差异只在那边拿得到。
    """
    section = daily_section(
        report,
        us,
        override=override,
        db_path=db_path,
        teaching_labels_db=teaching_labels_db,
        card_dir=card_dir,
    )
    return section.guided, section.reason


def write_teaching_card(teaching_db: str | Path, as_of: str, slice_dict: dict[str, Any], out_path: Path) -> str | None:
    """把上证卡片写到 ``out_path``；切片里没有教学对象就不写、返回 None。返回写出的文件名（相对复盘产物目录）。"""
    from intelligence.services.teaching_framework.reading import index_card_svg, teaching_lines

    market = (slice_dict.get("tracks") or {}).get("market")
    objs = [o for o in (market if isinstance(market, list) else []) if _is_teaching(o)]
    if not objs:
        return None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(index_card_svg(teaching_db, as_of, teaching_lines(objs)), encoding="utf-8")
    return out_path.name


def lint_output(text: str) -> list[compliance_gate.Hit]:
    """带读产物的用词 lint（G-12a）：产品语言里不许出现「策略」「第二天的方向」等。"""
    return compliance_gate.scan(
        text, codes=compliance_gate.OBSERVATION_SCRIPT_CODES + (compliance_gate.E_STRATEGY_WORD,)
    )
