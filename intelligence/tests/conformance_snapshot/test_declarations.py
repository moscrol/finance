"""声明表/notes/baseline 完整性——三件之一必须有消费者。"""

from __future__ import annotations

from intelligence.tests.conformance_snapshot.baseline import BASELINE
from intelligence.tests.conformance_snapshot.providers import (
    CHAIN_ORDER,
    MS_INVARIANT_IDS,
    PROVIDER_DECLARATIONS,
    PROVIDER_NAMES,
    PROVIDER_NOTES,
)


def test_declaration_table_covers_every_provider_and_invariant() -> None:
    assert set(PROVIDER_DECLARATIONS) == set(PROVIDER_NAMES)
    for provider, verdicts in PROVIDER_DECLARATIONS.items():
        assert set(verdicts) == set(MS_INVARIANT_IDS), (
            f"{provider} 的声明缺不变量：{set(MS_INVARIANT_IDS) - set(verdicts)}"
        )
        for invariant, verdict in verdicts.items():
            assert verdict == "supported", (
                f"{provider}:{invariant} 声明为 {verdict!r}——attempt/发布契约由"
                "编排器单点收口，出现非 supported 先在 PROVIDER_NOTES 写清出处"
            )


def test_chain_order_is_a_subset_with_bypass_upfront() -> None:
    assert PROVIDER_NAMES[0] == "existing_complete"
    assert PROVIDER_NAMES[1:] == CHAIN_ORDER


def test_notes_reference_known_providers_only() -> None:
    unknown = set(PROVIDER_NOTES) - set(PROVIDER_NAMES)
    assert not unknown, f"notes 引用了不存在的 provider：{sorted(unknown)}"


def test_baseline_keys_reference_known_providers_and_invariants() -> None:
    for key, reason in BASELINE.items():
        invariant, _, provider = key.partition(":")
        assert invariant in MS_INVARIANT_IDS, f"baseline key 不合法：{key}"
        assert provider in PROVIDER_NAMES, f"baseline key 指向未知 provider：{key}"
        assert reason.strip(), f"baseline 条目缺原因：{key}"
