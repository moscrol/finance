"""运行态拆分（R-20260815-01 / -02）。

背景：``evidence_bound`` 是交付层计数，把至少四种互不相同的运行态压成同一个
``0``。2026-08-14 那份诊断因此把 9 个 ``Connection refused`` 读成了业务行为，
并据以推出「C 组按题型设计不填证据」的错误结论。

下面每个形状的字段取值都来自 2026-08-14/15 实测的真实 run，注释里写明出处，
**不要按直觉改数**——改了就不再是那次事故的回归。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.eval.acceptance import (
    EXECUTION_STATES,
    TurnTrace,
    _classify_execution_state,
    _read_episode_facts,
    counts_toward_quality,
    summarize_execution_states,
)


def _episode(
    tmp_path: Path,
    run_id: str,
    *,
    user: str = "tester",
    draft: str = "",
    evidence: int = 0,
    bindings: int | list[tuple[str, int, bool]] = 0,
    missing: int = 0,
    fulfilled: int = 0,
) -> Path:
    run_dir = tmp_path / user / "runs" / run_id
    run_dir.mkdir(parents=True)
    outputs = [{"output_id": f"m{i}", "status": "missing"} for i in range(missing)]
    outputs += [{"output_id": f"f{i}", "status": "fulfilled"} for i in range(fulfilled)]
    payload = {
        "outcome": {
            "draft": draft,
            "evidence": [{"content_hash": f"h{i}"} for i in range(evidence)],
            "bindings": (
                [
                    {
                        "output_id": oid,
                        "evidence_hashes": [f"h{j}" for j in range(n)],
                        "gap": "缺少一手证据" if gap else None,
                    }
                    for oid, n, gap in bindings
                ]
                if isinstance(bindings, list)
                else [{"output_id": f"o{i}"} for i in range(bindings)]
            ),
        },
        "structural_verifier": {"completion": {"outputs": outputs}},
    }
    (run_dir / "continuous-episode.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    return run_dir


def test_connection_refused_turn_is_not_run_and_leaves_the_denominator() -> None:
    """C2-C10 形状：`status=error` + `trace_steps=[]`（20260813T1810Z 实测 9 例）。

    这是部署接缝失败。把它计进质量分母，就会得到「C 组 90% 证据为零」这种
    读起来像业务结论、实际是服务器不可达的数字。
    """

    trace = TurnTrace(
        question="q",
        status="error",
        error="<urlopen error [Errno 61] Connection refused>",
    )
    assert _classify_execution_state(trace, None) == "not_run"
    assert counts_toward_quality({"execution_state": "not_run"}) is False


def test_clarification_turn_is_not_a_failure() -> None:
    """B6 形状：2.0s / 4 步 / 无 gaps / 无 episode 产物。

    1446Z 与 1813Z 两次复跑都是这个形状，是稳定的产品行为（反问用户），
    不是「证据为零的失败」。它必须与 `no_evidence` 分开。
    """

    trace = TurnTrace(
        question="q",
        status="completed",
        elapsed_s=2.0,
        trace_steps=["research", "understanding", "research", "research"],
    )
    assert _classify_execution_state(trace, None) == "clarification"
    # 澄清轮仍留在分母里：它是真实产品行为，屏蔽它等于关掉信号
    assert counts_toward_quality({"execution_state": "clarification"}) is True


def test_retrieved_but_never_synthesized(tmp_path: Path) -> None:
    """B4 在 20260813T1810Z 的形状：取回 125 条证据、draft 为空、零绑定。"""

    _episode(tmp_path, "r1", draft="", evidence=125, bindings=0, missing=3)
    facts = _read_episode_facts("r1", "tester")
    assert facts is not None
    assert facts["evidence_retrieved"] == 125
    trace = TurnTrace(question="q", status="completed", trace_steps=["a"] * 38)
    assert _classify_execution_state(trace, facts) == "retrieved_unsynthesized"


def test_bound_but_dropped_is_distinct_from_never_retrieving(tmp_path: Path) -> None:
    """B1 在 1446Z / 1813Z 两次复跑的形状：draft 有、3 条绑定有哈希、全被判缺。

    这是本轮最要紧的一格：它和 `no_evidence` 在旧读数里都是 `0`，但成因相反
    ——一个是压根没取到，一个是取到并绑上了却在交付前被零掉。
    """

    _episode(
        tmp_path,
        "r2",
        draft="x" * 302,
        evidence=19,
        bindings=[("direct_assessment", 1, True), ("chain_mapping", 6, True)],
        missing=3,
    )
    facts = _read_episode_facts("r2", "tester")
    trace = TurnTrace(question="q", status="completed", trace_steps=["a"] * 21)
    assert _classify_execution_state(trace, facts) == "gap_zeroed"

    _episode(tmp_path, "r3", draft="y" * 209, evidence=0, bindings=3, missing=3)
    facts_empty = _read_episode_facts("r3", "tester")
    assert _classify_execution_state(trace, facts_empty) == "no_evidence"


def test_mixed_turn_keeps_both_slot_shapes_visible(tmp_path: Path) -> None:
    """B7@RunA 实测形状：同一 turn 内真缺口格与滑档格并存（R-20260815-07）。

    `direct_answer` 0 哈希是**真缺口**，判缺正确、不该修；`evidence_boundary`
    13 哈希带 gap 是**滑档**，证据被无谓扣住、该修。只给 turn 级一个标签会把
    其中一种抹掉——那是 `evidence_bound` 同码问题在下一层的复发。
    """

    _episode(
        tmp_path,
        "r7",
        draft="w" * 266,
        evidence=13,
        bindings=[("direct_answer", 0, True), ("evidence_boundary", 13, True)],
        missing=2,
    )
    facts = _read_episode_facts("r7", "tester")
    assert facts["slot_shapes"] == {
        "direct_answer": "no_hash",
        "evidence_boundary": "gap_zeroed",
    }
    assert facts["slots_gap_zeroed"] == 1
    assert facts["slots_no_hash"] == 1
    trace = TurnTrace(question="q", status="completed", trace_steps=["a"] * 16)
    # 混合形按 gap_zeroed 归类：存在可修的格，就是行动意义上更强的信号
    assert _classify_execution_state(trace, facts) == "gap_zeroed"


def test_all_slots_without_hashes_is_a_true_gap_not_a_defect(tmp_path: Path) -> None:
    """被判缺的格全部零哈希 → `no_hash`：判缺是**正确行为**，不该当缺陷去修。"""

    _episode(
        tmp_path,
        "r8",
        draft="v" * 180,
        evidence=4,
        bindings=[("direct_answer", 0, True), ("evidence_boundary", 0, True)],
        missing=2,
    )
    facts = _read_episode_facts("r8", "tester")
    assert facts["slots_gap_zeroed"] == 0
    assert facts["slots_no_hash"] == 2
    trace = TurnTrace(question="q", status="completed", trace_steps=["a"] * 12)
    assert _classify_execution_state(trace, facts) == "no_hash"


def test_delivered_when_evidence_reaches_the_acceptance_surface(
    tmp_path: Path,
) -> None:
    """B4 在 1446Z 的形状：绑定不带 gap、三格 fulfilled、eb=10。"""

    _episode(tmp_path, "r4", draft="z" * 593, evidence=129, bindings=3, fulfilled=3)
    facts = _read_episode_facts("r4", "tester")
    trace = TurnTrace(question="q", status="completed", evidence_bound=10)
    assert _classify_execution_state(trace, facts) == "delivered"


def test_missing_episode_artifact_is_undetermined_not_a_guess() -> None:
    """拿不到 episode 产物时不许猜一个像样的默认值。

    公共 `/trace` 是脱敏展示投影（step_id 为哈希、name 只有 research /
    understanding），结构化判据本来就取不到。此时落 `undetermined` 是唯一诚实的
    写法——把它默认成 `no_evidence` 会凭空制造一个业务结论。
    """

    trace = TurnTrace(question="q", status="completed", trace_steps=["a"] * 21)
    assert _classify_execution_state(trace, None) == "undetermined"
    assert counts_toward_quality({"execution_state": "undetermined"}) is True


def test_read_episode_facts_returns_none_without_users_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FORESIGHT_USERS_DIR", raising=False)
    assert _read_episode_facts("whatever", "tester") is None


def test_legacy_turns_without_execution_state_still_classify() -> None:
    """旧产物没有 `execution_state`，退回既有判据，不得整批掉出分母。"""

    assert counts_toward_quality({"status": "completed", "trace_steps": ["a"]}) is True
    assert counts_toward_quality({"status": "error", "trace_steps": []}) is False


def test_every_state_is_reachable_and_frozen() -> None:
    """枚举是冻结的：新增值必须同步判定函数，否则又退回同码读数。"""

    assert set(EXECUTION_STATES) == {
        "not_run",
        "clarification",
        "no_evidence",
        "retrieved_unsynthesized",
        "gap_zeroed",
        "no_hash",
        "delivered",
        "undetermined",
    }


def test_summary_drops_not_run_from_the_quality_denominator() -> None:
    """20260813T1810Z 的真实构成：19 题跑了、9 题 Connection refused。

    旧口径分母 28，于是 C 组读作「90% 证据为零」。新口径分母 19，被剔除的 9 题
    逐个列名——剔除必须留痕，否则下一个人无法判断分母是怎么来的。
    """

    cases = [
        {"case_id": f"A{i}", "turns": [{"execution_state": "delivered"}]}
        for i in range(1, 11)
    ]
    cases += [
        {"case_id": "B1", "turns": [{"execution_state": "retrieved_unsynthesized"}]},
        {"case_id": "B5", "turns": [{"execution_state": "gap_zeroed"}]},
        {"case_id": "C1", "turns": [{"execution_state": "delivered"}]},
    ]
    cases += [
        {"case_id": f"C{i}", "turns": [{"execution_state": "not_run"}]}
        for i in range(2, 11)
    ]
    summary = summarize_execution_states(cases)
    assert summary["quality_denominator"] == 13
    assert summary["excluded_from_denominator"] == [f"C{i}" for i in range(2, 11)]
    assert summary["execution_state_tally"]["not_run"] == 9
    assert summary["execution_state_tally"]["gap_zeroed"] == 1


def test_summary_skips_cases_without_turns() -> None:
    assert summarize_execution_states([{"case_id": "X", "turns": []}]) == {
        "execution_state_tally": {},
        "execution_state_source_tally": {},
        "quality_denominator": 0,
        "excluded_from_denominator": [],
    }


def test_summary_reports_how_many_states_are_artifact_backed() -> None:
    """来源必须跟着统计一起报。

    `api_only` 那部分只能落 not_run / clarification / undetermined 三档；
    不报来源，读者会把一张半数没有产物支撑的表当成全测出来的。
    """

    cases = [
        {
            "case_id": "A1",
            "turns": [
                {
                    "execution_state": "delivered",
                    "execution_state_source": "episode_artifact",
                }
            ],
        },
        {
            "case_id": "C2",
            "turns": [
                {"execution_state": "not_run", "execution_state_source": "api_only"}
            ],
        },
    ]
    summary = summarize_execution_states(cases)
    assert summary["execution_state_source_tally"] == {
        "api_only": 1,
        "episode_artifact": 1,
    }


@pytest.fixture(autouse=True)
def _users_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path))


def test_true_gap_slots_from_the_clean_baseline_batch(tmp_path: Path) -> None:
    """干净基线批（`20260814T1926Z-r3-clean-baseline`）实测的 6 个真缺口格。

    取值来自该批 A4 / C6 / C9 / C10-t3：这些格 `n_hash=0` 且带 gap，structural 判
    `missing` 是**正确行为**，不是缺陷。把它们和滑档格分开，正是 R-20260815-07
    的目的——同一个 `missing` 底下，一种该修、一种不该动。
    C10-t3 两格（`direct_answer`+`evidence_boundary`）被 tally 按首轮掩成
    delivered，勘误 E-r3-2 补进计数；本用例仍用 C6 形状自证分类器。

    注：该批 `gap_zeroed` 出现 **0 次**（R-001 部署后该形状未在本窗口再现），
    故 `gap_zeroed` 一侧仍只由三个冻结 run 夹具覆盖，本用例不冒充有 live 样本。
    """

    _episode(
        tmp_path,
        "c6",
        draft="u" * 300,
        evidence=0,
        bindings=[("direct_answer", 0, True), ("evidence_boundary", 0, True)],
        missing=2,
    )
    facts = _read_episode_facts("c6", "tester")
    assert facts["slot_shapes"] == {
        "direct_answer": "no_hash",
        "evidence_boundary": "no_hash",
    }
    assert facts["slots_gap_zeroed"] == 0
    trace = TurnTrace(question="q", status="completed", trace_steps=["a"] * 18)
    # C6 实测 evidence_retrieved=0，故先落 no_evidence——真缺口格的判缺与
    # 「压根没取到」在本批同时出现，两者也必须分得开
    assert _classify_execution_state(trace, facts) == "no_evidence"
