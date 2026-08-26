"""inherited_golden 观察生成器的行为合同。

钉住四件事：
1. 四条闸轴（answered / 实体召回 / episode 语法引用真实性 / forbid 表）各自的
   pass/fail/unjudgeable 判定；
2. 引用真实性用的是 episode 语法（E 号 ∈ [1, evidence_retrieved]），不是
   agent_eval 的 [SGRW] 语法——语法漂移不得记成产品失败；
3. 免责声明/概念召回/工具跨度是报告项不闸（60/60 turn 实证 episode 公开稿
   不渲染「非投资建议」）；
4. 端到端：对真实 cases/overlay 出 sidecar，必须能过 load_observation_artifact
   的哈希与 schema 校验（自检不过不落盘）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.eval.acceptance import _read_episode_facts
from intelligence.eval.inherited_golden import (
    EPISODE_CITE_RE,
    load_golden_spec,
    observe_case,
    write_truth_sidecar,
)

REPO = Path(__file__).resolve().parents[2]
CASES_PATH = REPO / "intelligence/eval/cases/acceptance_cases.json"

GOLDEN = {
    "id": "fixture-golden",
    "expect_entities": ["甲公司", "乙公司", "丙公司", "丁公司"],
    "expect_concepts": ["光刻胶"],
    "min_tool_calls": 3,
    "max_tool_calls": 40,
    "entity_recall_gate": 0.5,
    "forbid_entities": ["无关公司"],
    "forbid_phrases": ["业绩已兑现"],
}
CASE = {"id": "B1-fixture", "inherit_from": "x#fixture-golden"}


def _turn(answer: str, retrieved: int | None = 30, tools: list[str] | None = None):
    turn = {"question": "q", "answer": answer, "evidence_retrieved": retrieved}
    if tools is not None:
        turn["episode_tools_called"] = tools
    return turn


def test_cite_re_matches_episode_grammar_variants() -> None:
    text = "涨 4.19%（E15），叠加 [E2] 与裸引 E7；年份 2026 与 E 系列型号E不误报"
    assert EPISODE_CITE_RE.findall(text) == ["15", "2", "7"]


def test_all_axes_pass() -> None:
    obs = observe_case(
        CASE,
        GOLDEN,
        [_turn("甲公司、乙公司、丙公司 光刻胶 领涨（E3），详见 E7", tools=["kb_search"] * 4)],
    )
    assert obs["state"] == "pass"
    assert "实体召回 0.75" in obs["reason"]
    assert obs["evidence_refs"] == ["turn:0"]


def test_entity_recall_below_gate_fails() -> None:
    obs = observe_case(CASE, GOLDEN, [_turn("只有甲公司 光刻胶（E1）")])
    assert obs["state"] == "fail"
    assert "实体召回 0.25" in obs["reason"]


def test_dangling_citation_beyond_retrieved_fails() -> None:
    obs = observe_case(CASE, GOLDEN, [_turn("甲公司、乙公司 光刻胶 见 E99", retrieved=30)])
    assert obs["state"] == "fail"
    assert "E99" in obs["reason"]


def test_citation_without_retrieved_count_is_unjudgeable() -> None:
    obs = observe_case(CASE, GOLDEN, [_turn("甲公司、乙公司 光刻胶 见 E3", retrieved=None)])
    assert obs["state"] == "unjudgeable"
    assert "evidence_retrieved" in obs["reason"]


def test_forbid_entity_and_phrase_fail() -> None:
    obs = observe_case(
        CASE, GOLDEN, [_turn("甲公司、乙公司 光刻胶；无关公司 业绩已兑现（E1）")]
    )
    assert obs["state"] == "fail"
    assert "错配题材实体" in obs["reason"]
    assert "overclaim" in obs["reason"]


def test_disclaimer_and_tools_are_report_only() -> None:
    # 无免责声明 + 工具埋点缺失：都不许把 pass 变 fail
    obs = observe_case(CASE, GOLDEN, [_turn("甲公司、乙公司 光刻胶（E1）")])
    assert obs["state"] == "pass"
    assert "免责声明轴按引擎语法降为报告项" in obs["reason"]
    assert "无 episode_tools_called 埋点" in obs["reason"]


def test_load_golden_spec_resolves_real_inherit_from() -> None:
    golden = load_golden_spec("intelligence/eval/cases/agent_cases.json#photoresist")
    assert golden["id"] == "photoresist"
    assert "彤程新材" in golden["expect_entities"]


def test_end_to_end_sidecar_passes_integrity_check(tmp_path: Path) -> None:
    """真实 cases/overlay + 合成 run：sidecar 必须过 load_observation_artifact。"""

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    inherit_ids = [c["id"] for c in cases["cases"] if c.get("inherit_from")]
    assert inherit_ids, "前提：acceptance_cases 里存在 inherit_from 用例"

    golden0 = load_golden_spec(
        next(c["inherit_from"] for c in cases["cases"] if c.get("inherit_from"))
    )
    hit_entities = "、".join(golden0["expect_entities"][:4])
    run_doc = {
        "generated_at": "2026-08-26T00:00:00Z",
        "cases": [
            {
                "case_id": case_id,
                "turns": [
                    {
                        "question": "q",
                        "answer": f"{hit_entities} 领涨（E3）",
                        "evidence_retrieved": 30,
                        "citations": [],
                        "evidence": [],
                    }
                ],
            }
            for case_id in inherit_ids
        ],
    }
    run_path = tmp_path / "run.json"
    run_path.write_text(json.dumps(run_doc, ensure_ascii=False), encoding="utf-8")

    out_path = tmp_path / "sidecar.json"
    payload = write_truth_sidecar(run_path, out_path, cases_path=CASES_PATH)
    assert out_path.is_file(), "自检通过才落盘"
    assert set(payload["case_observations"]) == set(inherit_ids)
    first = payload["case_observations"][inherit_ids[0]]["truth_observations"][
        "inherited_golden"
    ]
    assert first["state"] in {"pass", "fail"}
    assert first["evidence_refs"] == ["turn:0"]


def test_sidecar_refuses_run_without_inherit_cases(tmp_path: Path) -> None:
    run_path = tmp_path / "run.json"
    run_path.write_text(json.dumps({"cases": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        write_truth_sidecar(run_path, tmp_path / "out.json", cases_path=CASES_PATH)
    assert not (tmp_path / "out.json").exists()


def test_episode_facts_carry_tools_called(tmp_path: Path) -> None:
    """埋点：tool_request 事件名进 facts；观察生成器由此拿到工具跨度。"""

    run_dir = tmp_path / "tester" / "runs" / "r-tools"
    run_dir.mkdir(parents=True)
    payload = {
        "outcome": {"draft": "x", "evidence": [], "bindings": []},
        "structural_verifier": {"completion": {"outputs": []}},
        "events": [
            {"kind": "tool_request", "payload": {"name": "finance_query"}},
            {"kind": "tool_result", "payload": {"name": "finance_query"}},
            {"kind": "tool_request", "payload": {"name": "kb_search"}},
            {"kind": "model_turn", "payload": {}},
        ],
    }
    (run_dir / "continuous-episode.json").write_text(json.dumps(payload), encoding="utf-8")
    facts = _read_episode_facts("r-tools", "tester", users_dir=tmp_path)
    assert facts is not None
    assert facts["tools_called"] == ["finance_query", "kb_search"]
