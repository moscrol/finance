"""弃权判定：一份答案有没有真正回答问题（能力放大 spec §3.2 · P1）。

失败形状（2026-08-27 四臂 38 题）：组件臂未见题 10/10 全弃权，rubric 均分 11.1，
读数上看不出「它什么都没说」——**一个 100% 弃权的系统零错误、分数不难看、产品
价值为零**。弃权是二值量，与均分并列念，**不折进连续分**（一票否决式的量不进
加权平均，见 ``10_knowledge/veto-inside-a-continuous-score.md``）。

判定分两层：

* 结构层（首选）：episode 终局事件 / gate receipt / 探针收据的 ``terminal_phase``。
* 文本层（兜底）：2026-08-27 机判脚本 ``REFUSAL_MARKERS`` 的同一套标记——那次
  「10/10 弃权」就是它认出来的——只在**短答案或开头段**里数，避免长文里一句
  「该日不是交易日」把整篇研判判成弃权。

``abstain_reason`` 枚举来自 spec：``evidence_gap`` / ``unsupported`` /
``judge_blocked`` / ``deadline_exhausted`` / ``other``。判不出原因时是 ``other``，
不编造。**弃权 ≠ 错**：C 组 / D 组里六道题本来就期望拒答，聚合时按
``expect_refusal`` 分开念（该拒而拒 vs 不该弃而弃）。
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

ABSTAIN_REASONS: tuple[str, ...] = (
    "evidence_gap",
    "unsupported",
    "judge_blocked",
    "deadline_exhausted",
    "other",
)

# 判官扣稿的固定话术（8792 `judge_unavailable` 时对外发的那段）：正文看着像弃权，
# 原因其实是复核链路，不是模型没答——单列一组，原因记 judge_blocked。
_JUDGE_BLOCKED_MARKERS: tuple[str, ...] = (
    "未完成独立复核",
    "复核服务不可用",
    "暂不对外引用",
    "暂不能引用",
)
_EVIDENCE_GAP_MARKERS: tuple[str, ...] = (
    "查不到",
    "没有记录",
    "无结果",
    "不存在",
    "未找到",
    "没有可用",
    "无可用",
    "没有开盘",
    "休市",
    "不是交易日",
    "未取到",
    "数据缺失",
    "不可用",
    "为 0 行",
    "为0行",
)
_DEADLINE_MARKERS: tuple[str, ...] = ("研究截止", "时间已到", "预算耗尽")
_UNSUPPORTED_MARKERS: tuple[str, ...] = ("证据不足", "不下结论", "无法核实", "不足以支持")
# 2026-08-27 `score_machine_truth.py` 原表 + 同批四臂产物里实际出现的弃权句
# （组件臂「结论未知」、C2「不能给出」、8792 D6「没法回答」、D7「无法评估」）。
REFUSAL_MARKERS: tuple[str, ...] = (
    "无法回答",
    "没法回答",
    "无法评估",
    "无法给出",
    "不能给出",
    "结论未知",
    "未能",
    *_EVIDENCE_GAP_MARKERS,
    *_DEADLINE_MARKERS,
    *_UNSUPPORTED_MARKERS,
    *_JUDGE_BLOCKED_MARKERS,
)

# 首句定性：结论在第一句。长篇诚实拒答（先说「不是交易日」再指路）首句就露底；
# 正文中段一句「未能取到 07-17 数据」则不算——那是缺口说明，不是拒答。
_SENTENCE_END = re.compile(r"[。！？!?\n]")
_MARKDOWN_NOISE = re.compile(r"[*#>`\-]+")
# 短于此的正文不可能是研判（连一个数字加单位都放不下）。
MIN_ANSWER_CHARS = 12
# 短答案（快答）里标记全文数；再长就只信首句。
SHORT_ANSWER_CHARS = 80

_JUDGE_BLOCKED_STATUSES = frozenset({"blocked", "withheld", "rejected"})
_DEADLINE_STOP_REASONS = frozenset(
    {"deadline_exhausted", "repair_deadline_exhausted", "budget_exhausted", "repair_budget_exhausted"}
)
_EVIDENCE_GAP_STOP_REASONS = frozenset(
    {"evidence_gap", "evidence_gap_fallback", "mandatory_l3_gap", "no_evidence"}
)
_UNSUPPORTED_REJECTIONS = frozenset({"unsupported_claims", "basis_mismatch", "unbound_outputs"})
_EVIDENCE_GAP_PHASES = frozenset({"evidence_gap_fallback"})
_COMPLETED_STATUSES = frozenset({"completed"})


@dataclass(frozen=True)
class AbstentionVerdict:
    abstained: bool
    reason: str | None
    detector: str
    signals: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "abstained": self.abstained,
            "abstain_reason": self.reason,
            "abstain_detector": self.detector,
            "abstain_signals": list(self.signals),
        }


def _answered(detector: str, *signals: str) -> AbstentionVerdict:
    return AbstentionVerdict(False, None, detector, tuple(signals))


def _abstained(reason: str, detector: str, *signals: str) -> AbstentionVerdict:
    if reason not in ABSTAIN_REASONS:
        raise ValueError(f"unknown abstain reason {reason!r}")
    return AbstentionVerdict(True, reason, detector, tuple(signals))


def _reason_from_text(segment: str) -> str:
    if any(marker in segment for marker in _JUDGE_BLOCKED_MARKERS):
        return "judge_blocked"
    if any(marker in segment for marker in _DEADLINE_MARKERS):
        return "deadline_exhausted"
    if any(marker in segment for marker in _UNSUPPORTED_MARKERS):
        return "unsupported"
    if any(marker in segment for marker in _EVIDENCE_GAP_MARKERS):
        return "evidence_gap"
    return "other"


def lead_sentence(text: str) -> str:
    """第一句正文（去 markdown 记号）。空行、纯标题行跳过。"""

    for raw in _SENTENCE_END.split(text):
        cleaned = _MARKDOWN_NOISE.sub("", raw).strip()
        if cleaned:
            return cleaned
    return ""


def classify_text(answer: str | None) -> AbstentionVerdict:
    """只看正文：空 / 过短 = 弃权；首句带拒答标记 = 弃权；短答案（快答）全文数标记，
    无标记就是答了；长答案只信首句，中段的缺口说明不算。"""

    text = str(answer or "").strip()
    if not text:
        return _abstained("other", "text_markers", "empty_answer")
    lead = lead_sentence(text)
    lead_hits = [marker for marker in REFUSAL_MARKERS if marker in lead]
    if lead_hits:
        return _abstained(_reason_from_text(lead), "text_markers", "lead_sentence", *(f"marker:{m}" for m in lead_hits))
    if len(text) < MIN_ANSWER_CHARS:
        return _abstained("other", "text_markers", f"too_short<{MIN_ANSWER_CHARS}")
    if len(text) < SHORT_ANSWER_CHARS:
        hits = [marker for marker in REFUSAL_MARKERS if marker in text]
        if hits:
            return _abstained(_reason_from_text(text), "text_markers", f"short_answer<{SHORT_ANSWER_CHARS}", *(f"marker:{m}" for m in hits))
        return _answered("text_markers", "short_answer_no_marker")
    later_hits = [marker for marker in REFUSAL_MARKERS if marker in text]
    return _answered("text_markers", *(f"ignored_marker:{m}" for m in later_hits[:4]))


def _events(episode: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = episode.get("events")
    if not isinstance(raw, list):
        outcome = episode.get("outcome")
        raw = outcome.get("events") if isinstance(outcome, Mapping) else None
    return [item for item in (raw or []) if isinstance(item, dict)]


def _payload(event: Mapping[str, Any]) -> dict[str, Any]:
    payload = event.get("payload")
    return payload if isinstance(payload, dict) else {}


def classify_episode(
    episode: Mapping[str, Any],
    *,
    answer: str | None = None,
    gate_receipt: Mapping[str, Any] | None = None,
) -> AbstentionVerdict:
    """episode 终局优先，正文兜底。

    读者拿到的是正文，所以「弃权」的最终判据仍是正文有没有研判；结构层负责
    两件事：(1) 判官扣稿这种正文看不出来的弃权；(2) 给弃权定原因。
    """

    events = _events(episode)
    outcome = episode.get("outcome") if isinstance(episode.get("outcome"), Mapping) else {}
    finishes = [_payload(e) for e in events if e.get("kind") == "finish"]
    last_finish = finishes[-1] if finishes else {}
    status = str(last_finish.get("status") or outcome.get("status") or "")
    stop_reason = str(last_finish.get("stop_reason") or outcome.get("stop_reason") or "")
    rejection = str(last_finish.get("rejection_code") or "")
    judge_status = str((gate_receipt or {}).get("judge_status") or "").lower()
    text = answer if answer is not None else str(outcome.get("draft") or "")
    evidence_count = len(outcome.get("evidence") or [])
    signals: list[str] = [f"status={status or '-'}", f"stop_reason={stop_reason or '-'}"]

    if judge_status in _JUDGE_BLOCKED_STATUSES:
        return _abstained("judge_blocked", "episode_events", *signals, f"judge_status={judge_status}")

    text_verdict = classify_text(text)
    if not text_verdict.abstained and status in _COMPLETED_STATUSES:
        return _answered("episode_events", *signals)
    if not text_verdict.abstained:
        # partial / failed 但正文给了研判：读者拿到了答案，缺格在 gaps 里说了。
        return _answered("episode_events", *signals, "partial_with_assessment")

    signals.extend(text_verdict.signals)
    if text_verdict.reason == "judge_blocked":
        return _abstained("judge_blocked", "episode_events", *signals)
    if stop_reason in _DEADLINE_STOP_REASONS:
        return _abstained("deadline_exhausted", "episode_events", *signals)
    if rejection in _UNSUPPORTED_REJECTIONS:
        return _abstained("unsupported", "episode_events", *signals, f"rejection={rejection}")
    if stop_reason in _EVIDENCE_GAP_STOP_REASONS or evidence_count == 0:
        return _abstained("evidence_gap", "episode_events", *signals, f"evidence={evidence_count}")
    if text_verdict.reason and text_verdict.reason != "other":
        return _abstained(text_verdict.reason, "episode_events", *signals)
    return _abstained("other", "episode_events", *signals)


def classify_probe_receipt(receipt: Mapping[str, Any], *, answer: str | None = None) -> AbstentionVerdict:
    """`smoke_workbench_self_use.py` 收据：``answer_stream`` 是阶段摘要不是正文，
    弃权信号在 ``terminal_phase`` / ``gate_receipt``；正文另给。"""

    gate = receipt.get("gate_receipt") if isinstance(receipt.get("gate_receipt"), Mapping) else {}
    judge_status = str(gate.get("judge_status") or "").lower()
    stream = receipt.get("answer_stream")
    phase = ""
    if isinstance(stream, Mapping):
        phase = str(stream.get("terminal_phase") or "")
    elif isinstance(stream, str) and "terminal_phase" in stream:
        # 旧收据把 dict 的 repr 存成了字串。
        marker = "'terminal_phase': '"
        start = stream.find(marker)
        if start >= 0:
            start += len(marker)
            phase = stream[start : stream.find("'", start)]
    signals = [f"terminal_phase={phase or '-'}", f"judge_status={judge_status or '-'}"]
    if judge_status in _JUDGE_BLOCKED_STATUSES:
        return _abstained("judge_blocked", "probe_receipt", *signals)
    if answer is not None:
        text_verdict = classify_text(answer)
        if not text_verdict.abstained:
            return _answered("probe_receipt", *signals)
        signals.extend(text_verdict.signals)
        if phase in _EVIDENCE_GAP_PHASES:
            return _abstained("evidence_gap", "probe_receipt", *signals)
        return _abstained(text_verdict.reason or "other", "probe_receipt", *signals)
    if phase in _EVIDENCE_GAP_PHASES:
        return _abstained("evidence_gap", "probe_receipt", *signals)
    return _answered("probe_receipt", *signals, "no_answer_text_given")


def abstain_rate(
    verdicts: Iterable[Mapping[str, Any] | AbstentionVerdict],
    *,
    expect_refusal: Iterable[bool] | None = None,
) -> dict[str, Any]:
    """弃权率 = 弃权数 / 样本数，与均分并列，不进总分。

    传 ``expect_refusal``（逐样本）时另算「不该弃而弃」：把期望拒答的题剔出分母。
    两个数都念，单念任一个都不许（spec §3.2 第 3 点）。
    """

    rows = [v.to_dict() if isinstance(v, AbstentionVerdict) else dict(v) for v in verdicts]
    flags = list(expect_refusal) if expect_refusal is not None else [False] * len(rows)
    if len(flags) != len(rows):
        raise ValueError("expect_refusal 长度必须与样本数一致")
    n = len(rows)
    abstained = [r for r in rows if r.get("abstained")]
    reasons = Counter(str(r.get("abstain_reason") or "other") for r in abstained)
    answer_expected = [r for r, flag in zip(rows, flags) if not flag]
    unexpected = [r for r in answer_expected if r.get("abstained")]
    expected_refusals = [r for r, flag in zip(rows, flags) if flag]
    honored = [r for r in expected_refusals if r.get("abstained")]
    return {
        "n": n,
        "abstained": len(abstained),
        "abstain_rate": round(len(abstained) / n, 4) if n else None,
        "by_reason": dict(reasons),
        "n_answer_expected": len(answer_expected),
        "abstained_where_answer_expected": len(unexpected),
        "abstain_rate_where_answer_expected": (
            round(len(unexpected) / len(answer_expected), 4) if answer_expected else None
        ),
        "n_refusal_expected": len(expected_refusals),
        "refusals_honored": len(honored),
    }
