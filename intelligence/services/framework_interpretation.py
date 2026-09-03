"""框架解读步（perspective-lab P1）：按 user_framework 画像解读当日复盘硬数据，判断自动落 checkpoint。

设计文档：``docs/superpowers/specs/2026-07-03-perspective-lab-design.md``（§2.5 用户主坐标系）。

核心取舍（与 P0 一致）：

- **确定性、不依赖 LLM**：解读段是画像信号词对当日 daily-review 硬事实摘要的确定性命中
  （复用 perspective_lab 的子串匹配），判断/理由/证伪条件全部可审计，不编造。
- **判断必落台账**：每条命中的判断自动登记 T+1 / T+3 checkpoint（``checkpoints.jsonl``），
  记录 ``framework_version``——profile 升级后胜率统计能区分新旧框架的判断，不会把框架升级
  误判成 AI 退步。同一 (claim, due) 幂等，不重复登记。
- **纠偏回灌**：报告头部注入最近 corrections（``corrections.jsonl``），沉默=默认认可，
  纠偏是框架边界的低成本迭代入口。
- **默认零动作**：profile 不存在时整步优雅跳过（exit 0 + 提示），不阻断复盘。
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date as date_cls, timedelta
from pathlib import Path
from typing import Any

from intelligence.services import checkpoints as checkpoints_svc
from intelligence.services import corrections as corrections_svc
from intelligence.userspace import UserSpace

FRAMEWORK_PERSPECTIVE_ID = "user_framework"
RECHECK_WINDOWS = (1, 3)  # T+1 / T+3（Q5.2：验证窗口必须短且固定）
CHECKPOINT_CATEGORY = "framework_interpretation"
CHECKPOINT_SOURCE = "framework_interpretation"
CORRECTIONS_WINDOW = 10

# daily-review md 里作为硬事实底座的节（确定性抽取，不做任何推断/改写）。
_FACT_SECTIONS = ("核心看板", "市场环境总评")


def framework_version(profile: dict[str, Any]) -> str:
    """profile 内容哈希版本号：``fw-<sha1[:10]>``。

    用内容哈希而非 updated_at——同一内容永远同一版本，手工编辑后自动换版本，
    胜率统计按版本分桶即可区分新旧框架。
    """
    payload = json.dumps(
        {
            k: profile.get(k)
            for k in (
                "market_lenses",
                "opportunity_preferences",
                "risk_triggers",
                "evidence_hierarchy",
                "reasoning_patterns",
                "anti_patterns",
                "falsification_style",
                "contradictions",
                "honest_boundaries",
            )
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return "fw-" + hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10]


def extract_facts_digest(daily_review_md: str) -> str:
    """从 daily-review md 确定性抽取硬事实摘要（核心看板 + 市场环境总评两节原文）。"""
    lines = daily_review_md.splitlines()
    out: list[str] = []
    keep = False
    for line in lines:
        m = re.match(r"^##\s+(?:\d+\.\s*)?(.+?)\s*$", line)
        if m:
            keep = any(sec in m.group(1) for sec in _FACT_SECTIONS)
        if keep and line.strip():
            out.append(line)
    return "\n".join(out).strip()


# 台账 JSON facts 里进硬事实底座的键：都是画像信号词常引用的口径
# （价日/量日/双量日切换口径、MA5 波峰波谷、多周期共振、连板高度）。
_FACT_KEYS: tuple[tuple[str, str], ...] = (
    ("nature", "市场性质"),
    ("market_stage", "市场阶段"),
    ("price_day", "价日"),
    ("volume_day", "量日"),
    ("double_volume_day", "双量日"),
    ("ma5_position", "涨家数MA5位置"),
    ("ma5_trend", "涨家数MA5趋势"),
    ("concentration_state", "成交集中度"),
    ("strength_status", "强度状态"),
    ("strength_status_prev", "昨日强度状态"),
    ("multi_period_themes", "多周期共振题材"),
    ("full_period_themes", "全周期共振题材"),
    ("limit_advance_count", "3板及以上个股数"),
    ("max_boards", "最高连板"),
)


def _fact_text(value: Any) -> str:
    if isinstance(value, bool):
        return "是" if value else "否"
    if value is None:
        return "-"
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, list) and len(item) == 2:
                parts.append(f"{item[0]}({item[1]}次)")
            else:
                parts.append(str(item))
        return "、".join(parts) or "无"
    return str(value)


def extract_facts_digest_from_json(report: dict[str, Any]) -> str:
    """从台账 JSON 真本源抽硬事实：核心看板 + 每节结论 + 关键口径字段。

    仍是逐字摘录（结论句就是台账里的那句），不做推断；比只读 md 两节多出
    MA5 波段、共振题材、连板等信号词真正会落在的地方——此前解读步长期
    「无信号命中」，不是没有信号，是没把这些数据递过去。
    """
    out: list[str] = ["## 核心看板"]
    for row in report.get("core_board") or []:
        if isinstance(row, dict):
            out.append(f"| {row.get('dimension')} | {row.get('conclusion')} |")
    facts = report.get("facts") or {}
    if isinstance(facts, dict):
        out.append("## 关键口径")
        for key, label in _FACT_KEYS:
            if key in facts:
                out.append(f"- {label}：{_fact_text(facts.get(key))}")
    out.append("## 分节结论")
    for section in report.get("sections") or []:
        if not isinstance(section, dict):
            continue
        title = str(section.get("title") or "")
        for block in section.get("blocks") or []:
            if not isinstance(block, dict):
                continue
            kind = block.get("kind")
            text = str(block.get("text") or "").strip()
            if not text:
                continue
            if kind == "conclusion":
                out.append(f"- {title}：{text}")
            elif kind == "note" and text.startswith("**MA5位置**"):
                out.append(f"- {title}：{text}")
    assessment = str(report.get("assessment") or "").strip()
    if assessment:
        out += ["## 市场环境总评", f"> {assessment}"]
    return "\n".join(out).strip()


def load_facts_digest(daily_review_md_path: Path) -> str:
    """优先读同名 JSON 真本源，没有（老日期）再退回 md 两节。"""
    json_path = daily_review_md_path.with_suffix(".json")
    if json_path.is_file():
        try:
            report = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            report = None
        if isinstance(report, dict) and report.get("core_board"):
            return extract_facts_digest_from_json(report)
    if not daily_review_md_path.is_file():
        return ""
    return extract_facts_digest(daily_review_md_path.read_text(encoding="utf-8"))


_MIN_FRAGMENT_LEN = 4


def _fragments(term: str) -> list[str]:
    """把画像信号句拆成可匹配片段（标点/连接词切分，长度 ≥ 4）——长句整句几乎不会
    原文出现在盘面数据里，片段级匹配才有召回；命中片段会写进报告供审计。"""
    parts = re.split(r"[，。；：、（）,;:()=→×+/「」“”\s]+", term)
    return [p for p in parts if len(p) >= _MIN_FRAGMENT_LEN]


def _hit(term: str, facts: str) -> str | None:
    """返回命中依据片段（未命中返回 None）：整句命中优先，否则取首个命中的片段。"""
    norm_facts = re.sub(r"\s+", "", facts)
    if term and re.sub(r"\s+", "", term) in norm_facts:
        return term
    for frag in _fragments(term):
        if frag in norm_facts:
            return frag
    return None


def _matched_signals(
    profile: dict[str, Any], facts: str
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """返回 (信号句, 命中片段) 列表：(机会命中, 风险命中)。"""
    opp: list[tuple[str, str]] = []
    risk: list[tuple[str, str]] = []
    for t in profile.get("opportunity_preferences") or []:
        frag = _hit(t, facts)
        if frag:
            opp.append((t, frag))
    for t in profile.get("risk_triggers") or []:
        frag = _hit(t, facts)
        if frag:
            risk.append((t, frag))
    return opp, risk


def _due(date: str, days: int) -> str:
    return (date_cls.fromisoformat(date) + timedelta(days=days)).isoformat()


def _existing_claim_dues(cpath: Path) -> set[tuple[str, str]]:
    records, _ = checkpoints_svc.load_checkpoints(cpath)
    return {(str(r.get("claim") or ""), str(r.get("due") or "")) for r in records}


def register_judgments(
    us: UserSpace,
    *,
    date: str,
    judgments: list[dict[str, Any]],
    version: str,
) -> list[dict[str, Any]]:
    """把判断登记为 T+1/T+3 checkpoint（幂等：同 claim+due 跳过）。返回新登记记录。"""
    cpath = us.checkpoints_path
    seen = _existing_claim_dues(cpath)
    added: list[dict[str, Any]] = []
    for j in judgments:
        claim = str(j.get("claim") or "").strip()
        if not claim:
            continue
        for days in RECHECK_WINDOWS:
            due = _due(date, days)
            if (claim, due) in seen:
                continue
            _, record = checkpoints_svc.register_checkpoint(
                cpath,
                claim=claim,
                due=due,
                category=CHECKPOINT_CATEGORY,
                source=CHECKPOINT_SOURCE,
                themes=j.get("themes") or [],
                framework_version=version,
            )
            seen.add((claim, due))
            added.append(record)
    return added


def build_report(
    us: UserSpace,
    *,
    date: str,
    profile: dict[str, Any],
    facts: str,
) -> tuple[str, list[dict[str, Any]]]:
    """生成「框架解读」markdown 节 + 待登记判断列表（判断=命中信号+理由+证伪条件）。"""
    version = framework_version(profile)
    opp_hits, risk_hits = _matched_signals(profile, facts)
    falsifiers = list(profile.get("falsification_style") or [])

    judgments: list[dict[str, Any]] = []
    for t, frag in opp_hits:
        judgments.append({"claim": f"[{date}][机会信号成立] {t}", "themes": [], "matched_by": frag})
    for t, frag in risk_hits:
        judgments.append({"claim": f"[{date}][风险信号成立] {t}", "themes": [], "matched_by": frag})

    lines = [
        f"# 框架解读 · {date}（user_framework {version}）",
        "",
        "> 本节为画像规则对当日硬数据的确定性命中（解释层，不是事实）；判断已自动落",
        f"> checkpoint（T+1/T+3 回检），framework_version={version}。纠偏方式：对话里直接说「不对，应为…」。",
        "",
    ]
    recs, _ = corrections_svc.load_corrections(us.corrections_path, CORRECTIONS_WINDOW)
    rendered = corrections_svc.render_for_prompt(recs) if recs else ""
    lines += ["## 最近纠偏回灌（先读，别再犯）", rendered or "- 暂无纠偏记录（沉默=默认认可）", ""]
    lines += ["## 硬事实底座（daily-review 摘录，未经改写）"]
    lines += [f"> {ln}" for ln in facts.splitlines() if ln.strip()] or ["> （未取得硬事实摘要）"]
    lines += ["", "## 框架镜头"]
    for ln in profile.get("market_lenses") or []:
        lines.append(f"- {ln.get('name')}（权重 {ln.get('weight')}）：{ln.get('description')}")
    lines += ["", "## 命中判断（每条已落 T+1/T+3 checkpoint）"]
    if judgments:
        for j in judgments:
            lines.append(f"- {j['claim']}\n  - 命中依据：硬事实中出现「{j['matched_by']}」")
    else:
        lines.append("- 无信号命中：当日硬事实未触发画像里的机会/风险信号词（属正常，宁缺毋滥）")
    lines += ["", "## 证伪条件（框架级）"]
    lines += [f"- {v}" for v in falsifiers] or ["- （画像未填写）"]
    return "\n".join(lines) + "\n", judgments


def run(
    us: UserSpace,
    *,
    date: str,
    daily_review_md_path: str | Path,
    out_md: str | Path | None = None,
) -> dict[str, Any]:
    """框架解读全流程：读硬事实 → 解读 → 落 checkpoint → 写报告。profile 缺失时优雅跳过。"""
    from intelligence.services import perspective_lab

    try:
        profile = perspective_lab.load_profile(us, FRAMEWORK_PERSPECTIVE_ID)
    except FileNotFoundError:
        return {"status": "skipped", "reason": "user_framework profile 不存在（perspective init 后手工编辑或用问卷 candidate 编译）"}

    md_path = Path(daily_review_md_path).expanduser()
    if not md_path.exists() and not md_path.with_suffix(".json").exists():
        return {"status": "skipped", "reason": f"daily-review md 不存在：{md_path}"}
    facts = load_facts_digest(md_path)
    if not facts:
        return {"status": "skipped", "reason": "daily-review md 中未抽到硬事实摘要节"}

    report, judgments = build_report(us, date=date, profile=profile, facts=facts)
    version = framework_version(profile)
    added = register_judgments(us, date=date, judgments=judgments, version=version)
    result: dict[str, Any] = {
        "status": "ok",
        "framework_version": version,
        "judgments": len(judgments),
        "checkpoints_added": len(added),
        "checkpoints_path": str(us.checkpoints_path),
    }
    if out_md:
        out_path = Path(out_md).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        result["out_md"] = str(out_path)
    result["report"] = report
    return result
