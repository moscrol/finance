"""Read-only skill bridge for the agent tool layer (P2).

Where :func:`intelligence.services.theme_modules.run_module` wires the
theme-radar report generators as agent recall backends, this module exposes
additional **read-only, local-only** finance skills as agent-callable tools via
the *same* vetted-subprocess pattern (timeout + return-code check + graceful
degrade). Only skills registered in :data:`SKILL_REGISTRY` can run; each one is
a local-wiki reader that performs **no network IO and no writes**, so the
agent's read-only red line is preserved.

The vast majority of finance-workspace skills pull live data (fupanhui / iFinD /
AKShare) or write back (飞书 / DuckDB) — those deliberately stay out of the
registry; exposing them would break the agent's read-only / no-HTTP discipline.

Currently registered:
- ``serenity-alpha`` — 个股弹性 / 预期差 / 补涨候选池，纯读本地知识库 wiki
  (概念定位 + 候选公司分层 + 角色预分桶)，输出挂 [G#] 引用。
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SKILL_TIMEOUT = 120
DEFAULT_SKILL_LIMIT = 12


@dataclass
class SkillResult:
    """Result of one read-only skill subprocess (mirrors ``ModuleResult``)."""

    name: str
    ok: bool = False
    command: str = ""
    title: str = ""
    highlights: list[str] = field(default_factory=list)
    follow_ups: list[str] = field(default_factory=list)
    citation_source: str = ""
    citation_detail: str = ""
    warning: str = ""
    # full subprocess stdout, retained only for optional drill-down
    raw: str = ""


# parser: parsed-json -> (title, highlights, follow_ups)
SkillParser = Callable[[dict], "tuple[str, list[str], list[str]]"]


@dataclass
class SkillSpec:
    name: str
    description: str
    script: Path
    citation_source: str
    parser: SkillParser
    needs_vault: bool = True
    limit: int = DEFAULT_SKILL_LIMIT


# --------------------------------------------------------------------------- #
# shared helpers
# --------------------------------------------------------------------------- #
def _squeeze(text: object, limit: int) -> str:
    s = str(text or "").strip().replace("\n", " ")
    return s[:limit] + ("…" if len(s) > limit else "")


def _join(names: list, limit: int = 10, width: int = 0) -> str:
    items = [str(n).strip() for n in names if str(n).strip()]
    if width:
        items = [_squeeze(n, width) for n in items]
    return "、".join(items[:limit])


# --------------------------------------------------------------------------- #
# serenity-alpha — local wiki expectation-gap context pack
# --------------------------------------------------------------------------- #
_SERENITY_BUCKET_LABELS = {
    "anchor": "锚候选(core主线)",
    "bottleneck": "二阶瓶颈(设备/材料/化学品)",
    "old_label": "旧标签重估(定位与题材词不重合)",
    "diffusion": "扩散观察(逻辑相关、证据更弱)",
}


def _parse_serenity(data: dict) -> "tuple[str, list[str], list[str]]":
    term = str(data.get("term") or "").strip()
    concepts = data.get("concepts") or {}
    candidates = data.get("candidate_companies") or []
    highlights: list[str] = []

    primary = str(concepts.get("primary") or "").strip()
    matched = _join(concepts.get("matched") or [], 6)
    related = _join(concepts.get("related") or [], 6)
    if primary or matched or related:
        seg = f"概念定位：主匹配 {primary or '未入库'}"
        if matched:
            seg += f"；命中 {matched}"
        if related:
            seg += f"；相关 {related}"
        highlights.append(seg)

    for row in candidates:
        if not isinstance(row, dict):
            continue
        desc = row.get("wiki_one_liner") or row.get("role") or ""
        flags = [
            str(row.get("strength") or "—"),
            f"证据{int(row.get('evidence_count') or 0)}",
        ]
        if row.get("has_logic_card"):
            flags.append("逻辑卡✓")
        flags.append("直接" if row.get("direct") else "扩散")
        highlights.append(
            f"候选 {row.get('company', '')}（{row.get('ticker', '')}｜{'｜'.join(flags)}）："
            f"{_squeeze(desc, 60) or '待补'}"
        )

    buckets = data.get("role_buckets") or {}
    for key, label in _SERENITY_BUCKET_LABELS.items():
        names = _join(buckets.get(key) or [], 12)
        if names:
            highlights.append(f"{label}：{names}")

    fine = data.get("fine_position_buckets") or {}
    fine_segs = [f"{con}({_join(names, 6)})" for con, names in list(fine.items())[:3] if names]
    if fine_segs:
        highlights.append("细分卡位：" + "；".join(fine_segs))

    snapshots = [s for s in (data.get("synthesis_snapshots") or []) if isinstance(s, dict)]
    if snapshots:
        latest = snapshots[0]
        highlights.append(
            f"历史快照 {len(snapshots)} 篇，最新 {latest.get('date', '')}"
            f"《{_squeeze(latest.get('title', ''), 36)}》：{_squeeze(latest.get('summary', ''), 60)}"
        )

    benchmarks = [b for b in (data.get("benchmark_matches") or []) if isinstance(b, dict)]
    if benchmarks:
        segs = [
            f"{b.get('benchmark_company', '')}({b.get('benchmark_ticker', '')})→{_join(b.get('theme_routes') or [], 4)}"
            for b in benchmarks[:4]
        ]
        highlights.append("海外对标：" + "；".join(s for s in segs if s.strip("()→")))

    n = len([r for r in candidates if isinstance(r, dict)])
    title = f"{term or primary} 弹性/预期差候选（{n} 家）"

    follow_ups: list[str] = []
    top = [str(r.get("company", "")).strip() for r in candidates[:2] if isinstance(r, dict) and r.get("company")]
    if top:
        follow_ups.append(f"{top[0]} 的最新逻辑卡/证据硬不硬")
    follow_ups.append("横向比较候选池近 5/10/20 日涨幅，核对预期差与补涨顺序")
    return title, highlights, follow_ups


# --------------------------------------------------------------------------- #
# registry (safelist) — only read-only, local, network-free skills
# --------------------------------------------------------------------------- #
SKILL_REGISTRY: dict[str, SkillSpec] = {
    "serenity-alpha": SkillSpec(
        name="serenity-alpha",
        description=(
            "serenity-alpha：基于本地知识库 wiki 给某题材/概念的「个股弹性·预期差·补涨候选池」——"
            "概念定位 + 候选公司分层(强度/证据数/逻辑卡) + 角色预分桶(锚/二阶瓶颈/旧标签重估/扩散)。"
            "纯读本地 wiki、不联网、不写库；用于找「谁可能补涨/预期差大」。"
        ),
        script=REPO_ROOT / "skills" / "serenity-alpha" / "scripts" / "serenity_context.py",
        citation_source="serenity-alpha · serenity_context.py（本地 wiki·只读）",
        parser=_parse_serenity,
    ),
}

ALL_SKILLS: tuple[str, ...] = tuple(SKILL_REGISTRY)


def skill_descriptions() -> str:
    """Human/LLM-readable one-line list of the registered skills (for the tool desc)."""
    return "；".join(spec.description for spec in SKILL_REGISTRY.values())


def run_skill(
    name: str,
    query: str,
    kb_wiki: str | Path | None,
    timeout: int = DEFAULT_SKILL_TIMEOUT,
) -> SkillResult:
    """Run one safelisted read-only skill as a subprocess and parse its JSON output.

    Defensive throughout (same discipline as ``run_module``): unknown skill,
    missing script, missing vault, timeout, non-zero exit, or unparseable output
    each record a ``warning`` and return ``ok=False`` so the agent degrades
    gracefully instead of crashing.
    """
    spec = SKILL_REGISTRY.get(name)
    if spec is None:
        return SkillResult(name=name, warning=f"未知 skill: {name}（可选：{'、'.join(ALL_SKILLS)}）")
    res = SkillResult(name=name)
    if not spec.script.exists():
        res.warning = f"{name} 脚本不存在: {spec.script}"
        return res
    if spec.needs_vault and not kb_wiki:
        res.warning = f"{name} 需要知识库 wiki 路径 (--kb-wiki / KNOWLEDGE_WIKI)"
        return res
    vault = Path(kb_wiki).expanduser() if kb_wiki else None
    cmd = [sys.executable, str(spec.script), "--term", str(query), "--format", "json", "--limit", str(spec.limit)]
    if vault is not None:
        cmd += ["--vault", str(vault)]
    res.command = f"{spec.script.name} --term {query} --vault <kb-wiki> --format json"
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(REPO_ROOT))
    except subprocess.TimeoutExpired:
        res.warning = f"{name} 超时(>{timeout}s)，已跳过"
        return res
    except Exception as exc:  # pragma: no cover - defensive
        res.warning = f"{name} 调用失败: {exc}"
        return res
    if proc.returncode != 0:
        res.warning = f"{name} 退出码 {proc.returncode}: {(proc.stderr or '').strip()[:160]}"
        return res
    try:
        data = json.loads(proc.stdout)
    except Exception as exc:
        res.warning = f"{name} 输出解析失败: {exc}"
        return res
    if not isinstance(data, dict):
        res.warning = f"{name} 输出格式异常（期望 JSON 对象）"
        return res
    res.raw = proc.stdout
    title, highlights, follow_ups = spec.parser(data)
    if not highlights:
        res.warning = f"{name} 无产出（知识库未命中该词）"
        return res
    res.title = title
    res.highlights = highlights
    res.follow_ups = follow_ups
    res.citation_source = spec.citation_source
    res.citation_detail = f"--term {query}"
    res.ok = True
    return res
