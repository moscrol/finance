from __future__ import annotations

from scripts.smoke_workbench_self_use import PublicLeakScanner, semantic_answer_issues


def test_public_scanner_does_not_treat_http_url_as_windows_path() -> None:
    scanner = PublicLeakScanner()

    scanner.scan("来源：https://example.com/a/1 后续判断", "answer")

    assert scanner.hits == []


def test_public_scanner_still_rejects_local_paths() -> None:
    scanner = PublicLeakScanner()

    scanner.scan("C:/Users/name/file.txt ", "answer")
    scanner.scan("/Users/name/file.txt ", "answer")

    assert [item["marker"] for item in scanner.hits] == [
        "local_path",
        "local_path",
    ]


def test_semantic_smoke_rejects_completed_but_unanswered_mainline() -> None:
    issues = semantic_answer_issues(
        "目前市场的主线是什么",
        {"answer_status": "complete"},
        [{"role": "assistant", "content": "本轮只展示候选来源。"}],
    )

    assert "mainline_direct_assessment_missing" in issues
    assert "mainline_evidence_missing" in issues


def test_semantic_smoke_accepts_forecast_required_outputs() -> None:
    issues = semantic_answer_issues(
        "明天是反弹还是继续下跌，分别给出理由",
        {"answer_status": "complete"},
        [
            {
                "role": "assistant",
                "content": "基准判断：偏向震荡。反弹情景：成交修复。继续下跌情景：跌停扩散。失效条件：宽度转强。",
            }
        ],
    )

    assert issues == []
