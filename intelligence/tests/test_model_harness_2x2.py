"""模型 × harness 2×2 冻结工具：排程可复现且平衡、作废口径、三条可判检验、判定表每一行。"""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

import pytest

from intelligence.eval import model_harness_2x2 as m

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "docs" / "superpowers" / "specs" / "2026-09-30-model-harness-2x2-preregistration.md"
SEEN = [f"S{i:02d}" for i in range(1, 29)]
QUESTIONS = list(m.UNSEEN_QUESTIONS) + [f"S{i:02d}" for i in range(1, 11)]
BASE = {q: 0.3 + 0.1 * (i % 3) for i, q in enumerate(QUESTIONS)}


def _records(score_of, *, questions=QUESTIONS, reps=3, drop=()):
    """score_of(question, cell, rep) → 单次得分；drop 里的 (题, 格) 不出任何记录。"""

    records, seq = [], 0
    for rep in range(reps):
        for q in questions:
            for cell in m.CELLS:
                if (q, cell) in drop:
                    continue
                seq += 1
                records.append(
                    {"seq": seq, "question": q, "cell": cell, "score": score_of(q, cell, rep),
                     "admission_exit": 0, "failure_class": None}
                )
    return records


def _additive(model=0.0, harness=0.0, interaction=0.0, per_question=None):
    def score_of(q, cell, _rep):
        bump = per_question(q) if per_question else model
        value = BASE[q] + (bump if cell[1] == "C" else 0) + (harness if cell[0] == "R" else 0)
        return value + (interaction if cell == "RC" else 0)

    return score_of


# ── 排程 ──


def test_seen_draw_is_exactly_the_preregistered_expression():
    shuffled = SEEN[::-1] + ["S03"]  # 顺序、重复都不影响：先去重排序再抽
    questions, picked = m.select_questions(shuffled)
    assert picked == random.Random(20260930).sample(sorted(SEEN), 10)
    assert questions == list(m.UNSEEN_QUESTIONS) + picked
    assert len(questions) == 20


@pytest.mark.parametrize(
    ("seen", "unseen", "message"),
    [
        (SEEN + ["D1"], m.UNSEEN_QUESTIONS, "重叠"),
        (SEEN[:9], m.UNSEEN_QUESTIONS, "不够抽"),
        (SEEN, ("D1", "D1"), "重复"),
    ],
)
def test_select_questions_rejects_bad_sets(seen, unseen, message):
    with pytest.raises(m.DesignError, match=message):
        m.select_questions(seen, unseen=unseen)


def test_latin_square_rotation():
    assert m.latin_square_cells(0, 0) == ("PG", "PC", "RG", "RC")
    assert m.latin_square_cells(1, 0) == ("PC", "RG", "RC", "PG")
    assert m.latin_square_cells(3, 1) == ("PG", "PC", "RG", "RC")


def test_plan_is_complete_balanced_and_reproducible():
    doc = m.plan_document(SEEN, models={"C": "claude-x"})
    runs = doc["runs"]
    assert len(runs) == 240 and [r["seq"] for r in runs] == list(range(1, 241))
    assert set(Counter((r["question"], r["cell"]) for r in runs).values()) == {3}
    # 每轮每题恰好一次、四格连排；四格在「第几个跑」上完全均衡（每轮每格每个位置 5 次）
    for round_no in (1, 2, 3):
        block = [r for r in runs if r["round"] == round_no]
        assert Counter(r["question"] for r in block) == Counter({q: 4 for q in doc["questions"]})
        slots = Counter((r["cell"], i % 4) for i, r in enumerate(block))
        assert set(slots.values()) == {5}
    assert {(r["cell"][1], r["provider"], r["model"]) for r in runs} == {
        ("G", "zhipu", "glm-5.3-flash"),
        ("C", "anthropic", "claude-x"),
    }
    assert m.plan_document(SEEN, models={"C": "claude-x"}) == doc
    orders = {tuple(r["question"] for r in runs if r["round"] == k)[::4] for k in (1, 2, 3)}
    assert len(orders) == 3  # 三轮题序各不相同


