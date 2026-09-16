"""离线 CLI 与夹具漂移守卫。"""

from __future__ import annotations

import json
from pathlib import Path

from intelligence.eval.product_value.cli import main
from intelligence.tests.product_value_fixtures import FIXTURE_DIR, build_protocol, render_files

PY_FIXTURES = FIXTURE_DIR


def test_fixtures_on_disk_match_generator() -> None:
    expected = render_files(build_protocol())
    on_disk = {str(p.relative_to(FIXTURE_DIR)): p.read_text(encoding="utf-8") for p in FIXTURE_DIR.rglob("*") if p.is_file() and p.name != "README.md"}
    assert set(on_disk) == set(expected), (set(on_disk) ^ set(expected))
    for name, content in expected.items():
        assert on_disk[name] == content, f"fixture drifted: {name}; rerun python -m intelligence.tests.product_value_fixtures"


def test_cli_validate_clean_fixture_exits_zero(capsys) -> None:
    code = main(["validate", "--events", str(PY_FIXTURES / "all" / "events.jsonl"), "--protocol", str(PY_FIXTURES / "protocol.yaml")])
    report = json.loads(capsys.readouterr().out)
    assert code == 0
    assert report["accepted"] == 69 and report["rejected"] == [] and report["conflicts"] == []


def test_cli_validate_reports_bad_events(tmp_path: Path, capsys) -> None:
    bad = tmp_path / "bad.jsonl"
    lines = (PY_FIXTURES / "complete_pair" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["event_at"] = "2026-09-14T09:00:00"  # 缺时区
    bad.write_text(json.dumps(first, ensure_ascii=False) + "\n" + "{not json}\n", encoding="utf-8")
    code = main(["validate", "--events", str(bad)])
    report = json.loads(capsys.readouterr().out)
    assert code == 1
    codes = {issue["code"] for item in report["rejected"] for issue in item["issues"]}
    assert "timestamp_naive" in codes and "schema_version_mismatch" in codes


def test_cli_summarize_all_fixture_writes_receipts_and_summary(tmp_path: Path, capsys) -> None:
    code = main(
        [
            "summarize",
            "--events",
            str(PY_FIXTURES / "all" / "events.jsonl"),
            "--protocol",
            str(PY_FIXTURES / "protocol.yaml"),
            "--evidence-json",
            str(PY_FIXTURES / "all" / "evidence.json"),
            "--due-rechecks",
            str(PY_FIXTURES / "all" / "due_rechecks.json"),
            "--out-dir",
            str(tmp_path / "out"),
        ]
    )
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["receipts"] == {"pair-01": "valid", "pair-02": "incomplete", "pair-03": "incomplete"}
    assert printed["engineering_status"] == "engineering_complete"
    assert printed["field_status"] == "pending" and printed["commercial_status"] == "unstarted"
    assert printed["synthetic"] is True
    out = tmp_path / "out"
    assert {p.name for p in out.iterdir()} == {
        "receipt-pair-01.json",
        "receipt-pair-01.md",
        "receipt-pair-02.json",
        "receipt-pair-02.md",
        "receipt-pair-03.json",
        "receipt-pair-03.md",
        "pilot-summary.json",
        "pilot-summary.md",
    }
    summary = json.loads((out / "pilot-summary.json").read_text(encoding="utf-8"))
    assert summary["schema_version"] == "pilot-summary/v1"
    assert summary["synthetic_check"]["counts_toward_field"] is False
    md = (out / "pilot-summary.md").read_text(encoding="utf-8")
    assert "SYNTHETIC" in md and "synthetic_check" in md
    receipt_md = (out / "receipt-pair-02.md").read_text(encoding="utf-8")
    assert "SYNTHETIC" in receipt_md and "2(1/1)" in receipt_md  # 2 次尝试，1 失败 1 降级


def test_cli_measure_single_pair(tmp_path: Path, capsys) -> None:
    code = main(
        [
            "measure",
            "--events",
            str(PY_FIXTURES / "all" / "events.jsonl"),
            "--protocol",
            str(PY_FIXTURES / "protocol.yaml"),
            "--evidence-json",
            str(PY_FIXTURES / "all" / "evidence.json"),
            "--out-dir",
            str(tmp_path),
            "--pair",
            "pair-01",
        ]
    )
    assert code == 0
    line = capsys.readouterr().out.strip().splitlines()[-1]
    assert line.startswith("pair-01\tvalid\t")
    assert (tmp_path / "receipt-pair-01.json").exists() and not (tmp_path / "receipt-pair-02.json").exists()


def test_cli_rejects_tampered_protocol(tmp_path: Path, capsys) -> None:
    import yaml

    protocol = yaml.safe_load((PY_FIXTURES / "protocol.yaml").read_text(encoding="utf-8"))
    protocol["criteria"]["time_saving"]["median_saving_min"] = 0.05  # 冻结后改判据
    tampered = tmp_path / "protocol.yaml"
    tampered.write_text(yaml.safe_dump(protocol, allow_unicode=True, sort_keys=False), encoding="utf-8")
    code = main(["measure", "--events", str(PY_FIXTURES / "complete_pair" / "events.jsonl"), "--protocol", str(tampered), "--out-dir", str(tmp_path / "out")])
    assert code == 2
    assert "protocol_hash does not match" in capsys.readouterr().err


def test_cli_freeze_template_then_reject_edits(tmp_path: Path, capsys) -> None:
    import yaml

    # 以测试文件定位仓根，不依赖 pytest 的 cwd（从子目录起跑也成立）。
    template = Path(__file__).resolve().parents[2] / "docs" / "research-pilots" / "research-evolution" / "protocol.yaml"
    assert template.is_file(), template
    frozen_path = tmp_path / "frozen.yaml"
    assert main(["freeze", "--protocol", str(template), "--out", str(frozen_path)]) == 0
    printed = json.loads(capsys.readouterr().out)
    frozen = yaml.safe_load(frozen_path.read_text(encoding="utf-8"))
    assert frozen["protocol_hash"] == printed["protocol_hash"] and len(frozen["protocol_hash"]) == 64
    # 冻结后再冻结一次：内容没变，哈希不变。
    assert main(["freeze", "--protocol", str(frozen_path), "--out", str(tmp_path / "again.yaml")]) == 0
    assert json.loads(capsys.readouterr().out)["protocol_hash"] == printed["protocol_hash"]
    # 冻结后改判据再喂进来：拒绝。
    frozen["criteria"]["time_saving"]["median_saving_min"] = 0.01
    frozen_path.write_text(yaml.safe_dump(frozen, allow_unicode=True, sort_keys=False), encoding="utf-8")
    assert main(["freeze", "--protocol", str(frozen_path), "--out", str(tmp_path / "bad.yaml")]) == 2


def test_cli_without_evidence_marks_runs_missing(tmp_path: Path) -> None:
    code = main(["measure", "--events", str(PY_FIXTURES / "complete_pair" / "events.jsonl"), "--protocol", str(PY_FIXTURES / "protocol.yaml"), "--out-dir", str(tmp_path)])
    assert code == 0
    receipt = json.loads((tmp_path / "receipt-pair-01.json").read_text(encoding="utf-8"))
    assert receipt["status"] == "incomplete"
    assert "run_evidence_missing:r-cp-1" in receipt["limitations"]
