"""证据条件是约束，不是可静默删除的检索偏好；验收消费者真实入口。"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from intelligence.services import kb_rag
from scripts import rag_query_worker

POLICY = "explicit_chunk_metadata; unknown_excluded; as_of=available_time"


def hit(**changes):
    row = {
        "page_id": "sources/report", "title": "Report",
        "file_path": "wiki/sources/report.md", "score": 0.9,
        "best_chunk_id": "report::0", "content_hash": "chunk-hash",
        "section": "Report > 订单", "index_source_revision": "manifest:v1:abc",
        "index_freshness": "fresh", "content_validity": "valid",
        "evidence_text": "订单确认十套。", "llm_evidence_text": "订单确认十套。",
        "evidence_chunk_ids": ["report::0"],
        "evidence_layer": "L3", "fact_hardness": "hard_fact",
        "source_type": "official_disclosure", "review_required": "false",
        "publish_time": "2026-08-01", "available_time": "2026-08-02",
        "source_refs": ["raw/report.md"], "applied_filters": {"evidence_layer": "L3"},
    }
    return row | changes


def receipt(rows=None, **changes):
    rows = [hit()] if rows is None else rows
    return {
        "status": "success" if rows else "no_results", "hits": rows,
        "applied_filters": {"evidence_layer": "L3"}, "filter_policy": POLICY,
        "metadata_version": 1, "metadata_update_required": False,
    } | changes


def response(payload, *, rc=0, stderr=""):
    return SimpleNamespace(returncode=rc, stdout=json.dumps(payload), stderr=stderr)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_WORKER_ENABLED", "0")
    monkeypatch.delenv("VECTOR_INDEX_DIR", raising=False)
    monkeypatch.delenv("RAG_INDEX_DIR", raising=False)
    script = tmp_path / "scripts/rag_index.py"
    script.parent.mkdir()
    script.write_text("# fake cli\n")
    page = tmp_path / "wiki/sources/report.md"
    page.parent.mkdir(parents=True)
    page.write_text("# Report\n## 订单\n订单确认十套。\n## 待核\n订单传闻一千套，尚待核验。\n")
    (tmp_path / ".rag_index").mkdir()
    kb_rag.clear_result_cache()
    yield tmp_path
    kb_rag.clear_result_cache()


def test_receipt_controls_filtered_delivery_and_telemetry(repo, monkeypatch):
    run = Mock(return_value=response(receipt()))
    monkeypatch.setattr(kb_rag.subprocess, "run", run)
    result = kb_rag.retrieve("订单", repo / "wiki", evidence_layer="L3", mode="bm25")
    assert result.ok, result.warning
    assert "--receipt" in run.call_args.args[0]
    assert result.telemetry.filters == {"evidence_layer": "L3"}  # 兼容字段 = 请求
    assert result.telemetry.applied_filters == {"evidence_layer": "L3"}
    assert result.telemetry.filter_verification == "verified"
    assert result.hits[0].available_time == "2026-08-02"
    assert result.hits[0].source_refs == ("raw/report.md",)
    assert result.hits[0].evidence_scope_bound
    assert result.hits[0].deep_read_paragraphs == ()
    assert "一千" not in result.hits[0].llm_evidence
    assert "实际过滤=" in result.telemetry.summary_line()


@pytest.mark.parametrize("payload", [
    [hit()],  # 旧列表即使带等级也不能证明邻块执行了过滤
    receipt(applied_filters={}),
    receipt(filter_policy="best_effort"),
    receipt(metadata_version="1"),
    receipt(metadata_update_required="false"),
    receipt(status="no_results"),
    receipt([hit(evidence_layer="L1")]),
    receipt([hit(evidence_layer="")]),
    receipt([hit(review_required="true")]),
    receipt([hit(fact_hardness="review_candidate")]),
    receipt([hit(applied_filters={})]),
    receipt([hit(content_validity="quarantined")]),
    receipt([hit(content_validity=[])]),
    receipt([hit(review_required=[True])]),
])
def test_unverified_or_contradictory_filter_receipt_fails_closed(repo, monkeypatch, payload):
    monkeypatch.setattr(kb_rag.subprocess, "run", Mock(return_value=response(payload)))
    result = kb_rag.retrieve("订单", repo / "wiki", evidence_layer="L3", mode="bm25")
    assert not result.ok
    assert not result.hits
    assert result.telemetry.applied_filters == {}
    assert result.telemetry.filter_verification == "unverified"
    assert result.telemetry.status == "error"
    assert "回执" in result.warning


def test_empty_legacy_metadata_is_migration_not_no_fact(repo, monkeypatch):
    monkeypatch.setattr(kb_rag.subprocess, "run", Mock(return_value=response(receipt(
        [], metadata_version=0, metadata_update_required=True,
    ))))
    result = kb_rag.retrieve("订单", repo / "wiki", evidence_layer="L3", mode="bm25")
    assert result.telemetry.status == "empty"
    assert result.telemetry.applied_filters == {"evidence_layer": "L3"}
    assert result.telemetry.metadata_update_required is True
    assert "元数据" in result.warning
    assert "不代表" in result.warning


@pytest.mark.parametrize("option,kwargs", [
    ("--evidence-layer", {"evidence_layer": "L3"}),
    ("--fact-hardness", {"fact_hardness": "hard_fact"}),
    ("--source-type", {"source_type": "official_disclosure"}),
    ("--as-of", {"as_of": "2026-08-03"}),
    ("--receipt", {"evidence_layer": "L3"}),
])
def test_unsupported_constraint_never_retries_unfiltered(repo, monkeypatch, option, kwargs):
    run = Mock(side_effect=[response(None, rc=2, stderr=f"error: unrecognized arguments: {option}"),
                            response([hit()])])
    monkeypatch.setattr(kb_rag.subprocess, "run", run)
    result = kb_rag.retrieve("订单", repo / "wiki", mode="bm25", **kwargs)
    assert not result.ok
    assert result.hits == []
    assert run.call_count == 1
    assert result.telemetry.applied_filters == {}
    assert option in result.telemetry.unsupported_options


@pytest.mark.parametrize("relative", ["scripts/rag_index.py", "skills/lib/rag/evidence.py"])
def test_legacy_unfiltered_retry_removes_only_receipt_flag_and_recovers_after_upgrade(repo, monkeypatch, relative):
    run = Mock(side_effect=[
        response(None, rc=2, stderr="error: unrecognized arguments: --receipt"),
        response([hit(applied_filters={})]),
        response(receipt([hit(applied_filters={})], applied_filters={})),
    ])
    monkeypatch.setattr(kb_rag.subprocess, "run", run)
    first = kb_rag.retrieve("订单", repo / "wiki", mode="bm25", cache_scope="session")
    assert first.ok, first.warning
    assert "--json" in run.call_args.args[0]
    assert "--receipt" not in run.call_args.args[0]
    assert first.telemetry.filter_verification == "not_requested"
    assert "过滤未生效" not in first.warning
    script = repo / relative
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("# upgraded receipt-capable cli or dependency\n")
    second = kb_rag.retrieve("订单", repo / "wiki", mode="bm25", cache_scope="session")
    assert second.ok, second.warning
    assert "--receipt" in run.call_args.args[0]
    assert not second.telemetry.cache_hit
    assert second.telemetry.receipt_received


def test_known_unsupported_filter_does_not_enter_worker(repo, monkeypatch):
    run = Mock(return_value=response(None, rc=2, stderr="error: unrecognized arguments: --evidence-layer L3"))
    worker = Mock()
    monkeypatch.setattr(kb_rag.subprocess, "run", run)
    monkeypatch.setattr(kb_rag.rag_worker, "query", worker)
    kb_rag.retrieve("订单", repo / "wiki", evidence_layer="L3", mode="bm25")
    second = kb_rag.retrieve("订单", repo / "wiki", evidence_layer="L3", mode="bm25", worker_enabled=True)
    assert not second.ok
    worker.assert_not_called()
    assert run.call_count == 1


@pytest.mark.parametrize("available,published", [("", ""), ("2026-08-04", "2026-08-01"),
                                                 ("2026-08-02", "2026-08-03")])
def test_as_of_checks_available_time_not_source_date(repo, monkeypatch, available, published):
    filters = {"as_of": "2026-08-03"}
    row = hit(available_time=available, publish_time=published, applied_filters=filters)
    monkeypatch.setattr(kb_rag.subprocess, "run", Mock(return_value=response(receipt([row], applied_filters=filters))))
    result = kb_rag.retrieve("订单", repo / "wiki", mode="bm25", as_of="2026-08-03")
    assert not result.ok
    assert result.telemetry.status == "error"


def test_as_of_is_forwarded_and_validated_before_io(repo, monkeypatch):
    filters = {"as_of": "2026-08-03"}
    run = Mock(return_value=response(receipt([hit(applied_filters=filters)], applied_filters=filters)))
    monkeypatch.setattr(kb_rag.subprocess, "run", run)
    result = kb_rag.retrieve("订单", repo / "wiki", mode="bm25", as_of="2026-08-03")
    assert result.ok, result.warning
    assert "--as-of" in run.call_args.args[0]
    run.reset_mock()
    invalid = kb_rag.retrieve("订单", repo / "wiki", as_of="2026-99-01")
    assert not invalid.ok
    run.assert_not_called()


def test_bound_evidence_cannot_be_recovered_reexcerpted_or_deep_read(repo):
    bound = kb_rag.WikiHit("report", "wiki/sources/report.md", "Report", 1, "订单确认十套。",
                          llm_evidence="订单确认十套。", section="Report > 订单",
                          index_freshness="stale", evidence_scope_bound=True)
    assert kb_rag.recover_stale_hits([bound], wiki_root=repo / "wiki", query="订单").recovered == 0
    assert kb_rag.deep_read_hits([bound], wiki_root=repo / "wiki", query="订单").pages == 0
    assert kb_rag.reexcerpt_hits([bound], wiki_root=repo / "wiki")[0][0].llm_evidence == "订单确认十套。"


def test_filtered_stale_receipt_does_not_promote_current_source_to_l3(repo, monkeypatch):
    monkeypatch.setattr(kb_rag.subprocess, "run", Mock(return_value=response(receipt([hit(index_freshness="stale")]))))
    result = kb_rag.retrieve("订单", repo / "wiki", evidence_layer="L3", mode="bm25")
    assert not result.ok
    assert result.telemetry.stale_recovered == 0


def test_receipt_queries_recheck_live_sources_instead_of_reusing_result_cache(repo, monkeypatch):
    run = Mock(side_effect=[response(receipt()), response(receipt([]))])
    monkeypatch.setattr(kb_rag.subprocess, "run", run)
    first = kb_rag.retrieve("订单", repo / "wiki", evidence_layer="L3", mode="bm25", cache_scope="s")
    second = kb_rag.retrieve("订单", repo / "wiki", evidence_layer="L3", mode="bm25", cache_scope="s")
    assert first.ok and not second.ok
    assert run.call_count == 2


def test_worker_preserves_receipt_and_bound_context_while_restamping_freshness():
    row = hit(llm_evidence_text="经过过滤的相邻证据。", evidence_chunk_ids=["report::0", "report::1"])
    payload = receipt([row])
    store = SimpleNamespace(meta={"built_at": "today"}, page_freshness=lambda *_: {row["file_path"]: "stale"})
    retriever = SimpleNamespace(store=store)
    state = {"chunks": {"report::0": {"text": "未经上下文裁切的整块", "content_hash": "h"}},
             "retriever": retriever, "store": store, "revision": "worker-identity", "freshness": "fresh"}
    module = SimpleNamespace(_vault=lambda: Path("/unused"))
    out = json.loads(rag_query_worker._enrich_query_output(json.dumps(payload), state, module))
    assert out["applied_filters"] == payload["applied_filters"]
    assert out["hits"][0]["index_freshness"] == "stale"
    assert out["hits"][0]["index_source_revision"] == "manifest:v1:abc"
    assert out["hits"][0]["llm_evidence_text"] == row["llm_evidence_text"]
    assert out["hits"][0]["evidence_chunk_ids"] == row["evidence_chunk_ids"]
