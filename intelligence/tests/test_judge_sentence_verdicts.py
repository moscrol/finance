"""P2 第一步：判官每条拒句进结构化账（``sentence_verdicts``），判据一字不改。

spec 2026-09-02 §3.3「先量后改」：先记 deleted_sentence / reason / bound_evidence /
source_tier，跑题集量「因来源档次被删的有出处真话」占比，够阈值才动判据。
这里钉的是账本与真实处置一致：记「deleted」的句子确实不在稿里，记「demoted」的确实还在。
"""

from __future__ import annotations

from dataclasses import replace

from intelligence.services.episode_semantic_verifier import (
    VERDICT_DELETED,
    VERDICT_DEMOTED,
    VERDICT_REASON_JUDGE,
    VERDICT_REASON_NUMERIC,
    VERDICT_REASON_ORDINAL,
    VERDICT_STAGE_JUDGE,
    VERDICT_STAGE_PREFLIGHT,
    SemanticEpisodeVerifier,
)
from intelligence.services.research_contract import ResearchDeadline
from intelligence.tests.test_episode_semantic_verifier import _judge, _structural


def _verify(structural, frame, judge):
    return SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )


def test_mechanical_reject_in_judge_round_is_recorded_as_deleted_with_unresolved_ordinal() -> None:
    frame, structural = _structural("市场下跌。据E99显示下跌。")
    judge = _judge(
        False,
        rejected=(2,),
        issues=("code=unresolved_evidence_ordinal :: 第2句引用的 E99 不在本轮证据表",),
    )

    result = _verify(structural, frame, judge)

    assert "E99" not in result.verified.outcome.draft
    assert len(result.sentence_verdicts) == 1
    verdict = result.sentence_verdicts[0]
    assert verdict["stage"] == VERDICT_STAGE_JUDGE
    assert verdict["judge_round"] == 1
    assert verdict["sentence_index"] == 2
    assert verdict["sentence"] == "据E99显示下跌。"
    assert verdict["decision"] == VERDICT_DELETED
    assert VERDICT_REASON_ORDINAL in verdict["reasons"]
    assert verdict["cited_evidence_ordinals"] == ["E99"]
    assert verdict["unresolved_evidence_ordinals"] == ["E99"]
    assert verdict["bound_evidence_hashes"] == []
    assert verdict["source_tiers"] == []
    assert verdict["judge_issues"] and "第2句" in verdict["judge_issues"][0]
    # 复判那一轮判官放行，不再追加账目。
    assert len(judge.calls) == 2  # type: ignore[attr-defined]
    assert result.to_dict()["sentence_verdicts"] == [dict(verdict)]


def test_semantic_reject_inside_required_block_is_recorded_as_demoted_not_deleted() -> None:
    frame, structural = _structural(
        "市场广度已经改善。CPO状态缺少绑定证据。创新药涨幅缺少绑定证据。"
    )

    def judge(request):
        return {
            "passed": False,
            "rejected_sentence_indexes": [3],
            "issues": ["句2包含未绑定的CPO状态。", "第3句包含未绑定的创新药涨幅。"],
        }

    result = _verify(structural, frame, judge)

    assert "CPO状态缺少绑定证据" in result.public_answer
    assert "创新药涨幅缺少绑定证据" in result.public_answer
    by_index = {int(v["sentence_index"]): v for v in result.sentence_verdicts}
    assert set(by_index) == {2, 3}
    for index, verdict in by_index.items():
        assert verdict["decision"] == VERDICT_DEMOTED, verdict
        assert verdict["reasons"] == [VERDICT_REASON_JUDGE]
        assert verdict["stage"] == VERDICT_STAGE_JUDGE and verdict["judge_round"] == 1
    assert by_index[2]["judge_issues"] == ["句2包含未绑定的CPO状态。"]
    assert by_index[3]["judge_issues"] == ["第3句包含未绑定的创新药涨幅。"]


