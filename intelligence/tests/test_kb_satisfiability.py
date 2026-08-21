"""W2a 静态供给预检：题材在 KB relations 有无链路证据（机械可查）。

spec: docs/superpowers/specs/2026-08-21-ceiling-shape-closeout-design.md W2-a。
判定口径是 entity_exposures 的命中行数——机械事实，不做「预测工具会不会
返回有用数据」这类猜测型预检（spec 禁区）。
"""

from __future__ import annotations

from intelligence.services.kb_satisfiability import chain_evidence_present


class _StubAdapter:
    def __init__(self, total_matched: int, *, errors: list[str] | None = None):
        self._total = total_matched
        self._errors = errors or []

    def get_exposure_matches(self, term: str, limit: int = 12) -> dict[str, object]:
        return {
            "found": bool(self._total),
            "term": term,
            "items": [],
            "total_matched": self._total,
            "truncated": False,
            "warnings": [],
            "errors": list(self._errors),
        }


class _BrokenAdapter:
    def get_exposure_matches(self, term: str, limit: int = 12) -> dict[str, object]:
        raise OSError("relations unreadable")


def test_theme_with_exposure_rows_reports_evidence_present() -> None:
    assert chain_evidence_present("钙钛矿", adapter=_StubAdapter(45)) is True


def test_theme_without_exposure_rows_reports_evidence_absent() -> None:
    assert chain_evidence_present("尚未入库的新题材", adapter=_StubAdapter(0)) is False


def test_blank_theme_fails_open_to_present() -> None:
    # 空主体查不了 relations，不得据此降级 mandatory——预检只在
    # 「机械确认无证据」时才有降级权。
    assert chain_evidence_present("", adapter=_StubAdapter(0)) is True
    assert chain_evidence_present("   ", adapter=_StubAdapter(0)) is True


def test_relations_read_error_fails_open_to_present() -> None:
    # 让一次坏的 relations 读取拥有降级权 = 造一个新的静默失败源
    # （与 satisfiability_precheck 的 fail-open 论证同源）。
    assert chain_evidence_present("钙钛矿", adapter=_BrokenAdapter()) is True


def test_relations_reported_errors_fail_open_to_present() -> None:
    assert (
        chain_evidence_present(
            "钙钛矿",
            adapter=_StubAdapter(0, errors=["entity_exposures.json missing"]),
        )
        is True
    )