def test_plan_refuses_missing_model_bad_reps_and_duplicates():
    with pytest.raises(m.DesignError, match="模型 ID"):
        m.build_plan(QUESTIONS)
    with pytest.raises(m.DesignError, match="reps"):
        m.build_plan(QUESTIONS, reps=0, models={"C": "c"})
    with pytest.raises(m.DesignError, match="重复"):
        m.build_plan(["D1", "D1"], models={"C": "c"})


# ── 作废与取数 ──


@pytest.mark.parametrize(
    ("admission", "failure", "reason"),
    [
        (None, None, "admission_missing"),
        (1, None, "admission_exit_1"),
        (2, None, "admission_exit_2"),
        (0, "provider_rate_limited", "provider_rate_limited"),
        (0, "provider_overloaded", "provider_overloaded"),
        (0, "provider_unavailable", "provider_unavailable"),
        (0, "deadline_exhausted_local", None),  # 自家 deadline 烧完照常计分
        (0, None, None),
    ],
)
def test_void_reasons(admission, failure, reason):
    run = m.Run(seq=1, question="D1", cell="PG", score=0.0, admission_exit=admission, failure_class=failure)
    assert run.void_reason() == reason


@pytest.mark.parametrize(
    ("record", "message"),
    [
        ({"seq": 1, "question": "D1", "cell": "XX", "score": 1, "admission_exit": 0}, "格名"),
        ({"question": "D1", "cell": "PG", "score": 1, "admission_exit": 0}, "缺 seq"),
        ({"seq": 1, "question": "D1", "cell": "PG", "score": None, "admission_exit": 0}, "照常计分"),
        ({"seq": 1, "question": "D1", "cell": "PG", "score": 1.5, "admission_exit": 0}, "不在"),
    ],
)
def test_parse_runs_rejects_bad_records(record, message):
    with pytest.raises(m.DesignError, match=message):
        m.parse_runs([record])


def test_parse_runs_rejects_duplicate_seq_and_void_runs_need_no_score():
    ok = {"seq": 1, "question": "D1", "cell": "PG", "score": None, "admission_exit": 2}
    assert m.parse_runs([ok])[0].void_reason() == "admission_exit_2"
    with pytest.raises(m.DesignError, match="重复"):
        m.parse_runs([ok, dict(ok)])


def _run(seq, score, reason=None):
    if reason == "admission":
        return m.Run(seq, "D1", "PG", None, 1, None)
    return m.Run(seq, "D1", "PG", score, 0, reason)


def test_first_n_valid_by_seq_and_requeue_limit():
    attempts = [_run(6, 1.0), _run(1, None, "provider_rate_limited"), _run(3, 1.0), _run(2, 0.5),
                _run(4, None, "admission"), _run(5, 0.0)]
    scores, incomplete, voids = m.select_valid(attempts, ["D1"])
    assert scores[("D1", "PG")] == [0.5, 1.0, 0.0]  # 按 seq，不按到达顺序；第 6 次多余不取
    assert voids == Counter({"provider_rate_limited": 1, "admission_exit_1": 1})
    assert [row["cell"] for row in incomplete] == ["PC", "RG", "RC"]  # 这三格压根没跑

    three_voids = [_run(1, None, "provider_overloaded"), _run(2, None, "provider_overloaded"),
                   _run(3, None, "provider_overloaded"), _run(4, 1.0), _run(5, 1.0), _run(6, 1.0)]
    scores, incomplete, _ = m.select_valid(three_voids, ["D1"])
    assert scores[("D1", "PG")] == []  # 第 3 次作废即超过「最多重排 2 次」，后面的不再算
    assert incomplete[0] == {"question": "D1", "cell": "PG", "valid": 0, "voids": 3}


# ── 噪声底与三条检验 ──


@pytest.mark.parametrize(
    ("score", "label"), [(1.0, "full"), (0.0, "zero"), (1e-12, "zero"), (0.999, "partial"), (0.5, "partial")]
)
def test_outcome_labels(score, label):
    assert m.outcome_label(score) == label


