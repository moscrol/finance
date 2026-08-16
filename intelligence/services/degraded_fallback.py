"""Degraded-answer discipline injection + gap transparency (ASK_DEGRADED_FALLBACK, default off).

蒸馏来源是 knevo 逆向语料（`docs/learning/knevo-distill/q13-拒答与降级纪律.md`
的「降级后必须保留的七项」、`E-004` 的诚实降级行为、逆向文档 §3C.5 的
缺数三档与「假设 × 可验证时点 × 推翻条件」范式），适配成本仓的两个挂钩：

1. prompt 侧：``episode_rule`` 把降级章法拼进 episode 指令（模型还能写时，
   按七项写有边界的降级回答，而不是被剥成裸边界句）。
2. 输出侧：``gap_transparency`` 在 ``_gap_answer`` 的结构性兜底上确定性
   补齐「尝试过什么 / 来源标注」两段——这条路径出现的场合正是 LLM 已经
   失败的场合，prompt 注入帮不上，只能由运行时按章法渲染。

红线与 ``_gap_answer`` 一致：只用结构性事实（调用计数、stop_reason、证据的
来源名与日期），draft 与证据 title/detail 一个字不进——它们未经核验。
两侧共用一个开关，默认 off；off 时既有输出逐字节不变。翻默认必须先走
对照窗（同 ASK_LONGTAIL_BASELINE 的纪律），不得因本文件默认打开。

本文件不是观点题核验预算回归（2026-08-16 立案）的修复：它只改「降级之后
怎么说话」，不改预算、不改核验路径、不改 ``_CLAIM_POLICY``。
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from intelligence.services.longtail_baseline import (
    ANALYTICAL_MARKERS,
    skill_body_is_clean,
)
from intelligence.services.task_frame import TaskFrame

ENV_NAME = "ASK_DEGRADED_FALLBACK"
SKILL_ID = "finance-degraded-fallback"
HEADING = "【降级回答章法】"
_SKILL_RELATIVE = Path("skills") / SKILL_ID / "SKILL.md"

# q13 七项在 SKILL.md 里的锚句；契约测试逐条钉住，改词表即红。
REQUIRED_ANCHORS = (
    "尝试过什么",
    "缺口是什么",
    "已核验与未核验分开",
    "来源标注不降级",
    "最大可判层级",
    "待补证清单与验证窗口",
    "推翻条件",
)

# stop_reason -> 用户可见的中断成因。只译机械性中断；model_finish 这类
# 正常终止不加成因行（缺口本身已由「仍需核验」说明）。
_STOP_REASON_CAUSES = {
    "deadline_exhausted": "研究时间预算耗尽",
    "repair_model_unavailable": "核验修复阶段模型服务不可用",
    "repair_model_stop": "核验修复轮提前停止",
}

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MAX_SOURCE_LABELS = 3


def enabled() -> bool:
    raw = os.environ.get(ENV_NAME, "off").strip().lower()
    return raw in {"on", "true", "1", "yes"}


def skill_path() -> Path:
    return Path(__file__).resolve().parents[2] / _SKILL_RELATIVE


def skill_body(path: Path | None = None) -> str:
    text = (path or skill_path()).read_text(encoding="utf-8")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4 :]
    return text.strip()


def assert_skill_contract(text: str | None = None) -> None:
    body = skill_body() if text is None else text
    missing = [marker for marker in ANALYTICAL_MARKERS if marker not in body]
    if missing:
        raise AssertionError(
            f"degraded fallback missing analytical markers: {missing}"
        )
    absent = [anchor for anchor in REQUIRED_ANCHORS if anchor not in body]
    if absent:
        raise AssertionError(
            f"degraded fallback missing required anchors: {absent}"
        )
    if not skill_body_is_clean(body):
        raise AssertionError("degraded fallback smuggles digits or market names")


def prompt_block(path: Path | None = None) -> str:
    return f"{HEADING}\n{skill_body(path)}"


def episode_rule(frame: TaskFrame) -> str:
    """episode 指令里的降级章法块；off 时空串，指令逐字节不变。

    与长尾骨架不同，不限题型：章法只约束「核验不完整时怎么写」，对完整
    交付没有额外要求。frame 参数保留 seam 对称性，当前不参与判定。
    """

    del frame
    if not enabled():
        return ""
    return f"{prompt_block()}\n"


def _source_labels(evidence) -> tuple[str, ...]:
    """证据来源标签：去重保序，取每个来源最新的 ISO 日期。

    只碰 ``source`` / ``source_date`` 两个结构性字段；``title`` / ``detail``
    可能含未核验数字，一个字不取。
    """

    latest: dict[str, str] = {}
    order: list[str] = []
    for item in evidence:
        source = str(getattr(item, "source", "") or "").strip()
        if not source:
            continue
        if source not in latest:
            latest[source] = ""
            order.append(source)
        date = str(getattr(item, "source_date", "") or "").strip()
        if _ISO_DATE.match(date) and date > latest[source]:
            latest[source] = date
    labels: list[str] = []
    for source in order[:_MAX_SOURCE_LABELS]:
        date = latest[source]
        labels.append(f"{source}（截至 {date}）" if date else source)
    return tuple(labels)


def gap_transparency(verified) -> str:
    """gap 兜底的透明补段：q13 七项里的「尝试过什么」「来源标注不降级」。

    其余五项由 ``_gap_answer`` 既有段落（仍需核验 / 本轮已核验 / 截至与
    复验）与 prompt 侧章法分担。输入 duck-typed：只读
    ``verified.outcome`` 的 usage / stop_reason / evidence。
    """

    if not enabled():
        return ""
    outcome = getattr(verified, "outcome", None)
    if outcome is None:
        return ""
    parts: list[str] = []
    usage = getattr(outcome, "usage", None)
    if usage is not None:
        attempt = (
            f"本轮尝试：检索调用 {usage.tool_calls} 次、"
            f"模型调用 {usage.llm_calls} 次"
        )
        cause = _STOP_REASON_CAUSES.get(
            str(getattr(outcome, "stop_reason", "") or "")
        )
        if cause:
            attempt += f"，中断于{cause}"
        parts.append(attempt + "。")
    sources = _source_labels(getattr(outcome, "evidence", ()) or ())
    if sources:
        parts.append(
            "材料来源：" + "、".join(sources) + "；未核验内容暂不引用。"
        )
    return "".join(parts)
