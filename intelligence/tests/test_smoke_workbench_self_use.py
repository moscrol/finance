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


def test_semantic_smoke_accepts_valuation_gap_worded_as_lack() -> None:
    issues = semantic_answer_issues(
        "瑞华泰的合理估值是多少",
        {"answer_status": "partial"},
        [
            {
                "role": "assistant",
                "content": (
                    "中性情景合理市值约40-63亿元。"
                    "关键缺口：缺乏历史PE/PS分位与机构盈利预测。"
                ),
            }
        ],
    )

    assert issues == []


def test_semantic_smoke_accepts_valuation_invalidation_slot_gap() -> None:
    issues = semantic_answer_issues(
        "瑞华泰的合理估值是多少",
        {"answer_status": "partial"},
        [
            {
                "role": "assistant",
                "content": (
                    "基准合理市值约35-60亿元。"
                    "证据缺口：判断失效或降级条件中的未核验表述已删除。"
                ),
            }
        ],
    )

    assert issues == []


def test_semantic_smoke_accepts_task_bound_valuation_data_gaps() -> None:
    issues = semantic_answer_issues(
        "瑞华泰的合理估值",
        {"answer_status": "partial"},
        [
            {
                "role": "assistant",
                "content": (
                    "瑞华泰当前PB为4.35，总市值约49.78亿元。"
                    "缺少历史PE/PS分位序列、公司最新财务报表及盈利趋势，"
                    "估值精度受限。"
                ),
            }
        ],
    )

    assert issues == []


def test_semantic_smoke_accepts_valuation_data_gaps_with_suffix_wording() -> None:
    issues = semantic_answer_issues(
        "瑞华泰的合理估值",
        {"answer_status": "partial"},
        [
            {
                "role": "assistant",
                "content": (
                    "当前PB约4.33。公司最新财报数据未获取，"
                    "历史PE/PB分位数据缺失，估值不确定性较高。"
                ),
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
                    "证据缺口：7月17日缺少同日新闻，单日大跌的"
                    "精确诱因无法确认。"
                ),
            }
        ],
    )

    assert issues == []


def test_semantic_smoke_accepts_referential_window_cause_gap() -> None:
    issues = semantic_answer_issues(
        "这一周行情下跌的主要原因是什么",
        {"answer_status": "partial"},
        [
            {
                "role": "assistant",
                "content": (
                    "数据覆盖2026-07-17至2026-07-23。"
                    "新闻检索在该窗口内返回空结果，原因层面的证据完全缺失。"
                ),
            }
        ],
    )

    assert issues == []


def test_semantic_smoke_accepts_time_aligned_news_no_result_wording() -> None:
    issues = semantic_answer_issues(
        "这一周行情下跌的主要原因是什么",
        {"answer_status": "partial"},
        [
            {
                "role": "assistant",
                "content": (
                    "对于7月17日单日下跌的因果关系，多次财经新闻检索"
                    "均未返回与该时间窗口对齐的资讯。"
                ),
            }
        ],
    )

    assert issues == []


def test_semantic_smoke_rejects_undefined_referential_window_cause_gap() -> None:
    issues = semantic_answer_issues(
        "这一周行情下跌的主要原因是什么",
        {"answer_status": "partial"},
        [
            {
                "role": "assistant",
                "content": "新闻在该窗口没有，原因证据完全缺失。",
            }
        ],
    )

    assert "answer_status='partial'" in issues


def test_semantic_smoke_rejects_unrelated_valuation_data_gap() -> None:
    issues = semantic_answer_issues(
        "瑞华泰的合理估值",
        {"answer_status": "partial"},
        [
            {
                "role": "assistant",
                "content": "估值结论不变，但天气数据缺失。",
            }
        ],
    )

    assert "answer_status='partial'" in issues


@pytest.mark.parametrize(
    "unrelated_gap",
    (
        "估值结论不变，但缺少天气数据，盈利正常。",
        "估值结论不变，盈利正常但天气数据缺失。",
    ),
)
def test_semantic_smoke_rejects_cross_phrase_valuation_gap(
    unrelated_gap: str,
) -> None:
    issues = semantic_answer_issues(
        "瑞华泰的合理估值",
        {"answer_status": "partial"},
        [{"role": "assistant", "content": unrelated_gap}],
    )

    assert "answer_status='partial'" in issues


