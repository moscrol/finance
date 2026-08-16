"""降级回答章法（ASK_DEGRADED_FALLBACK）：契约、注入与 gap 透明段。

钉住四件事：

1. 开关默认 off，off 时 episode 指令与 ``_gap_answer`` 输出逐字节不变。
2. SKILL.md 契约：判断词表与 ``_JUDGE_SYSTEM_PROMPT`` 逐字一致（共享
   ``ANALYTICAL_MARKERS``，不另立词表）、q13 七项锚句齐全、正文无阿拉伯
   数字与板块名（复用长尾骨架的洁净判定）。
3. 透明段红线：draft 与证据 title/detail 一个字不进 gap 答案——它们未经
   核验；只允许调用计数、中断成因、来源名与 ISO 日期。
4. 扩展后的 gap 答案不惊动 layer 4 标记闸（对照 #327 缺口模板的既有钉法，
   见 R-20260816-04）。
"""

from __future__ import annotations

from dataclasses import replace

from intelligence.services.degraded_fallback import (
    ENV_NAME,
    HEADING,
    REQUIRED_ANCHORS,
    assert_skill_contract,
    enabled,
    episode_rule,
    gap_transparency,
    skill_body,
)
from intelligence.services.episode_protocol import build_episode_instructions
from intelligence.services.episode_semantic_verifier import (
    _JUDGE_SYSTEM_PROMPT,
    SemanticEpisodeVerifier,
)
from intelligence.services.longtail_baseline import (
    ANALYTICAL_MARKERS,
    skill_body_is_clean,
)
from intelligence.services.task_fulfillment import evaluate_marker_coverage
from intelligence.tests.test_episode_protocol import _context, _frame, _registry
from intelligence.tests.test_gap_answer_middle_tier import _verified


def test_flag_defaults_off(monkeypatch) -> None:
    monkeypatch.delenv(ENV_NAME, raising=False)
    assert enabled() is False
    assert episode_rule(_frame()) == ""
    _question_frame, verified = _verified()
    assert gap_transparency(verified) == ""


def test_skill_contract_markers_and_anchors() -> None:
    assert_skill_contract()
    body = skill_body()
    for marker in ANALYTICAL_MARKERS:
        assert marker in _JUDGE_SYSTEM_PROMPT
        assert marker in body
    for anchor in REQUIRED_ANCHORS:
        assert anchor in body
    assert skill_body_is_clean(body) is True


def test_episode_instructions_unchanged_when_off(monkeypatch) -> None:
    monkeypatch.delenv(ENV_NAME, raising=False)
    frame = _frame()
    off_text = build_episode_instructions(frame, _context(frame), _registry())
    assert HEADING not in off_text


def test_episode_instructions_inject_when_on(monkeypatch) -> None:
    monkeypatch.setenv(ENV_NAME, "on")
    frame = _frame()
    text = build_episode_instructions(frame, _context(frame), _registry())
    assert HEADING in text
    for anchor in REQUIRED_ANCHORS:
        assert anchor in text


def test_gap_answer_unchanged_when_off(monkeypatch) -> None:
    monkeypatch.delenv(ENV_NAME, raising=False)
    frame, verified = _verified()
    answer = SemanticEpisodeVerifier._gap_answer(frame, verified)
    assert "本轮尝试" not in answer
    assert "材料来源" not in answer


def test_gap_answer_appends_transparency_when_on(monkeypatch) -> None:
    monkeypatch.setenv(ENV_NAME, "on")
    frame, verified = _verified()
    answer = SemanticEpisodeVerifier._gap_answer(frame, verified)

    # 既有段落原样保留（#327 缺口模板句是钉住的形状，不许动）。
    assert "现有证据不足，暂不能可靠回答" in answer
    assert "仍需核验：失效条件" in answer
    # 新增两段：尝试过什么 / 来源标注不降级。
    assert "本轮尝试：检索调用 1 次、模型调用 1 次。" in answer
    assert "材料来源：行情快照（截至 2026-08-12）；未核验内容暂不引用。" in answer


def test_transparency_never_quotes_draft_or_evidence_content(monkeypatch) -> None:
    """红线：draft 原文与证据 title/detail（未核验数字）一个字不进。"""

    monkeypatch.setenv(ENV_NAME, "on")
    frame, verified = _verified(draft="市场偏弱，观察缩量。")
    answer = SemanticEpisodeVerifier._gap_answer(frame, verified)
    assert "市场偏弱" not in answer
    assert "观察缩量" not in answer
    # 证据 detail 里的未核验数字（成交额 21949 亿 / 涨停 116 家）不得出现。
    assert "21949" not in answer
    assert "116" not in answer
    # 证据 title 也不进。
    assert "A股市场快照" not in answer
    assert "涨停结构" not in answer


def test_transparency_translates_mechanical_stop_reasons(monkeypatch) -> None:
    monkeypatch.setenv(ENV_NAME, "on")
    _question_frame, verified = _verified()

    timed_out = replace(
        verified,
        outcome=replace(verified.outcome, stop_reason="deadline_exhausted"),
    )
    assert "中断于研究时间预算耗尽" in gap_transparency(timed_out)

    no_model = replace(
        verified,
        outcome=replace(
            verified.outcome, stop_reason="repair_model_unavailable"
        ),
    )
    assert "中断于核验修复阶段模型服务不可用" in gap_transparency(no_model)

    # 正常终止（model_finish）不加成因行：缺口由「仍需核验」说明。
    assert "中断于" not in gap_transparency(verified)


def test_source_labels_dedupe_and_ignore_non_iso_dates(monkeypatch) -> None:
    monkeypatch.setenv(ENV_NAME, "on")
    _question_frame, verified = _verified()
    evidence = verified.outcome.evidence
    scrambled = replace(
        verified,
        outcome=replace(
            verified.outcome,
            evidence=(
                evidence[0],
                replace(evidence[1], source_date="上周·某媒体"),
            ),
        ),
    )
    text = gap_transparency(scrambled)
    # 同名来源去重；非 ISO 日期不参与「截至」取值。
    assert text.count("行情快照") == 1
    assert "行情快照（截至 2026-08-11）" in text
    assert "上周·某媒体" not in text


def test_extended_gap_answer_keeps_marker_gate_quiet(monkeypatch) -> None:
    """透明段不惊动 layer 4：与 #327 缺口模板同样不触发
    ``uncheckable_judgment_empty``（对照 R-20260816-04 的既有钉法）。"""

    monkeypatch.setenv(ENV_NAME, "on")
    frame, verified = _verified()
    answer = SemanticEpisodeVerifier._gap_answer(frame, verified)
    coverage = evaluate_marker_coverage(
        ("direct_answer", "evidence_boundary"),
        answer,
    )
    assert coverage["warnings"] == []
    assert coverage["marker_coverage"] == "complete"
    assert coverage["uncheckable"] == ["direct_answer"]
    assert "evidence_boundary" in coverage["present"]
