"""四态口径：合成健康度不能再按 accepted/rejected 二分统计。

被测的那个错很具体：``judge_outage_released``（绑定过了、语义审缺席、带告示放行）
以前也写成 ``state=accepted``。按 accepted 聚合，2026-08-02 那批 23 个 turn 读出来
是 7 个健康，真实值是 1 个。

这里最要紧的一条不是分类本身，而是 **旧产物必须算 unknown 而不是默认算好** ——
把「没测到」和「测到是好的」混为一谈，正是这次要修的毛病本身。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.eval import synthesis_health as sh

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = REPO_ROOT / "intelligence" / "eval" / "runs"


def _turn(**kwargs) -> dict:
    base = {"status": "completed", "answer": "正文", "elapsed_s": 10.0}
    base.update(kwargs)
    return base


class TestClassification:
    def test_modern_released_state_is_its_own_bucket(self) -> None:
        health = sh.classify_turn(
            "A1",
            _turn(
                synthesis_diagnostic={
                    "state": "released_unverified",
                    "reason_code": "judge_outage_released",
                }
            ),
        )

        assert health.state == sh.RELEASED_UNVERIFIED
        assert not health.inferred_from_answer

    def test_legacy_accepted_with_notice_is_reclassified(self) -> None:
        """修复前的产物：state 写着 accepted，正文却说语义审没跑。以正文为准。"""
        health = sh.classify_turn(
            "A5",
            _turn(
                answer="（本条已通过证据绑定校验，但语义复核因服务瞬时问题未完成。）\n正文",
                synthesis_diagnostic={
                    "state": "accepted",
                    "reason_code": "validated",
                },
            ),
        )

        assert health.state == sh.RELEASED_UNVERIFIED
        assert health.inferred_from_answer

    def test_clean_accepted_is_a_full_pass(self) -> None:
        health = sh.classify_turn(
            "A4",
            _turn(
                synthesis_diagnostic={
                    "state": "accepted",
                    "reason_code": "validated",
                }
            ),
        )

        assert health.state == sh.FULL_PASS

    @pytest.mark.parametrize(
        ("state", "expected"),
        [
            ("rejected", sh.TEMPLATE_FALLBACK),
            ("failed", sh.TEMPLATE_FALLBACK),
            ("attempted", sh.TEMPLATE_FALLBACK),
            ("not_prepared", sh.NOT_SYNTHESIZED),
            ("not_requested", sh.NOT_SYNTHESIZED),
        ],
    )
    def test_remaining_states_map_deterministically(
        self, state: str, expected: str
    ) -> None:
        health = sh.classify_turn(
            "X", _turn(synthesis_diagnostic={"state": state, "reason_code": "r"})
        )

        assert health.state == expected

    def test_missing_diagnostic_is_unknown_not_healthy(self) -> None:
        """没有诊断字段的旧产物必须落 unknown。

        这条是整个文件的重点：如果它退化成 full_pass，仪表盘就会在数据缺失时
        显示一切正常——那正是我们刚修完的那个失败模式。
        """
        health = sh.classify_turn("old", _turn())

        assert health.state == sh.UNKNOWN

    def test_unfinished_turns_are_excluded(self) -> None:
        payload = {
            "cases": [
                {
                    "case_id": "A1",
                    "turns": [
                        {"status": "error", "answer": ""},
                        {"status": "timeout", "answer": ""},
                    ],
                }
            ]
        }

        assert sh.classify_run(payload) == []


class TestAggregateOnFrozenArtifacts:
    """跑在真实冻结产物上——仪表盘自己也要有回归样本。"""

    PATHS = [
        RUNS_DIR / "20260802T154424Z.json",
        RUNS_DIR / "20260802T174057Z.json",
        RUNS_DIR / "20260802T180504Z.json",
    ]

    def test_aug02_batch_has_exactly_one_full_pass(self) -> None:
        missing = [path.name for path in self.PATHS if not path.exists()]
        if missing:
            pytest.skip(f"缺少冻结产物：{missing}")

        counts = sh.Counter()
        for path in self.PATHS:
            payload = json.loads(path.read_text(encoding="utf-8"))
            counts.update(sh.summarize(sh.classify_run(payload)))

        # 22 个 completed turn 里只有 1 个走完了完整链路。按旧口径读是 6 个。
        assert counts[sh.FULL_PASS] == 1
        assert counts[sh.RELEASED_UNVERIFIED] == 5
        assert counts[sh.TEMPLATE_FALLBACK] == 14
        assert counts[sh.NOT_SYNTHESIZED] == 1

    def test_old_artifacts_are_not_counted_as_healthy(self) -> None:
        path = RUNS_DIR / "20260801T034001Z.json"
        if not path.exists():
            pytest.skip("缺少冻结产物")

        payload = json.loads(path.read_text(encoding="utf-8"))
        counts = sh.summarize(sh.classify_run(payload))

        # 这批早于 synthesis_diagnostic 采集，全部应落 unknown。
        assert counts[sh.FULL_PASS] == 0
        assert counts[sh.UNKNOWN] == sum(counts.values())


def test_render_reports_phase_instrumentation_gap() -> None:
    """没有 phase 埋点的产物要在报告里说出来，否则读的人不知道查不出段。"""
    payload = {
        "preflight_detail": "revision=abc",
        "cases": [
            {
                "case_id": "A1",
                "turns": [
                    _turn(
                        synthesis_diagnostic={
                            "state": "rejected",
                            "reason_code": "grounded_required_fallback",
                        }
                    )
                ],
            }
        ],
    }

    assert sh._phase_note(payload) == "无 phase 埋点（查不出是哪一段）"

    payload["cases"][0]["turns"][0]["synthesis_diagnostic"]["phases"] = [
        {"name": "composer", "status": "failed"}
    ]
    assert sh._phase_note(payload) == "有 phase 埋点"


def _write_cli_run(
    tmp_path: Path,
    *,
    name: str = "sample.json",
    state: str = "accepted",
    completed: bool = True,
    include_diagnostic: bool = True,
) -> Path:
    turn = {
        "status": "completed" if completed else "timeout",
        "answer": "正文",
        "elapsed_s": 10.0,
    }
    if include_diagnostic:
        turn["synthesis_diagnostic"] = {
            "state": state,
            "reason_code": "validated",
            "phases": [{"name": "judge", "status": "ok"}],
        }
    payload = {
        "preflight_detail": "revision=abc",
        "cases": [{"case_id": "A4", "turns": [turn]}],
    }
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_cli_default_output_stays_byte_for_byte(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write_cli_run(tmp_path)

    assert sh.main([str(path)]) == 0

    assert capsys.readouterr().out == (
        "\n=== sample  revision=abc  [有 phase 埋点] ===\n"
        "  完整通过                 1/1\n"
        "\n=== 合计 1 个 completed turn ===\n"
        "  完整通过                 1/1  (100%)\n"
        "\n真实完整通过率：1/1 = 100%\n"
        "  注：放行未核验不计入通过——绑定过了但没有第二意见，"
        "把它算进健康数就是这次要修的那个错。\n"
    )


def test_gate_full_pass_returns_zero(tmp_path: Path) -> None:
    path = _write_cli_run(tmp_path)

    assert sh.main(["--gate", "--min-full-pass", "1.0", str(path)]) == 0


def test_gate_template_fallback_returns_one(tmp_path: Path) -> None:
    path = _write_cli_run(tmp_path, state="rejected")

    assert sh.main(["--gate", "--min-full-pass", "1.0", str(path)]) == 1


def test_gate_unknown_can_be_blocked_at_a_lower_ratio(tmp_path: Path) -> None:
    path = _write_cli_run(tmp_path, include_diagnostic=False)

    assert (
        sh.main(
            [
                "--gate",
                "--min-full-pass",
                "0.0",
                "--fail-on-unknown",
                str(path),
            ]
        )
        == 1
    )


def test_gate_fails_when_any_input_is_missing(tmp_path: Path) -> None:
    path = _write_cli_run(tmp_path)
    missing = tmp_path / "missing.json"

    assert (
        sh.main(
            [
                "--gate",
                "--min-full-pass",
                "1.0",
                str(path),
                str(missing),
            ]
        )
        == 1
    )


def test_gate_fails_when_an_input_has_no_completed_turn(tmp_path: Path) -> None:
    path = _write_cli_run(tmp_path, completed=False)

    assert sh.main(["--gate", "--min-full-pass", "0.0", str(path)]) == 1


@pytest.mark.parametrize("ratio", ["nan", "inf", "-0.1", "1.1"])
def test_gate_rejects_non_finite_or_out_of_range_ratio(
    tmp_path: Path,
    ratio: str,
) -> None:
    path = _write_cli_run(tmp_path)

    with pytest.raises(SystemExit) as caught:
        sh.main(["--gate", "--min-full-pass", ratio, str(path)])

    assert caught.value.code == 2


def test_gate_only_flags_require_gate(tmp_path: Path) -> None:
    path = _write_cli_run(tmp_path)

    with pytest.raises(SystemExit) as caught:
        sh.main(["--min-full-pass", "1.0", str(path)])

    assert caught.value.code == 2
