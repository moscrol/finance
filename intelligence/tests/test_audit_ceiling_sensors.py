"""封上限四形状传感器：量纲诚实 + 金标形状。

seam：``scripts/audit_ceiling_sensors.py`` 的 ``inspect_episode`` / ``audit`` /
退出码。不读生产 runs 目录也能复现判据；本机金标 run 在场时另加一条实跑钉。

A 缺字段必须报「不可判」不报 0——把 ``projection_cited_unbound_count`` 缺席
当成 0，本文件第一条就会红（变异目标）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.audit_ceiling_sensors import (  # noqa: E402
    audit,
    inspect_episode,
    main,
    render_report,
)


def _episode(**overrides: object) -> dict:
    base: dict = {
        "task_frame": {
            "raw_question": "CXO概念这波是怎么发酵到 2026-08-20 的",
            "subject": "CXO",
        },
        "contract": {
            "question": "CXO概念这波是怎么发酵到 2026-08-20 的",
            "subject": "CXO",
        },
        "semantic_verifier": {
            "judge_status": "repaired",
            "rejected_claim_indexes": [],
            "issues": [],
        },
        "structural_verifier": {
            "issues": [],
            "mandatory_missing_capabilities": [],
        },
        "events": [],
        "outcome": {"evidence": []},
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merged = dict(base[key])
            merged.update(value)
            base[key] = merged
        else:
            base[key] = value
    return base


def _write_run(root: Path, run_id: str, episode: dict) -> Path:
    run_dir = root / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "continuous-episode.json").write_text(
        json.dumps(episode, ensure_ascii=False), encoding="utf-8"
    )
    return run_dir


def test_missing_projection_field_is_unjudgeable_not_zero() -> None:
    """历史 run 没有 #298 字段：报不可判。当成 0 就是假绿。"""

    verdict = inspect_episode(_episode())
    assert verdict["A"]["status"] == "unjudgeable"
    assert verdict["A"]["hit"] is False
    assert "不可判" in verdict["A"]["summary"]


def test_projection_zero_is_clean_not_unjudgeable() -> None:
    verdict = inspect_episode(
        _episode(semantic_verifier={"projection_cited_unbound_count": 0})
    )
    assert verdict["A"]["status"] == "clean"
    assert verdict["A"]["hit"] is False


def test_projection_positive_is_shape_a_hit() -> None:
    verdict = inspect_episode(
        _episode(semantic_verifier={"projection_cited_unbound_count": 2})
    )
    assert verdict["A"]["status"] == "hit"
    assert verdict["A"]["hit"] is True
    assert "2" in verdict["A"]["summary"]


def test_shape_b_from_missing_mandatory_capability_issue() -> None:
    verdict = inspect_episode(
        _episode(
            semantic_verifier={
                "issues": [
                    "code=missing_mandatory_capability subject=mainline_context "
                    ":: missing mandatory capability evidence: mainline_context"
                ]
            }
        )
    )
    assert verdict["B"]["hit"] is True
    assert "missing_mandatory_capability" in verdict["B"]["summary"]


def test_shape_b_from_unreachable_without_tools_list() -> None:
    """落盘是输出格名单，不是布尔；非空即 True。"""

    verdict = inspect_episode(
        _episode(
            events=[
                {
                    "kind": "repair_goal",
                    "payload": {
                        "unreachable_without_tools": [
                            "direct_assessment",
                            "chain_mapping",
                        ],
                        "reopen_tools": False,
                    },
                }
            ]
        )
    )
    assert verdict["B"]["hit"] is True
    assert "unreachable_without_tools" in verdict["B"]["summary"]


def test_shape_c_from_marker_loss() -> None:
    verdict = inspect_episode(
        _episode(
            semantic_verifier={
                "issues": [
                    "code=marker_loss subject=chain_mapping :: "
                    "semantic repair removed required output: chain_mapping"
                ]
            }
        )
    )
    assert verdict["C"]["hit"] is True
    assert "marker_loss" in verdict["C"]["summary"]


def test_shape_c_from_repaired_with_rejected_indexes() -> None:
    verdict = inspect_episode(
        _episode(
            semantic_verifier={
                "judge_status": "repaired",
                "rejected_claim_indexes": [3, 7],
            }
        )
    )
    assert verdict["C"]["hit"] is True
    assert "rejected_claim_indexes" in verdict["C"]["summary"]


