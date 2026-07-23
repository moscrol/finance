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


def test_semantic_smoke_accepts_direct_mainline_judgment_heading() -> None:
    issues = semantic_answer_issues(
        "目前市场的主线是什么",
        {"answer_status": "complete"},
        [
            {
                "role": "assistant",
                "content": (
                    "### 一、直接判断\n"
                    "当前并非单一主升行情，而是多条线并行、"
                    "各自处于不同生命周期阶段的存量博弈格局。\n"
                    "盘面数据表明电力与医药更值得观察。"
                ),
            }
        ],
    )

    assert issues == []


def test_semantic_smoke_accepts_quantified_mainline_evidence() -> None:
    issues = semantic_answer_issues(
        "目前市场的主线是什么",
        {"answer_status": "complete"},
        [
            {
                "role": "assistant",
                "content": (
                    "【主线判断】半导体与AI算力仍是持续性方向。"
                    "全市场成交约21949.97亿元，涨停116家、跌停2家；"
                    "半导体近20日出现15天，但当日缩量分歧。"
                ),
            }
        ],
    )

    assert issues == []


def test_semantic_smoke_accepts_direct_mainline_conclusion() -> None:
    issues = semantic_answer_issues(
        "目前市场的主线是什么",
        {"answer_status": "complete"},
        [
            {
                "role": "assistant",
                "content": (
                    "一、直接结论：科技、医药与电力多线轮动。"
                    "支持证据：成交额约2.19万亿元。"
                ),
            }
        ],
    )

    assert issues == []


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


def test_semantic_smoke_accepts_question_bound_partial_gap() -> None:
    issues = semantic_answer_issues(
        "你觉得目前市场的主线是什么，给我你的判断依据",
        {"answer_status": "partial"},
        [
            {
                "role": "assistant",
                "content": "本轮尚未完成问题所需的直接回答：仍缺少同日主线结构依据，暂不下结论。",
            }
        ],
    )

    assert issues == []


def test_semantic_smoke_accepts_useful_partial_with_explicit_evidence_gap() -> None:
    issues = semantic_answer_issues(
        "这一周行情下跌的主要原因是什么",
        {"answer_status": "partial"},
        [
            {
                "role": "assistant",
                "content": (
                    "直接判断：本周实际上上涨约3%。"
                    "证据缺口：7月17日单日大跌的精确诱因无法确认。"
                ),
            }
        ],
    )

    assert issues == []


def test_semantic_smoke_accepts_useful_partial_with_evidence_boundary_gap() -> None:
    issues = semantic_answer_issues(
        "这一周行情下跌的主要原因是什么",
        {"answer_status": "partial"},
        [
            {
                "role": "assistant",
                "content": (
                    "直接判断：本周实际上涨约3%。"
                    "证据边界与缺口：单日大跌缺少时间对齐的事件证据。"
                ),
            }
        ],
    )

    assert issues == []


def test_semantic_smoke_rejects_generic_partial_source_list() -> None:
    issues = semantic_answer_issues(
        "你觉得目前市场的主线是什么，给我你的判断依据",
        {"answer_status": "partial"},
        [{"role": "assistant", "content": "已找到相关来源，但证据强度不足。"}],
    )

    assert "answer_status='partial'" in issues
    assert "mainline_direct_assessment_missing" in issues