def test_noise_floor_is_the_max_cell_flip_rate():
    table = {
        "PG": {"D1": [1.0, 1.0, 0.0], "D2": [0.5, 0.5, 0.5]},  # 1/3、0 → 1/6
        "PC": {"D1": [1.0, 0.5, 0.0], "D2": [0.5, 0.2, 0.9]},  # 三档全不同 2/3；同为部分 0 → 1/3
        "RG": {"D1": [0.0, 0.0, 0.0], "D2": [1.0, 1.0, 1.0]},
        "RC": {"D1": [0.2, 0.3, 0.4], "D2": [0.0, 0.0, 0.5]},  # 0、1/3 → 1/6
    }
    scores = {(q, c): v for c, rows in table.items() for q, v in rows.items()}
    result = m.analyze_subset(scores, ["D1", "D2"], iterations=200)
    assert result["cell_flip_rates"] == {"PG": round(1 / 6, 9), "PC": round(1 / 3, 9), "RG": 0.0, "RC": round(1 / 6, 9)}
    assert result["noise_floor"] == round(1 / 3, 9)


def test_callable_requires_all_three_checks():
    assert m.gate(0.2, (0.1, 0.3), 0.1)["callable"] is True
    assert m.gate(0.08, (0.05, 0.1), 0.05)["checks"]["min_effect"] is False
    assert m.gate(0.15, (0.1, 0.2), 0.2)["checks"]["floor"] is False
    assert m.gate(0.15, (-0.01, 0.3), 0.1)["checks"]["ci_excludes_zero"] is False
    assert m.gate(0.15, (0.0, 0.3), 0.1)["checks"]["ci_excludes_zero"] is False  # 端点恰为 0 也算含 0
    assert m.gate(-0.15, (-0.3, -0.01), 0.1)["callable"] is True  # 负方向同样可判
    # 边界：浮点里 0.3-0.2 = 0.0999…，恰好等于噪声底也算过（与 ab_decision 同一口径）
    assert m.gate(0.3 - 0.2, (0.05, 0.15), 0.1)["callable"] is True


@pytest.mark.parametrize(
    ("dm", "dh", "decision"),
    [
        ((True, 0.2), (False, 0.0), "model_only"),
        ((False, 0.0), (True, 0.2), "harness_only_react_better"),
        ((False, 0.0), (True, -0.2), "harness_only_product_better"),
        ((True, 0.2), (True, -0.2), "both"),
        ((False, 0.05), (False, 0.05), "neither"),
    ],
)
def test_decision_table_rows(dm, dh, decision):
    assert m.decide({"callable": dm[0], "value": dm[1]}, {"callable": dh[0], "value": dh[1]}) == decision


# ── 端到端：每一行判定都能从数据走到 ──


@pytest.mark.parametrize(
    ("effects", "decision", "hypotheses", "direction"),
    [
        ({"model": 0.2}, "model_only", (True, False, False), ("C>G", "=")),
        ({"model": -0.2}, "model_only", (False, False, False), ("G>C", "=")),  # 方向反了，H1 不成立
        ({"harness": 0.2}, "harness_only_react_better", (False, True, False), ("=", "R>P")),
        ({"harness": -0.2}, "harness_only_product_better", (False, False, False), ("=", "P>R")),
        ({"model": 0.2, "harness": 0.15}, "both", (True, False, False), ("C>G", "R>P")),
        ({"model": 0.05, "harness": 0.05}, "neither", (False, False, False), ("C>G", "R>P")),
        ({"interaction": 0.3}, "both", (False, False, True), ("C>G", "R>P")),
    ],
)
def test_end_to_end_decisions(effects, decision, hypotheses, direction):
    report = m.analyze(_records(_additive(**effects)))
    primary = report["primary"]
    assert primary["decision"] == decision
    assert tuple(primary["hypotheses"][h] for h in ("H1", "H2", "H3")) == hypotheses
    assert (primary["direction"]["model"], primary["direction"]["harness"]) == direction
    assert report["secondary_unseen"]["agrees_with_primary"] is True
    assert report["sensitivity"]["n_questions"] == 17
    text = m.render(report)
    assert f"判定：{decision} —— {m.DECISIONS[decision]}" in text


