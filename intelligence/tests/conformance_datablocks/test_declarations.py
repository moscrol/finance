"""声明表/notes/findings/baseline 自身的完整性——三件之一必须有消费者。"""

from __future__ import annotations

from intelligence.tests.conformance_datablocks.baseline import BASELINE
from intelligence.tests.conformance_datablocks.blocks import (
    ASSEMBLY_FINDINGS,
    BLOCK_DECLARATIONS,
    BLOCK_NAMES,
    BLOCK_NOTES,
    DB_INVARIANT_IDS,
)


def test_declaration_table_covers_every_block_and_invariant() -> None:
    assert set(BLOCK_DECLARATIONS) == set(BLOCK_NAMES)
    for block_name, verdicts in BLOCK_DECLARATIONS.items():
        assert set(verdicts) == set(DB_INVARIANT_IDS), (
            f"{block_name} 的声明缺不变量：{set(DB_INVARIANT_IDS) - set(verdicts)}"
        )
        for invariant, verdict in verdicts.items():
            assert verdict == "supported", (
                f"{block_name}:{invariant} 声明为 {verdict!r}——注册表/运行器层"
                "契约单点强制，出现非 supported 说明装配面分叉，先在 BLOCK_NOTES"
                " 写清出处再改这里"
            )


def test_notes_reference_known_blocks_only() -> None:
    unknown = set(BLOCK_NOTES) - set(BLOCK_NAMES)
    assert not unknown, f"notes 引用了不存在的块：{sorted(unknown)}"


def test_assembly_findings_are_stated() -> None:
    assert ASSEMBLY_FINDINGS, "装配面 findings 被清空——若缺口已修，连同本断言一起更新"
    for finding in ASSEMBLY_FINDINGS:
        assert finding.strip(), "finding 不得为空串"


def test_baseline_keys_reference_known_blocks_and_invariants() -> None:
    for key, reason in BASELINE.items():
        invariant, _, block_name = key.partition(":")
        assert invariant in DB_INVARIANT_IDS, f"baseline key 不合法：{key}"
        assert block_name in BLOCK_NAMES, f"baseline key 指向未知块：{key}"
        assert reason.strip(), f"baseline 条目缺原因：{key}"
