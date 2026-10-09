"""Contract tests for the knevo 专项 added/rewritten from the 44-round skill texts.

补 `test_knevo_skill_layer.py` 没钉的三件事：三个新专项（review-check / associate / kol-analyze）的
frontmatter 与无市场事实红线；六个专项都按 knevo 八章通式带「输出契约」与 🎯 收尾；
机制来源清单登记了全部九个 knevo skill 的去向。锚句出自 44 轮原文的 load_skill 返回正文。
"""
from __future__ import annotations

from pathlib import Path
import re

import pytest

REPO = Path(__file__).resolve().parents[2]
SKILLS = REPO / "skills"
NEW_APP_SKILLS = ("finance-review-check", "finance-associate", "finance-kol-analyze")
EIGHT_CHAPTER_SKILLS = (
    "finance-analyze-stock",
    "finance-industry-track",
    "finance-forecast-event",
    *NEW_APP_SKILLS,
)
INVENTORY = REPO / "docs" / "superpowers" / "specs" / "2026-10-10-knevo-mechanism-inventory.md"
KNEVO_SKILLS = (
    "finance-mode", "finance-analyze-stock", "finance-earnings-review", "finance-industry-report",
    "finance-industry-track", "finance-forecast-event", "finance-kol-analyze", "finance-review-check",
    "finance-associate",
)


def _frontmatter(text: str) -> tuple[dict[str, str], str]:
    assert text.startswith("---\n")
    head, _, body = text[4:].partition("\n---\n")
    fields: dict[str, str] = {}
    for line in head.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields, body


def _skill(name: str) -> tuple[dict[str, str], str]:
    path = SKILLS / name / "SKILL.md"
    assert path.is_file(), f"missing runtime skill: {path}"
    return _frontmatter(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", NEW_APP_SKILLS)
def test_new_app_skill_frontmatter_contract(name: str) -> None:
    fields, body = _skill(name)
    assert fields["name"] == name
    assert len(fields["description"]) > 40
    assert fields["pattern"] == "prompt-only"
    assert fields["routable"] == "false"
    assert fields["layer"] == "app"
    assert fields["requires"] == "finance-mode"
    assert "44轮原文" in fields["absorbed_from"], "new 专项 must cite the load_skill transcript it was absorbed from"
    assert body.strip()


@pytest.mark.parametrize("name", NEW_APP_SKILLS)
def test_new_app_skill_carries_no_market_facts(name: str) -> None:
    _, body = _skill(name)
    assert not re.search(r"\b\d{6}\b", body), "looks like a stock code"
    assert not re.search(r"\d+(?:\.\d+)?\s*%", body), "looks like a market percentage or a copied threshold"
    assert not re.search(r"\d+(?:\.\d+)?\s*亿", body), "looks like a market amount"


@pytest.mark.parametrize("name", EIGHT_CHAPTER_SKILLS)
def test_app_skill_follows_knevo_eight_chapter_shape(name: str) -> None:
    """knevo 专项通式：使用边界 → 流程 → 框架 → 骨架 → 来源标注 → 契约 → 交付后，以 🎯 核心结论收尾。"""
    _, body = _skill(name)
    if name == "finance-review-check":
        # knevo 的审查专项以 Review Verdict 一行收口（报告在前、审查在后），原文骨架没有 🎯。
        assert "## Review Verdict" in body, name
    else:
        assert "🎯 核心结论" in body, name
    assert "输出契约" in body, name
    assert "交付前自检" in body, name
    assert "追问建议" in body, name


_ANCHORS = {
    "finance-review-check": ("修订版报告为主体", "Review Verdict", "FAIL 阻塞写回", "不改报告结构、立场和核心结论"),
    "finance-associate": ("暂无显著关联", "查图谱（先于其他", "[inference]", "联想是「发散」不是「结论」"),
    "finance-kol-analyze": ("不强行模拟", "禁止凭空捏造", "仅在有证据时陈述", "历史立场是先验"),
    "finance-analyze-stock": ("现价除以记忆里的每股收益", "同源、同截至日", "没有估值锚的推荐是空中楼阁", "业绩点评"),
    "finance-industry-track": ("只保留有信息量的变化", "观点更新", "下期关注", "跟踪信号清单"),
    "finance-forecast-event": ("决策者行为模拟", "禁止退化为", "怎样算发生", "无市场定价参考"),
}


@pytest.mark.parametrize("name", sorted(_ANCHORS))
def test_app_skill_keeps_knevo_anchor_sentences(name: str) -> None:
    _, body = _skill(name)
    for anchor in _ANCHORS[name]:
        assert anchor in body, f"{name} lost knevo anchor: {anchor}"


def test_inventory_registers_every_knevo_skill_and_the_four_corrections() -> None:
    text = INVENTORY.read_text(encoding="utf-8")
    for name in KNEVO_SKILLS:
        assert name in text, f"inventory does not mention {name}"
    # 四个防反向归因的前提必须留在清单里，否则下次又会把 8792 词表当 knevo 机制。
    for needle in ("task_stage", "list_skills", "finance_memory_write", "recommend_decision"):
        assert needle in text, needle
    assert "故意不抄" in text and "待炼化" in text