def test_high_rep_noise_blocks_the_call_through_the_floor():
    def noisy(q, cell, rep):
        if cell == "PG":
            return (1.0, 0.0, 0.5)[rep]  # 三档全不同：题翻转率 2/3
        return _additive(model=0.2)(q, cell, rep)

    primary = m.analyze(_records(noisy))["primary"]
    assert primary["noise_floor"] == round(2 / 3, 9)
    assert primary["effects"]["delta_m"]["checks"]["floor"] is False
    assert primary["decision"] == "neither"


def test_voided_runs_are_requeued_not_scored_zero():
    records = _records(_additive(model=0.2))
    # 把 D1/PC 的第一次改成限流：不计 0 分，按 seq 从后补的一次取数
    first = next(r for r in records if (r["question"], r["cell"]) == ("D1", "PC"))
    first.update(score=None, failure_class="provider_rate_limited")
    records.append({"seq": 10_000, "question": "D1", "cell": "PC", "score": BASE["D1"] + 0.2,
                    "admission_exit": 0, "failure_class": None})
    report = m.analyze(records)
    assert report["voids"] == {"total": 1, "by_reason": {"provider_rate_limited": 1}}
    assert report["primary"]["effects"]["delta_m"]["value"] == 0.2
    assert "作废 1 次（provider_rate_limited 1）" in m.render(report)


def test_incomplete_cell_blocks_the_main_call_and_reports_simple_effects():
    report = m.analyze(_records(_additive(model=0.2), drop={("D4", "PC")}))
    primary = report["primary"]
    assert primary["decision"] == "incomplete"
    assert primary["incomplete_cells"] == ["PC"]
    assert set(primary["simple_effects"]) == {"model_within_R", "harness_within_G"}
    assert primary["simple_effects"]["model_within_R"]["value"] == 0.2
    assert "effects" not in primary
    text = m.render(report)
    assert "有格不完整，不下主结论" in text and "PC/D4（有效 0，作废 0）" in text and "仅供参考" in text


def test_incomplete_question_that_sensitivity_drops_is_flagged_as_disagreeing():
    report = m.analyze(_records(_additive(model=0.2), drop={("D5", "RG")}))
    assert report["primary"]["decision"] == "incomplete"
    assert report["sensitivity"]["decision"] == "model_only"
    assert report["sensitivity"]["agrees_with_primary"] is False


def test_sensitivity_flip_is_called_out():
    # 17 题各 +0.08（单看过不了最小效应），D2/D5/D6 各 +0.4 → 主判定靠这三题才过 0.10
    big = {"D2", "D5", "D6"}
    report = m.analyze(_records(_additive(per_question=lambda q: 0.4 if q in big else 0.08)))
    assert report["primary"]["decision"] == "model_only"
    assert report["sensitivity"]["decision"] == "neither"
    text = m.render(report)
    assert "⚠️ 与主判定不同" in text and "主结论依赖被针对性修过的题" in text


def test_subsets_that_cannot_run_are_skipped_loudly():
    report = m.analyze(_records(_additive(model=0.2)), unseen=("X1",), exclude=("Z9",))
    assert report["secondary_unseen"]["skipped"].endswith("X1")
    assert "Z9" in report["sensitivity"]["skipped"]
    assert "未执行" in m.render(report)


def test_records_outside_the_question_set_are_rejected():
    with pytest.raises(m.DesignError, match="题集外"):
        m.analyze(_records(_additive(), questions=["D1", "D2"]), questions=["D1"])
    with pytest.raises(m.DesignError, match="为空"):
        m.analyze_subset({}, [])


def test_bootstrap_is_seeded_and_brackets_the_mean():
    rows = [[v] for v in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)]
    first = m.bootstrap_ci(rows)
    assert first == m.bootstrap_ci(rows)
    low, high = first[0]
    assert low < 0.45 < high and 0.25 < low and high < 0.65


