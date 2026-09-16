"""DB-1 注册表形状：spec 三字段齐全，PROVIDER_NAMES 与注册顺序同源。"""

from __future__ import annotations

import pytest

from intelligence.services.evidence_registry import PROVIDER_NAMES, REGISTRY
from intelligence.tests.conformance_datablocks.baseline import ratchet
from intelligence.tests.conformance_datablocks.blocks import BLOCK_NAMES

INV = "DB-1"


@pytest.mark.parametrize("block_name", BLOCK_NAMES)
def test_spec_fields_are_present_and_meaningful(
    block_name: str,
    request: pytest.FixtureRequest,
) -> None:
    ratchet(request, INV, block_name)
    spec = next(item for item in REGISTRY if item.name == block_name)
    assert spec.name.strip() == spec.name and spec.name, "name 必须非空且无首尾空白"
    assert spec.label.strip(), f"{block_name} 的 label 为空——汇总/trace 全靠它辨认"
    assert spec.description.strip(), f"{block_name} 缺 description——注册表即文档"


def test_names_unique_and_order_is_single_sourced() -> None:
    assert len(set(PROVIDER_NAMES)) == len(PROVIDER_NAMES), "块名重复"
    assert PROVIDER_NAMES == tuple(spec.name for spec in REGISTRY), (
        "PROVIDER_NAMES 与 REGISTRY 顺序漂移——注册顺序即汇总顺序，两者必须同源"
    )
    labels = tuple(spec.label for spec in REGISTRY)
    assert len(set(labels)) == len(labels), "label 重复——trace/引用按 label 辨块会串"
