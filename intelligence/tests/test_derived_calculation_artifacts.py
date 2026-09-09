"""派生计算结果视图与产物渲染（工单 04）。

正文、表、图、文件都从同一份 ``result`` 出——这里钉三件事：读得对（v1 与平铺字典）、
数字全部进观察值、产物幂等且可从 continuous-episode.json 同源的私有产物里重建。
"""

from __future__ import annotations

import json

from intelligence.services import derived_calculation_artifacts as art

CALC_ID = "0123456789abcdef"

_RESULT_V1 = {
    "schema": art.RESULT_SCHEMA_V1,
    "summary": {"latest_quarter_yi": 375.75, "consistent": True, "label": "ok"},
    "tables": [
        {
            "name": "单季营收",
            "columns": ["期间", "累计(亿)", "单季(亿)"],
            "rows": [["2026Q1", 547.03, 547.03], ["2026Q2", 922.78, 375.75], ["2026Q3", None, None]],
            "unit": "亿元",
            "note": "单季 = 本期累计 − 上期累计",
        }
    ],
    "charts": [
        {"name": "单季营收走势", "kind": "bar", "x": ["2026Q1", "2026Q2"], "series": {"单季": [547.03, 375.75]}, "unit": "亿元"}
    ],
    "params": {"growth_pct": 5},
    "formulas": ["单季 = 本期累计 − 上期累计"],
    "notes": ["2026Q3 未披露"],
}


def _record(result=None) -> dict[str, object]:
    return {
        "calc_id": CALC_ID,
        "purpose": "茅台单季营收还原",
        "script": "emit_result(...)  # <script>alert(1)</script>",
        "as_of": "2026-03-31",
        "enforcement": "process",
        "result": _RESULT_V1 if result is None else result,
        "inputs": [
            {"ref": "E1", "hash": "a" * 16, "tool": "financial_data", "title": "茅台 D7", "source": "东财 F10", "as_of": "2026-08-15"}
        ],
        "params": {"growth_pct": 5},
    }


def test_normalize_reads_v1_and_plain_results() -> None:
    view = art.normalize_result(_RESULT_V1)
    assert view.schema == "v1"
    assert view.summary == {"latest_quarter_yi": 375.75, "consistent": True, "label": "ok"}
    assert [table.name for table in view.tables] == ["单季营收"]
    assert view.tables[0].rows[2] == ("2026Q3", None, None)
    assert view.charts[0].kind == "bar" and view.charts[0].series["单季"] == (547.03, 375.75)
    assert view.params == {"growth_pct": 5}

    plain = art.normalize_result({"diff": 1.44, "consistent": False, "inputs": ["E1", "E2"]})
    assert plain.schema == "plain"
    assert plain.summary == {"diff": 1.44, "consistent": False}
    assert plain.extra == {"inputs": ["E1", "E2"]}
    assert plain.tables == ()


def test_every_number_in_the_result_becomes_an_observation() -> None:
    metrics = dict(art.numeric_observations(art.normalize_result(_RESULT_V1)))

    assert metrics["latest_quarter_yi"] == 375.75
    assert metrics["单季营收.单季(亿)[2026Q2]"] == 375.75
    assert metrics["单季营收.累计(亿)[2026Q1]"] == 547.03
    # 布尔与文本不是数；None 格没有观察值。
    assert "consistent" not in metrics and "label" not in metrics
    assert not any(key.endswith("[2026Q3]") for key in metrics)


def test_compact_text_stays_within_budget_and_points_to_artifacts() -> None:
    view = art.normalize_result(_RESULT_V1)
    text = art.compact_text(view, budget=700)
    assert text.startswith("摘要 latest_quarter_yi=375.75")
    assert "2026Q2: 累计(亿)=922.78 单季(亿)=375.75" in text
    assert "2026Q3: 累计(亿)=缺 单季(亿)=缺" in text
    assert "公式 单季 = 本期累计 − 上期累计" in text

    wide = {
        "schema": art.RESULT_SCHEMA_V1,
        "summary": {},
        "tables": [
            {"name": "大表", "columns": ["期间", "值"], "rows": [[f"2020Q{i % 4 + 1}-{i}", float(i)] for i in range(40)]}
        ],
    }
    clipped = art.compact_text(art.normalize_result(wide), budget=300)
    assert len(clipped) <= 300
    assert "完整见产物" in clipped


