"""声明表/notes/baseline 完整性——三件之一必须有消费者。"""

from __future__ import annotations

from intelligence.tests.conformance_transport.baseline import BASELINE
from intelligence.tests.conformance_transport.transports import (
    LT_INVARIANT_IDS,
    TRANSPORT_DECLARATIONS,
    TRANSPORT_NAMES,
    TRANSPORT_NOTES,
)


def test_declaration_table_covers_every_transport_and_invariant() -> None:
    assert set(TRANSPORT_DECLARATIONS) == set(TRANSPORT_NAMES)
    for transport, verdicts in TRANSPORT_DECLARATIONS.items():
        assert set(verdicts) == set(LT_INVARIANT_IDS), (
            f"{transport} 的声明缺不变量：{set(LT_INVARIANT_IDS) - set(verdicts)}"
        )
        for invariant, verdict in verdicts.items():
            assert verdict == "supported", (
                f"{transport}:{invariant} 声明为 {verdict!r}——两路已声明偏差"
                "（CLI 1s 地板/类名承载故障）走 TRANSPORT_NOTES 且各有钉住"
                "测试，不降声明档"
            )


def test_notes_cover_both_transports() -> None:
    assert set(TRANSPORT_NOTES) == set(TRANSPORT_NAMES), (
        "两路的已知形状差异都必须写进 notes"
    )


def test_baseline_keys_reference_known_transports_and_invariants() -> None:
    for key, reason in BASELINE.items():
        invariant, _, transport = key.partition(":")
        assert invariant in LT_INVARIANT_IDS, f"baseline key 不合法：{key}"
        assert transport in TRANSPORT_NAMES, f"baseline key 指向未知传输：{key}"
        assert reason.strip(), f"baseline 条目缺原因：{key}"
