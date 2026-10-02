"""用户记忆语义召回：默认不变、语义能召回换了说法的记录、走不通就退回关键词且有信号、缓存不存正文。

依据 docs/handoffs/2026-08-05b-user-memory-semantic-recall.md 的硬约束与通过标准（结构化意图、
语义召回、不可用时降级且有信号、空结果仍有明确信号；每条做变异）。测试只用临时台账，不读真实台账。
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import pytest

from intelligence.eval import retrieval_recall
from intelligence.services import memory_semantic, user_memory
from intelligence.services.memory_semantic import (
    BUILTIN_BIGRAM,
    MODE_ENV,
    MODEL_ENV,
    CharBigramEmbedder,
    EmbedderUnavailable,
)
from intelligence.services.user_memory import relevant_memory_records, select_relevant

CDP = {"ts": "2026-07-01T04:07:18+08:00", "correction": "CDP 端口要用 IPv6 地址连，别用 localhost", "themes": []}
REVIEW = {"ts": "2026-07-02T00:31:00+08:00", "correction": "日度复盘推演先定大盘阶段再看主线", "themes": ["日度复盘推演"]}
LIQUID = {"ts": "2026-07-03T09:00:00+08:00", "correction": "液冷题材双红看边际量不是涨幅", "themes": ["液冷"]}


class ConceptEmbedder:
    """测试用「语义」：按概念词表投影，CDP 与「远程调试」同属一个概念，字面不重合也相近。"""

    name = "test:concepts"
    CONCEPTS = (("CDP", "远程调试", "Chrome", "调试端口"), ("复盘", "推演", "盘前"), ("液冷", "温控"))

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, texts):
        self.calls.append(list(texts))
        vectors = []
        for text in texts:
            lowered = text.lower()
            vector = [float(sum(lowered.count(word.lower()) for word in group)) for group in self.CONCEPTS]
            vector.append(0.01)  # 无概念的文本也给个非零向量，和谁都不相近
            vectors.append(memory_semantic._normalize(vector))
        return vectors


class FailingEmbedder:
    name = "test:failing"

    def embed(self, texts):
        raise RuntimeError("model blew up")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
    for key in (MODE_ENV, MODEL_ENV, memory_semantic.MIN_SIM_ENV):
        monkeypatch.delenv(key, raising=False)
    # 缓存一律落进本用例的临时目录：不碰家目录下的真缓存。
    monkeypatch.setenv(memory_semantic.CACHE_DIR_ENV, str(tmp_path / "vector-cache"))
    memory_semantic._EMBEDDERS.clear()
    memory_semantic._WARNED_REASONS.clear()


def _ledger(tmp_path: Path, corrections: list[dict]) -> Path:
    root = tmp_path / "linxiaoqi5111"
    root.mkdir()
    (root / "corrections.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in corrections), encoding="utf-8"
    )
    return root


def _use(monkeypatch, embedder) -> None:
    monkeypatch.setattr(memory_semantic, "resolve_embedder", lambda env=None: embedder)


def _ts(recall) -> list[str]:
    return [r["ts"] for r in recall.corrections]


def test_keyword_mode_is_unchanged_and_never_touches_the_semantic_path(tmp_path, monkeypatch):
    root = _ledger(tmp_path, [CDP, REVIEW, LIQUID])

    def boom(*args, **kwargs):
        raise AssertionError("keyword 档不该进语义路径")

    monkeypatch.setattr(memory_semantic, "select", boom)
    expected = select_relevant(
        [CDP, REVIEW, LIQUID][::-1], "液冷怎么看", "液冷",
        text_keys=("correction", "original", "principle"), tag_keys=("themes",),
    )
    for mode in (None, "keyword"):
        if mode:
            monkeypatch.setenv(MODE_ENV, mode)
        recall = relevant_memory_records("液冷怎么看", "液冷", users_root=root)
        assert _ts(recall) == [r["ts"] for r in expected] == [LIQUID["ts"]]


def test_semantic_recalls_a_record_that_shares_no_words_with_the_question(tmp_path, monkeypatch):
    root = _ledger(tmp_path, [CDP, REVIEW, LIQUID])
    question = "Chrome没开远程调试怎么办"
    assert _ts(relevant_memory_records(question, users_root=root)) == []  # 关键词：整句当检索词，打不到
    _use(monkeypatch, ConceptEmbedder())
    telemetry: dict = {}
    recall = relevant_memory_records(question, users_root=root, recall_mode="semantic", telemetry=telemetry)
    assert _ts(recall) == [CDP["ts"]]
    assert telemetry["corrections"]["effective"] == "semantic"
    assert telemetry["corrections"]["degraded"] is None


def test_semantic_does_not_force_top_k_when_nothing_is_similar(tmp_path, monkeypatch):
    root = _ledger(tmp_path, [CDP, REVIEW, LIQUID])
    _use(monkeypatch, ConceptEmbedder())
    assert _ts(relevant_memory_records("白酒需求怎么看", users_root=root, recall_mode="semantic")) == []


def test_hybrid_keeps_keyword_hits_first_and_fills_the_rest_semantically(tmp_path, monkeypatch):
    root = _ledger(tmp_path, [CDP, REVIEW, LIQUID])
    _use(monkeypatch, ConceptEmbedder())
    question = "Chrome 远程调试 调试端口 液冷"  # 语义上更像 CDP，关键词只打到液冷标签
    assert _ts(relevant_memory_records(question, "液冷", users_root=root)) == [LIQUID["ts"]]
    assert _ts(relevant_memory_records(question, "液冷", users_root=root, recall_mode="semantic", limit=1)) == [CDP["ts"]]
    recall = relevant_memory_records(question, "液冷", users_root=root, recall_mode="hybrid")
    assert _ts(recall) == [LIQUID["ts"], CDP["ts"]]
    # 名额紧时关键词命中优先：标签命中精度高，混合档不拿语义结果把它挤掉。
    assert _ts(relevant_memory_records(question, "液冷", users_root=root, recall_mode="hybrid", limit=1)) == [LIQUID["ts"]]


def test_unset_model_degrades_to_keyword_with_a_signal_and_no_ledger_text_in_logs(tmp_path, monkeypatch, caplog):
    root = _ledger(tmp_path, [CDP, REVIEW, LIQUID])
    monkeypatch.setenv(MODE_ENV, "semantic")
    telemetry: dict = {}
    with caplog.at_level(logging.DEBUG, logger="intelligence.services.memory_semantic"):
        recall = relevant_memory_records("液冷怎么看", "液冷", users_root=root, telemetry=telemetry)
        relevant_memory_records("液冷怎么看", "液冷", users_root=root)
    assert _ts(recall) == [LIQUID["ts"]]  # 关键词兜底，不是空
    assert telemetry["corrections"] == {"mode": "semantic", "effective": "keyword", "degraded": "embed_model_unset"}
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1, "同一原因每进程只告警一次"
    assert "embed_model_unset" in caplog.text
    assert all(record["correction"] not in caplog.text for record in (CDP, REVIEW, LIQUID))


def test_embedder_failure_degrades_instead_of_failing_the_recall(tmp_path, monkeypatch):
    root = _ledger(tmp_path, [CDP, REVIEW, LIQUID])
    _use(monkeypatch, FailingEmbedder())
    telemetry: dict = {}
    recall = relevant_memory_records("液冷怎么看", "液冷", users_root=root, recall_mode="hybrid", telemetry=telemetry)
    assert _ts(recall) == [LIQUID["ts"]]
    assert telemetry["corrections"]["degraded"] == "embed_failed:RuntimeError"


def test_missing_sentence_transformers_is_a_named_degradation(monkeypatch):
    import importlib.util

    monkeypatch.setenv(MODEL_ENV, "BAAI/bge-small-zh-v1.5")
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    with pytest.raises(EmbedderUnavailable) as excinfo:
        memory_semantic.resolve_embedder()
    assert excinfo.value.reason == "sentence_transformers_missing"


def test_vector_cache_reuses_vectors_and_never_stores_ledger_text(tmp_path, monkeypatch):
    root = _ledger(tmp_path, [CDP, REVIEW, LIQUID])
    embedder = ConceptEmbedder()
    _use(monkeypatch, embedder)
    relevant_memory_records("远程调试", users_root=root, recall_mode="semantic")
    assert sum(len(batch) for batch in embedder.calls) == 4  # 3 条记录 + 1 个问句
    embedder.calls.clear()
    relevant_memory_records("远程调试", users_root=root, recall_mode="semantic")
    assert embedder.calls == [["远程调试"]]  # 记录向量走缓存，只算问句
    cache_files = list((tmp_path / "vector-cache").rglob("corrections.*.json"))
    assert len(cache_files) == 1
    assert not list(root.rglob("*.json")), "缓存不许落在台账旁边（真台账在自动同步的记忆库里）"
    raw = cache_files[0].read_text(encoding="utf-8")
    for record in (CDP, REVIEW, LIQUID):
        assert record["correction"] not in raw
        for tag in record["themes"]:
            assert tag not in raw


def test_cache_follows_ledger_edits(tmp_path, monkeypatch):
    root = _ledger(tmp_path, [CDP, REVIEW])
    embedder = ConceptEmbedder()
    _use(monkeypatch, embedder)
    relevant_memory_records("远程调试", users_root=root, recall_mode="semantic")
    edited = dict(CDP, correction="CDP 调试端口改走 127.0.0.1")
    (root / "corrections.jsonl").write_text(json.dumps(edited, ensure_ascii=False), encoding="utf-8")
    embedder.calls.clear()
    recall = relevant_memory_records("远程调试", users_root=root, recall_mode="semantic")
    assert _ts(recall) == [CDP["ts"]]
    assert embedder.calls[0] == [memory_semantic.record_text(edited, ("correction", "original", "principle"), ("themes",))]
    (cache_file,) = (tmp_path / "vector-cache").rglob("corrections.*.json")
    assert len(json.loads(cache_file.read_text(encoding="utf-8"))["vectors"]) == 1  # 删掉的 REVIEW 不滞留


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root 无视目录权限")
def test_unwritable_cache_dir_still_recalls(tmp_path, monkeypatch):
    root = _ledger(tmp_path, [CDP, REVIEW, LIQUID])
    _use(monkeypatch, ConceptEmbedder())
    locked = tmp_path / "locked"
    locked.mkdir()
    monkeypatch.setenv(memory_semantic.CACHE_DIR_ENV, str(locked / "vectors"))
    locked.chmod(0o555)
    try:
        telemetry: dict = {}
        recall = relevant_memory_records("远程调试", users_root=root, recall_mode="semantic", telemetry=telemetry)
    finally:
        locked.chmod(0o755)
    assert _ts(recall) == [CDP["ts"]]
    assert telemetry["corrections"]["cache"] == "unwritable"


@pytest.mark.parametrize("value", ["off", "relative/dir"])
def test_cache_can_be_switched_off_and_never_lands_in_the_working_dir(tmp_path, monkeypatch, value):
    root = _ledger(tmp_path, [CDP, REVIEW, LIQUID])
    _use(monkeypatch, ConceptEmbedder())
    monkeypatch.setenv(memory_semantic.CACHE_DIR_ENV, value)
    monkeypatch.chdir(tmp_path)
    telemetry: dict = {}
    relevant_memory_records("远程调试", users_root=root, recall_mode="semantic", telemetry=telemetry)
    assert telemetry["corrections"]["cache"] == "disabled"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["linxiaoqi5111"]


def test_char_bigram_arm_catches_the_whole_sentence_query_shape(tmp_path, monkeypatch):
    """08-15 基线 r-007 的形状：问句无空格整句当检索词，标签是「日度复盘推演」不是问句子串。"""

    embedder = CharBigramEmbedder()
    first, second = embedder.embed(["盘前复盘推演", "盘前复盘推演"])
    assert first == second and abs(sum(x * x for x in first) - 1) < 1e-9
    root = _ledger(tmp_path, [CDP, REVIEW, LIQUID])
    question = "明天盘前的复盘推演怎么做"
    assert _ts(relevant_memory_records(question, users_root=root)) == []
    monkeypatch.setenv(MODEL_ENV, BUILTIN_BIGRAM)
    recall = relevant_memory_records(question, users_root=root, recall_mode="semantic", telemetry={}, limit=5)
    assert _ts(recall)[:1] == [REVIEW["ts"]]


def test_invalid_mode_value_means_keyword(monkeypatch):
    monkeypatch.setenv(MODE_ENV, "vector")
    assert memory_semantic.recall_mode() == "keyword"


def test_telemetry_carries_only_machine_fields(tmp_path, monkeypatch):
    root = _ledger(tmp_path, [CDP, REVIEW, LIQUID])
    _use(monkeypatch, ConceptEmbedder())
    telemetry: dict = {}
    relevant_memory_records("远程调试", users_root=root, recall_mode="hybrid", telemetry=telemetry)
    assert set(telemetry) == {"judgments", "corrections"}
    dumped = json.dumps(telemetry, ensure_ascii=False)
    assert all(record["correction"] not in dumped for record in (CDP, REVIEW, LIQUID))
    assert telemetry["corrections"]["embedder"] == "test:concepts"


def test_tiers_mark_degraded_semantic_rows_and_count_unlabelled_recalls(tmp_path, monkeypatch):
    root = _ledger(tmp_path, [CDP, REVIEW, LIQUID])
    cases = [
        {"case_id": "c-1", "query": "液冷怎么看", "theme": "液冷", "relevant": [LIQUID["ts"]]},
        {"case_id": "c-2", "query": "明天盘前的复盘推演怎么做", "theme": "", "relevant": [REVIEW["ts"]]},
    ]
    monkeypatch.setenv(MODEL_ENV, "keep-me")
    report = retrieval_recall.compare_memory_tiers(
        cases, k=5, embed_models=[BUILTIN_BIGRAM, "BAAI/not-installed"], users_root=root,
    )
    assert os.environ[MODEL_ENV] == "keep-me"  # 分档跑完把环境还原
    rows = {row["tier"]: row for row in report["tiers"]}
    assert list(rows) == ["T0", "T1", "T2-1", "T3-1", "T2-2", "T3-2"]
    assert rows["T1"]["hits"] == 1 and rows["T1"]["degraded"] == []
    assert rows["T2-1"]["hits"] == 2  # 字符二元组救回 c-2
    assert rows["T2-2"]["degraded"], "模型不可用的档必须标降级，不能把关键词兜底的数当语义读"
    assert all(isinstance(row["false_positives"], int) for row in rows.values())
    text = retrieval_recall.render_tiers(report)
    assert "降级：" in text and "| c-2 | — | 0 |" in text


def test_tiers_cli_runs_on_the_bundled_synthetic_fixture(capsys, monkeypatch, tmp_path):
    before = sorted(p.name for p in retrieval_recall.FIXTURE_LEDGERS.rglob("*"))
    monkeypatch.setattr("sys.argv", [
        "retrieval_recall", "--cases", str(retrieval_recall.FIXTURE_CASES),
        "--users-root", str(retrieval_recall.FIXTURE_LEDGERS), "--tiers", "--embed-model", BUILTIN_BIGRAM,
    ])
    assert retrieval_recall._main() == 0
    out = capsys.readouterr().out
    assert "user_memory 分档对照（2 cases，k=5）" in out
    assert "T2 | +字符二元组（非语义对照）" in out
    # 本尺子只读：仓内夹具目录跑完不多一个文件，向量缓存也没写。
    assert sorted(p.name for p in retrieval_recall.FIXTURE_LEDGERS.rglob("*")) == before
    assert not (tmp_path / "vector-cache").exists()


def test_user_memory_module_still_exposes_the_old_recall_contract():
    # MemoryRecall 的槽位是读侧契约（ReadSideContractTests 另钉）；本改动不加槽位。
    assert set(user_memory.MemoryRecall.__slots__) == {
        "judgments", "corrections", "judgments_path", "corrections_path", "methods",
    }