def test_artifact_files_are_named_by_calc_id_and_render_all_three_formats() -> None:
    files = {item.filename: item for item in art.artifact_files(_record())}

    assert set(files) == {f"calc-{CALC_ID}.json", f"calc-{CALC_ID}.html", f"calc-{CALC_ID}-t1.csv"}
    record = json.loads(files[f"calc-{CALC_ID}.json"].content)
    assert record["calc_id"] == CALC_ID and record["result"]["schema"] == art.RESULT_SCHEMA_V1
    csv_text = files[f"calc-{CALC_ID}-t1.csv"].content
    assert csv_text.startswith("﻿期间,累计(亿),单季(亿)\n")
    assert "2026Q2,922.78,375.75\n" in csv_text and "2026Q3,,\n" in csv_text
    assert files[f"calc-{CALC_ID}-t1.csv"].renderer == art.CSV_RENDERER
    html_text = files[f"calc-{CALC_ID}.html"].content
    assert "<script" not in html_text.lower().replace("&lt;script", "")
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_text
    assert "<svg" in html_text and "单季营收走势" in html_text
    assert "growth_pct" in html_text and "0123456789abcdef" in html_text

    # 同一记录再渲染一次：文件名与内容逐字节相同（幂等）。
    again = {item.filename: item.content for item in art.artifact_files(_record())}
    assert again == {name: item.content for name, item in files.items()}

    assert art.planned_artifact_names(CALC_ID, art.normalize_result(_RESULT_V1)) == tuple(sorted(files, key=list(files).index))


def test_plain_result_without_tables_gets_a_summary_csv() -> None:
    files = {item.filename for item in art.artifact_files(_record({"diff": 1.44, "consistent": False}))}
    assert files == {f"calc-{CALC_ID}.json", f"calc-{CALC_ID}.html", f"calc-{CALC_ID}-summary.csv"}


def test_records_are_recovered_from_private_artifact_events_and_published() -> None:
    private = {
        "events": [
            {"kind": "task", "payload": {}},
            {"kind": "tool_result", "payload": {"tool": "web_fetch", "telemetry": {}}},
            {
                "kind": "tool_result",
                "payload": {"tool": "derived_calculation", "telemetry": {"derived_calculation": _record()}},
            },
            # 同一 calc_id 再来一次：去重。
            {
                "kind": "tool_result",
                "payload": {"tool": "derived_calculation", "telemetry": {"derived_calculation": _record()}},
            },
            {"kind": "tool_result", "payload": {"tool": "derived_calculation", "telemetry": {"derived_calculation": {"calc_id": "not-hex"}}}},
        ]
    }
    records = art.calc_records_from_private_artifact(private)
    assert [record["calc_id"] for record in records] == [CALC_ID]

    class FakeStore:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, str, str]] = []

        def add_artifact(self, run_id, filename, content, *, renderer, title, **_kwargs):
            self.calls.append((run_id, filename, renderer, title))
            return filename

    store = FakeStore()
    written = art.publish_calculation_artifacts(store, "run-1", private)
    assert written == [f"calc-{CALC_ID}.json", f"calc-{CALC_ID}.html", f"calc-{CALC_ID}-t1.csv"]
    assert {call[2] for call in store.calls} == {"json", "html", art.CSV_RENDERER}
    assert all(call[0] == "run-1" for call in store.calls)
    assert art.publish_calculation_artifacts(store, "run-1", None) == []
    assert art.publish_calculation_artifacts(store, "run-1", {"events": "not-a-list"}) == []
