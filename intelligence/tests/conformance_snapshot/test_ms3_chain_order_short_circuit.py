"""MS-3 回退链顺序如实、首个成功即短路（成功者之后零执行）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from intelligence.tests.conformance_snapshot.baseline import ratchet
from intelligence.tests.conformance_snapshot.providers import (
    CHAIN_ORDER,
    PROVIDER_NAMES,
    run_publishing_scenario,
    run_total_failure,
)

INV = "MS-3"


@pytest.mark.parametrize("provider", PROVIDER_NAMES)
def test_attempt_sequence_is_the_chain_prefix_up_to_publisher(
    provider: str,
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, provider)
    result = run_publishing_scenario(provider, tmp_path)
    sequence = tuple(item.provider for item in result.attempts)
    if provider == "existing_complete":
        # 旁路命中：整条链零执行（akshare 禁跑 runner 未触发即为证）。
        assert sequence == ("existing_complete",)
        return
    index = CHAIN_ORDER.index(provider)
    assert sequence == CHAIN_ORDER[: index + 1], (
        "attempt 序列必须是链序前缀——乱序或跳项都意味着收据说谎"
    )
    assert [item.published for item in result.attempts].count(True) == 1
    assert result.attempts[-1].published is True, "发布者必须是序列最后一项"


def test_total_failure_walks_the_whole_chain_in_order(tmp_path: Path) -> None:
    result = run_total_failure(tmp_path)
    assert tuple(item.provider for item in result.attempts) == CHAIN_ORDER