def test_shape_c_repaired_empty_indexes_is_not_a_hit() -> None:
    """B 臂形态：repaired 但零删句，批评走质检段——不是 C。"""

    verdict = inspect_episode(
        _episode(
            semantic_verifier={
                "judge_status": "repaired",
                "rejected_claim_indexes": [],
                "issues": ["第6句将区间首尾对比夸大为全程持续缩量"],
            }
        )
    )
    assert verdict["C"]["hit"] is False


def test_shape_c_from_repair_wiped_all_outputs() -> None:
    verdict = inspect_episode(
        _episode(
            semantic_verifier={
                "issues": [
                    "code=repair_wiped_all_outputs :: semantic repair removed every required output"
                ]
            }
        )
    )
    assert verdict["C"]["hit"] is True
    assert "repair_wiped_all_outputs" in verdict["C"]["summary"]


def test_shape_d_prefetch_short_name_vs_question_concept() -> None:
    """#288 漏网：问句是 PCB概念，预取观察值仍是短名 PCB。"""

    verdict = inspect_episode(
        _episode(
            task_frame={
                "raw_question": "PCB概念这波是怎么发酵到 2026-08-07",
                "subject": "PCB",
            },
            contract={"question": "PCB概念这波是怎么发酵到 2026-08-07"},
            outcome={
                "evidence": [
                    {
                        "tool": "market_data",
                        "title": "PCB 双红时间轴",
                        "source": "本地 DuckDB · 问句日预取",
                        "observations": [{"subject": "PCB", "metric": "pct_chg"}],
                    }
                ]
            },
        )
    )
    assert verdict["D"]["hit"] is True
    assert "PCB概念" in verdict["D"]["summary"]


def test_shape_d_prefetch_matches_question_exact_name() -> None:
    verdict = inspect_episode(
        _episode(
            outcome={
                "evidence": [
                    {
                        "tool": "market_data",
                        "title": "CXO概念 双红时间轴",
                        "source": "本地 DuckDB · 问句日预取",
                        "observations": [{"subject": "CXO概念"}],
                    }
                ]
            }
        )
    )
    assert verdict["D"]["hit"] is False


def test_gold_e4_shape_via_fixture() -> None:
    """E4 案字段形状：A 不可判、C 因 marker_loss 命中。

    实件 ``rejected_claim_indexes`` 是 []（repair 后清空，见 trace-profile），
    C 仍应由 ``marker_loss`` 落账触发。表里的 OR 不能退化成只看 indexes。
    """

    verdict = inspect_episode(
        _episode(
            task_frame={
                "raw_question": "钙钛矿电池板块到2026-08-18的发酵路径怎么走的？",
                "subject": "钙钛矿",
            },
            contract={
                "question": "钙钛矿电池板块到2026-08-18的发酵路径怎么走的？"
            },
            semantic_verifier={
                "judge_status": "repaired",
                "rejected_claim_indexes": [],
                "issues": [
                    "第2句引用未注册的E4",
                    "code=marker_loss subject=chain_mapping :: "
                    "semantic repair removed required output: chain_mapping",
                ],
            },
            events=[
                {
                    "kind": "repair_goal",
                    "payload": {
                        "unreachable_without_tools": [
                            "direct_assessment",
                            "chain_mapping",
                            "counterpoint",
                            "scenario_tree",
                        ]
                    },
                }
            ],
            outcome={
                "evidence": [
                    {
                        "tool": "market_data",
                        "title": "钙钛矿电池 双红时间轴",
                        "source": "本地 DuckDB · 问句日预取",
                        "observations": [{"subject": "钙钛矿电池"}],
                    }
                ]
            },
        )
    )
    assert verdict["A"]["status"] == "unjudgeable"
    assert verdict["C"]["hit"] is True
    assert verdict["D"]["hit"] is False


def test_gold_b_arm_is_clean_except_unjudgeable_a() -> None:
    verdict = inspect_episode(
        _episode(
            semantic_verifier={
                "judge_status": "repaired",
                "rejected_claim_indexes": [],
                "issues": ["第6句将区间写成持续缩量，观察事实不成立。"],
            },
            outcome={
                "evidence": [
                    {
                        "tool": "market_data",
                        "title": "CXO概念 双红时间轴",
                        "source": "本地 DuckDB · 问句日预取",
                        "observations": [{"subject": "CXO概念"}],
                    }
                ]
            },
        )
    )
    assert verdict["A"]["status"] == "unjudgeable"
    assert verdict["B"]["hit"] is False
    assert verdict["C"]["hit"] is False
    assert verdict["D"]["hit"] is False


