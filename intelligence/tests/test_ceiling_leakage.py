from __future__ import annotations

import json

import pytest

from intelligence.eval.ceiling_leakage import (
    ForbiddenCorpus,
    ForbiddenText,
    SemanticLeakReceipt,
    build_forbidden_corpus,
    normalize_char_stream,
    scan_export,
    tokenize,
    validate_semantic_receipt,
)


def test_normalization_is_nfkc_casefolded_and_punctuation_free() -> None:
    assert normalize_char_stream("Ａ股， Weekly  Cause！") == "a股weeklycause"


def test_tokenization_uses_han_codepoints_and_alnum_runs() -> None:
    assert tokenize("瑞华泰 PB 4.33") == (
        "瑞",
        "华",
        "泰",
        "pb",
        "4",
        "33",
    )


def test_scan_rejects_normalized_question_and_required_output_leaks(
    tmp_path,
) -> None:
    export = tmp_path / "export"
    export.mkdir()
    (export / "question.md").write_text(
        "昨天 的 反弹，能持续多久？",
        encoding="utf-8",
    )
    (export / "contract.txt").write_text(
        "scenario_ range",
        encoding="utf-8",
    )
    corpus = ForbiddenCorpus(
        (
            ForbiddenText(
                source_id="question:rebound-duration",
                kind="question",
                text="昨天的反弹能持续多久",
            ),
            ForbiddenText(
                source_id="output:ruihuatai-valuation",
                kind="required_output",
                text="scenario_range",
            ),
        )
    )

    result = scan_export(export, corpus)

    assert result.status == "rejected"
    assert {finding.relative_path for finding in result.findings} == {
        "contract.txt",
        "question.md",
    }
    assert all(finding.rule == "full_normalized_match" for finding in result.findings)
    assert len(result.scan_sha256) == 64


def test_scan_rejects_known_reference_fragment_by_ngram(tmp_path) -> None:
    export = tmp_path / "export"
    export.mkdir()
    (export / "fragment.md").write_text(
        "说明：悲观基准乐观假设需要分开核验。",
        encoding="utf-8",
    )
    corpus = ForbiddenCorpus(
        (
            ForbiddenText(
                source_id="reference:ruihuatai-valuation",
                kind="reference_answer",
                text=(
                    "合理估值应采用情景区间，分别设置悲观基准乐观假设，"
                    "缺少一致预期时不输出单点目标价"
                ),
            ),
        )
    )

    result = scan_export(export, corpus)

    assert result.status == "rejected"
    assert result.findings[0].rule in {
        "character_ngram_match",
        "token_ngram_match",
    }


def test_scan_keeps_semantic_near_match_for_independent_review(tmp_path) -> None:
    export = tmp_path / "export"
    export.mkdir()
    (export / "paraphrase.md").write_text(
        "这周下挫或许源于资金避险，以及高位持仓集中松动。",
        encoding="utf-8",
    )
    corpus = ForbiddenCorpus(
        (
            ForbiddenText(
                source_id="reference:weekly-market-cause",
                kind="reference_answer",
                text="本周下跌更像风险偏好收缩与高位筹码松动共振",
            ),
        )
    )

    result = scan_export(export, corpus)

    assert result.status == "passed"
    assert result.semantic_candidates
    assert result.semantic_candidates[0].relative_path == "paraphrase.md"


def test_semantic_receipt_binds_export_scan_model_and_reviewer() -> None:
    receipt = SemanticLeakReceipt.create(
        export_manifest_sha256="a" * 64,
        deterministic_scan_sha256="b" * 64,
        model="gpt-5.6-sol",
        prompt_sha256="c" * 64,
        reviewer="independent:spec-reviewer",
        verdict="pass",
    )

    assert validate_semantic_receipt(
        receipt.to_dict(),
        expected_export_manifest_sha256="a" * 64,
        expected_deterministic_scan_sha256="b" * 64,
        producer_identity="codex:/root",
    ) == receipt


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("model", "gpt-5.6-terra", "model"),
        ("reviewer", "codex:/root", "independent"),
        ("verdict", "fail", "pass"),
        ("receipt_sha256", "d" * 64, "self hash"),
    ],
)
def test_semantic_receipt_fails_closed(
    field: str,
    value: str,
    message: str,
) -> None:
    receipt = SemanticLeakReceipt.create(
        export_manifest_sha256="a" * 64,
        deterministic_scan_sha256="b" * 64,
        model="gpt-5.6-sol",
        prompt_sha256="c" * 64,
        reviewer="independent:spec-reviewer",
        verdict="pass",
    ).to_dict()
    receipt[field] = value

    with pytest.raises(ValueError, match=message):
        validate_semantic_receipt(
            receipt,
            expected_export_manifest_sha256="a" * 64,
            expected_deterministic_scan_sha256="b" * 64,
            producer_identity="codex:/root",
        )


def test_forbidden_corpus_loads_questions_references_and_prior_answers(
    tmp_path,
) -> None:
    questions = tmp_path / "questions.json"
    questions.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": "rebound-duration",
                        "question": "昨天的反弹能持续多久",
                        "conversation_context": [
                            {"role": "assistant", "content": "短周期修复"}
                        ],
                        "required_outputs": ["duration_assessment"],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    references = tmp_path / "references.json"
    references.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": "rebound-duration",
                        "answer": "先按三到五个交易日观察",
                        "direct_targets": ["三到五个交易日"],
                        "requirements": [
                            {
                                "id": "duration_assessment",
                                "satisfy_any": ["短周期"],
                            }
                        ],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    prior = tmp_path / "prior.json"
    prior.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": "rebound-duration",
                        "arms": [
                            {"candidate_answer": "原始候选答案"},
                            {"published_answer": "最终公开答案"},
                        ],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    handoff = tmp_path / "handoff.md"
    handoff.write_text(
        "2026-07-27 的反弹题最终验收失败，不能作为提前提示。",
        encoding="utf-8",
    )

    corpus = build_forbidden_corpus(
        question_file=questions,
        reference_file=references,
        prior_artifacts=(prior,),
        post_cutoff_documents=(handoff,),
    )

    texts = {entry.text for entry in corpus.entries}
    assert "昨天的反弹能持续多久" in texts
    assert "duration_assessment" in texts
    assert "先按三到五个交易日观察" in texts
    assert "短周期" in texts
    assert "原始候选答案" in texts
    assert "最终公开答案" in texts
    assert "2026-07-27 的反弹题最终验收失败，不能作为提前提示" in texts
