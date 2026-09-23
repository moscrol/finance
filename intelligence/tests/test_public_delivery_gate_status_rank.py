"""交付门落点取「更差」而不是覆盖（PR #862 独立 QC 的 M1 发现）。

原接线 ``answer_status = delivery.answer_status or answer_status`` 是无条件覆盖：
业务状态已是 ``blocked`` 时，门判 ``incomplete``（→ ``partial``）会把
``report["answer_status"]`` 字段抬回 partial。``complete_report`` 的 ``status`` 本来就取
更差值，所以用户可见终态没错，但字段本身在说谎。修法：排序只有一张
``STATUS_RANK``，``complete_report`` 与 runtime 接线都用 ``worse_status`` 取更差。
"""

from __future__ import annotations

from intelligence.api.structured_reports import (
    STATUS_RANK,
    complete_report,
    worse_status,
)


def test_status_rank_is_the_single_ordering() -> None:
    assert STATUS_RANK["complete"] < STATUS_RANK["partial"] < STATUS_RANK["gap"]
    assert STATUS_RANK["gap"] == STATUS_RANK["missing"]
    assert STATUS_RANK["blocked"] > STATUS_RANK["gap"]


def test_worse_status_never_lifts_an_existing_status() -> None:
    assert worse_status("complete", "partial") == "partial"
    assert worse_status("partial", "gap") == "gap"
    assert worse_status("blocked", "partial") == "blocked"
    assert worse_status("partial", "blocked") == "blocked"
    assert worse_status("blocked", "missing") == "blocked"
    assert worse_status("gap", None) == "gap"
    assert worse_status(None, "partial") == "partial"


def test_worse_status_ties_keep_the_existing_value_and_ignore_unknowns() -> None:
    # gap 与 missing 同级：调用方把「已有状态」放前面，就不会被同级新值改写。
    assert worse_status("gap", "missing") == "gap"
    assert worse_status("missing", "gap") == "missing"
    assert worse_status("bogus", None) is None
    assert worse_status() is None
    assert worse_status("bogus", "partial") == "partial"


def test_complete_report_uses_the_same_ordering() -> None:
    report = complete_report(
        {},
        as_of=None,
        warnings=[],
        llm_provider=None,
        llm_model=None,
        business_status="blocked",
        answer_status="partial",
    )
    # 终态取更差（blocked）；字段按调用方给的值如实记录——所以「取更差」必须
    # 发生在调用方（runtime 接线），这条只钉 complete_report 自己不再另抄一张表。
    assert report["status"] == "blocked"
    assert report["business_status"] == "blocked"
    assert report["research_status"] == "blocked"
    assert report["answer_status"] == "partial"

    healthy = complete_report(
        {},
        as_of=None,
        warnings=[],
        llm_provider=None,
        llm_model=None,
        business_status="complete",
        answer_status="missing",
    )
    assert healthy["status"] == "missing"
    assert healthy["answer_status"] == "missing"
