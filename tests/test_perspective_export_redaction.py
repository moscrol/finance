"""脱敏导出的契约。

``intelligence/users/*/perspectives/`` 被 gitignore 排除，理由写在 ``perspective_lab``
的文档头：「版权 + 隐私边界」。但不能整个推上去 ≠ 不能分享——该分享的是蒸馏后的框架
（market_lenses / risk_triggers / …），不是来源（文章原文、excerpt、带日期的私人复盘）。

这个工具只会往一个方向出错，而那个方向不可撤销：推上公开仓的东西，删了也还在 git
历史里。所以它的测试要比一般工具狠，重点全在**阴性**（不该导的有没有真的没导）：

1. 白名单而非黑名单——schema 新增字段必须默认**不导出**且**点名**；
2. 已知的私密字段不导，且说得出不导的理由；
3. 夹带原文片段要被标出来（这不是边界，是提醒；边界是白名单）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def fake_user(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """造一份「什么都有」的画像：框架字段 + 私密字段 + schema 新字段 + 原文残留。"""
    import scripts.export_perspective_framework as ex

    user = "probe_user"
    d = tmp_path / "intelligence" / "users" / user / "perspectives" / "profiles"
    d.mkdir(parents=True)
    (d / "p1.json").write_text(
        json.dumps(
            {
                # —— 框架：应当导出
                "display_name": "探针视角",
                "type": "blogger",
                "market_lenses": [{"name": "镜头A", "description": "一句正常的框架描述", "weight": 1.0}],
                "risk_triggers": ["利多不涨"],
                "reasoning_patterns": [{"name": "条件化", "rule": "先定位置再谈标的"}],
                "falsification_style": ["给出 T+3 反向证据"],
                "anti_patterns": ["把单次观察写成定律"],
                "evidence_hierarchy": ["盘面"],
                "honest_boundaries": ["不适用于港股"],
                # —— 私密：不该导出，且要说得出理由
                "contradictions": ["2026-08-12 这天我自己打脸了，当时仓位 7 成"],
                "sources": {"allowed_sources": ["uploaded_articles"], "citation_required": True},
                "voice_guidance": {"style": "清晰", "forbidden": ["复刻私人语气"]},
                "confidence": {"article_count": 50, "known_gaps": ["样本偏短线"]},
                # —— schema 以后长出来的新字段：必须默认不导且点名
                "private_notes_v2": "这是以后才加的字段，里面可能是任何东西",
                "subscriber_list": ["a@example.com"],
                # —— 原文残留：excerpt 截断会留「…」
                "opportunity_preferences": [
                    "…他在文中写道「这一轮的核心矛盾是供给侧出清没有走完，所以任何反弹都只是修复而不是反转」，"
                    "这段话我认为点出了问题的本质，值得反复看，因为它把两个常被混为一谈的概念区分开了…"
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ex, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "intelligence" / "users"))
    return user


def test_框架字段导出而私密字段不导(fake_user: str) -> None:
    import scripts.export_perspective_framework as ex

    data, rep = ex.export("p1", fake_user, with_confidence=False)

    for k in ("display_name", "market_lenses", "risk_triggers", "reasoning_patterns",
              "falsification_style", "anti_patterns", "evidence_hierarchy", "honest_boundaries"):
        assert k in data, f"{k} 是可迁移框架，应当导出"

    for k in ("contradictions", "sources", "voice_guidance", "confidence"):
        assert k not in data, f"{k} 不该出现在对外导出里"
        assert k in rep["dropped_with_reason"], f"{k} 不导就要说得出理由，不能默默吞掉"


def test_schema_新字段必须默认不导且点名(fake_user: str) -> None:
    """这条是整个工具的支点。

    黑名单的形状下，画像以后加一个字段就会默认漏出去，而且漏的时候没有提示。
    白名单下它必须：① 不出现在导出里；② 出现在 dropped_unknown 里让人看见。
    两者缺一都不行——只做 ① 是静默丢弃，人会以为导全了。
    """
    import scripts.export_perspective_framework as ex

    data, rep = ex.export("p1", fake_user, with_confidence=False)

    assert "private_notes_v2" not in data
    assert "subscriber_list" not in data
    assert set(rep["dropped_unknown"]) == {"private_notes_v2", "subscriber_list"}, (
        "本工具不认识的字段必须逐个点名，由人判断它是框架还是来源"
    )


def test_夹带原文的片段会被标出来(fake_user: str) -> None:
    """白名单挡不住「框架字段里被塞进了一整段原文」这种情况——那得靠人看。

    所以工具要把超长句、残留引号与省略号的地方指出来。这是提醒不是边界：
    报告里必须出现那一条，且要给出字段路径让人能定位。
    """
    import scripts.export_perspective_framework as ex

    _, rep = ex.export("p1", fake_user, with_confidence=False)

    flagged = {f["field"] for f in rep["possible_verbatim"]}
    assert any(f.startswith("opportunity_preferences") for f in flagged), (
        f"夹带了引号 + 省略号 + 超长句的那条没被标出来；实际标了：{flagged}"
    )


def test_正常的框架描述不该被误标(fake_user: str) -> None:
    """误报率也要管：每条都标 = 等于没标，人会直接略过整个报告。

    ``market_lenses[0].description`` 是一句干干净净的框架描述，不该进提醒列表。
    """
    import scripts.export_perspective_framework as ex

    _, rep = ex.export("p1", fake_user, with_confidence=False)
    flagged = {f["field"] for f in rep["possible_verbatim"]}
    assert not any(f.startswith("market_lenses") for f in flagged), f"正常描述被误标：{flagged}"


def test_with_confidence_是显式开关(fake_user: str) -> None:
    """样本量（article_count）有时需要随框架一起给——但必须是**主动要**，不是默认带。"""
    import scripts.export_perspective_framework as ex

    off, _ = ex.export("p1", fake_user, with_confidence=False)
    on, _ = ex.export("p1", fake_user, with_confidence=True)
    assert "confidence" not in off
    assert on["confidence"]["article_count"] == 50


def test_内置画像也能导_用于自检() -> None:
    """不给 --user 时回退到内置画像。这条顺便保证工具在干净 clone 上可自检。"""
    import scripts.export_perspective_framework as ex

    data, rep = ex.export("kol_fengyuan", None, with_confidence=False)
    assert data["display_name"] == "风远框架视角"
    assert len(data["market_lenses"]) == 5
    assert not rep["dropped_unknown"], f"内置画像出现了未知字段：{rep['dropped_unknown']}"


def test_nested_private_fields_are_not_exported(fake_user, monkeypatch):
    import scripts.export_perspective_framework as ex

    prof, _ = ex.load_profile("p1", fake_user)
    prof["market_lenses"][0]["raw"] = "PRIVATE-NESTED"
    prof["reasoning_patterns"][0]["excerpt"] = "PRIVATE-EXCERPT"
    prof["confidence"]["subscriber_list"] = ["PRIVATE-SUBSCRIBER"]
    monkeypatch.setattr(ex, "load_profile", lambda *args: (prof, "synthetic"))
    data, report = ex.export("p1", fake_user, with_confidence=True)
    assert "PRIVATE-" not in json.dumps(data)
    assert set(report["dropped_nested"]) == {
        "market_lenses[0].raw", "reasoning_patterns[0].excerpt", "confidence.subscriber_list",
    }


def test_profile_export_uses_configured_userspace(tmp_path, monkeypatch):
    import scripts.export_perspective_framework as ex

    root = tmp_path / "external-users"
    profile = root / "probe" / "perspectives" / "profiles" / "p1.json"
    profile.parent.mkdir(parents=True)
    profile.write_text(json.dumps({"display_name": "external", "market_lenses": []}))
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(root))
    data, _ = ex.export("p1", "probe", with_confidence=False)
    assert data["display_name"] == "external"


def test_白名单与解释名单不得重叠() -> None:
    """同一个字段既在 ALLOW 又在 DENY_REASON = 意图自相矛盾，而 ALLOW 会赢（静默导出）。"""
    import scripts.export_perspective_framework as ex

    overlap = set(ex.ALLOW) & set(ex.DENY_REASON)
    assert not overlap, f"这些字段同时出现在白名单与拒绝说明里：{sorted(overlap)}"