def test_audit_window_filters_by_run_id_date(tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        "run_20260810_120000_000001",
        _episode(
            semantic_verifier={
                "issues": ["code=marker_loss subject=x :: removed"]
            }
        ),
    )
    _write_run(
        tmp_path,
        "run_20260821_171744_929436",
        _episode(
            semantic_verifier={
                "issues": ["code=marker_loss subject=chain_mapping :: removed"]
            }
        ),
    )
    report = audit(
        [tmp_path], since="2026-08-20", until="2026-08-21"
    )
    assert report["scanned"] == 1
    assert report["counts"]["C"] == 1
    assert report["hits"]["C"][0]["run_id"] == "run_20260821_171744_929436"


def test_bc_nonzero_exits_one(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write_run(
        tmp_path,
        "run_20260821_010000_1",
        _episode(
            semantic_verifier={
                "issues": ["code=marker_loss subject=chain_mapping :: removed"]
            }
        ),
    )
    code = main(["--runs-dir", str(tmp_path), "--since", "2026-08-21", "--until", "2026-08-21"])
    out = capsys.readouterr().out
    assert code == 1
    assert "C" in out
    assert "run_20260821_010000_1" in out


def test_clean_window_exits_zero(tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        "run_20260821_010000_2",
        _episode(
            semantic_verifier={"projection_cited_unbound_count": 0},
            outcome={
                "evidence": [
                    {
                        "source": "本地 DuckDB · 问句日预取",
                        "observations": [{"subject": "CXO概念"}],
                    }
                ]
            },
        ),
    )
    report = audit([tmp_path], since="2026-08-21", until="2026-08-21")
    assert report["counts"]["B"] == 0
    assert report["counts"]["C"] == 0
    rendered = render_report(report)
    assert "不可判" not in rendered or report["unjudgeable"]["A"] == 0


def test_report_lists_unjudgeable_a_separately(tmp_path: Path) -> None:
    _write_run(tmp_path, "run_20260821_010000_3", _episode())
    report = audit([tmp_path], since="2026-08-21", until="2026-08-21")
    assert report["unjudgeable"]["A"] == 1
    assert report["counts"]["A"] == 0
    text = render_report(report)
    assert "不可判" in text


_GOLD_E4 = (
    Path.home()
    / ".local/share/finance-workbench/users/linxiaoqi5111/runs"
    / "run_20260821_171744_929436"
)
_GOLD_B_ARM = (
    Path.home()
    / ".local/share/finance-workbench/users/probe-ab-0821-post/runs"
    / "run_20260821_164659_624916"
)


@pytest.mark.skipif(
    not (_GOLD_E4 / "continuous-episode.json").is_file(),
    reason="本机没有 E4 金标 run",
)
def test_live_gold_e4_reports_c_and_unjudgeable_a() -> None:
    report = audit([_GOLD_E4], since="2026-08-21", until="2026-08-21")
    assert report["scanned"] == 1
    assert report["unjudgeable"]["A"] == 1
    assert report["counts"]["A"] == 0
    assert report["counts"]["C"] == 1


@pytest.mark.skipif(
    not (_GOLD_B_ARM / "continuous-episode.json").is_file(),
    reason="本机没有 B 臂金标 run",
)
def test_live_gold_b_arm_is_clean() -> None:
    report = audit([_GOLD_B_ARM], since="2026-08-21", until="2026-08-21")
    assert report["scanned"] == 1
    assert report["counts"]["B"] == 0
    assert report["counts"]["C"] == 0
    assert report["counts"]["D"] == 0
    assert report["unjudgeable"]["A"] == 1


# --- V7 输入侧形状 I / III -------------------------------------------------

_KB_CAPS = ("kb_search", "evidence_search")
_R11_GOLD = (
    (
        "减肥药",
        Path.home()
        / ".local/share/finance-workbench/users/probe-ledger-0821/runs"
        / "run_20260821_165210_889002",
        "general_finance_qa",
    ),
    (
        "CXO-B",
        Path.home()
        / ".local/share/finance-workbench/users/probe-ab-0821-post/runs"
        / "run_20260821_164659_624916",
        "theme_analysis",
    ),
    (
        "CXO-A",
        Path.home()
        / ".local/share/finance-workbench/users/probe-tracediff-0821/runs"
        / "run_20260821_152044_472523",
        "theme_analysis",
    ),
    (
        "钙钛矿",
        Path.home()
        / ".local/share/finance-workbench/users/linxiaoqi5111/runs"
        / "run_20260821_171744_929436",
        "theme_analysis",
    ),
    (
        "皇氏集团",
        Path.home()
        / ".local/share/finance-workbench/users/linxiaoqi5111/runs"
        / "run_20260821_171744_955225",
        "stock_deep_dive",
    ),
)


def _kb_episode(
    *,
    question_type: str = "theme_analysis",
    allowed: tuple[str, ...] = _KB_CAPS,
    planned: tuple[str, ...] = ("market_data", "news_search"),
    events: list | None = None,
    traces: list | None = None,
) -> dict:
    return _episode(
        task_frame={"question_type": question_type},
        contract={
            "question_type": question_type,
            "allowed_capabilities": list(allowed),
            "evidence_plan": {
                "requirements": [{"capability": cap} for cap in planned]
            },
        },
        events=events or [],
        traces=traces or [],
        outcome={"traces": traces or [], "evidence": []},
    )


def _kb_tool_result(*, telemetry: object | None, observation: str = "命中正文") -> dict:
    payload: dict = {
        "ok": True,
        "tool": "kb_search",
        "observation": observation,
        "evidence": [{"title": "页A", "detail": "x" * 40}],
    }
    if telemetry is not None:
        payload["telemetry"] = telemetry
    return {"kind": "tool_result", "payload": payload}


def test_shape_i_authorized_not_planned_not_called() -> None:
    """R-11 手工扫描形态：授权躺着、计划不含 KB、零调用。"""

    verdict = inspect_episode(_kb_episode())
    assert verdict["I"]["authorized"] is True
    assert verdict["I"]["planned"] is False
    assert verdict["I"]["called"] is False
    assert verdict["I"]["question_type"] == "theme_analysis"


def test_shape_i_planned_and_called_layers() -> None:
    verdict = inspect_episode(
        _kb_episode(
            planned=("market_data", "kb_search"),
            events=[_kb_tool_result(telemetry={"delivered_chars": 12, "hit_count": 1, "source_pages": ["页A"]})],
        )
    )
    assert verdict["I"]["planned"] is True
    assert verdict["I"]["called"] is True


def test_shape_i_called_uses_provider_not_capability() -> None:
    """成功 trace 的 capability 是 agent_loop；按 capability 分组会漏计调用。"""

    verdict = inspect_episode(
        _kb_episode(
            traces=[
                {
                    "provider": "agent:kb_search",
                    "capability": "agent_loop",
                    "status": "success",
                    "result_count": 5,
                }
            ]
        )
    )
    assert verdict["I"]["called"] is True


def test_missing_kb_telemetry_is_unjudgeable_not_zero() -> None:
    """历史 run 调过 kb_search 但 telemetry 缺字段：报不可判，不当 0。"""

    verdict = inspect_episode(
        _kb_episode(events=[_kb_tool_result(telemetry=None)])
    )
    assert verdict["III"]["status"] == "unjudgeable"
    assert verdict["III"]["unjudgeable"] == 1
    assert verdict["III"]["delivered_chars"] == []
    assert "不可判" in verdict["III"]["summary"]


def test_empty_kb_telemetry_dict_is_unjudgeable_not_zero() -> None:
    """R-12 现状：telemetry 落盘空 dict。空 dict 不是 0 字符。"""

    verdict = inspect_episode(_kb_episode(events=[_kb_tool_result(telemetry={})]))
    assert verdict["III"]["status"] == "unjudgeable"
    assert verdict["III"]["delivered_chars"] == []


def test_shape_iii_no_call_is_not_zero_chars() -> None:
    """没调 KB 是 no_call，不是送达 0——和「缺字段当 0」是同一条诚实线。"""

    verdict = inspect_episode(_kb_episode())
    assert verdict["III"]["status"] == "no_call"
    assert verdict["III"]["delivered_chars"] == []
    assert verdict["III"]["calls"] == 0


def test_shape_iii_reads_actual_delivered_chars_not_800() -> None:
    """V3 会改管道；计数按实际送达，不写死 800。"""

    verdict = inspect_episode(
        _kb_episode(
            events=[
                _kb_tool_result(
                    telemetry={
                        "delivered_chars": 247,
                        "hit_count": 2,
                        "source_pages": ["页A", "页B"],
                    }
                )
            ]
        )
    )
    assert verdict["III"]["status"] == "judgeable"
    assert verdict["III"]["delivered_chars"] == [247]
    assert verdict["III"]["hit_counts"] == [2]
    assert 800 not in verdict["III"]["delivered_chars"]


def test_audit_aggregates_shape_i_by_question_type(tmp_path: Path) -> None:
    _write_run(tmp_path, "run_20260821_010000_a", _kb_episode(question_type="theme_analysis"))
    _write_run(tmp_path, "run_20260821_010000_b", _kb_episode(question_type="theme_analysis"))
    _write_run(
        tmp_path,
        "run_20260821_010000_c",
        _kb_episode(question_type="stock_deep_dive"),
    )
    report = audit([tmp_path], since="2026-08-21", until="2026-08-21")
    by_type = report["inputside"]["shape_I"]["by_question_type"]
    assert by_type["theme_analysis"] == {
        "n": 2,
        "authorized": 2,
        "planned": 0,
        "called": 0,
    }
    assert by_type["stock_deep_dive"]["n"] == 1
    assert report["inputside"]["shape_I"]["totals"]["authorized"] == 3
    assert report["inputside"]["shape_III"]["unjudgeable"] == 0
    assert report["inputside"]["shape_III"]["no_call_runs"] == 3


def test_audit_shape_iii_unjudgeable_not_counted_as_zero(tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        "run_20260821_010000_d",
        _kb_episode(events=[_kb_tool_result(telemetry={})]),
    )
    report = audit([tmp_path], since="2026-08-21", until="2026-08-21")
    shape_iii = report["inputside"]["shape_III"]
    assert shape_iii["unjudgeable"] == 1
    assert shape_iii["judgeable"] == 0
    assert shape_iii["delivered_chars"] == []
    text = render_report(report)
    assert "不可判" in text


@pytest.mark.skipif(
    not all((path / "continuous-episode.json").is_file() for _n, path, _t in _R11_GOLD),
    reason="本机缺少 R-11 五案例金标 run",
)
def test_live_gold_r11_five_cases_match_manual_scan() -> None:
    """docs/verification/2026-08-21-inputside-kb-dark-asset.md §1：5/5 授权、零计划、零调用。"""

    roots = [path for _name, path, _qtype in _R11_GOLD]
    report = audit(roots, since="2026-08-21", until="2026-08-21")
    assert report["scanned"] == 5
    totals = report["inputside"]["shape_I"]["totals"]
    assert totals == {"n": 5, "authorized": 5, "planned": 0, "called": 0}
    by_type = report["inputside"]["shape_I"]["by_question_type"]
    assert by_type["theme_analysis"]["n"] == 3
    assert by_type["theme_analysis"]["authorized"] == 3
    assert by_type["theme_analysis"]["planned"] == 0
    assert by_type["theme_analysis"]["called"] == 0
    assert by_type["general_finance_qa"] == {
        "n": 1,
        "authorized": 1,
        "planned": 0,
        "called": 0,
    }
    assert by_type["stock_deep_dive"] == {
        "n": 1,
        "authorized": 1,
        "planned": 0,
        "called": 0,
    }
    assert report["inputside"]["shape_III"]["no_call_runs"] == 5
    assert report["inputside"]["shape_III"]["judgeable"] == 0
    assert report["inputside"]["shape_III"]["delivered_chars"] == []


@pytest.mark.parametrize("name,path,question_type", _R11_GOLD)
def test_live_gold_r11_each_case_layers(name: str, path: Path, question_type: str) -> None:
    episode_path = path / "continuous-episode.json"
    if not episode_path.is_file():
        pytest.skip(f"本机没有 {name} 金标 run")
    episode = json.loads(episode_path.read_text(encoding="utf-8"))
    verdict = inspect_episode(episode)
    assert verdict["I"]["authorized"] is True, name
    assert verdict["I"]["planned"] is False, name
    assert verdict["I"]["called"] is False, name
    assert verdict["I"]["question_type"] == question_type, name
    assert verdict["III"]["status"] == "no_call", name
