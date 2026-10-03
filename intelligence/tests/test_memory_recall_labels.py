"""Keep stale labels and timestamp collisions from becoming recall scores."""
from __future__ import annotations

import json

import pytest

from intelligence.eval import retrieval_recall as recall
from intelligence.services import corrections, memory_status


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def case(label, *, query="订单", theme=None):
    return {"case_id": "probe", "query": query, "theme": theme, "relevant": [label]}


def score(root, cases, **kwargs):
    return recall.evaluate_cases(cases, recall.user_memory_retriever, ks=(5,), users_root=root, **kwargs)


def colliding_rows(root):
    path = root / "corrections.jsonl"
    _, first = corrections.record_correction(path, correction="客户验证", ts="same-second")
    _, second = corrections.record_correction(path, correction="订单兑现", ts="same-second")
    return first, second


def test_legacy_timestamp_cannot_credit_the_wrong_record(tmp_path):
    colliding_rows(tmp_path)
    # The old evaluator returned recall=1 for a timestamp shared by A and B,
    # even though the query returned only B and the annotation could mean A.
    with pytest.raises(ValueError, match="invalid memory labels") as error:
        score(tmp_path, [case("same-second")])
    assert error.value.report["ambiguous_candidates"] == ["same-second"]


def test_stable_identity_keeps_same_second_records_distinct(tmp_path):
    first, second = colliding_rows(tmp_path)
    report = score(tmp_path, [case("correction:" + first["id"])], identity_mode="stable")
    assert report["recall_at"][5] == 0
    assert report["per_case"][0]["missed"][5] == ["correction:" + first["id"]]
    ids = recall.user_memory_retriever("订单", None, None, 5, users_root=tmp_path, identity_mode="stable")
    assert ids == ["correction:" + second["id"]]


def test_stable_identity_counts_each_unlabelled_record(tmp_path):
    rows = [{"ts": "same-second", "correction": text, "themes": ["订单"]}
            for text in ("订单客户验证", "订单兑现", "订单退货")]
    write_rows(tmp_path / "corrections.jsonl", rows)
    first = "correction:" + memory_status.memory_record_id("correction", "same-second", rows[0]["correction"])
    report = recall.compare_memory_tiers(
        [case(first, theme="订单")], users_root=tmp_path, identity_mode="stable",
    )
    tier = next(row for row in report["tiers"] if row["tier"] == "T1")
    assert tier["hits"] == 1 and tier["false_positives"] == 2
    # Legacy rows receive derived identities only in the evaluator; no migration.
    assert all("id" not in json.loads(line) for line in (tmp_path / "corrections.jsonl").read_text().splitlines())


@pytest.mark.parametrize("state", ["missing", "inactive", "outside_window"])
def test_unreachable_label_prevents_metrics(tmp_path, state):
    rows = [] if state == "missing" else [{"ts": "target", "correction": "订单核验"}]
    if state == "inactive":
        rows.append({"record_type": "memory_status", "target_ts": "target", "status": "archived"})
    if state == "outside_window":
        rows += [{"ts": f"new-{i}", "correction": "其他事项"} for i in range(200)]
    write_rows(tmp_path / "corrections.jsonl", rows)
    with pytest.raises(ValueError, match="invalid memory labels") as error:
        score(tmp_path, [case("target")])
    assert error.value.report["cases"][0]["labels"][0]["state"] == state


def test_valid_label_missed_by_query_is_still_scored(tmp_path):
    write_rows(tmp_path / "corrections.jsonl", [{"ts": "target", "correction": "客户验证"}])
    assert score(tmp_path, [case("target")])["recall_at"][5] == 0


def test_source_namespace_prevents_cross_ledger_collision(tmp_path):
    write_rows(tmp_path / "corrections.jsonl", [{"id": "shared", "ts": "t", "correction": "订单兑现"}])
    write_rows(tmp_path / "judgments.jsonl", [{"id": "shared", "ts": "t", "memo": "客户验证"}])
    report = score(tmp_path, [case("judgment:shared")], identity_mode="stable")
    assert report["hit_rate_at"][5] == 0