def test_preflight_numeric_condition_is_recorded_before_any_judge_call() -> None:
    judge = _judge(True)
    frame, structural = _structural(
        "我的基准判断是反弹仍可持续2至5个交易日。若指数跌破3870点则失效。"
    )

    result = _verify(structural, frame, judge)

    assert "3870点" not in result.verified.outcome.draft
    preflight = [v for v in result.sentence_verdicts if v["stage"] == VERDICT_STAGE_PREFLIGHT]
    assert len(preflight) == 1
    verdict = preflight[0]
    assert verdict["judge_round"] is None
    assert verdict["decision"] == VERDICT_DELETED
    assert verdict["reasons"] == [VERDICT_REASON_NUMERIC]
    assert "3870点" in verdict["sentence"]


def test_cited_ordinal_resolves_to_evidence_hash_and_source_tier() -> None:
    frame, structural = _structural("市场下跌（E1）。据E1显示成交额放大。")
    web_evidence = replace(structural.outcome.evidence[0], evidence_tier="public_web")
    structural = replace(structural, outcome=replace(structural.outcome, evidence=(web_evidence,)))
    judge = _judge(False, rejected=(2,), issues=("第2句「成交额放大」证据里没有。",))

    result = _verify(structural, frame, judge)

    verdicts = [v for v in result.sentence_verdicts if v["sentence_index"] == 2]
    assert len(verdicts) == 1
    verdict = verdicts[0]
    assert verdict["decision"] == VERDICT_DEMOTED
    assert verdict["cited_evidence_ordinals"] == ["E1"]
    assert verdict["unresolved_evidence_ordinals"] == []
    assert verdict["bound_evidence_hashes"] == ["HASH_PRIVATE_SENTINEL"]
    assert verdict["source_tiers"] == ["public_web"]


def test_clean_pass_leaves_ledger_empty_and_artifact_shape_stable() -> None:
    frame, structural = _structural("市场下跌。")

    result = _verify(structural, frame, _judge(True))

    assert result.sentence_verdicts == ()
    assert result.to_dict()["sentence_verdicts"] == []


def test_offline_census_reads_verdicts_and_reports_historic_runs_as_unjudgeable(tmp_path) -> None:
    """读侧：有字段的 run 进分母，没字段的历史 run 单列，不进任何分母。"""

    import importlib.util
    import json
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "offline_judge_verdict_census",
        Path(__file__).resolve().parents[2] / "scripts" / "offline_judge_verdict_census.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    frame, structural = _structural("市场下跌（E1）。据E1显示成交额放大。据E99显示反弹。")
    web_evidence = replace(structural.outcome.evidence[0], evidence_tier="public_web")
    structural = replace(structural, outcome=replace(structural.outcome, evidence=(web_evidence,)))
    judge = _judge(False, rejected=(2, 3), issues=("第2句无证据。", "第3句引用表外 E99。"))
    result = _verify(structural, frame, judge)

    live_run = tmp_path / "u" / "runs" / "run_20260903_150000_000001"
    live_run.mkdir(parents=True)
    (live_run / "continuous-episode.json").write_text(
        json.dumps({"semantic_verifier": result.to_dict()}, ensure_ascii=False), encoding="utf-8"
    )
    old_run = tmp_path / "u" / "runs" / "run_20260827_120000_000002"
    old_run.mkdir(parents=True)
    (old_run / "continuous-episode.json").write_text(
        json.dumps({"semantic_verifier": {"issues": []}}), encoding="utf-8"
    )

    report = module.census(module._iter_episode_files(tmp_path), since=None)

    assert report["runs_with_field"] == 1
    assert report["runs_without_field"] == 1
    assert report["verdict_count"] == 2
    assert report["by_decision"] == {VERDICT_DEMOTED: 1, VERDICT_DELETED: 1}
    # 第 3 句只引了表外 E99 → 机械删除、无出处；第 2 句引 E1（public_web）→ 语义、降级。
    assert report["deleted"]["count"] == 1
    assert report["deleted"]["with_source_count"] == 0
    assert report["deleted"]["unresolved_ordinal_only_count"] == 1
    assert report["demoted"]["source_tiers"] == {"public_web": 1}
    assert report["verdict"].startswith("可判")
    assert "不可判" in module.census(module._iter_episode_files(old_run), since=None)["verdict"]
    rendered = module.render_markdown(report)
    assert "有出处" in rendered and "public_web" in rendered
