"""知识库暴露度适配器：别名归一、后缀剥离、硬/软证据分档、as_of 前视闸门。"""
from __future__ import annotations

import json

import pytest

from market_feature_store.sources import kb_exposure as kbx

EXPOSURES = {
    "entities": {
        "剑桥科技": {
            "name": "剑桥科技", "codes": ["603083"],
            "concepts": {
                "800G/1.6T光模块": {"strength": "core", "evidence_layer": "L2", "updated": "2026-05-01"},
                "散热": {"strength": "related", "evidence_layer": "graph_only", "updated": "2026-08-20"},
            },
        },
        "蹭概念股": {
            "name": "蹭概念股", "codes": ["000999"],
            "concepts": {"PCB": {"strength": "core", "evidence_layer": "L1_L3_candidate", "updated": "2026-05-01"}},
        },
        "没代码的": {"name": "没代码的", "codes": [], "concepts": {"PCB": {"strength": "core"}}},
    }
}
ALIASES = {"aliases": {"800G1.6T光模块": "800G_1.6T光模块", "800G/1.6T光模块": "800G_1.6T光模块",
                       "散热": "液冷温控"}, "version": 4}


@pytest.fixture()
def kb(tmp_path, monkeypatch):
    rel = tmp_path / "wiki" / "relations"
    rel.mkdir(parents=True)
    (rel / "entity_exposures.json").write_text(json.dumps(EXPOSURES, ensure_ascii=False), encoding="utf-8")
    (rel / "aliases.json").write_text(json.dumps(ALIASES, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("KB_VAULT", str(tmp_path / "wiki"))
    return rel


def test_relations_dir_follows_kb_vault_env(kb):
    assert kbx.kb_relations_dir() == kb


def test_hard_layer_scores_above_soft_layer(kb):
    index = kbx.exposure_index()
    aliases = kbx.concept_aliases()
    names = kbx.concept_candidates("800G/1.6T光模块", aliases)
    score, edge = kbx.best_exposure(index["603083"], names)
    assert score == 1.0 and edge["evidence_layer"] == "L2"        # core + 年报层 = 满分
    # 同为 core，但证据层是「研报说的、还没坐实」→ 只给软分
    soft, soft_edge = kbx.best_exposure(index["000999"], kbx.concept_candidates("PCB概念", aliases))
    assert soft == 0.6 and soft_edge["evidence_layer"] == "L1_L3_candidate"


def test_decor_suffix_and_alias_both_route_to_same_concept(kb):
    aliases = kbx.concept_aliases()
    # 「PCB概念」是板块名，KB 里只有「PCB」——剥掉装饰后缀才对得上
    assert "PCB" in kbx.concept_candidates("PCB概念", aliases)
    # 「散热」经别名表指向「液冷温控」，两个写法都要能命中同一条边
    index = kbx.exposure_index()
    assert kbx.best_exposure(index["603083"], kbx.concept_candidates("散热", aliases))[0] > 0
    assert kbx.best_exposure(index["603083"], {"液冷温控"})[0] > 0


def test_as_of_drops_edges_the_day_did_not_know_yet(kb):
    """回测历史日时，2026-08-20 才写进知识库的那条边不许参与 2026-06-01 的判断。"""
    early = kbx.exposure_index(as_of="2026-06-01")
    assert [e["raw_concept"] for e in early["603083"]] == ["800G/1.6T光模块"]
    later = kbx.exposure_index(as_of="2026-08-20")
    assert len(later["603083"]) == 2
    assert len(kbx.exposure_index()["603083"]) == 2


def test_entities_without_codes_are_not_indexed(kb):
    index = kbx.exposure_index()
    assert set(index) == {"603083", "000999"}


def test_missing_relations_is_fail_closed(tmp_path, monkeypatch):
    """读不到知识库要抛，不能静默返回空表——空表会让正宗度全 0 却看起来一切正常。"""
    monkeypatch.setenv("KB_VAULT", str(tmp_path / "nope"))
    with pytest.raises(kbx.KbExposureUnavailable):
        kbx.exposure_index()
