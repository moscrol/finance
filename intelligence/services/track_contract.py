"""题材跟踪表达契约（slice 4）：delta-only + 观点四态对照 + 结论 TTL + 下期关注。

背景（knevo q8 蒸馏的回灌）：
    knevo finance-industry-track 的核心是「上期基线为锚，只报变化」的 delta-only
    跟踪契约：观点四态对照（支持/削弱/无变化/信息不足）、观点有效期（TTL）、
    「下期关注 + 触发条件」作为下一轮输入形成自衔接链。本仓的 theme_track 路由
    已有检索与模板，但输出没有这三件纪律——跟踪题容易被答成一次性全景重跑。

设计（沿 scenario_tree 的表达层模式，零取数）：
    - 这是**表达层模板**（注入 synthesis prompt 的格式契约），不是数据块：
      不新增证据、不改证据链，只约束输出组织方式。
    - **确定性意图路由**：问题类型为 theme_track，或命中「跟踪/近况/新变化/
      自上次」类词面才注入；普通问答不注入，行为不变。
    - 四态对照的「上期结论」来源是 [M]（用户记忆）与 [V]（回检）块——没有
      相关记录时必须显式声明「无上期基线，本期建立基线」，禁止虚构上期结论。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import re

# 跟踪类词面：持续性 + 增量性表述。刻意不收「最近怎么样」这类泛化问法——
# 它们既可能是跟踪也可能是首次全景，由 route/question_type 判定兜底。
_TRACK_TERMS = (
    "跟踪",
    "追踪",
    "近况",
    "新变化",
    "有什么变化",
    "最新进展",
    "进展如何",
    "自上次",
    "上次之后",
    "相比上次",
    "更新一下",
    "有没有新",
)


def parse_track_intent(query: str, question_type: str | None = None) -> bool:
    """问题类型为 theme_track，或命中跟踪/增量词面即触发。"""
    if question_type == "theme_track":
        return True
    text = re.sub(r"\s+", "", str(query or ""))
    if not text:
        return False
    return any(term in text for term in _TRACK_TERMS)


def build_track_guidance() -> str:
    """跟踪表达契约（注入 synthesis prompt；确定性文本，无取数）。"""
    return "\n".join(
        [
            "## 跟踪表达契约（本题为持续跟踪类问题，回答必须按此结构组织）",
            "1. **delta-only 纪律**：以上期基线为锚只报有信息量的变化；上期结论仍成立的项"
            "写一句「无变化」即可，禁止重跑全景模板凑字数。上期基线取 [M]（用户既有判断）与"
            " [V]（回检记录）块；两块都无相关记录时，开头显式声明「无上期基线，本期建立基线」，"
            "禁止虚构或臆测上期说过什么。",
            "2. **观点四态对照**：对 [M]/[V] 中每条相关既有判断给显式判定——"
            "「支持 / 削弱 / 无变化 / 信息不足」四态之一，判定后必须紧跟本轮证据编号"
            "（如 [D0]/[D6]/[W7]/[L1-x]）；没有证据支撑的判定只能写「信息不足」。",
            "3. **结论 TTL**：本期每条新结论标注有效期「复核期限：YYYY-MM-DD」——"
            "跟踪级结论默认 30 天、框架级结论默认 90 天；到期未复核视为待复核，"
            "不得在后续轮次当作已验证事实引用。",
            "4. **下期关注清单**（结尾必给）：每项 = 指标/事件 + 时间节点 + 触发条件"
            "（可观察、可证伪，如「若 X 月中报毛利率 <Y% 则削弱扩产逻辑」），"
            "作为下一轮跟踪开头的强制对照输入；禁止「持续关注市场情绪」这类不可证伪表述。",
            "5. 数据缺口照常显式声明；跟踪不改变证据纪律——变化必须来自本轮检索块，"
            "不得由「距上次隔了很久」推断「肯定有变化」。",
        ]
    )


def build_track_guidance_for_episode() -> str:
    """episode 主路径版跟踪契约——纪律同 :func:`build_track_guidance`，术语换血。

    legacy 版的「上期基线」指向 [M]/[V] 检索块、证据引用用 [D0]/[W7] 编号——
    这些是 ask_synthesis 路径的记号，episode 里不存在：episode 的记忆通道是
    memory_lookup 工具、证据纪律是 evidence_hash 绑定。原样注入会让模型对照
    一个不存在的块。两版共存于本模块（单一真本源），改纪律要两边一起动。
    """
    return "\n".join(
        [
            "【跟踪表达契约】本题为持续跟踪类问题，draft 必须按此结构组织：\n"
            "1. delta-only 纪律：以上期基线为锚只报有信息量的变化；上期结论仍成立的项"
            "写一句「无变化」即可，禁止重跑全景模板凑字数。上期基线只能来自 "
            "memory_lookup 召回的用户既有判断或 conversation_context 里的先前结论；"
            "两处都无相关记录时，draft 开头显式声明「无上期基线，本期建立基线」，"
            "禁止虚构或臆测上期说过什么。\n"
            "2. 观点四态对照：对每条召回的既有判断给显式判定——"
            "「支持 / 削弱 / 无变化 / 信息不足」四态之一；判定必须由本轮 evidence "
            "支撑并进入对应 binding，没有证据支撑的判定只能写「信息不足」。\n"
            "3. 结论 TTL：本期每条新结论标注「复核期限：YYYY-MM-DD」——跟踪级默认 "
            "30 天、框架级默认 90 天；到期未复核视为待复核，不得当作已验证事实引用。\n"
            "4. 下期关注清单（draft 结尾必给）：每项 = 指标/事件 + 时间节点 + 触发条件"
            "（可观察、可证伪，如「若 X 月中报毛利率 <Y% 则削弱扩产逻辑」）；"
            "禁止「持续关注市场情绪」这类不可证伪表述。\n"
            "5. 跟踪不改变证据纪律：变化必须来自本轮工具证据，"
            "不得由「距上次隔了很久」推断「肯定有变化」。"
        ]
    )


def track_guidance_for_query(query: str, question_type: str | None = None) -> str:
    """命中意图返回表达契约，否则空串（不注入，行为不变）。"""
    if not parse_track_intent(query, question_type):
        return ""
    return build_track_guidance()


def episode_track_rule(query: str, question_type: str | None = None) -> str:
    """episode 指令的条件注入口：命中跟踪意图返回 episode 版契约，否则空串。"""
    if not parse_track_intent(query, question_type):
        return ""
    return build_track_guidance_for_episode()


# 结构门：prompt 对中转模型约束力有限（2026-08-13 live）。缺段用确定性文本补上，
# 不覆盖模型已写的正文——与 ensure_forecast_scenarios_visible 同一形状。
_QUAD_MARKERS = ("削弱", "无变化", "信息不足", "四态")
_TTL_MARKERS = ("复核期限", "valid_until")
_WATCH_MARKERS = ("下期关注",)
_BASELINE_MARKERS = ("无上期基线",)
CONTRACT_STUB_HEADING = "## 跟踪契约补全（模型未按强制结构输出的段落）"


def missing_contract_elements(answer: str) -> tuple[str, ...]:
    """扫描回答里缺了契约的哪几件。非跟踪题的调用方应先自己判断是否要查。"""
    text = str(answer or "")
    missing: list[str] = []
    has_baseline_decl = any(m in text for m in _BASELINE_MARKERS)
    has_quad = any(m in text for m in _QUAD_MARKERS) or ("支持 /" in text) or ("判定：支持" in text)
    if not has_quad and not has_baseline_decl:
        missing.append("quad_or_baseline")
    if not any(m in text for m in _TTL_MARKERS):
        missing.append("ttl")
    if not any(m in text for m in _WATCH_MARKERS):
        missing.append("next_watch")
    return tuple(missing)


_STUB_LINES = {
    "quad_or_baseline": (
        "- **观点四态对照**：正文未给出「支持 / 削弱 / 无变化 / 信息不足」，"
        "也未声明「无上期基线」。按契约视为信息不足，不得把未对照的旧判断当成仍成立。"
    ),
    "ttl": (
        "- **结论 TTL**：正文未标注「复核期限」。跟踪级默认 30 天、框架级默认 90 天；"
        "到期未复核不得当已验证事实引用。"
    ),
    "next_watch": (
        "- **下期关注清单**：正文未给出「指标 + 时间节点 + 触发条件」。"
        "下一轮跟踪缺少强制对照输入，本期只建立观察、不升格为已验证。"
    ),
}


def append_contract_stub(answer: str, missing: tuple[str, ...]) -> str:
    """把缺件以可见补全段追加到回答末尾；missing 为空则原文返回。"""
    if not missing:
        return str(answer or "")
    lines = [CONTRACT_STUB_HEADING]
    lines.extend(_STUB_LINES[key] for key in missing if key in _STUB_LINES)
    stub = "\n".join(lines)
    body = str(answer or "").rstrip()
    if not body:
        return stub
    disclaimer = "（非投资建议）"
    if body.endswith(disclaimer):
        head = body[: -len(disclaimer)].rstrip()
        return f"{head}\n\n{stub}\n\n{disclaimer}"
    return f"{body}\n\n{stub}"


# —— Q4（bookgap S8）：契约缺件的程序核对——「能程序判定的约束进程序，不堆 prompt」。
# 三件套（四态对照/无基线声明、TTL、下期关注）是可确定检查的输出结构，此前只有
# prompt 约束 + 可见补全段（append_contract_stub），live 遵守不全且缺件不进任何
# 机器可读通道。这里把缺件映射成 ``repair_coordinator.missing_outputs`` 词表里的
# 输出项 id（直接可并入 ``build_repair_goal(missing_outputs=...)`` 的缺口修复环），
# 并给出 EVAL 可读收据。本条只落程序核对与收据（08-13 质检判的 1 档：小补丁+单测）；
# episode 运行时接线是 2 档，且落点 agent_episode/episode_protocol 是在飞保留缝
# （索引 §2 冲突矩阵），归缝持有者。prompt 原文一字不动。
TRACK_CONTRACT_OUTPUT_IDS: dict[str, str] = {
    "quad_or_baseline": "track_quad_or_baseline",
    "ttl": "track_ttl",
    "next_watch": "track_next_watch",
}


def contract_missing_outputs(
    answer: str,
    *,
    query: str = "",
    question_type: str | None = None,
) -> tuple[str, ...]:
    """程序核对：跟踪题的契约缺件 → missing_outputs 词表输出项 id。

    非跟踪意图恒返回空元组（普通问答零改动）。返回值形状与
    ``repair_coordinator.build_repair_goal(missing_outputs=...)`` 兼容。
    """
    if not parse_track_intent(query, question_type):
        return ()
    return tuple(
        TRACK_CONTRACT_OUTPUT_IDS[key]
        for key in missing_contract_elements(answer)
        if key in TRACK_CONTRACT_OUTPUT_IDS
    )


def contract_receipt(
    answer: str,
    *,
    query: str = "",
    question_type: str | None = None,
) -> dict[str, object]:
    """EVAL 可读收据：``missing_outputs`` 字段恒在场（空列表 = 契约齐/非跟踪题）。

    只含 JSON 原生类型，可直接落 ledger/trace/eval 载荷；``track_intent``
    区分「契约齐」与「本题不适用契约」两种空缺件。
    """
    track_intent = parse_track_intent(query, question_type)
    missing = contract_missing_outputs(
        answer, query=query, question_type=question_type
    )
    return {
        "check": "track_contract",
        "track_intent": track_intent,
        "missing_outputs": list(missing),
    }


# —— P1-E4：下期关注消费端。产出侧已有 prompt + stub；缺口是次日流程不读。
# 只登记可证伪条目到既有 checkpoints.jsonl（不新开台账），foresight 发问时强制对照。
# 补全 stub 本身不是观察项，解析时丢掉。直写 checkpoint 不是 memory_gate 晋升。
NEXT_WATCH_SOURCE = "track_next_watch"
NEXT_WATCH_CATEGORY = "下期关注"
_DATE_RE = re.compile(r"(20\d{2}-\d{2}-\d{2})")
_DAYS_RE = re.compile(r"(\d+)\s*天")
_BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)、])\s+(.+)$")
_FALSIFIABLE_MARKERS = ("若", "则", "低于", "高于", "<", ">", "跌破", "突破", "到期")
_VAGUE_WATCH = ("持续关注市场情绪", "持续关注", "继续观察")


@dataclass(frozen=True)
class NextWatchItem:
    claim: str
    due: str


def _as_of_date(as_of: str | None) -> date:
    raw = str(as_of or "").strip()[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return date.today()


def _item_due(line: str, as_of: str | None) -> str:
    found = _DATE_RE.search(line)
    if found:
        return found.group(1)
    base = _as_of_date(as_of)
    days = _DAYS_RE.search(line)
    if days:
        return (base + timedelta(days=int(days.group(1)))).isoformat()
    return (base + timedelta(days=30)).isoformat()


def _is_registerable_watch(line: str) -> bool:
    text = str(line or "").strip()
    if len(text) < 8:
        return False
    if any(vague in text and "则" not in text for vague in _VAGUE_WATCH):
        return False
    return any(marker in text for marker in _FALSIFIABLE_MARKERS) or bool(
        _DATE_RE.search(text)
    )


def _watch_section_body(answer: str) -> str:
    text = str(answer or "")
    if CONTRACT_STUB_HEADING in text:
        text = text.split(CONTRACT_STUB_HEADING, 1)[0]
    start = -1
    for marker in ("## 下期关注清单", "## 下期关注", "下期关注清单", "下期关注"):
        found = text.find(marker)
        if found >= 0:
            start = found
            break
    if start < 0:
        return ""
    body = text[start:]
    lines = body.splitlines()
    kept: list[str] = []
    for index, line in enumerate(lines):
        if index == 0:
            continue
        if line.startswith("## ") and "下期关注" not in line:
            break
        kept.append(line)
    return "\n".join(kept)


def parse_next_watch_items(
    answer: str, *, as_of: str | None = None
) -> tuple[NextWatchItem, ...]:
    """从跟踪题正文抽出可证伪的下期关注项。忽略契约补全 stub。"""
    items: list[NextWatchItem] = []
    seen: set[str] = set()
    for line in _watch_section_body(answer).splitlines():
        match = _BULLET_RE.match(line)
        claim = (match.group(1) if match else "").strip()
        if not _is_registerable_watch(claim):
            continue
        key = re.sub(r"\s+", "", claim)
        if key in seen:
            continue
        seen.add(key)
        items.append(NextWatchItem(claim=claim, due=_item_due(claim, as_of)))
    return tuple(items)


def ingest_next_watch(
    checkpoints_path: str | Path,
    answer: str,
    *,
    query: str = "",
    question_type: str | None = None,
    as_of: str | None = None,
    theme: str | None = None,
    session_id: str | None = None,
) -> list[dict[str, Any]]:
    """把可证伪的下期关注登记进 checkpoints.jsonl。非跟踪题 / 无条目时空操作。"""
    from intelligence.services.checkpoints import (
        load_checkpoints,
        load_verdicts,
        register_checkpoint,
    )

    if not parse_track_intent(query, question_type):
        return []
    items = parse_next_watch_items(answer, as_of=as_of)
    if not items:
        return []
    path = Path(checkpoints_path).expanduser()
    existing, _ = load_checkpoints(path)
    verdicts, _ = load_verdicts(path.with_name("verdicts.jsonl"))
    open_claims = {
        re.sub(r"\s+", "", str(row.get("claim") or ""))
        for row in open_next_watch_records(existing, verdicts)
    }
    written: list[dict[str, Any]] = []
    themes = [theme] if theme and str(theme).strip() else None
    for item in items:
        key = re.sub(r"\s+", "", item.claim)
        if key in open_claims:
            continue
        _, record = register_checkpoint(
            path,
            claim=item.claim,
            due=item.due,
            category=NEXT_WATCH_CATEGORY,
            source=NEXT_WATCH_SOURCE,
            themes=themes,
            session_id=session_id,
            metric={"type": "manual"},
        )
        open_claims.add(key)
        written.append(record)
    return written


def open_next_watch_records(
    checkpoint_rows: list[dict[str, Any]],
    verdict_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """尚未拿到终态裁决的下期关注条目（到期与未到期都要对照）。"""
    from intelligence.services.checkpoints import TERMINAL_VERDICTS

    scored = {
        str(row.get("id") or "")
        for row in verdict_rows
        if row.get("verdict") in TERMINAL_VERDICTS
    }
    return tuple(
        row
        for row in checkpoint_rows
        if row.get("source") == NEXT_WATCH_SOURCE
        and str(row.get("id") or "") not in scored
        and str(row.get("claim") or "").strip()
    )


def render_next_watch_for_prompt(records: tuple[dict[str, Any], ...] | list[dict[str, Any]]) -> str:
    if not records:
        return ""
    lines = []
    for row in records:
        due = str(row.get("due") or "未标到期")
        claim = str(row.get("claim") or "").strip()
        lines.append(f"- [due={due}] {claim}")
    return "\n".join(lines)
