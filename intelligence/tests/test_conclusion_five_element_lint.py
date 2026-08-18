from __future__ import annotations

from pathlib import Path

from intelligence.services.conclusion_five_element_lint import (
    ELEMENT_IDS,
    lint_conclusion_five_elements,
    render_presence_baseline,
)


COMPLETE = """
## 结论
**直接定性：** 仍是预期交易，不是业绩主升。
**主要风险：** 若毛利率连续两季回落，判断降级。
**下一步验证：** T+1 看放量，T+3 看扩散是否同步。
未验证变量是单季毛利率，时点看 2026-10-31 三季报。
替代路径：若被证伪则改看有公告订单的中游。
"""


def test_complete_conclusion_has_all_five_elements() -> None:
    report = lint_conclusion_five_elements(COMPLETE)

    assert report.present_ids == ELEMENT_IDS
    assert report.missing_ids == ()


def test_qualitative_line_longer_than_40_chars_is_absent() -> None:
    text = COMPLETE.replace(
        "仍是预期交易，不是业绩主升。",
        "它真正的问题在于产业叙事很多但能进入当期报表的部分并不多所以更像旧逻辑被重新唤醒。",
    )
    report = lint_conclusion_five_elements(text)

    assert "qualitative" in report.missing_ids


def test_risk_without_variable_direction_and_signal_is_absent() -> None:
    text = COMPLETE.replace(
        "若毛利率连续两季回落，判断降级。",
        "仍有不确定性，需要继续观察。",
    )
    report = lint_conclusion_five_elements(text)

    assert "risk_signal" in report.missing_ids


def test_next_step_without_layers_is_absent() -> None:
    text = COMPLETE.replace(
        "T+1 看放量，T+3 看扩散是否同步。",
        "后续再看一下盘面。",
    )
    report = lint_conclusion_five_elements(text)

    assert "next_layered" in report.missing_ids


def test_unverified_without_time_is_absent() -> None:
    text = COMPLETE.replace(
        "未验证变量是单季毛利率，时点看 2026-10-31 三季报。",
        "还有一些变量没验证。",
    )
    report = lint_conclusion_five_elements(text)

    assert "unverified_timed" in report.missing_ids


def test_missing_alternative_path_is_absent() -> None:
    text = COMPLETE.replace(
        "替代路径：若被证伪则改看有公告订单的中游。",
        "继续跟踪原逻辑即可。",
    )
    report = lint_conclusion_five_elements(text)

    assert "alternative" in report.missing_ids


def test_each_element_has_an_independent_positive_sample() -> None:
    samples = {
        "qualitative": "**直接定性：** 防御性试盘，不是主线切换。",
        "risk_signal": "**主要风险：** 若成交连续三日缩量，判断走弱。",
        "next_layered": "**下一步验证：** T+1 看回封，T+5 看板块扩散。",
        "unverified_timed": "未验证变量是库存，时点看本月库存公告。",
        "alternative": "替代路径：证伪后切到有订单的上游。",
    }
    for element_id, snippet in samples.items():
        report = lint_conclusion_five_elements(f"## 结论\n{snippet}")
        assert element_id in report.present_ids, element_id


def test_baseline_report_lists_presence_rate_for_each_element() -> None:
    corpus = {
        "complete": COMPLETE,
        "empty": "随便聊聊行情。",
    }
    text = render_presence_baseline(corpus, as_of="2026-08-18")

    assert "结论五元素在场率" in text
    for element_id in ELEMENT_IDS:
        assert element_id in text
    assert "1/2" in text


def test_golden_snapshots_can_be_batched_for_baseline() -> None:
    snapshots = Path(__file__).parent / "fixtures" / "golden_answers" / "snapshots"
    corpus = {
        path.stem: path.read_text(encoding="utf-8")
        for path in sorted(snapshots.glob("*.md"))
    }
    assert len(corpus) >= 3
    text = render_presence_baseline(corpus, as_of="2026-08-18")
    assert "stock_anchor" in text
    assert "theme_analysis" in text
