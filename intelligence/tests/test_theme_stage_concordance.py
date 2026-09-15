"""对照集脚本（G-04 验收 b）：取样、报告一致率与样本不足口径。"""

from __future__ import annotations

import csv
import importlib.util
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

from intelligence.services import theme_lifecycle_timeline as timeline

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "theme_stage_concordance.py"
_spec = importlib.util.spec_from_file_location("theme_stage_concordance_under_test", _SCRIPT)
assert _spec and _spec.loader
concordance = importlib.util.module_from_spec(_spec)
# exec 前注册进 sys.modules：脚本里的 @dataclass 解析类型时按 __module__ 反查模块，
# 不注册会拿到 None（dataclasses._is_type 的已知坑）
sys.modules[_spec.name] = concordance
_spec.loader.exec_module(concordance)


def _artifact() -> timeline.ThemeTimelineArtifact:
    segs = (
        timeline.StageSegment("发酵", "2026-08-01", "2026-08-03", "双红"),
        timeline.StageSegment("主升", "2026-08-04", "2026-08-20", "连续双红 ≥3"),
    )
    return timeline.ThemeTimelineArtifact(theme="固态电池", segments=segs, gaps=())


def test_sample_points_boundary_midpoint_and_window():
    points = concordance.sample_points(_artifact(), window_start="2026-08-01")
    kinds = {(p.day, p.kind) for p in points}
    assert ("2026-08-01", "boundary") in kinds
    assert ("2026-08-04", "boundary") in kinds
    # 长段（17 天）取中点；短段（3 天 < LONG_SEGMENT_DAYS）不取
    assert any(k == "midpoint" and d.startswith("2026-08-1") for d, k in kinds)
    assert not any(k == "midpoint" and d < "2026-08-04" for d, k in kinds)
    # 窗口起点晚于第一段起点时，第一段边界被滤掉，段身仍可贡献中点
    later = concordance.sample_points(_artifact(), window_start="2026-08-05")
    assert not any(p.day == "2026-08-01" for p in later)


def _write_set(path: Path, rows: list[dict[str, str]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=concordance.CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in concordance.CSV_FIELDS})
    return path


def _run_report(src: Path) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = concordance.cmd_report(SimpleNamespace(set=str(src), out=None))
    assert rc == 0
    return buf.getvalue()


def test_report_insufficient_sample_never_prints_rate(tmp_path):
    rows = [
        {"theme": "固态电池", "date": f"2026-08-0{i}", "sample_kind": "boundary",
         "timeline_stage": "发酵", "timeline_trigger": "双红",
         "diagnosis_stage": concordance.DIAGNOSIS_GAP, "human_stage_canonical": "发酵"}
        for i in range(1, 6)
    ]
    out = _run_report(_write_set(tmp_path / "set.csv", rows))
    assert "样本不足（N=5" in out
    assert "%" not in out.split("## ")[0]  # 头部读数区不出现任何比率


def test_report_rates_and_mismatch_attribution(tmp_path):
    rows = []
    for i in range(1, 13):  # 12 个标注样本 ≥ MIN_N；其中 2 个不一致
        human = "退潮" if i <= 2 else "发酵"
        rows.append(
            {"theme": "固态电池", "date": f"2026-08-{i:02d}", "sample_kind": "boundary",
             "timeline_stage": "发酵", "timeline_trigger": "双红触发",
             "diagnosis_stage": "升温验证",  # 经映射 = 发酵
             "human_stage_canonical": human}
        )
    out = _run_report(_write_set(tmp_path / "set.csv", rows))
    assert "timeline vs 人工：10/12" in out
    assert "诊断 vs 人工：10/12" in out
    assert "timeline vs 诊断：12/12" in out  # 升温验证 → 发酵，两模块映射后同名
    assert "不一致样本" in out and "双红触发" in out


def test_report_rejects_non_canonical_human_words(tmp_path):
    rows = [{"theme": "t", "date": "2026-08-01", "sample_kind": "boundary",
             "timeline_stage": "发酵", "timeline_trigger": "x",
             "diagnosis_stage": concordance.DIAGNOSIS_GAP,
             "human_stage_canonical": "升温验证"}]  # 细词不是钦定词
    out = _run_report(_write_set(tmp_path / "set.csv", rows))
    assert "不是钦定七段词" in out and "升温验证" in out
