from intelligence.services.episode_output_substance import (
    label_unlabelled_analytical_inferences,
)


def test_relabel_prefixes_bare_inference_but_keeps_facts_and_boundary() -> None:
    draft = (
        "基准判断：周一优先观察有色金属的资金承接。\n"
        "铜也呈现走强与净流入，构成相对清晰的强势簇。\n"
        "稀有金属强度 2544。\n"
        "若转弱则不宜追高。\n"
        "证据边界：可用最新行情日期为2026-08-14。"
    )

    labeled = label_unlabelled_analytical_inferences(draft)

    assert "基准判断：周一优先观察" in labeled
    assert labeled.count("基准判断：") == 1
    assert "据此判断：铜也呈现走强与净流入，构成相对清晰的强势簇。" in labeled
    assert "据此判断：若转弱则不宜追高。" in labeled
    assert "稀有金属强度 2544。" in labeled
    assert "据此判断：稀有金属强度" not in labeled
    assert "据此判断：证据边界" not in labeled


def test_relabel_does_not_mark_external_cause_as_analysis() -> None:
    draft = "政策变化导致市场下跌。"

    assert label_unlabelled_analytical_inferences(draft) == draft


def test_relabel_is_idempotent() -> None:
    draft = "据此判断：说明更偏结构性机会。"

    assert label_unlabelled_analytical_inferences(draft) == draft
    assert (
        label_unlabelled_analytical_inferences(
            label_unlabelled_analytical_inferences(
                "说明更偏结构性机会。"
            )
        )
        == "据此判断：说明更偏结构性机会。"
    )
