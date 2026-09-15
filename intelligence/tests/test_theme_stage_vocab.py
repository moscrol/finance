"""G-04 题材阶段钦定词表：映射全覆盖、fail-closed、与 tsc-v0 逐字节等价、两模块输出带 canonical。"""

from __future__ import annotations

import pytest

from intelligence.services import opinion_stage, theme_lifecycle, theme_stage_vocab
from intelligence.services import theme_lifecycle_timeline as timeline

# tsc-v0 冻结对照：G-04 之前 opinion_stage.THEME_STAGE_COARSE 的手工双表原文。
# 派生表必须与它逐字节相等——词表统一是「换唯一出处」，不是「换行为」。
TSC_V0_FROZEN = {
    "theme_lifecycle": {
        "新出现": "early", "旧逻辑唤醒": "early", "升温验证": "mid", "加速定价": "late",
        "高位分歧": "late", "二阶段回流": "late", "衰退观察": "late", "证伪退出": "late",
    },
    "theme_lifecycle_timeline": {
        "酝酿": "early", "首发": "early", "发酵": "mid", "主升": "late",
        "分歧": "late", "退潮": "late", "回流": "late",
    },
}


def test_diagnosis_mapping_covers_exactly_the_eight_stages():
    assert set(theme_stage_vocab.TO_CANONICAL[theme_stage_vocab.MODULE_DIAGNOSIS]) == set(
        theme_lifecycle.LIFECYCLE_STAGES
    )


def test_timeline_mapping_is_identity_over_canonical_stages():
    mapping = theme_stage_vocab.TO_CANONICAL[theme_stage_vocab.MODULE_TIMELINE]
    assert mapping == {s: s for s in theme_stage_vocab.CANONICAL_STAGES}
    # timeline 模块自己的七个常量与 canonical 词一一相同（词表就是从它钦定的）
    module_stages = {
        timeline.STAGE_INCUBATION, timeline.STAGE_FIRST_MOVE, timeline.STAGE_FERMENT,
        timeline.STAGE_MAIN_UP, timeline.STAGE_DIVERGENCE, timeline.STAGE_EBB, timeline.STAGE_REFLOW,
    }
    assert module_stages == set(theme_stage_vocab.CANONICAL_STAGES)


def test_all_mapping_values_are_canonical_and_have_coarse():
    for mapping in theme_stage_vocab.TO_CANONICAL.values():
        for canonical in mapping.values():
            assert canonical in theme_stage_vocab.CANONICAL_STAGES
            assert theme_stage_vocab.coarse_of(canonical) in {"early", "mid", "late"}


def test_to_canonical_fail_closed():
    with pytest.raises(ValueError):
        theme_stage_vocab.to_canonical("酝酿", "no_such_module")
    # 未知细词与 None：返回 None（不在生命周期序上），不猜
    assert theme_stage_vocab.to_canonical("无法判定", theme_stage_vocab.MODULE_DIAGNOSIS) is None
    assert theme_stage_vocab.to_canonical(None, theme_stage_vocab.MODULE_DIAGNOSIS) is None
    assert theme_stage_vocab.coarse_of(None) is None


def test_module_coarse_tables_byte_equal_to_tsc_v0():
    assert theme_stage_vocab.module_coarse_tables() == TSC_V0_FROZEN


def test_opinion_stage_now_derives_from_vocab():
    assert opinion_stage.THEME_STAGE_COARSE == TSC_V0_FROZEN
    assert opinion_stage.THEME_STAGE_MAPPING_VERSION == theme_stage_vocab.VOCAB_VERSION
    # 错位标记行为不变（tsc-v0 时代的三个代表用例）
    assert opinion_stage.dislocation("主升", opinion_stage.STAGE_SPROUT, theme_module="theme_lifecycle_timeline") == "opinion_lags"
    assert opinion_stage.dislocation("新出现", opinion_stage.STAGE_CROWDED) == "opinion_leads"
    assert opinion_stage.dislocation(None, opinion_stage.STAGE_SPREAD) == opinion_stage.UNVERIFIABLE


@pytest.mark.parametrize("stage", theme_lifecycle.LIFECYCLE_STAGES)
def test_diagnosis_payload_carries_canonical(stage):
    diag = theme_lifecycle.ThemeLifecycleDiagnosis(theme="固态电池", stage=stage)
    payload = diag.to_dict()
    assert payload["stage"] == stage
    assert payload["stage_canonical"] == theme_stage_vocab.TO_CANONICAL[theme_stage_vocab.MODULE_DIAGNOSIS][stage]
    assert payload["vocab_version"] == theme_stage_vocab.VOCAB_VERSION


def test_diagnosis_unknown_stage_maps_to_none():
    diag = theme_lifecycle.ThemeLifecycleDiagnosis(theme="固态电池")  # 默认 无法判定
    assert diag.to_dict()["stage_canonical"] is None


def test_timeline_payload_carries_canonical():
    seg = timeline.StageSegment(stage="发酵", start_date="2026-09-01", end_date="2026-09-03", trigger="双红")
    assert seg.to_payload()["stage_canonical"] == "发酵"
    artifact = timeline.ThemeTimelineArtifact(theme="固态电池", segments=(seg,), gaps=())
    payload = artifact.to_payload()
    assert payload["current_stage_canonical"] == "发酵"
    assert payload["vocab_version"] == theme_stage_vocab.VOCAB_VERSION
    empty = timeline.ThemeTimelineArtifact(theme="固态电池", segments=(), gaps=("no rows",))
    assert empty.to_payload()["current_stage_canonical"] is None
