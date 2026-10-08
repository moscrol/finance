from __future__ import annotations

import copy
import hashlib
import json
from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from intelligence.api.river_daily_routes import register_daily_river_routes
from intelligence.services.river_daily_review import available_dates, daily_review_snapshot, project_review


def payload(day="2026-09-24"):
    def section(id_, index, blocks):
        return {"id": id_, "index": index, "title": id_, "blocks": blocks}
    return {"schema": "daily-review/v1", "trade_date": day, "generated_at": "2026-09-29 10:00:00", "warnings": [],
            "facts": {"focus_sw_l1": ["电子", "机械设备"], "top_amount_sw_l1": ["电子"], "double_red_count": 0,
                      "stock_high_120d_count": 56, "top3_industry_ratio": 42.7},
            "sections": [section("double_red_matrix", 6, [
                {"kind": "heading", "text": "电子"},
                {"kind": "table", "columns": ["子板块", "09-23", "09-24"], "rows": [
                    ["申万一级：电子（占比/涨跌幅）", "28.1%/0.2%", "-/-2.9%"],
                    ["上证指数（120日均量比/涨跌幅）", "0.68x/-0.4%", "0.64x/-1.2%"],
                    ["芯片", "🔥1.0%/15.0/800", "-2.0%/-10.0/750"]]},
            ]), section("stock_highs", 9, [{"kind": "heading", "text": "电子"}, {"kind": "text", "text": "没有映射"}]),
                section("limit_up", 10, [{"kind": "heading", "text": "电子"}, {"kind": "table", "columns": ["题材", "09-23", "09-24"], "rows": [["芯片", 12, "-"]]}]),
                section("industry_engines", 7, [{"kind": "heading", "text": "电子"}, {"kind": "table", "columns": ["排序", "股票", "代码", "涨幅", "成交额", "当日开根加权", "新高状态", "命中双红", "双红题材"], "rows": [[1, "测试股", "600001.SH", "7.87%", "80.5亿", "70.60", "历史新高", "否", "-"]]}])]}


