from __future__ import annotations

import pytest

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


def test_semantic_smoke_accepts_reason_attribution_gap_heading() -> None:
    issues = semantic_answer_issues(
        "这一周行情下跌的主要原因是什么",
        {"answer_status": "partial"},
        [
            {
                "role": "assistant",
                "content": (
                    "核心判断：本周实际上涨约3%。"
                    "原因归因：缺口。"
                    "同一时间窗口未检索到事件报道，无法建立经过核验的因果链。"
                    "证据边界：盘面事实可确认，外部原因暂时无法确认。"
                ),
            }
        ],
    )

    assert issues == []


def test_semantic_smoke_accepts_task_specific_partial_without_gap_heading() -> None:
    issues = semantic_answer_issues(
        "这一周行情下跌的主要原因是什么",
        {"answer_status": "partial"},
        [
            {
                "role": "assistant",
                "content": (
                    "核心结论：本周A股实际上涨约3%，问题前提不成立。"
                    "同一时间窗口未检索到对齐的新闻证据，无法核验7月17日"
                    "单日下跌的外部原因。"
                ),
            }
        ],
    )

    assert issues == []


def test_semantic_smoke_rejects_forecast_gap_without_duration() -> None:
    issues = semantic_answer_issues(
        "昨天的反弹能持续多久",
        {"answer_status": "partial"},
        [
            {
                "role": "assistant",
                "content": (
                    "关于反弹持续性，现有证据不足，暂不能可靠回答。"
                    "仍需核验：最新市场基线、持续时间窗口与失效条件。"
                ),
            }
        ],
    )

    assert "forecast_duration_missing" in issues


def test_semantic_smoke_accepts_duration_forecast_with_invalidation() -> None:
    issues = semantic_answer_issues(
        "昨天的反弹能持续多久",
        {"answer_status": "complete"},
        [
            {
                "role": "assistant",
                "content": (
                    "核心判断：基准情景还能持续3至5个交易日。"
                    "若成交继续缩量则判断失效。"
                ),
            }
        ],
    )

    assert issues == []


@pytest.mark.parametrize(
    "non_forecast",
    [
        "近5个交易日成交额下降。失效条件尚待观察。",
        "过去一周市场波动较大。失效条件需要关注。",
        "判断：近5个交易日成交额下降。若成交继续缩量则判断失效。",
        "基准数据覆盖近5个交易日。若数据缺失则判断失效。",
    ],
)
def test_semantic_smoke_rejects_historical_duration_as_forecast(
    non_forecast: str,
) -> None:
    issues = semantic_answer_issues(
        "昨天的反弹能持续多久",
        {"answer_status": "complete"},
        [{"role": "assistant", "content": non_forecast}],
    )

    assert "forecast_duration_missing" in issues
    if "若成交继续缩量" not in non_forecast:
        assert "forecast_invalidation_missing" in issues


@pytest.mark.parametrize(
    "generic_gap",
    ["未检索到资料。", "仍需核验。", "市场下跌。证据缺口。"],
)
def test_semantic_smoke_rejects_generic_gap_keywords(generic_gap: str) -> None:
    issues = semantic_answer_issues(
        "这一周行情下跌的主要原因是什么",
        {"answer_status": "partial"},
        [{"role": "assistant", "content": generic_gap}],
    )

    assert "answer_status='partial'" in issues


def test_semantic_smoke_rejects_degraded_even_with_specific_gap() -> None:
    issues = semantic_answer_issues(
        "这一周行情下跌的主要原因是什么",
        {"answer_status": "degraded"},
        [
            {
                "role": "assistant",
                "content": "证据缺口：单日下跌原因仍缺时间对齐的新闻。",
            }
        ],
    )

    assert "answer_status='degraded'" in issues


def test_semantic_smoke_rejects_generic_partial_source_list() -> None:
    issues = semantic_answer_issues(
        "你觉得目前市场的主线是什么，给我你的判断依据",
        {"answer_status": "partial"},
        [{"role": "assistant", "content": "已找到相关来源，但证据强度不足。"}],
    )

    assert "answer_status='partial'" in issues
    assert "mainline_direct_assessment_missing" in issues