@pytest.mark.parametrize(
    ("question", "answer"),
    (
        (
            "瑞华泰的合理估值",
            "财报并未缺失，估值结论完备。",
        ),
        (
            "昨天的反弹能持续多久",
            "预计还能持续1-3个交易日。"
            "证据缺口：判断继续成立的条件没有问题。",
        ),
        (
            "这一周行情下跌的主要原因是什么",
            "数据覆盖2026-07-17至2026-07-23。"
            "天气新闻在该窗口缺失，但原因证据齐全。",
        ),
    ),
)
def test_semantic_smoke_rejects_negated_or_contradicted_gap_claims(
    question: str,
    answer: str,
) -> None:
    issues = semantic_answer_issues(
        question,
        {"answer_status": "partial"},
        [{"role": "assistant", "content": answer}],
    )

    assert "answer_status='partial'" in issues


@pytest.mark.parametrize(
    ("question", "answer"),
    (
        ("瑞华泰的合理估值", "财报并非缺失，估值结论完备。"),
        ("瑞华泰的合理估值", "财报并不缺失，估值结论完备。"),
        ("瑞华泰的合理估值", "财报缺失已经补齐，估值结论完备。"),
        ("瑞华泰的合理估值", "估值证据不充分的问题已经解决。"),
        ("瑞华泰的合理估值", "已解决财报缺失问题，估值结论完备。"),
        (
            "你觉得目前市场的主线是什么，给我你的判断依据",
            "直接判断：当前主线是人工智能。主线证据缺口已经补齐。",
        ),
        (
            "昨天的反弹能持续多久",
            "预计还能持续1-3个交易日。失效条件证据缺口已经补齐。",
        ),
        (
            "这一周行情下跌的主要原因是什么",
            "数据覆盖2026-07-17至2026-07-23。"
            "天气新闻在该窗口缺失，但原因证据足够。",
        ),
    ),
)
def test_semantic_smoke_rejects_resolved_or_non_target_gap_language(
    question: str,
    answer: str,
) -> None:
    issues = semantic_answer_issues(
        question,
        {"answer_status": "partial"},
        [{"role": "assistant", "content": answer}],
    )

    assert "answer_status='partial'" in issues


def test_semantic_smoke_accepts_negative_sufficiency_as_real_valuation_gap() -> (
    None
):
    issues = semantic_answer_issues(
        "瑞华泰的合理估值",
        {"answer_status": "partial"},
        [
            {
                "role": "assistant",
                "content": "估值证据不充分，财报数据缺失。",
            }
        ],
    )

    assert issues == []


def test_semantic_smoke_accepts_sparse_comparable_sample_as_valuation_gap() -> (
    None
):
    issues = semantic_answer_issues(
        "瑞华泰的合理估值",
        {"answer_status": "partial"},
        [
            {
                "role": "assistant",
                "content": "可比样本太少，无法给出可靠估值。",
            }
        ],
    )

    assert issues == []


