from pathlib import Path

from skills.lib import pdf_ingest_lint


def _write_entity(root: Path, source_name: str) -> None:
    (root / "测试公司.md").write_text(
        "# 测试公司\n\n"
        "## 高信度研究线索\n\n"
        f"### 测试概念｜{source_name}\n\n"
        "缺少三项 annotation。\n",
        encoding="utf-8",
    )


def _exposure(source_quality: str) -> list[tuple[str, str, dict[str, str]]]:
    return [
        (
            "测试公司",
            "测试概念",
            {
                "update_type": "curated_research",
                "fact_hardness": "review_candidate",
                "source_quality": source_quality,
            },
        )
    ]


def test_broker_curated_research_requires_annotations(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(pdf_ingest_lint, "ENTITIES_DIR", tmp_path)
    pdf_ingest_lint.ISSUES.clear()
    _write_entity(tmp_path, "测试来源")

    pdf_ingest_lint.check_entity_annotation(
        "测试来源", _exposure("broker_research_high")
    )

    messages = [item["message"] for item in pdf_ingest_lint.ISSUES]
    assert len(messages) == 3
    assert any("source_quality" in message for message in messages)
    assert any("fact_hardness" in message for message in messages)
    assert any("evidence_layer" in message for message in messages)


def test_non_broker_curated_research_is_outside_annotation_gate(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(pdf_ingest_lint, "ENTITIES_DIR", tmp_path)
    pdf_ingest_lint.ISSUES.clear()
    _write_entity(tmp_path, "测试来源")

    pdf_ingest_lint.check_entity_annotation(
        "测试来源", _exposure("official_disclosure")
    )

    assert pdf_ingest_lint.ISSUES == []