# ── 命令行 ──


def _cli():
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location("model_harness_2x2_cli", REPO / "scripts" / "model_harness_2x2.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("model_harness_2x2_cli", module)
    spec.loader.exec_module(module)
    return module


def test_cli_plan_then_analyze(tmp_path, capsys):
    cli = _cli()
    seen_file = tmp_path / "seen.txt"
    seen_file.write_text("# seen 组\n" + "\n".join(SEEN) + "\n", encoding="utf-8")
    assert cli.main(["plan", "--seen-file", str(seen_file), "--model-c", "claude-x"]) == 0
    out = capsys.readouterr()
    plan = json.loads(out.out)
    assert len(plan["runs"]) == 240 and "240 次" in out.err
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    plan_questions = plan["questions"]
    base = {q: 0.3 + 0.1 * (i % 3) for i, q in enumerate(plan_questions)}
    records = [
        {"seq": r["seq"], "question": r["question"], "cell": r["cell"],
         "score": base[r["question"]] + (0.2 if r["cell"][1] == "C" else 0.0), "admission_exit": 0,
         "failure_class": None}
        for r in plan["runs"]
    ]
    # CLI 现在必须检查原始产物；这里只构造明示的单测夹具，不靠自报 exit=0。
    for row in records:
        artifact = tmp_path / f"episode-{row['seq']}.json"
        artifact.write_text(json.dumps({"served_model": plan["models"][row["cell"][1]]}))
        row["artifacts"] = [artifact.name]
    runs_path = tmp_path / "runs.jsonl"
    runs_path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    assert cli.main(["analyze", str(runs_path), "--plan", str(plan_path)]) == 0
    assert "判定：model_only" in capsys.readouterr().out

    array_path = tmp_path / "runs.json"
    array_path.write_text(json.dumps(records), encoding="utf-8")
    assert cli.main(["analyze", str(array_path), "--plan", str(plan_path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["primary"]["decision"] == "model_only"


def test_cli_rejects_bad_inputs(tmp_path, capsys):
    cli = _cli()
    assert cli.main(["plan", "--seen", "S01,S02", "--model-c", "c"]) == 2
    assert "不够抽" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        cli.main(["plan", "--seen", ",".join(SEEN)])  # 缺 --model-c
    bad_plan = tmp_path / "plan.json"
    bad_plan.write_text(json.dumps({"schema": "other"}), encoding="utf-8")
    runs = tmp_path / "runs.jsonl"
    runs.write_text('{"seq": 1, "question": "D1", "cell": "PG", "score": 1, "admission_exit": 0}\n', encoding="utf-8")
    assert cli.main(["analyze", str(runs), "--plan", str(bad_plan)]) == 2
    runs.write_text('{"seq": 1, "question": "D1", "cell": "QQ", "score": 1, "admission_exit": 0}\n', encoding="utf-8")
    assert cli.main(["analyze", str(runs)]) == 2
    runs.write_text("{not json\n", encoding="utf-8")
    assert cli.main(["analyze", str(runs)]) == 2
    assert "输入不符合预注册" in capsys.readouterr().err


# ── 预注册原文与冻结常量同一份口径 ──


def test_constants_match_the_preregistration_text():
    text = SPEC.read_text(encoding="utf-8")
    for needle in (
        "`glm-5.3-flash`",
        "random.Random(20260930).sample(sorted(seen), 10)",
        "10,000",
        "0.10",
        "D2 / D5 / D6",
        "240",
        "(题位 + 轮次) % 4",
        "scripts/model_harness_2x2.py",
    ):
        assert needle in text, needle
    assert m.SEED == 20260930 and m.MIN_EFFECT == 0.10 and m.BOOTSTRAP_ITERATIONS == 10_000
    assert m.DEFAULT_MODELS["G"] == "glm-5.3-flash" and m.SENSITIVITY_EXCLUDE == ("D2", "D5", "D6")
    assert m.MAX_REQUEUES == 2 and m.DEFAULT_REPS == 3 and m.SEEN_SAMPLE_SIZE == 10
