"""Contract tests for the knevo-absorbed runtime skill layer (finance-mode + 专项).

这些 skill 是给运行时模型看的方法论层（knevo「1 入口 + 专项」的载体），不是编码 agent 的工作流。
测试钉三件事：frontmatter 合同、不夹带市场事实、knevo 机制的锚句仍在。改词表即红。
"""
from __future__ import annotations

from pathlib import Path
import re

import pytest

REPO = Path(__file__).resolve().parents[2]
SKILLS = REPO / "skills"
OS_SKILL = "finance-mode"
APP_SKILLS = (
    "finance-market-review",
    "finance-analyze-stock",
    "finance-industry-track",
    "finance-forecast-event",
)
RUNTIME_SKILLS = (OS_SKILL, *APP_SKILLS)


def _frontmatter(text: str) -> tuple[dict[str, str], str]:
    assert text.startswith("---\n"), "SKILL.md must start with frontmatter"
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


@pytest.mark.parametrize("name", RUNTIME_SKILLS)
def test_runtime_skill_frontmatter_contract(name: str) -> None:
    fields, body = _skill(name)
    assert fields["name"] == name, "name must equal the directory name (registry rule)"
    assert len(fields["description"]) > 40, "description is the routing text; must say what and when"
    assert fields["pattern"] == "prompt-only"
    assert fields["routable"] == "false"
    assert body.strip(), "empty skill body"


def test_os_skill_declares_os_layer_and_apps_require_it() -> None:
    fields, _ = _skill(OS_SKILL)
    assert fields["layer"] == "os"
    for name in APP_SKILLS:
        app_fields, _ = _skill(name)
        assert app_fields["layer"] == "app"
        assert app_fields["requires"] == OS_SKILL


@pytest.mark.parametrize("name", RUNTIME_SKILLS)
def test_runtime_skill_carries_no_market_facts(name: str) -> None:
    """运行时 skill 只能有章法，不得夹带市场事实、数字或板块名（与 finance-degraded-fallback 同一红线）。"""
    _, body = _skill(name)
    assert not re.search(r"\b\d{6}\b", body), "looks like a stock code"
    assert not re.search(r"\d+(?:\.\d+)?\s*%", body), "looks like a market percentage"
    assert not re.search(r"\d+(?:\.\d+)?\s*亿", body), "looks like a market amount"


# knevo 机制锚句：每句对应 knevo-reverse-engineering.md 的一条自述/实测规则。
_OS_ANCHORS = (
    "应用只能加、不能改、不能删",            # §1.1.2 OS 与应用不平级
    "专项只能选「什么时候查」，不能改「用什么查」",
    "价格永远现查",                           # §1.1.4 硬触发原则
    "空结果也是信息",
    "最多改写两次、合计三次",                 # 重试 1+2=3
    "矛盾是深度的触发器，印证是快答的许可",   # §1.1.3 升档四维之矛盾度
    "并行不超过四个，串行不超过两跳",         # 复合编排硬约束
    "信息流依赖",                             # 派单判据
    "模型自己过去写的综合判断不得原样当当前事实",  # §3.3 防自证循环
    "缺 X → 仍可判 Y → 验证窗口 Z",           # §3C 诚实缺口模板
    "假设 × 可验证时点 × 推翻条件",           # §3C 统一范式
    "待检验假设",                             # 反顺从
    "跟踪信号清单",                           # report→track 接口
    "交付前自检",                             # 清单由模型执行，不是程序门
)


@pytest.mark.parametrize("anchor", _OS_ANCHORS)
def test_finance_mode_keeps_knevo_anchor(anchor: str) -> None:
    _, body = _skill(OS_SKILL)
    assert anchor in body, f"finance-mode lost knevo anchor: {anchor}"


def test_market_review_keeps_pi_comparison_error_shapes() -> None:
    """复盘专项的防遗漏清单来自 2026-10-09 对照里 Pi 的五类错句；少一类就是把已知错误放回去。"""
    _, body = _skill("finance-market-review")
    for anchor in ("全集边界", "量价不是资金", "指数贡献需要贡献数据", "广度与中位数一致", "一股多题材"):
        assert anchor in body, f"market-review lost error shape: {anchor}"


def test_each_app_skill_has_delivery_self_check_and_output_skeleton() -> None:
    for name in APP_SKILLS:
        _, body = _skill(name)
        assert "交付前自检" in body, name
        assert "追问建议" in body, name


def test_pi_extension_declares_the_knevo_surface() -> None:
    """扩展是 Pi 侧的接线层：工具桥、派单、OS 注入、只读守门、可选二看。文本合同，改名即红。"""
    source = (REPO / "integrations" / "pi" / "finance-mode.ts").read_text(encoding="utf-8")
    for needle in (
        'registerTool({ name: "finance_call"',
        'registerTool({ name: "spawn_sub_agent"',
        'pi.on("before_agent_start"',
        'pi.on("tool_call"',
        'pi.on("agent_before_settle"',
        "FINANCE_PI_SUBAGENT_DEPTH",
    ):
        assert needle in source, needle
