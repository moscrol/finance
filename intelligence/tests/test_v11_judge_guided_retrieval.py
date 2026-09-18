"""V11 · 判官引导的一次有界回检索（设计 §5.5 ①–⑦ + query 规则 + adapter 注入）。

设计：docs/superpowers/specs/2026-08-22-v11-judge-guided-retrieval-design.md
接进默认路径：2026-09-09 判官修复 01 第三刀。

夹具形状：一句必需块内的语义拒句（无数字 / 日期 / E 号，判官说「因果无据」），
V8 把它降成 issue 直接出门——这正是 V11 唯一开火的那条路。
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from intelligence.runtime.continuous_turn_adapter import (
    _accepts_keyword,
    _build_guided_retriever,
)
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_semantic_verifier import (
    GUIDED_RETRIEVE_ENV,
    VERDICT_LIFTED,
    VERDICT_REASON_GUIDED_EVIDENCE,
    VERDICT_STAGE_GUIDED_REJUDGE,
    GuidedRetrievalTelemetry,
    SemanticEpisodeVerifier,
    build_guided_query,
)
from intelligence.services.research_contract import ResearchDeadline
from intelligence.tests.test_episode_semantic_verifier import _frame, _judge, _structural

CAUSAL_DRAFT = "基准判断：量能处于修复中段。散热升级推动液冷渗透率提升。"
CAUSAL_SENTENCE = "散热升级推动液冷渗透率提升。"
CAUSAL_ISSUE = "第2句因果无据"


def _kb_card(digest: str = "KB_GUIDED_1") -> AgentEvidence:
    return AgentEvidence(
        tool="kb_search",
        title="液冷服务器：散热升级路径",
        detail="功率密度上升后风冷到顶，散热升级推动液冷渗透率提升。",
        source="wiki/synthesis/liquid-cooling.md",
        source_date="2026-08-01",
        content_hash=digest,
    )


class _Retriever:
    def __init__(self, hits: tuple[AgentEvidence, ...] = (), *, fail: bool = False):
        self.hits = hits
        self.fail = fail
        self.calls: list[tuple[str, float]] = []

    def __call__(self, query: str, timeout: float):
        self.calls.append((query, timeout))
        if self.fail:
            raise RuntimeError("kb down")
        return self.hits


def _sticky_judge(rejected: tuple[int, ...], *, second: tuple[int, ...] | None = None):
    """首判拒 ``rejected``；重判拒 ``second``（None = 与首判相同）。"""

    calls: list[dict[str, object]] = []

    def run(request):
        calls.append(request)
        indexes = rejected if len(calls) == 1 or second is None else second
        # issue 文案里的「第 N 句」会被 _reconcile_issue_sentence_indexes 并回拒句集，
        # 所以句号必须跟着本次真正拒的索引走，否则夹具自己把句 2 拒回去。
        return {
            "passed": not indexes,
            "rejected_sentence_indexes": list(indexes),
            "issues": [f"第{index}句因果无据" for index in indexes],
        }

    run.calls = calls  # type: ignore[attr-defined]
    return run


def _verify(judge, retriever, *, seconds: float = 60.0, draft: str = CAUSAL_DRAFT):
    frame, structural = _structural(draft)
    verifier = SemanticEpisodeVerifier(judge_fn=judge)
    result = verifier.verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(seconds),
        retrieve_fn=retriever,
    )
    return verifier, frame, structural, result


# ---------------------------------------------------------------------------
# §5.5 ① 空检不重判、标留下
# ---------------------------------------------------------------------------


def test_empty_retrieval_keeps_annotation_and_does_not_rejudge() -> None:
    judge = _judge(False, rejected=(2,), issues=(CAUSAL_ISSUE,))
    retriever = _Retriever(())
    _verifier, _frame_, _structural_, result = _verify(judge, retriever)

    assert len(retriever.calls) == 1
    assert len(judge.calls) == 1, "空库不得触发重判"
    telemetry = result.guided_retrieval
    assert telemetry.triggered is True
    assert telemetry.outcome == "retrieved_empty"
    assert telemetry.hit_count == 0 and telemetry.new_hit_count == 0
    assert telemetry.still_doubted_count == 1
    assert telemetry.reserved_seconds is not None and telemetry.reserved_seconds >= 15.0
    assert telemetry.effective_mode == "hybrid"
    assert result.status == "partial" and result.judge_status == "rejected"
    assert CAUSAL_SENTENCE in result.public_answer
    assert "核验批注" in result.public_answer
    payload = result.to_dict()
    assert payload["v11_outcome"] == "retrieved_empty"
    assert payload["v11_triggered"] is True
    assert payload["v11_lifted_count"] is None


def test_retriever_failure_is_retrieved_empty_not_an_episode_failure() -> None:
    judge = _judge(False, rejected=(2,), issues=(CAUSAL_ISSUE,))
    retriever = _Retriever(fail=True)
    _verifier, _frame_, _structural_, result = _verify(judge, retriever)

    assert len(judge.calls) == 1
    assert result.guided_retrieval.outcome == "retrieved_empty"
    assert result.status == "partial"
    assert result.judge_status == "rejected"
    assert CAUSAL_SENTENCE in result.public_answer


# ---------------------------------------------------------------------------
# §5.5 ② 命中 + 重判放过 → 撤标；draft 字节不变；新卡不写回证据
# ---------------------------------------------------------------------------


def test_hit_and_lifting_rejudge_removes_doubt_without_touching_draft() -> None:
    judge = _judge(False, rejected=(2,), issues=(CAUSAL_ISSUE,))
    card = _kb_card()
    retriever = _Retriever((card,))
    _verifier, _frame_, structural, result = _verify(judge, retriever)

    assert len(retriever.calls) == 1
    assert len(judge.calls) == 2
    telemetry = result.guided_retrieval
    assert telemetry.outcome == "lifted"
    assert telemetry.rejudge_called is True
    assert telemetry.lifted_count == 1 and telemetry.still_doubted_count == 0
    assert telemetry.new_hit_count == 1
    assert [row["content_hash"] for row in telemetry.support_evidence] == [card.content_hash]
    # 重判看到的是同一份分句 + 扩展证据表（新卡带 guided_retrieval 标）
    second_request = judge.calls[1]
    assert second_request["sentences"] == judge.calls[0]["sentences"]
    guided_rows = [
        row for row in second_request["evidence_registry"] if row.get("guided_retrieval")
    ]
    assert len(guided_rows) == 1 and guided_rows[0]["title"].startswith("液冷服务器")
    # never-add：draft 不变、证据池不变（v1 不写回）
    assert result.verified.outcome.draft == structural.outcome.draft == CAUSAL_DRAFT
    assert len(result.verified.outcome.evidence) == len(structural.outcome.evidence)
    assert CAUSAL_SENTENCE in result.public_answer
    lifted = [v for v in result.sentence_verdicts if v["decision"] == VERDICT_LIFTED]
    assert len(lifted) == 1
    assert lifted[0]["stage"] == VERDICT_STAGE_GUIDED_REJUDGE
    assert lifted[0]["reasons"] == [VERDICT_REASON_GUIDED_EVIDENCE]
    assert result.to_dict()["v11_support_evidence"][0]["content_hash"] == card.content_hash


# ---------------------------------------------------------------------------
# §5.5 ③ 命中 + 重判仍拒 → 标留下
# ---------------------------------------------------------------------------


def test_hit_but_rejudge_still_rejects_keeps_annotation() -> None:
    judge = _sticky_judge((2,))
    retriever = _Retriever((_kb_card(),))
    _verifier, _frame_, _structural_, result = _verify(judge, retriever)

    assert len(judge.calls) == 2
    telemetry = result.guided_retrieval
    assert telemetry.outcome == "still_annotated"
    assert telemetry.lifted_count == 0 and telemetry.still_doubted_count == 1
    assert telemetry.support_evidence == ()
    assert result.status == "partial" and result.judge_status == "rejected"
    assert CAUSAL_SENTENCE in result.public_answer
    assert "核验批注" in result.public_answer
    assert not [v for v in result.sentence_verdicts if v["decision"] == VERDICT_LIFTED]


# ---------------------------------------------------------------------------
# §5.5 ④ 余量不足不开枪（含全部 from_timeout(5) 夹具）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seconds", (5.0, 14.9))
def test_budget_below_hybrid_floor_never_retrieves(seconds: float) -> None:
    judge = _judge(False, rejected=(2,), issues=(CAUSAL_ISSUE,))
    retriever = _Retriever((_kb_card(),))
    _verifier, _frame_, _structural_, result = _verify(judge, retriever, seconds=seconds)

    assert retriever.calls == []
    assert len(judge.calls) == 1
    assert result.guided_retrieval.triggered is False
    assert result.guided_retrieval.skip_reason == "budget"
    assert result.guided_retrieval.outcome == "skipped"
    assert result.to_dict()["v11_hit_count"] is None


# ---------------------------------------------------------------------------
# §5.5 ⑤ 机械拒句路径永不开火
# ---------------------------------------------------------------------------


def test_mechanical_out_of_table_citation_never_retrieves() -> None:
    """表外 E 号直接标疑，不删除、不浪费检索和重判额度。"""

    judge = _judge(True)
    retriever = _Retriever((_kb_card(),))
    _verifier, _frame_, _structural_, result = _verify(
        judge, retriever, draft="基准判断：量能处于修复中段。据E9，散热升级推动液冷渗透率提升。"
    )

    assert retriever.calls == []
    assert result.guided_retrieval.skip_reason == "mechanical_pending"
    assert result.guided_retrieval.triggered is False
    assert "E9" in result.public_answer
    assert "不能作为出处" in result.public_answer
    assert result.judge_status == "rejected"


def test_first_judge_pass_records_passed_skip() -> None:
    judge = _judge(True)
    retriever = _Retriever((_kb_card(),))
    _verifier, _frame_, _structural_, result = _verify(judge, retriever)

    assert retriever.calls == []
    assert result.guided_retrieval.skip_reason == "passed"


# ---------------------------------------------------------------------------
# §5.5 ⑥ 每 episode 一枪：同一实例同帧第二次 verify 不再开火
# ---------------------------------------------------------------------------


def test_second_verify_on_same_frame_is_already_used() -> None:
    # 判官两轮都拒句 2（_judge 夹具第二次会放行，那就走不到早退路了）。
    judge = _sticky_judge((2,))
    retriever = _Retriever(())
    verifier, frame, structural, first = _verify(judge, retriever)
    assert first.guided_retrieval.outcome == "retrieved_empty"

    second = verifier.verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(60),
        retrieve_fn=retriever,
    )

    assert len(retriever.calls) == 1, "空检后不得补枪"
    assert second.guided_retrieval.skip_reason == "already_used"


# ---------------------------------------------------------------------------
# §5.5 ⑦ 重判点了新句号：不删、不进 _repair、稿长不变
# ---------------------------------------------------------------------------


def test_rejudge_new_rejections_never_delete() -> None:
    judge = _sticky_judge((2,), second=(1,))
    retriever = _Retriever((_kb_card(),))
    _verifier, _frame_, structural, result = _verify(judge, retriever)

    assert result.verified.outcome.draft == structural.outcome.draft
    assert result.guided_retrieval.outcome == "lifted"
    assert result.guided_retrieval.lifted_count == 1
    assert result.guided_retrieval.still_doubted_count == 1
    assert "量能处于修复中段" in result.public_answer
    assert CAUSAL_SENTENCE in result.public_answer
    assert result.judge_status == "rejected"
    assert result.status == "partial"
    assert "原稿第1句" in result.public_answer
    assert "原稿第2句" not in result.public_answer
    assert any(v["sentence_index"] == 1 and v["decision"] == "demoted_to_issue"
               for v in result.sentence_verdicts)


# ---------------------------------------------------------------------------
# 开关 / 无注入 / 闭集
# ---------------------------------------------------------------------------


def test_env_kill_switch_disables_guided_retrieval(monkeypatch) -> None:
    monkeypatch.setenv(GUIDED_RETRIEVE_ENV, "0")
    judge = _judge(False, rejected=(2,), issues=(CAUSAL_ISSUE,))
    retriever = _Retriever((_kb_card(),))
    _verifier, _frame_, _structural_, result = _verify(judge, retriever)

    assert retriever.calls == []
    assert result.guided_retrieval.skip_reason == "disabled"


def test_no_retriever_is_a_skip_and_matches_pre_v11_shape() -> None:
    judge = _judge(False, rejected=(2,), issues=(CAUSAL_ISSUE,))
    frame, structural = _structural(CAUSAL_DRAFT)
    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(60),
    )

    assert result.guided_retrieval.skip_reason == "no_retriever"
    assert result.status == "partial" and result.judge_status == "rejected"
    assert CAUSAL_SENTENCE in result.public_answer
    assert "核验批注" in result.public_answer
    payload = result.to_dict()
    assert payload["v11_outcome"] == "skipped"
    assert payload["v11_skip_reason"] == "no_retriever"


def test_guided_outcome_is_a_closed_set() -> None:
    with pytest.raises(ValueError):
        GuidedRetrievalTelemetry(outcome="succeeded")


# ---------------------------------------------------------------------------
# §6 query 规则：骨干是被拒句，不含判官元话语，80 字帽
# ---------------------------------------------------------------------------


def test_guided_query_uses_rejected_sentences_not_judge_meta_words() -> None:
    query = build_guided_query(
        subject="液冷服务器",
        raw_question="液冷服务器产业链怎么看",
        reject_texts=(
            "【质检存疑】散热升级推动液冷渗透率提升。",
            "快接头是液冷系统的发明环节。",
            "风冷改良主要来自外部原因。",
        ),
        reject_issues=("第1句因果无据", "句2 发明环节", "第3句外部原因偷渡", "code=x subject=y :: 证据不足"),
    )

    assert query.startswith("液冷服务器 散热升级推动液冷渗透率提升")
    assert "快接头" in query and "风冷改良" in query
    for banned in ("无据", "偷渡", "质检", "code=", "证据不足"):
        assert banned not in query
    assert len(query) <= 80


def test_guided_query_falls_back_to_question_prefix_and_caps_length() -> None:
    long_sentence = "甲" * 120
    query = build_guided_query(
        subject="",
        raw_question="钙钛矿电池怎么看",
        reject_texts=(long_sentence,),
    )
    assert query.startswith("钙钛矿电池 ")
    assert len(query) <= 80

    empty = build_guided_query(subject="", raw_question="  ", reject_texts=("。",))
    assert empty == ""


def test_guided_query_takes_at_most_three_sentences() -> None:
    query = build_guided_query(
        subject="主体",
        raw_question="q",
        reject_texts=("一号句", "二号句", "三号句", "四号句"),
    )
    assert "四号句" not in query and "三号句" in query


# ---------------------------------------------------------------------------
# adapter 注入：走注册表 kb_search、授予秒数到达执行者、替身不炸
# ---------------------------------------------------------------------------


class _Spec:
    def __init__(self, capability: str) -> None:
        self.capability = capability


class _Observation:
    def __init__(self, evidence) -> None:
        self.evidence = evidence


class _FakeRegistry:
    def __init__(self, *, tools=("kb_search", "market_data"), capability="kb_search"):
        self._tools = tools
        self._capability = capability
        self.calls: list[dict[str, object]] = []

    def names(self):
        return tuple(self._tools)

    def resolve(self, name: str):
        return _Spec(self._capability)

    def execute(self, name, arguments, *, context, step_id, is_cancelled=None, **_kw):
        self.calls.append(
            {
                "name": name,
                "arguments": dict(arguments),
                "remaining": context.deadline.remaining(),
                "step_id": step_id,
            }
        )
        return _Observation((_kb_card(),))


def test_build_guided_retriever_routes_through_registry_with_bounded_deadline() -> None:
    frame = _frame()
    context = build_episode_context(
        frame,
        task_id="v11-adapter",
        capabilities=("kb_search", "market_data"),
        timeout=120.0,
    )
    registry = _FakeRegistry()
    retrieve = _build_guided_retriever(registry, context, is_cancelled=lambda: False)
    assert retrieve is not None
    root_before = context.deadline.remaining()
    assert root_before > 20.0, "夹具前提：根窗远大于授予的 20s"

    hits = retrieve("液冷服务器 散热升级", 20.0)

    assert [item.content_hash for item in hits] == ["KB_GUIDED_1"]
    call = registry.calls[0]
    assert call["name"] == "kb_search"
    assert call["arguments"] == {"query": "液冷服务器 散热升级"}
    assert str(call["step_id"]).startswith("guided-retrieval:")
    # 授予的 20s 到达了执行者：工具拿到的是 ≤20s 的绝对子 deadline，而不是整条根窗
    assert 0.0 < call["remaining"] <= 20.0
    # 根 deadline 是绝对时刻，只随墙钟流逝，不被子窗改写
    assert context.deadline.remaining() >= root_before - 1.0


def test_build_guided_retriever_fails_closed_when_unauthorized_or_missing() -> None:
    frame = _frame()
    unauthorized = build_episode_context(
        frame, task_id="v11-noauth", capabilities=("market_data",), timeout=60.0
    )
    assert _build_guided_retriever(_FakeRegistry(), unauthorized, is_cancelled=lambda: False) is None

    authorized = build_episode_context(
        frame, task_id="v11-notool", capabilities=("kb_search",), timeout=60.0
    )
    assert (
        _build_guided_retriever(
            _FakeRegistry(tools=("market_data",)), authorized, is_cancelled=lambda: False
        )
        is None
    )
    assert _build_guided_retriever("registry", authorized, is_cancelled=lambda: False) is None


def test_accepts_keyword_matches_strict_and_kwargs_signatures() -> None:
    def strict(*, frame, structurally_verified, deadline):
        return None

    def loose(*, structurally_verified, **_kwargs):
        return None

    def explicit(*, frame, structurally_verified, deadline, retrieve_fn=None):
        return None

    assert _accepts_keyword(strict, "retrieve_fn") is False
    assert _accepts_keyword(loose, "retrieve_fn") is True
    assert _accepts_keyword(explicit, "retrieve_fn") is True
    assert _accepts_keyword(object(), "retrieve_fn") is False


def test_verify_signature_change_keeps_default_behaviour_for_old_callers() -> None:
    """不传 retrieve_fn 的老调用方（含 8792 现有装配）行为不变：skip no_retriever。"""

    frame, structural = _structural("基准判断：量能处于修复中段。")
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame,
        structurally_verified=replace(structural),
        deadline=ResearchDeadline.from_timeout(60),
    )
    assert result.status == "completed"
    assert result.guided_retrieval.skip_reason == "passed"
