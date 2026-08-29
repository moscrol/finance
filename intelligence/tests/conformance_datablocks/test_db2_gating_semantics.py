"""DB-2 门控语义：None=全允许、名单=白名单、未知名 fail closed。

``provider_enabled`` 的契约只读 ``options.enabled_providers``（对 AskOptions
的引用仅 TYPE_CHECKING），故用最小鸭子型 options——理由见 blocks.DuckOptions。
"""

from __future__ import annotations

import pytest

from intelligence.services.evidence_registry import (
    provider_enabled,
    providers_allowing_memory,
    without_providers,
)
from intelligence.tests.conformance_datablocks.baseline import ratchet
from intelligence.tests.conformance_datablocks.blocks import BLOCK_NAMES, DuckOptions

INV = "DB-2"


@pytest.mark.parametrize("block_name", BLOCK_NAMES)
def test_allowlist_semantics_per_block(
    block_name: str,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, block_name)
    assert provider_enabled(DuckOptions(None), block_name), "None 必须=全部允许"
    assert provider_enabled(DuckOptions((block_name,)), block_name)
    assert not provider_enabled(DuckOptions(()), block_name), "空名单必须=全部禁止"
    others = tuple(name for name in BLOCK_NAMES if name != block_name)
    assert not provider_enabled(DuckOptions(others), block_name), (
        "不在名单内必须被裁剪"
    )


@pytest.mark.parametrize("block_name", BLOCK_NAMES)
def test_without_providers_excludes_exactly_the_named_block(
    block_name: str,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, block_name)
    remaining = without_providers(block_name)
    assert block_name not in remaining
    assert remaining == tuple(n for n in BLOCK_NAMES if n != block_name), (
        "剔除一个块不得扰动其余块的注册顺序"
    )


def test_unknown_names_fail_closed() -> None:
    with pytest.raises(KeyError):
        provider_enabled(DuckOptions(None), "不存在的块")
    with pytest.raises(ValueError):
        without_providers("不存在的块")


def test_memory_gate_removes_exactly_memory_blocks() -> None:
    assert providers_allowing_memory(True) is None, "needs_memory=True 必须不限制"
    allowed = providers_allowing_memory(False)
    assert allowed is not None
    assert set(BLOCK_NAMES) - set(allowed) == {"M", "V"}, (
        "needs_memory=False 只应裁掉记忆两块（M/V），不得多裁或漏裁"
    )