def write(tmp_path, data):
    path = tmp_path / f"{data['trade_date']}-daily-review.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_exact_values_provenance_read_only_and_missing_kept(tmp_path):
    data = payload()
    path = write(tmp_path, data)
    raw, stat = path.read_bytes(), path.stat()
    result = daily_review_snapshot(tmp_path, as_of=date(2026, 9, 24))
    assert result["status"] == "available"
    assert result["provenance"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["provenance"]["generated_at"].startswith("2026-09-29")
    assert result["knowledge_mode"] == "archived_report_not_as_known"
    assert result["report"]["sections"] == data["sections"]
    matrix = result["report"]["matrices"]["double_red"][0]
    assert matrix["dates"] == ["2026-09-23", "2026-09-24"]
    assert matrix["rows"][2][1] == "🔥1.0%/15.0/800"
    assert matrix["rows"][0][-1] == "-/-2.9%"
    assert result["report"]["matrices"]["limit_up"][0]["rows"][0][-1] == "-"
    assert result["report"]["engines"][0]["rows"][0][5] == "70.60"
    assert path.read_bytes() == raw and path.stat().st_mtime_ns == stat.st_mtime_ns
    assert len(list(tmp_path.iterdir())) == 1


def test_missing_exact_day_never_falls_back(tmp_path):
    write(tmp_path, payload())
    result = daily_review_snapshot(tmp_path, as_of=date(2026, 9, 23))
    assert result["status"] == "missing" and result["report"] is None
    assert result["trade_date"] == "2026-09-23"
    assert result["available_dates"] == ["2026-09-24"]


def test_empty_high_mapping_not_zero_and_double_red_empty_not_mapping_failure():
    result = project_review(payload(), date(2026, 9, 24))
    assert result["matrices"]["stock_highs"][0]["status"] == "empty"
    assert len(result["diagnostics"]) == 3
    assert any("56" in message and "空矩阵不等于" in message for message in result["diagnostics"])


def test_cross_year_dates_and_zero_counts_preserved():
    data = payload("2026-01-05")
    for section in data["sections"]:
        for block in section["blocks"]:
            if block["kind"] == "table" and len(block["columns"]) == 3:
                block["columns"][1:] = ["12-31", "01-05"]
    data["sections"][2]["blocks"][1]["rows"][0][-1] = 0
    matrix = project_review(data, date(2026, 1, 5))["matrices"]["limit_up"][0]
    assert matrix["dates"] == ["2025-12-31", "2026-01-05"]
    assert matrix["rows"][0][-1] == 0


@pytest.mark.parametrize("mutation", [
    lambda d: d.update(schema="daily-review/v99"),
    lambda d: d.update(trade_date="2026-09-23"),
    lambda d: d.update(facts=[]),
    lambda d: d["facts"].update(focus_sw_l1="电子"),
    lambda d: d["facts"].update(stock_high_120d_count="56"),
    lambda d: d.update(warnings="warning"),
    lambda d: d["sections"].append(copy.deepcopy(d["sections"][0])),
    lambda d: d["sections"][0]["blocks"][1]["rows"][0].append("extra"),
    lambda d: d["sections"][0]["blocks"][1]["rows"][0].__setitem__(1, {}),
    lambda d: d["sections"][0]["blocks"][1]["columns"].__setitem__(1, "09-24"),
    lambda d: d["sections"][0]["blocks"][1]["columns"].__setitem__(2, "09-25"),
])
def test_invalid_archive_fails_closed(mutation):
    data = payload()
    mutation(data)
    with pytest.raises(ValueError):
        project_review(data, date(2026, 9, 24))


@pytest.mark.parametrize("raw", [b"{broken", b'[]', b'NaN', b'\xff'])
def test_corrupt_json_fails_closed(tmp_path, raw):
    (tmp_path / "2026-09-24-daily-review.json").write_bytes(raw)
    with pytest.raises(ValueError):
        daily_review_snapshot(tmp_path, as_of=date(2026, 9, 24))


def test_oversize_and_symlink_fail_closed(tmp_path, monkeypatch):
    from intelligence.services import river_daily_review as module
    path = write(tmp_path, payload())
    monkeypatch.setattr(module, "MAX_BYTES", 20)
    with pytest.raises(ValueError, match="大小"):
        daily_review_snapshot(tmp_path, as_of=date(2026, 9, 24))
    root = tmp_path / "nested"
    root.mkdir()
    (root / path.name).symlink_to(path)
    assert available_dates(root) == []
    with pytest.raises(ValueError, match="路径"):
        daily_review_snapshot(root, as_of=date(2026, 9, 24))


def test_discovery_skips_invalid_names(tmp_path):
    write(tmp_path, payload())
    (tmp_path / "2026-02-30-daily-review.json").write_text("{}")
    (tmp_path / "latest-daily-review.json").write_text("{}")
    (tmp_path / "2026-09-23-daily-review.md").write_text("legacy")
    assert available_dates(tmp_path) == ["2026-09-24"]


def test_endpoint_validation_missing_corrupt_and_root(tmp_path, monkeypatch):
    write(tmp_path, payload())
    monkeypatch.setenv("FINANCE_WS", str(tmp_path / "unused"))
    app = FastAPI()
    register_daily_river_routes(app, review_exports_path=tmp_path)
    client = TestClient(app)
    assert client.get("/api/river/daily-review?as_of=not-a-date").status_code == 422
    assert client.get("/api/river/daily-review").status_code == 422
    assert client.get("/api/river/daily-review?as_of=2026-09-24").json()["status"] == "available"
    assert client.get("/api/river/daily-review?as_of=2026-09-23").json()["status"] == "missing"
    (tmp_path / "2026-09-24-daily-review.json").write_text("broken")
    response = client.get("/api/river/daily-review?as_of=2026-09-24")
    assert response.status_code == 503 and str(tmp_path) not in response.text


def test_default_export_root_follows_finance_ws(tmp_path, monkeypatch):
    exports = tmp_path / "market_feature_store" / "exports"
    exports.mkdir(parents=True)
    write(exports, payload())
    monkeypatch.setenv("FINANCE_WS", str(tmp_path))
    app = FastAPI()
    register_daily_river_routes(app)
    assert TestClient(app).get("/api/river/daily-review?as_of=2026-09-24").json()["report"]["facts"]["top3_industry_ratio"] == 42.7


def test_history_adjacent_differences_gaps_and_own_matrix(tmp_path):
    from intelligence.services.river_review_history import review_history
    for day, amount in [("2026-09-21", 100), ("2026-09-22", 120), ("2026-09-24", 180)]:
        data = payload(day)
        data["facts"]["total_amount"] = amount
        # Every report deliberately has an overlapping historical value.
        for section in data["sections"]:
            for block in section["blocks"]:
                if block["kind"] == "table" and len(block["columns"]) == 3:
                    block["columns"][1:] = ["09-18", day[5:]]
        write(tmp_path, data)
    before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in tmp_path.iterdir()}
    result = review_history(tmp_path, end=date(2026, 9, 24), days=5, industry="电子")
    points = {p["date"]: p for p in result["points"]}
    assert points["2026-09-22"]["deltas"]["total_amount"] == 20
    assert points["2026-09-23"]["status"] == "missing"
    assert points["2026-09-24"]["comparison_date"] is None
    assert points["2026-09-24"]["deltas"] == {}
    assert points["2026-09-24"]["matrices"]["double_red"]["rows"][2]["value"] == "-2.0%/-10.0/750"
    assert result["coverage"] == {"available": 3, "total": 5}
    assert result["knowledge_mode"] == "archived_report_not_as_known"
    assert before == {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in tmp_path.iterdir()}
    assert points["2026-09-24"]["provenance"]["sha256"]


