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

from intelligence.services import compliance_gate, observation_script, river_projection

ENV_FLAG = "FORESIGHT_GUIDED_READING"

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


def build(
    slice_dict: dict[str, Any],
    *,
    alias_applied: bool | None = None,
    framework_version: str | None = None,
) -> GuidedReading:
    """河切片 → 带读对象。纯函数：不读盘、不调模型、同一输入同一输出。

    入参是 ``RiverSlice.to_dict()`` 的形状，不直接吃 ``RiverSlice``——带读要能被
    回放器喂历史 JSON，绑死对象会把「从收据重建当日带读」这条路堵死。

    选什么、省什么、限制与缺口由投影决定；本函数只把投影块按轨归拢成可渲染的行。
    """
    # 缺省从切片自己读：调用方漏传就丢掉换源警告，是「限定语被静默吃掉」的老形状。
    # 显式传了就以显式为准——投影读的是切片，所以这里把显式值写回切片副本再投影。
    source = dict(slice_dict)
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
    scope = "index" if entity_id.upper().startswith("SH0") or entity_id in {"上证指数", "全市场"} else "theme"
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


def render(gr: GuidedReading) -> str:
    """人类可读带读。段序固定：限制 → 缺口 → 事实 → 判读 → 待确认剧本。

    限制与缺口排在事实之前是 09-06 spec §4.5 第 2 条：缺口是判读的边界条件，不是脚注。
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

    lines += ["", "## 判读", "- 待授课框架 v0（G-01）落地；母本由人写，此处不生成推断。"]

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


def merge_into_daily_review(text: str, gr: GuidedReading | None) -> str:
    """把带读并进每日复盘正文。**关闭时原样返回同一个对象**。

    这条 ``is`` 级别的等价是刻意的：spec / roadmap 要求「关掉带读 = 现有行为逐字节不变」。
    只做 ``==`` 相等还留着「重新拼一遍恰好拼回原样」的余地，那种实现一旦哪天多加一个
    换行，验收就悄悄不成立了。返回同一个对象，改动无处藏身。
    """
    if gr is None:
        return text
    body = text or ""
    section = render(gr)
    if section in body:  # 幂等：重复合并不叠加
        return body
    return (body.rstrip("\n") + "\n\n" + section + "\n") if body else section + "\n"


def build_for_daily_review(
    report: dict[str, Any],
    us: Any,
    *,
    override: bool | None = None,
    db_path: str | Path | None = None,
) -> tuple[GuidedReading | None, str]:
    """每日复盘用的带读。返回 ``(带读 | None, 理由)``——关闭或挑不出实体都返回 None。

    ``import river`` 放函数里：本模块其余部分不碰数据库，保持可离线单测。
    """
    enabled, reason = resolve_enabled(us, override=override)
    if not enabled:
        return None, reason
    entity = pick_entity(report)
    if not entity:
        return None, "report 里挑不出可带读的题材（logic_batch.results 为空或无题材名）"
    as_of = str((report or {}).get("date") or "").strip()
    if not as_of:
        return None, "report 没有 date，无法定 as_of"

    from intelligence.services import river

    try:
        sl = river.slice_river(as_of, entity, db_path=db_path, checkpoints_path=us.checkpoints_path)
    except Exception as exc:  # 读不到就不出这一段，不让带读把整份复盘带崩
        return None, f"切片读取失败：{type(exc).__name__}: {exc}"
    return build(sl.to_dict(), framework_version=None), f"带读 {entity}（{reason}）"


def lint_output(text: str) -> list[compliance_gate.Hit]:
    """带读产物的用词 lint（G-12a）：产品语言里不许出现「策略」「第二天的方向」等。"""
    return compliance_gate.scan(
        text, codes=compliance_gate.OBSERVATION_SCRIPT_CODES + (compliance_gate.E_STRATEGY_WORD,)
    )