@pytest.mark.parametrize("tiers", [False, True])
def test_cli_rejects_invalid_labels_without_emitting_scores(tmp_path, monkeypatch, capsys, tiers):
    labels = tmp_path / "cases.jsonl"
    write_rows(labels, [case("missing")])
    argv = ["recall", "--cases", str(labels), "--users-root", str(tmp_path), "--json"]
    if tiers:
        argv.append("--tiers")
    monkeypatch.setattr("sys.argv", argv)
    assert recall._main() == 2
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "invalid_memory_labels"
    assert "hit_rate_at" not in report and "tiers" not in report


def test_cli_stable_mode_accepts_explicit_label(tmp_path, monkeypatch, capsys):
    _, second = colliding_rows(tmp_path)
    labels = tmp_path / "cases.jsonl"
    write_rows(labels, [case("correction:" + second["id"])])
    monkeypatch.setattr("sys.argv", ["recall", "--cases", str(labels), "--users-root", str(tmp_path),
                                  "--memory-identity", "stable", "--json"])
    assert recall._main() == 0
    assert json.loads(capsys.readouterr().out)["hit_rate_at"]["5"] == 1


@pytest.mark.parametrize("entry", ["api", "tiers", "cli", "tiers_cli"])
def test_read_failure_after_admission_is_not_a_recall_miss(tmp_path, monkeypatch, capsys, entry):
    from pathlib import Path

    path = tmp_path / "corrections.jsonl"
    write_rows(path, [{"ts": "target", "correction": "订单兑现"}])
    cases = [case("target")]
    labels = tmp_path / "cases.jsonl"
    write_rows(labels, cases)
    read_text = Path.read_text
    reads = 0

    def interrupted_read(self, *args, **kwargs):
        nonlocal reads
        if self == path:
            reads += 1
            # Admission reads active, window and raw successfully. The actual
            # retriever must report a subsequent IO failure, never a score of 0.
            if reads > 3:
                raise PermissionError("private-ledger-path")
        return read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", interrupted_read)
    if entry in {"api", "tiers"}:
        with pytest.raises(OSError, match="memory retrieval unavailable"):
            if entry == "api":
                score(tmp_path, cases)
            else:
                recall.compare_memory_tiers(cases, users_root=tmp_path)
    else:
        argv = ["recall", "--cases", str(labels), "--users-root", str(tmp_path), "--json"]
        if entry == "tiers_cli":
            argv.append("--tiers")
        monkeypatch.setattr("sys.argv", argv)
        assert recall._main() == 2
        output = capsys.readouterr().out
        assert json.loads(output) == {"status": "memory_retrieval_unavailable"}
        assert "private-ledger-path" not in output


@pytest.mark.parametrize("change", ["deleted", "replaced"])
@pytest.mark.parametrize("tiers", [False, True])
def test_ledger_change_after_admission_invalidates_scores(tmp_path, monkeypatch, capsys, change, tiers):
    path = tmp_path / "corrections.jsonl"
    write_rows(path, [{"ts": "target", "correction": "订单兑现"}])
    labels = tmp_path / "cases.jsonl"
    write_rows(labels, [case("target")])
    retriever = recall.user_memory_retriever
    changed = False

    def changing_retriever(*args, **kwargs):
        nonlocal changed
        if not changed:
            if change == "deleted":
                path.unlink()
            else:
                write_rows(path, [{"ts": "target", "correction": "无关资料"}])
            changed = True
        return retriever(*args, **kwargs)

    monkeypatch.setattr(recall, "user_memory_retriever", changing_retriever)
    monkeypatch.setitem(recall.RETRIEVERS, "user_memory", changing_retriever)
    argv = ["recall", "--cases", str(labels), "--users-root", str(tmp_path), "--json"]
    if tiers:
        argv.append("--tiers")
    monkeypatch.setattr("sys.argv", argv)
    assert recall._main() == 2
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "invalid_memory_labels"
    assert report["label_audit"]["input_changed"] is True
    assert "tiers" not in report and "hit_rate_at" not in report
