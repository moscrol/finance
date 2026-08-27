#!/usr/bin/env python3
"""Opinion-cross: 把一段卖方观点/产业消息流提纯成"三重共振"机会卡片。

输入是**已经筛过的**观点流（卖方研报口播、产业小作文、机构观点合集），不是全市场公告。
管道：观点流文本
  → [C1 观点事件抽取]  逐标的拆出 观点/预期差/催化
  → [C2 事实硬度分层]  硬证据 / 卖方喊单(软推演) / 情绪噪音 三档
  → [C3 多空分歧识别]  看多 vs 看空 + 预期差拐点
  → [C4 三维交叉引擎]  复用 theme-radar 的 signal_dimension_rows / resonance_tier 逐标的排 Tier
  → [C5 Tier 卡片报告] 按 Tier1/2/3 分组 + 操作建议

设计原则（与 build_context.py 一致）：
- **题材无关**：标的/产业映射全部取自知识库 relations（concept_graph + entity_exposures），不写死。
- **规则层不臆造**：硬度/多空/Tier 都来自原文证据；缺证据就标"待补/仅题材弹性"，由 agent 复核时定夺。
- 输出是可复核草稿（JSON + Markdown），不是最终结论。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 复用 theme-radar 的三维交叉引擎（已在 main 上，import-safe）。
# ---------------------------------------------------------------------------
_RADAR_SCRIPTS = Path(__file__).resolve().parent.parent.parent / "theme-radar" / "scripts"
if str(_RADAR_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_RADAR_SCRIPTS))

try:  # pragma: no cover - exercised at runtime, guarded for static checks
    from radar import resonance_tier, signal_dimension_rows  # type: ignore
except Exception:  # noqa: BLE001 - fall back to a local re-implementation
    resonance_tier = None  # type: ignore
    signal_dimension_rows = None  # type: ignore


def _default_vault() -> Path:
    for var in ("KB_VAULT", "KNOWLEDGE_WIKI", "CONCEPT_VAULT", "ENTITY_VAULT"):
        val = os.environ.get(var)
        if val:
            return Path(os.path.expanduser(val))
    return Path.home() / "knowledge-base-private" / "wiki"


DEFAULT_VAULT = _default_vault()

# 事实硬度词典（与 build_context.py 对齐，便于跨脚本一致）。
HARD_FACT_KEYS = [
    "订单", "中标", "合同", "入股", "持股", "公告", "确收", "供货", "签署",
    "收购", "增资", "量产", "扩产", "投产", "送样", "定点", "验证通过", "交付",
]
SOFT_KEYS = [
    "目标", "预期", "预计", "看好", "空间", "市值", "有望", "弹性", "或将",
    "假设", "首选", "首推", "推荐", "翻倍", "看多", "看到", "对标", "中枢",
]
NOISE_KEYS = [
    "拒绝一惊一乍", "悲观者", "乐观者", "一笑了之", "泼冷水", "历史总是惊人",
    "静态的", "纠结", "情绪", "便一笑", "前行", "印象深刻",
]

# 多空立场词典。
BULL_KEYS = ["看好", "坚定看好", "首推", "首选", "推荐", "上修", "超预期", "放量", "刚需", "确定性", "兑现"]
BEAR_KEYS = ["看空", "不及预期", "砍单", "泼冷水", "良率低", "良率只有", "延期", "拖到", "谨慎", "高估", "证伪", "证伪"]
EXPECTATION_KEYS = ["预期差", "超预期", "不及预期", "符合预期", "price in", "预期", "辟谣", "证实", "证伪"]

# 催化触发词（与 calendar/验证有关的硬动作）。
CATALYST_KEYS = HARD_FACT_KEYS + ["辟谣", "调研", "释放", "落地", "导入", "客户认证", "认证", "扩产至"]

STRENGTH_ORDER = {"core": 0, "related": 1, "peripheral": 2}

CHAIN_LABELS = {
    "upstream_materials": "上游材料",
    "upstream_equipment": "上游设备",
    "upstream_components": "上游零部件/光芯片",
    "midstream": "中游制造",
    "midstream_manufacturing": "中游制造",
    "midstream_components": "中游器件",
    "downstream": "下游应用",
    "downstream_infrastructure": "下游基础设施",
}


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------
def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default


def unique(items):
    out, seen = [], set()
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def contains_any(text: str, words) -> bool:
    lowered = text.lower()
    return any(w.lower() in lowered for w in words)


def found_keys(text: str, words) -> list[str]:
    lowered = text.lower()
    return [w for w in words if w.lower() in lowered]


def split_sentences(text: str) -> list[str]:
    """切句：先按行，再按中英文句末标点。保留较完整的短句。"""
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        for part in re.split(r"(?<=[。！；;!？?])|\n", line):
            part = part.strip(" 　\t#1234567890⃣.、")
            if len(part) >= 4:
                out.append(part)
    return out


def compact(text: str, limit: int = 90) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


# ---------------------------------------------------------------------------
# 知识库 relations 加载（题材无关骨架来源）
# ---------------------------------------------------------------------------
def load_relations(vault: Path) -> tuple[dict, dict]:
    relations = vault / "relations"
    concept_graph = load_json(relations / "concept_graph.json", {})
    entity_exposures = load_json(relations / "entity_exposures.json", {})
    concepts = concept_graph.get("concepts", {}) if isinstance(concept_graph, dict) else {}
    entities = entity_exposures.get("entities", {}) if isinstance(entity_exposures, dict) else {}
    return concepts, entities


def match_concept(term: str, concepts: dict) -> str:
    if not concepts or not term:
        return term
    if term in concepts:
        return term
    lowered = term.lower()
    for key in concepts:
        if key.lower() == lowered:
            return key
    candidates = [k for k in concepts if lowered in k.lower() or k.lower() in lowered]
    if candidates:
        return min(candidates, key=len)
    return term


# ---------------------------------------------------------------------------
# C1 观点事件抽取：逐标的拆出观点/预期差/催化
# ---------------------------------------------------------------------------
def detect_entities(text: str, entities: dict, limit: int = 30) -> list[str]:
    """从文本里识别出现过的 KB 实体（最长优先，去重叠）。"""
    names = [n for n in entities if n != "ALL" and isinstance(n, str) and len(n) >= 2]
    names.sort(key=len, reverse=True)
    hits, consumed = [], []
    for name in names:
        if name in text and not any(name in h for h in consumed):
            hits.append(name)
            consumed.append(name)
        if len(hits) >= limit:
            break
    # 还原成在文中首次出现的顺序，便于阅读
    hits.sort(key=lambda n: text.find(n))
    return hits


def entity_sentences(name: str, sentences: list[str]) -> list[str]:
    return [s for s in sentences if name in s]


def source_attributions(text: str) -> list[str]:
    """抓【】里的机构/账号来源，用于多空归属。"""
    return unique(re.findall(r"[【\[]([^】\]]{2,20})[】\]]", text))


# ---------------------------------------------------------------------------
# C2 事实硬度分层
# ---------------------------------------------------------------------------
def hardness_profile(snippets: list[str]) -> dict:
    hard, soft, noise = [], [], []
    for s in snippets:
        if contains_any(s, NOISE_KEYS) and not contains_any(s, HARD_FACT_KEYS):
            noise.append(s)
        elif contains_any(s, HARD_FACT_KEYS):
            hard.append(s)
        elif contains_any(s, SOFT_KEYS):
            soft.append(s)
    if hard:
        dominant = "硬证据"
    elif soft:
        dominant = "软推演"
    elif noise:
        dominant = "情绪噪音"
    else:
        dominant = "中性陈述"
    return {
        "dominant": dominant,
        "hard": unique([compact(s) for s in hard])[:4],
        "soft": unique([compact(s) for s in soft])[:4],
        "noise": unique([compact(s) for s in noise])[:3],
    }


# ---------------------------------------------------------------------------
# C3 多空分歧识别
# ---------------------------------------------------------------------------
def classify_stance(snippets: list[str]) -> dict:
    bull = unique([compact(s) for s in snippets if contains_any(s, BULL_KEYS)])[:4]
    bear = unique([compact(s) for s in snippets if contains_any(s, BEAR_KEYS)])[:4]
    if bull and bear:
        stance = "多空分歧"
    elif bull:
        stance = "看多"
    elif bear:
        stance = "看空"
    else:
        stance = "中性"
    gap = unique([compact(s) for s in snippets if contains_any(s, EXPECTATION_KEYS)])[:4]
    return {"stance": stance, "bull": bull, "bear": bear, "expectation_gap": gap}


def theme_divergence(sentences: list[str], sources: list[str]) -> dict:
    bull = unique([compact(s) for s in sentences if contains_any(s, BULL_KEYS)])
    bear = unique([compact(s) for s in sentences if contains_any(s, BEAR_KEYS)])
    pivots = unique(
        [compact(s) for s in sentences if contains_any(s, ["符合预期", "辟谣", "超预期", "预期差", "price in"])]
    )
    if bull and bear:
        verdict = "存在多空分歧：看多与看空证据并存，重点抓预期差拐点而非单边复述。"
    elif bull:
        verdict = "整体偏多：未见明显看空证据。"
    elif bear:
        verdict = "整体偏空：未见明显看多证据。"
    else:
        verdict = "中性：未检出明确多空措辞。"
    return {
        "verdict": verdict,
        "bull_count": len(bull),
        "bear_count": len(bear),
        "bull_samples": bull[:4],
        "bear_samples": bear[:4],
        "expectation_pivots": pivots[:5],
        "sources": sources[:12],
    }


# ---------------------------------------------------------------------------
# 知识库映射：标的 → 命中的产业方向（产业维度）
# ---------------------------------------------------------------------------
def concept_for_entity(name: str, theme_key: str, entities: dict) -> dict:
    """返回标的在 KB 中与本题材最相关的一条 exposure（用于产业维度交叉）。"""
    info = entities.get(name, {})
    cmap = info.get("concepts", {}) if isinstance(info, dict) else {}
    if not isinstance(cmap, dict) or not cmap:
        return {}
    # 优先题材本身或包含题材关键字的 concept
    preferred = [c for c in cmap if theme_key and (theme_key in c or c in theme_key)]
    pool = preferred or list(cmap.keys())

    def rank(c):
        rel = cmap.get(c, {}) or {}
        return (STRENGTH_ORDER.get(rel.get("strength"), 3), 0 if rel.get("fact_hardness") == "hard_fact" else 1)

    best = min(pool, key=rank)
    rel = cmap.get(best, {}) or {}
    layer = rel.get("chain_layer") or ""
    return {
        "concept": best,
        "strength": rel.get("strength") or "",
        "role": rel.get("role") or "",
        "chain_layer": CHAIN_LABELS.get(layer, layer),
        "kb_fact_hardness": rel.get("fact_hardness") or "",
        "evidence_layer": rel.get("evidence_layer") or "",
    }


# ---------------------------------------------------------------------------
# C4 三维交叉引擎（复用 radar）
# ---------------------------------------------------------------------------
def _local_tier(source_count: int, quality_count: int = 0) -> str:
    if source_count >= 3 and quality_count >= 2:
        return "Tier 1"
    if source_count >= 2:
        return "Tier 2"
    if source_count >= 1:
        return "Tier 3"
    return "待补"


def _local_dimension_rows(context: dict, signal: dict, _companies) -> list[dict]:
    """与 radar.signal_dimension_rows 同契约的本地回退（仅在 import 失败时使用）。"""
    fact = signal.get("order_signals") or []
    industry = (context.get("demand_drivers") or []) + [
        r.get("name", "") for r in context.get("direction_scan", []) if isinstance(r, dict)
    ]
    market = signal.get("market_heat") or []
    return [
        {"dimension": "公告/事实", "signal": (fact or ["待补"])[0], "source": "opinion_hard",
         "tier": _local_tier(2 if fact else 0, 1 if fact else 0)},
        {"dimension": "产业趋势", "signal": (industry or ["待补"])[0], "source": "concept_graph",
         "tier": _local_tier(int(bool(industry)))},
        {"dimension": "市场热点", "signal": (market or ["待补"])[0], "source": "opinion_market",
         "tier": _local_tier(int(bool(market)))},
    ]


def _local_resonance(rows: list[dict]) -> str:
    active = [r for r in rows if r.get("signal") and r.get("signal") != "待补"]
    hard = [r for r in active if r.get("tier") in ("Tier 1", "Tier 2")]
    if len(hard) >= 3:
        return "Tier 1：公告/事实 + 产业趋势 + 市场热点三重共振"
    if len(active) >= 2:
        return "Tier 2：双重验证，已具备跟踪价值但仍需补强缺口"
    if len(active) == 1:
        return "Tier 3：单点逻辑，进入观察池"
    return "待补：缺触发信号，暂按静态产业链处理"


def cross_score(opportunity: dict, theme_key: str, market_signals: list[str]) -> dict:
    """为单个标的机会构造 signal/context 并调用三维交叉引擎。"""
    hp = opportunity["hardness"]
    kb = opportunity.get("kb", {})
    industry_signal = []
    if kb.get("concept"):
        layer = f"（{kb['chain_layer']}）" if kb.get("chain_layer") else ""
        industry_signal.append(f"{kb['concept']}{layer} · {kb.get('role') or kb.get('strength')}")
    # 注意：radar.signal_dimension_rows 会把 signal["industry_progress"] 同时算进
    # "公告/事实" 和 "产业趋势" 两个维度。为避免产业信号污染事实维度（导致软推演
    # 标的也被抬成 Tier 2），这里事实维度只放硬证据/催化，产业信号只走 context。
    signal = {
        "order_signals": hp["hard"],
        "market_heat": market_signals,
    }
    context = {
        "demand_drivers": industry_signal,
        "direction_scan": [{"name": kb.get("concept", theme_key)}] if kb else [],
        "catalysts": opportunity.get("catalysts", []),
    }
    rows_fn = signal_dimension_rows or _local_dimension_rows
    tier_fn = resonance_tier or _local_resonance
    rows = rows_fn(context, signal, [])
    tier = tier_fn(rows)
    return {"dimension_rows": rows, "resonance_tier": tier}


# ---------------------------------------------------------------------------
# 操作建议（输出端）
# ---------------------------------------------------------------------------
def action_suggestion(tier: str, hardness: dict, stance: dict) -> str:
    t = tier.split("：")[0].strip()
    dominant = hardness["dominant"]
    if t == "Tier 1":
        base = "三重共振，可重点跟踪；遇盘面回调可低吸，硬证据兑现即加配。"
    elif t == "Tier 2":
        base = "双重验证，已有跟踪价值；等第三维（多为盘面或硬公告）补齐再下重手。"
    elif t == "Tier 3":
        base = "单点线索，先入观察池，等扩散到产业/盘面再升级。"
    else:
        base = "暂缺触发信号，按静态产业链处理。"
    if dominant == "情绪噪音":
        base += " 注意：当前主要是情绪话术，剔除后再评估。"
    elif dominant == "软推演" and t in ("Tier 2", "Tier 3"):
        base += " 当前以卖方目标价/预期为主，仅给题材弹性，需等硬催化。"
    if stance["stance"] == "多空分歧":
        base += " 多空分歧中，重点验证预期差拐点是否成立。"
    return base


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
TIER_ORDER = {"Tier 1": 0, "Tier 2": 1, "Tier 3": 2, "待补": 3}


def build(term: str, text: str, vault: Path) -> dict:
    concepts, entities = load_relations(vault)
    theme_key = match_concept(term, concepts) if term else term
    concept_matched = theme_key in concepts
    sentences = split_sentences(text)
    sources = source_attributions(text)

    detected = detect_entities(text, entities)
    opportunities = []
    for name in detected:
        snippets = entity_sentences(name, sentences)
        if not snippets:
            continue
        hardness = hardness_profile(snippets)
        stance = classify_stance(snippets)
        catalysts = unique([compact(s) for s in snippets if contains_any(s, CATALYST_KEYS)])[:4]
        kb = concept_for_entity(name, theme_key, entities)
        market_signals = [
            compact(s) for s in snippets if contains_any(s, ["涨停", "大跌", "异动", "涨", "跌", "交易", "price in", "估值切换"])
        ][:2]
        opp = {
            "target": name,
            "hardness": hardness,
            "stance": stance,
            "catalysts": catalysts,
            "kb": kb,
            "market_signals": market_signals,
            "mention_count": len(snippets),
        }
        scored = cross_score(opp, theme_key, market_signals)
        opp.update(scored)
        opp["action"] = action_suggestion(opp["resonance_tier"], hardness, stance)
        opportunities.append(opp)

    # 排序：Tier 优先，其次硬证据多者，其次提及多者
    def opp_key(o):
        t = o["resonance_tier"].split("：")[0].strip()
        return (TIER_ORDER.get(t, 3), -len(o["hardness"]["hard"]), -o["mention_count"])

    opportunities.sort(key=opp_key)

    divergence = theme_divergence(sentences, sources)
    tier_counts: dict[str, int] = {}
    for o in opportunities:
        t = o["resonance_tier"].split("：")[0].strip()
        tier_counts[t] = tier_counts.get(t, 0) + 1

    return {
        "term": term,
        "theme": theme_key,
        "concept_matched": concept_matched,
        "generated_at": _dt.date.today().isoformat(),
        "source_count": len(sources),
        "sources": sources,
        "divergence": divergence,
        "opportunities": opportunities,
        "summary": {
            "target_count": len(opportunities),
            "tier_counts": tier_counts,
            "hard_evidence_targets": sum(1 for o in opportunities if o["hardness"]["hard"]),
        },
        "extraction_note": (
            "观点提纯草稿（题材无关，标的/产业映射取自知识库 entity_exposures/concept_graph，"
            "硬度/多空/催化取自原文）。三维交叉复用 theme-radar 引擎。"
            "Tier 与操作建议是规则草稿，需 agent 复核盘面维度与硬度后定稿。"
        ),
    }


# ---------------------------------------------------------------------------
# 渲染 Markdown Tier 卡片
# ---------------------------------------------------------------------------
def _stars(tier_label: str) -> str:
    t = tier_label.split("：")[0].strip()
    return {"Tier 1": "⭐⭐⭐", "Tier 2": "⭐⭐", "Tier 3": "⭐"}.get(t, "—")


def render_markdown(data: dict) -> str:
    L = []
    L.append(f"# 观点三重共振扫描 · {data.get('term') or data.get('theme') or '未命名题材'}")
    L.append("")
    L.append(f"- 生成日期：{data['generated_at']}")
    L.append(f"- 题材命中知识库：{'是' if data['concept_matched'] else '否（降级为纯文本抽取）'}")
    s = data["summary"]
    tc = "、".join(f"{k}×{v}" for k, v in sorted(s["tier_counts"].items())) or "无"
    L.append(f"- 标的数：{s['target_count']}（{tc}）；含硬证据标的：{s['hard_evidence_targets']}")
    L.append("")

    d = data["divergence"]
    L.append("## 多空分歧")
    L.append("")
    L.append(f"> {d['verdict']}")
    L.append("")
    L.append(f"- 看多线索 {d['bull_count']} 条 / 看空线索 {d['bear_count']} 条")
    if d["expectation_pivots"]:
        L.append("- 预期差拐点：")
        for p in d["expectation_pivots"]:
            L.append(f"  - {p}")
    if d["sources"]:
        L.append(f"- 观点来源：{ '、'.join(d['sources']) }")
    L.append("")

    L.append("## 机会卡片（按 Tier 排序）")
    L.append("")
    if not data["opportunities"]:
        L.append("（未识别到知识库内标的，可能题材未入库或观点流无具体公司。）")
        return "\n".join(L)

    for o in data["opportunities"]:
        tier = o["resonance_tier"]
        kb = o.get("kb", {})
        L.append(f"### {_stars(tier)} {o['target']} — {tier}")
        L.append("")
        if kb.get("concept"):
            L.append(
                f"- 产业定位：[[{kb['concept']}]]"
                + (f" · {kb['chain_layer']}" if kb.get("chain_layer") else "")
                + (f" · {kb.get('role')}" if kb.get("role") else "")
                + (f" · KB硬度={kb.get('kb_fact_hardness')}" if kb.get("kb_fact_hardness") else "")
            )
        L.append(f"- 观点立场：{o['stance']['stance']}（提及 {o['mention_count']} 次）")
        # 三维交叉表
        L.append("")
        L.append("| 维度 | 信号 | Tier |")
        L.append("|---|---|---|")
        for row in o["dimension_rows"]:
            L.append(f"| {row.get('dimension','')} | {compact(row.get('signal',''),120)} | {row.get('tier','')} |")
        L.append("")
        # 事实硬度分层
        hp = o["hardness"]
        L.append(f"- 事实硬度（主导：{hp['dominant']}）")
        if hp["hard"]:
            L.append(f"  - 🟢 硬证据：{ '；'.join(hp['hard']) }")
        if hp["soft"]:
            L.append(f"  - 🟡 软推演：{ '；'.join(hp['soft']) }")
        if hp["noise"]:
            L.append(f"  - 🔴 情绪噪音：{ '；'.join(hp['noise']) }")
        if o["catalysts"]:
            L.append(f"- 催化：{ '；'.join(o['catalysts']) }")
        L.append(f"- 操作建议：{o['action']}")
        L.append("")

    L.append("---")
    L.append(f"> {data['extraction_note']}")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="观点流 → 三重共振机会卡片（提纯草稿）")
    ap.add_argument("--term", default="", help="题材名（可选，留空则尝试从文本推断）")
    ap.add_argument("--input", required=True, help="观点流文本文件路径")
    ap.add_argument("--vault", default=str(DEFAULT_VAULT), help="知识库 wiki 根目录")
    ap.add_argument("--out", default="", help="JSON 输出路径（可选）")
    ap.add_argument("--markdown", default="", help="Markdown 报告输出路径（可选）")
    ap.add_argument("--format", choices=["markdown", "json", "both"], default="markdown")
    args = ap.parse_args(argv)

    text = Path(args.input).expanduser().read_text(encoding="utf-8")
    vault = Path(args.vault).expanduser()
    data = build(args.term, text, vault)

    if args.out:
        out = Path(args.out).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    md = render_markdown(data)
    if args.markdown:
        mp = Path(args.markdown).expanduser()
        mp.parent.mkdir(parents=True, exist_ok=True)
        mp.write_text(md, encoding="utf-8")

    if args.format == "json":
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif args.format == "both":
        print(json.dumps(data["summary"], ensure_ascii=False, indent=2))
        print()
        print(md)
    else:
        print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
