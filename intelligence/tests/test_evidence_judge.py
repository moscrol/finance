from __future__ import annotations

from intelligence.services import evidence_judge, llm_refine


def _complete_returning(content: str | None):
    def complete(messages, timeout=0, temperature=0.0):
        return content, None, "" if content else "no key"

    return complete


def test_judge_keeps_listed_indexes_and_reports_reason() -> None:
    verdict = evidence_judge.judge_relevance(
        "科创50的支撑点位在哪",
        [
            ("科创50指数分析", "科创50 近期支撑位讨论"),
            ("兰花科创", "煤价反弹提供基本面支撑"),
        ],
        complete_fn=_complete_returning(
            '{"keep": [0], "reason": "兰花科创与指数问题无关"}'
        ),
    )

    assert verdict is not None
    keep, reason = verdict
    assert keep == {0}
    assert "兰花科创" in reason


def test_judge_fails_open_on_llm_unavailable_or_bad_output() -> None:
    candidates = [("标题", "摘录")]
    assert (
        evidence_judge.judge_relevance(
            "问题", candidates, complete_fn=_complete_returning(None)
        )
        is None
    )
    assert (
        evidence_judge.judge_relevance(
            "问题", candidates, complete_fn=_complete_returning("不是 JSON")
        )
        is None
    )
    assert (
        evidence_judge.judge_relevance(
            "问题", candidates, complete_fn=_complete_returning('{"keep": "全部"}')
        )
        is None
    )


def test_judge_keeps_candidates_beyond_window() -> None:
    candidates = [(f"标题{i}", "摘录") for i in range(evidence_judge.MAX_CANDIDATES + 2)]
    verdict = evidence_judge.judge_relevance(
        "问题",
        candidates,
        complete_fn=_complete_returning('{"keep": [0], "reason": ""}'),
    )

    assert verdict is not None
    keep, _reason = verdict
    assert evidence_judge.MAX_CANDIDATES in keep
    assert evidence_judge.MAX_CANDIDATES + 1 in keep


def test_judge_mode_env(monkeypatch) -> None:
    monkeypatch.setenv(evidence_judge.ENV_MODE, "off")
    assert not evidence_judge.should_judge()
    monkeypatch.setenv(evidence_judge.ENV_MODE, "on")
    assert evidence_judge.should_judge()
    monkeypatch.setenv(evidence_judge.ENV_MODE, "无效值")
    assert evidence_judge.judge_mode() == evidence_judge.MODE_AUTO


def test_judge_translates_absolute_deadline_to_complete_timeout() -> None:
    captured: dict[str, object] = {}
    deadline = llm_refine.Deadline.from_timeout(1)

    def complete(
        messages,
        model_override=None,
        timeout=0,
        temperature=0.0,
    ):
        del messages, model_override
        captured["timeout"] = timeout
        captured["temperature"] = temperature
        return '{"keep": [0], "reason": ""}', None, ""

    verdict = evidence_judge.judge_relevance(
        "后市怎么演绎",
        [("市场结构", "指数与量能变化")],
        timeout=2,
        deadline=deadline,
        complete_fn=complete,
    )

    assert verdict is not None
    assert 0 < float(captured["timeout"]) <= 1
    assert captured["temperature"] == 0.0


def test_judge_skips_llm_when_absolute_deadline_is_exhausted() -> None:
    called = False

    def complete(messages, timeout=0, temperature=0.0):
        del messages, timeout, temperature
        nonlocal called
        called = True
        return '{"keep": [0], "reason": ""}', None, ""

    verdict = evidence_judge.judge_relevance(
        "问题",
        [("标题", "摘录")],
        deadline=llm_refine.Deadline.from_timeout(0),
        complete_fn=complete,
    )

    assert verdict is None
    assert called is False