def test_semantic_smoke_accepts_task_bound_valuation_marker_loss_gap() -> None:
    issues = semantic_answer_issues(
        "瑞华泰的合理估值",
        {"answer_status": "partial"},
        [
            {
                "role": "assistant",
                "content": (
                    "当前PB约4.33。证据缺口：估值的证据覆盖范围中的"
                    "未核验表述已删除，需补充直接证据后再判断。"
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
                    "证据边界与缺口：单日大跌缺少时间对齐的事件证据，"
                    "因此无法完成原因归因。"
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


def test_semantic_smoke_accepts_explicit_unattributable_cause_boundary() -> None:
    issues = semantic_answer_issues(
        "这一周行情下跌的主要原因是什么",
        {"answer_status": "partial"},
        [
            {
                "role": "assistant",
                "content": (
                    "直接回答：本周实际上涨2.99%，问题前提与数据不符。"
                    "现有证据库不含与7月17日对齐的新闻或政策信息，"
                    "无法将单日下跌归因于特定催化剂。"
                ),
            }
        ],
    )

    assert issues == []


@pytest.mark.parametrize(
    "generic_gap",
    [
        "没有新闻。",
        "现有证据库没有新闻。",
        "未检索到新闻。",
        "仍需核验新闻。",
    ],
)
def test_semantic_smoke_rejects_unaligned_generic_cause_gap(
    generic_gap: str,
) -> None:
    issues = semantic_answer_issues(
        "这一周行情下跌的主要原因是什么",
        {"answer_status": "partial"},
        [{"role": "assistant", "content": generic_gap}],
    )

    assert "answer_status='partial'" in issues


@pytest.mark.parametrize(
    "cause_question",
    [
        "这一周为什么下跌",
        "这一周行情下跌的主要诱因是什么",
        "这轮下跌怎么回事",
    ],
)
def test_semantic_smoke_applies_cause_gate_to_equivalent_phrasings(
    cause_question: str,
) -> None:
    issues = semantic_answer_issues(
        cause_question,
        {"answer_status": "partial"},
        [{"role": "assistant", "content": "未检索到新闻。"}],
    )

    assert "answer_status='partial'" in issues


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


def test_semantic_smoke_accepts_partial_forecast_with_specific_invalidation_gap() -> (
    None
):
    issues = semantic_answer_issues(
        "昨天的反弹能持续多久",
        {"answer_status": "partial"},
        [
            {
                "role": "assistant",
                "content": (
                    "基准判断：本轮反弹预计还可持续1-3个交易日。"
                    "证据缺口：失效条件中的未核验数值阈值已删除，"
                    "需补充直接证据。"
                ),
            }
        ],
    )

    assert issues == []


def test_semantic_smoke_accepts_continuation_condition_gap_wording() -> None:
    issues = semantic_answer_issues(
        "昨天的反弹能持续多久",
        {"answer_status": "partial"},
        [
            {
                "role": "assistant",
                "content": (
                    "基准判断：本轮反弹短期内（约1-3个交易日）"
                    "大概率仍可惯性维持。"
                    "证据缺口：判断继续成立的可核验条件中的未核验表述"
                    "已删除，需补充直接证据。"
                ),
            }
        ],
    )

    assert issues == []


@pytest.mark.parametrize(
    "answer",
    (
        (
            "预计本轮反弹还能持续1-3个交易日。"
            "成交数据存在证据缺口。失效条件尚待观察。"
        ),
        (
            "预计本轮反弹还能持续1-3个交易日。"
            "量能仍需核验。这里的判断可能失效。"
        ),
        (
            "预计本轮反弹还能持续1-3个交易日。"
            "证据缺口：反弹依据不足。另需考虑失效。"
        ),
    ),
)
def test_semantic_smoke_rejects_unrelated_gap_plus_invalidation_word(
    answer: str,
) -> None:
    issues = semantic_answer_issues(
        "昨天的反弹能持续多久",
        {"answer_status": "partial"},
        [{"role": "assistant", "content": answer}],
    )

    assert "forecast_invalidation_missing" in issues


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


def test_semantic_smoke_accepts_real_forecast_wording_and_listed_triggers() -> None:
    issues = semantic_answer_issues(
        "昨天的反弹能持续多久",
        {"answer_status": "complete"},
        [
            {
                "role": "assistant",
                "content": (
                    "【基准判断与持续时间】主观基准：本轮反弹短期"
                    "（约3-5个交易日内）仍有惯性但持续性偏弱。"
                    "【失效或降级条件】①成交继续萎缩；"
                    "②涨停家数大幅回落、跌停扩散。"
                ),
            }
        ],
    )

    assert issues == []


def test_semantic_smoke_accepts_markdown_invalidation_heading() -> None:
    issues = semantic_answer_issues(
        "昨天的反弹能持续多久",
        {"answer_status": "complete"},
        [
            {
                "role": "assistant",
                "content": (
                    "**基准判断与持续时间**：本轮反弹预计还可持续1-3个交易日。"
                    "**失效条件**：①上证指数失守反弹起点；"
                    "②成交额继续萎缩。"
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
        "本轮反弹发生在近5个交易日。若成交继续缩量则判断失效。",
        "主观基准数据采用近5个交易日。若成交继续缩量则判断失效。",
        "本轮反弹已持续5个交易日。若成交继续缩量则判断失效。",
        "主观基准：过去5个交易日市场上涨。若成交继续缩量则判断失效。",
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
    "non_trigger",
    [
        "【失效条件】成交额为2万亿元。",
        "【失效条件】成交数据仍待核实。",
        "失效条件：若成交数据仍待核实。",
    ],
)
def test_semantic_smoke_rejects_observation_as_invalidation(
    non_trigger: str,
) -> None:
    issues = semantic_answer_issues(
        "昨天的反弹能持续多久",
        {"answer_status": "complete"},
        [
            {
                "role": "assistant",
                "content": (
                    "主观基准：本轮反弹短期约3-5个交易日，仍有惯性。"
                    + non_trigger
                ),
            }
        ],
    )

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