def test_history_exit_is_not_zero_budget_invalid_and_truncation(tmp_path, monkeypatch):
    from intelligence.services import river_review_history as history
    data = payload()
    data["sections"][3]["blocks"][1]["rows"] *= 90
    write(tmp_path, data)
    result = history.review_history(tmp_path, end=date(2026, 9, 24), days=5, industry="电子")
    assert result["points"][-1]["engines"]["truncated"]
    assert len(result["points"][-1]["engines"]["rows"]) == 80
    result = history.review_history(tmp_path, end=date(2026, 9, 24), days=5, industry="机械设备")
    assert result["points"][-1]["industry_status"] == "not_in_list"
    assert result["points"][-1]["industry_rank"] is None
    monkeypatch.setattr(history, "READ_BUDGET", 1)
    assert history.review_history(tmp_path, end=date(2026, 9, 24), days=5)["points"][-1]["reason"] == "read_budget_exceeded"
    monkeypatch.setattr(history, "READ_BUDGET", 10000)
    (tmp_path / "2026-09-24-daily-review.json").write_text("broken")
    assert history.review_history(tmp_path, end=date(2026, 9, 24), days=5)["points"][-1]["reason"] == "invalid_archive"


def test_history_calendar_cross_year_and_unknown(tmp_path):
    from intelligence.services.river_review_history import review_history
    result = review_history(tmp_path, end=date(2026, 1, 5), days=5)
    dates = [p["date"] for p in result["points"]]
    assert dates == ["2026-01-05"]
    assert result["calendar_complete"] is False  # Repository calendar has no 2025 coverage.
    with pytest.raises(ValueError, match="未来"):
        review_history(tmp_path, end=date(2099, 1, 1))
    with pytest.raises(ValueError, match="交易日历未知"):
        review_history(tmp_path, end=date(1900, 1, 1))


def test_history_api_validation_and_contract(tmp_path):
    write(tmp_path, payload())
    app = FastAPI()
    register_daily_river_routes(app, review_exports_path=tmp_path)
    client = TestClient(app)
    for query in ["days=4", "days=61", "end=invalid", "end=2099-01-01", "industry=", "industry=" + "x" * 161]:
        assert client.get("/api/river/review-history?" + query).status_code == 422
    response = client.get("/api/river/review-history?end=2026-09-24&days=5&industry=电子")
    assert response.status_code == 200
    assert response.json()["points"][-1]["date"] == "2026-09-24"
    assert response.json()["points"][-1]["metrics"]["double_red_count"] == 0


def test_history_rejects_forced_calendar(tmp_path, monkeypatch):
    from intelligence.services.river_review_history import review_history
    monkeypatch.setenv("L2_FORCE_TRADE_DAY", "1")
    with pytest.raises(ValueError, match="强制"):
        review_history(tmp_path, end=date(2026, 9, 24), days=5)


def test_history_human_agent_contract_is_lossless_and_explicit(tmp_path):
    from intelligence.services.river_review_history import review_history
    data = payload()
    data["facts"].update(total_amount=123.45, advancers_ma5=1500.2, strength_avg_pct=-1.25)
    write(tmp_path, data)
    result = review_history(tmp_path, end=date(2026, 9, 24), days=5, industry="电子")
    contract = result["evidence_contract"]
    assert contract["version"] == "review-evidence/v1"
    assert [g["id"] for g in contract["groups"]] == ["market", "industry", "subsector", "engines"]
    assert contract["groups"][0]["fields"] == [f"metrics.{m['key']}" for m in result["metrics"]]
    point = result["points"][-1]
    for group in contract["groups"]:
        for field in group["fields"]:
            value = point
            for part in field.split("."):
                assert part in value, field
                value = value[part]
    assert point["metrics"]["advancers_ma5"] == data["facts"]["advancers_ma5"]
    assert point["engines"]["rows"] == data["sections"][3]["blocks"][1]["rows"]
    policy = contract["provenance_policy"]
    assert policy["hash_algorithm"] == "SHA-256"
    assert policy["point_in_time_guaranteed"] is False
    for key in ["industry_classification_version", "formula_version", "calendar_version", "archive_revision_id", "upstream_provider"]:
        assert policy[key] is None
    # No unsupported claim that missing formula or revision versions are known.
    assert "not_in_list" in contract["missing_semantics"]
    assert "truncated" in contract["missing_semantics"]
    assert "evidence_contract" in json.loads(json.dumps(result, ensure_ascii=False))
