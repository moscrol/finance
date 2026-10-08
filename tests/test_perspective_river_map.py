"""视角 ↔ 河 映射表的契约。

这张表是**唯一**把「我的判据」和「河的标签」连起来的东西。此前两边互不引用
（实测双向 0 处 import），agent 每次都得临场把散文翻译成标签组合——翻译结果
不确定、不可复算、也没人说得出这次漏了哪条判据。

所以映射表本身要有门禁。它最可能的三种烂法：

1. **悄悄落后于画像**：画像加了一条判据，映射表没跟，审计照样输出一个好看的百分比，
   而那个分母是旧的。第一版的覆盖检查用字符串前缀模糊匹配，把 6 条已覆盖的判据
   误报成未覆盖——会误报的检查比没有检查更坏，人会学会忽略它。改成集合相等。
2. **引用不存在的标签**：映射表写 ``needs_labels: ["xxx"]``，而河里根本没这个词，
   于是这条判据永远停在 🟡，看着像「数据不够」，实际是映射表打错字。
3. **档位写死**：把结论直接写进 JSON（"这条是可判的"）。那样河扩了标签之后，
   审计还在报旧档。档位必须每次现算。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MAP_DIR = REPO_ROOT / "docs" / "learning" / "perspective-river-map"
MAPS = sorted(MAP_DIR.glob("*.json"))

VALID_KEYS = {
    "lens", "criterion", "needs_labels", "needs_fields", "needs_schema",
    "architecture", "absent_note", "note",
}


def test_audit_missing_profile_is_not_reported_as_zero_coverage_gap(monkeypatch):
    from scripts import audit_perspective_consumability as tool

    monkeypatch.setattr(tool, "load_map", lambda pid: {"criteria": [], "profile_coverage": {"old": []}})

    def missing(*args):
        raise SystemExit("profile absent")

    monkeypatch.setattr(tool, "profile_criteria", missing)
    with pytest.raises(SystemExit, match="profile absent"):
        tool.audit("synthetic", {"labels": set(), "slice_note": "fixture"}, user=None)


def test_audit_empty_profile_exposes_stale_mapping(monkeypatch):
    from scripts import audit_perspective_consumability as tool

    monkeypatch.setattr(tool, "load_map", lambda pid: {"criteria": [], "profile_coverage": {"old": []}})
    monkeypatch.setattr(tool, "profile_criteria", lambda *args: [])
    result = tool.audit("synthetic", {"labels": set(), "slice_note": "fixture"}, user=None)
    assert result["stale"] == ["old"]


def _ids(paths: list[Path]) -> list[str]:
    return [p.stem for p in paths]


@pytest.mark.skipif(not MAPS, reason="还没有任何映射表")
@pytest.mark.parametrize("path", MAPS, ids=_ids(MAPS))
def test_映射表与画像逐条对齐(path: Path) -> None:
    """``profile_coverage`` 的 key 集合必须**恰好等于**画像里的判据原文集合。

    少一条 = 映射表落后于画像（审计的分母是旧的）；
    多一条 = 画像改过而映射表还认领着已经不存在的判据。
    两种都要红，且要指名道姓说出是哪一条。
    """
    import sys

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from scripts.audit_perspective_consumability import profile_criteria

    spec = json.loads(path.read_text(encoding="utf-8"))
    live = set(profile_criteria(spec["perspective"], None))
    declared = set(spec.get("profile_coverage") or {})

    missing = sorted(live - declared)
    stale = sorted(declared - live)
    assert not missing, f"{path.name} 没有覆盖画像里的这些判据（审计分母会偏小）：\n  " + "\n  ".join(missing)
    assert not stale, f"{path.name} 认领了画像里已经没有的判据：\n  " + "\n  ".join(stale)


@pytest.mark.skipif(not MAPS, reason="还没有任何映射表")
@pytest.mark.parametrize("path", MAPS, ids=_ids(MAPS))
def test_覆盖声明引用的判据都真实存在(path: Path) -> None:
    """``profile_coverage`` 的 value 里每个名字都要在 ``criteria`` 里找得到，反之亦然。

    一条画像原文拆成多条可核对判据是常态（风远的「条件化买点」一句里含四个独立观测量），
    但拆出来的每一条都必须被某条原文认领——否则它是凭空多出来的，没人知道它从哪来。
    """
    spec = json.loads(path.read_text(encoding="utf-8"))
    names = {c["criterion"] for c in spec["criteria"]}
    claimed = {n for v in (spec.get("profile_coverage") or {}).values() for n in v}

    assert not (claimed - names), f"覆盖声明引用了不存在的判据：{sorted(claimed - names)}"
    assert not (names - claimed), f"这些判据没被任何画像原文认领：{sorted(names - claimed)}"


@pytest.mark.skipif(not MAPS, reason="还没有任何映射表")
@pytest.mark.parametrize("path", MAPS, ids=_ids(MAPS))
def test_引用的标签必须是河真的能判的(path: Path) -> None:
    """``needs_labels`` 里打错一个字，这条判据会永远停在 🟡，看着像数据不够、实则是笔误。

    注意这里比的是 ``SLICE_EVALUABLE_LABELS`` 而不是 ``ALL_LABELS``：
    映射表声明「这条判据靠这个标签」，指的是能写进情景树分枝的那种能判。
    """
    from intelligence.services.river_derive import SLICE_EVALUABLE_LABELS

    spec = json.loads(path.read_text(encoding="utf-8"))
    bad = []
    for c in spec["criteria"]:
        for lab in c.get("needs_labels") or []:
            if lab not in SLICE_EVALUABLE_LABELS:
                bad.append(f"{c['criterion']} → {lab!r}")
    assert not bad, (
        "映射表引用了河判不了的标签（是笔误还是该先去接线？）：\n  "
        + "\n  ".join(bad)
        + f"\n  当前可判：{sorted(SLICE_EVALUABLE_LABELS)}"
    )


@pytest.mark.skipif(not MAPS, reason="还没有任何映射表")
@pytest.mark.parametrize("path", MAPS, ids=_ids(MAPS))
def test_映射表不得写死档位(path: Path) -> None:
    """档位（可判 / 有料无词 / …）必须由工具现算，不能存进 JSON。

    写死的后果很具体：河今天把 lifecycle_stage 接进了白名单，这条判据应当自动从
    🟡 升到 ✅。若 JSON 里存着「🟡」，审计会继续报旧档，而且**没有任何测试会红**——
    一个只会往「低估自己能力」方向出错的数字，比高估更难被发现。
    """
    spec = json.loads(path.read_text(encoding="utf-8"))
    for c in spec["criteria"]:
        extra = set(c) - VALID_KEYS
        assert not extra, f"{c['criterion']}: 未知字段 {sorted(extra)}（档位由工具现算，不写进表）"
        assert "verdict" not in c and "status" not in c


@pytest.mark.skipif(not MAPS, reason="还没有任何映射表")
@pytest.mark.parametrize("path", MAPS, ids=_ids(MAPS))
def test_每条判据都要说清楚凭什么(path: Path) -> None:
    """四个依赖字段至少占一个。一条都不写 = 这条判据没人想过它要什么数据。"""
    spec = json.loads(path.read_text(encoding="utf-8"))
    naked = [
        c["criterion"]
        for c in spec["criteria"]
        if not any(c.get(k) for k in ("needs_labels", "needs_fields", "needs_schema", "architecture", "absent_note"))
    ]
    assert not naked, f"这些判据没声明任何依赖：{naked}"


@pytest.mark.skipif(not MAPS, reason="还没有任何映射表")
@pytest.mark.parametrize("path", MAPS, ids=_ids(MAPS))
def test_草稿必须标明未经认定(path: Path) -> None:
    """映射表编码的是**用户自己的**判据，认定权不在 agent。

    agent 草拟的表必须自带 ``status: draft`` 与署名，否则下游会把一份猜测当成
    已确认的方法论——本仓 skill 第 4 步写明「认定权在用户」，这是同一条纪律。
    """
    spec = json.loads(path.read_text(encoding="utf-8"))
    assert spec.get("author"), "映射表必须署名"
    assert spec.get("version"), "映射表必须有版本"
    if "agent" in spec["author"] and "认定" not in spec["author"]:
        pytest.fail("agent 草拟的映射表要在 author 里写明是否经用户认定")


@pytest.mark.skipif(not MAPS, reason="还没有任何映射表")
def test_审计跑得起来且档位是现算的() -> None:
    """端到端：工具能跑完，且 lifecycle_stage 这条确实被算成「可判」。

    最后这句是有来历的阳性对照：2026-10-07 之前 ``lifecycle_stage`` 不在可判白名单里，
    这条判据当时应当是 🟡。它现在是 ✅，证明档位真的跟着河的能力走，而不是抄的 JSON。
    """
    import sys

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from scripts.audit_perspective_consumability import audit, river_capability

    cap = river_capability(None, "半导体", None)
    rep = audit("kol_fengyuan", cap, user=None)

    assert rep["total"] == sum(rep["tally"].values())
    cycle = next(r for r in rep["rows"] if r["criterion"] == "先定周期位置再谈标的")
    assert cycle["verdict"] == "judgeable", (
        "lifecycle_stage 已在可判白名单里，这条判据应当现算成「可判」；"
        f"实际 {cycle['verdict']}（{cycle['why']}）"
    )
