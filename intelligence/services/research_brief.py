"""P0 投研技能层：证据分层审计 / RAG 命中质量遥测 / 反证与证伪计划 / 个股研究简报.

对应 docs/learning/finance-agent-skill-expansion-brainstorm.md 第一阶段四个 P0 技能，
把它们串成一条确定性链：

1. ``audit_evidence_chain``      —— 证据分层审计：把证据链逐条归入 L1/L2/L3/L4/E，
   防止弱证据支撑强结论（回答只能写成"预期交易"还是"事实验证"由它裁定）。
2. ``build_retrieval_telemetry`` —— RAG 命中质量遥测（检索可观测性）：检索模式、
   索引类型、命中来源分布、分数、邻居扩展、是否覆盖 L3、降级/超时。
3. ``build_counterevidence_plan``—— 反证与证伪点生成：最强反证、降级触发条件、
   T+1/T+3/T+5 验证排期，把回答从"观点"升级为"可验证假设"。
4. ``build_stock_research_brief``—— 个股研究路径编排：公司本体→题材暴露→证据硬度
   →市场价值→同链对比→生命周期→反证→条件化结论，缺哪个视角显式写缺口。

全部为纯函数/纯数据结构：不写库、不改知识库、不输出买卖指令（人工复核红线）。
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from intelligence.services.answer_quality import LAYER_L1, LAYER_L2, LAYER_L3, LAYER_L4

LAYER_EXPERIENCE = "E"

_CITATION_TAG_RE = re.compile(r"\[([A-Z])\d*\]")
_SUBHEAD_PREFIX = "\x00SUB\x00"

# L3 硬事实要求"官方口径来源 + 硬动作"同时命中，避免研报里的"预计量产"被误判为硬证据。
_L3_SOURCE_TERMS = ("公告", "互动易", "互动平台", "年报", "季报", "半年报", "招股书", "定期报告", "问询函", "交易所", "官网", "监管", "调研纪要")
_L3_ACTION_TERMS = ("订单", "合同", "中标", "认证", "量产", "投产", "扩产", "产能", "出货", "供货", "定点", "客户验证", "通过验证", "收入确认", "已应用")
_L2_TERMS = ("主营", "收入结构", "毛利", "baseline", "F10", "产业链位置", "核心层", "客户结构")
_L4_TERMS = ("涨停", "新高", "双红", "边际量", "成交", "量能", "相对强度", "涨跌家数", "MA5", "盘面", "信号", "市场环境", "容量前三", "连板", "强势股")
_EXPERIENCE_TERMS = ("经验卡", "纠偏", "历史样板", "用户偏好")
_SPECULATIVE_TERMS = ("预计", "有望", "推断", "测算", "可能", "预期", "或将", "弹性", "传闻")


# ---------------------------------------------------------------------------
# 1) 证据分层审计
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceAuditItem:
    text: str
    source_tag: str  # 引用编号前缀：S/G/R/W/D/L；无引用为 ""
    layer: str  # L1/L2/L3/L4/E


@dataclass
class EvidenceAudit:
    items: list[EvidenceAuditItem] = field(default_factory=list)
    layer_counts: dict[str, int] = field(default_factory=dict)
    gaps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_l3(self) -> bool:
        return self.layer_counts.get(LAYER_L3, 0) > 0

    @property
    def has_l4(self) -> bool:
        return self.layer_counts.get(LAYER_L4, 0) > 0

    @property
    def verdict(self) -> str:
        """结论允许写到哪一档：事实验证 / 预期交易 / 情绪脉冲 / 证据不足。"""
        if self.has_l3:
            return "事实验证"
        if self.layer_counts.get(LAYER_L1, 0) or self.layer_counts.get(LAYER_L2, 0):
            return "预期交易"
        if self.has_l4:
            return "情绪脉冲"
        return "证据不足"

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer_counts": dict(self.layer_counts),
            "verdict": self.verdict,
            "gaps": list(self.gaps),
            "warnings": list(self.warnings),
            "items": [asdict(i) for i in self.items],
        }

    def to_prompt_block(self) -> str:
        lines = [
            "## 证据分层审计（回答前必须先接受这个裁定，不得越级写结论）",
            "- 证据层分布：" + ("、".join(f"{k}×{v}" for k, v in sorted(self.layer_counts.items())) or "无有效证据"),
            f"- 结论允许写到的档位：{self.verdict}",
        ]
        if self.gaps:
            lines.append("- 证据缺口：")
            lines.extend(f"  - {g}" for g in self.gaps)
        if self.warnings:
            lines.append("- 审计警告：")
            lines.extend(f"  - {w}" for w in self.warnings)
        return "\n".join(lines)


def classify_evidence_line(line: str, source_tag: str) -> str:
    text = line.lower()
    if any(t in line for t in _EXPERIENCE_TERMS):
        return LAYER_EXPERIENCE
    has_l3_source = any(t in line for t in _L3_SOURCE_TERMS)
    has_l3_action = any(t in line for t in _L3_ACTION_TERMS)
    speculative = any(t in line for t in _SPECULATIVE_TERMS)
    if has_l3_source and has_l3_action and not speculative:
        return LAYER_L3
    if source_tag in {"S", "D"} or any(t in line for t in _L4_TERMS):
        return LAYER_L4
    if any(t.lower() in text for t in _L2_TERMS):
        return LAYER_L2
    return LAYER_L1


def audit_evidence_chain(evidence_chain: list[str], gap_lines: list[str] | None = None) -> EvidenceAudit:
    audit = EvidenceAudit()
    counts: dict[str, int] = {}
    for raw in evidence_chain:
        line = str(raw or "").strip()
        if not line or line.startswith(_SUBHEAD_PREFIX) or line.startswith("（"):
            continue
        m = _CITATION_TAG_RE.search(line)
        tag = m.group(1) if m else ""
        layer = classify_evidence_line(line, tag)
        audit.items.append(EvidenceAuditItem(text=line[:160], source_tag=tag, layer=layer))
        counts[layer] = counts.get(layer, 0) + 1
    audit.layer_counts = counts

    gap_text = "\n".join(gap_lines or [])
    if not audit.has_l3:
        audit.gaps.append("缺 L3 硬证据（公告/订单/互动易/认证/量产）：逻辑高度受限，先走 L3 evidence tools 补查")
    if not counts.get(LAYER_L2):
        audit.gaps.append("缺 L2 公司 baseline（主营/收入结构/毛利）：不得把题材标签当基本面结论")
    if not audit.has_l4:
        audit.gaps.append("缺 L4 盘面验证：不能只由产业逻辑外推空间")
    if "graph_only" in gap_text or "低置信" in gap_text:
        audit.gaps.append("存在 graph_only/低置信暴露：属预期差待证伪区，不作为事实引用")

    l1 = counts.get(LAYER_L1, 0)
    total = sum(v for k, v in counts.items() if k != LAYER_EXPERIENCE)
    if total and not audit.has_l3 and l1 / total >= 0.6:
        audit.warnings.append(
            f"证据链以 L1 研报/语义召回为主（{l1}/{total}），未见 L3 硬证据：结论只能写成预期交易，不能写成事实验证"
        )
    if audit.has_l4 and not audit.has_l3 and not counts.get(LAYER_L2):
        audit.warnings.append("只有盘面热度（L4）支撑：属情绪脉冲，不能倒推产业逻辑成立")
    return audit


# ---------------------------------------------------------------------------
# 2) RAG 命中质量遥测（检索可观测性）
# ---------------------------------------------------------------------------

_SOURCE_LABELS = {
    "S": "盘面快照",
    "G": "知识图谱",
    "R": "证据索引",
    "W": "wiki 向量召回",
    "D": "DuckDB 数据块",
    "L": "L3 官方证据工具",
}


@dataclass
class RetrievalTelemetry:
    wiki_attempted: bool = False
    wiki_ok: bool = False
    wiki_mode: str = ""
    wiki_index: str = ""
    wiki_hits: int = 0
    wiki_top_score: float | None = None
    wiki_mean_score: float | None = None
    wiki_neighbor_hits: int = 0
    wiki_degraded: str | None = None
    wiki_pages: list[str] = field(default_factory=list)
    source_hits: dict[str, int] = field(default_factory=dict)
    l3_lookup_items: int = 0
    covers_l3: bool = False
    verdict: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def summary_lines(self) -> list[str]:
        dist = "、".join(
            f"{_SOURCE_LABELS.get(k, k)}×{v}" for k, v in sorted(self.source_hits.items())
        ) or "无命中"
        lines = [f"命中来源分布：{dist}"]
        if self.wiki_attempted:
            if self.wiki_ok and self.wiki_hits:
                score = (
                    f"最高分 {self.wiki_top_score:.4f} / 均分 {self.wiki_mean_score:.4f}"
                    if self.wiki_top_score is not None and self.wiki_mean_score is not None
                    else "无分数"
                )
                lines.append(
                    f"W 源检索：mode={self.wiki_mode}｜索引={self.wiki_index}｜命中 {self.wiki_hits} 页"
                    f"（邻居扩展 {self.wiki_neighbor_hits}）｜{score}"
                )
            else:
                lines.append(f"W 源检索：mode={self.wiki_mode}｜未命中/未接入")
        else:
            lines.append("W 源检索：未启用")
        if self.wiki_degraded:
            lines.append(f"检索降级：{self.wiki_degraded}")
        lines.append(
            "L3 硬证据覆盖：" + ("已覆盖" if self.covers_l3 else "未覆盖（回答需显式降权）")
            + (f"｜L3 工具补查命中 {self.l3_lookup_items} 条" if self.l3_lookup_items else "")
        )
        lines.append(f"检索质量裁定：{self.verdict}")
        return lines

    def to_prompt_block(self) -> str:
        lines = ["## RAG 命中质量遥测（回答里要如实说明查得扎不扎实，不要复述字段）"]
        lines.extend(f"- {item}" for item in self.summary_lines())
        return "\n".join(lines)


@dataclass
class DBlockStat:
    """D1-D4 DuckDB 数据块的 per-block 可观测字段（手册 Retrieval 层要求）。"""

    tag: str  # D1/D2/D3/D4
    source: str  # 数据块名称
    attempted: bool = False  # 是否尝试生成（仅 compose/LLM 路径会生成 D 块）
    generated: bool = False  # 是否产出非空块
    line_count: int = 0  # 产出行数（数据量代理）
    note: str = ""  # 未生成原因/缺口

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def summary_line(self) -> str:
        if not self.attempted:
            return f"{self.tag} {self.source}：未尝试（{self.note or '仅 compose 路径生成'}）"
        if self.generated:
            return f"{self.tag} {self.source}：命中，{self.line_count} 行"
        return f"{self.tag} {self.source}：未命中（{self.note or '无匹配数据'}）"


def summarize_d_blocks(stats: list[DBlockStat]) -> list[str]:
    if not stats:
        return []
    generated = sum(1 for s in stats if s.generated)
    lines = [f"D 源数据块：{generated}/{len(stats)} 块命中"]
    lines.extend(s.summary_line() for s in stats)
    return lines


def build_retrieval_telemetry(
    *,
    audit: EvidenceAudit,
    citation_tags: list[str],
    wiki_stats: dict[str, Any] | None = None,
    l3_lookup_items: int = 0,
) -> RetrievalTelemetry:
    tele = RetrievalTelemetry(l3_lookup_items=l3_lookup_items, covers_l3=audit.has_l3 or l3_lookup_items > 0)
    hits: dict[str, int] = {}
    for tag in citation_tags:
        prefix = tag[:1]
        if prefix:
            hits[prefix] = hits.get(prefix, 0) + 1
    tele.source_hits = hits

    ws = wiki_stats or {}
    tele.wiki_attempted = bool(ws.get("attempted"))
    tele.wiki_ok = bool(ws.get("ok"))
    tele.wiki_mode = str(ws.get("mode") or "")
    tele.wiki_index = str(ws.get("index") or "")
    tele.wiki_hits = int(ws.get("hits") or 0)
    scores = [float(s) for s in (ws.get("scores") or [])]
    if scores:
        tele.wiki_top_score = max(scores)
        tele.wiki_mean_score = sum(scores) / len(scores)
    tele.wiki_neighbor_hits = int(ws.get("neighbor_hits") or 0)
    tele.wiki_pages = [str(p) for p in (ws.get("pages") or []) if str(p).strip()]
    warning = ws.get("warning")
    tele.wiki_degraded = str(warning) if warning else None

    total = sum(hits.values())
    if total == 0:
        tele.verdict = "本地检索全空：只能做方法论推演，不能伪装成有据判断"
    elif tele.covers_l3:
        tele.verdict = "命中含 L3 硬证据，回答可写到事实验证档"
    elif tele.wiki_attempted and not tele.wiki_ok:
        tele.verdict = "W 源降级/未接入且无 L3：命中偏结构化信号，结论需降置信"
    else:
        tele.verdict = "有命中但无 L3 硬证据：查得到叙事，查不到硬事实，按预期交易表述"
    return tele


# ---------------------------------------------------------------------------
# 3) 反证与证伪点生成
# ---------------------------------------------------------------------------


@dataclass
class CounterEvidencePlan:
    rebuttals: list[str] = field(default_factory=list)
    downgrade_triggers: list[str] = field(default_factory=list)
    verification_schedule: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def follow_up_lines(self) -> list[str]:
        out: list[str] = []
        for window in ("T+1", "T+3", "T+5"):
            for item in self.verification_schedule.get(window, []):
                out.append(f"[{window}] {item}")
        return out

    def to_prompt_block(self) -> str:
        lines = ["## 反证与证伪计划（候选项，最终由人工在台账里挑选有效项）"]
        lines.append("- 最强反证候选：")
        lines.extend(f"  - {r}" for r in self.rebuttals)
        lines.append("- 降级/证伪触发条件：")
        lines.extend(f"  - {t}" for t in self.downgrade_triggers)
        lines.append("- 验证排期：")
        lines.extend(f"  - {item}" for item in self.follow_up_lines())
        return "\n".join(lines)


def build_counterevidence_plan(audit: EvidenceAudit, stage: str = "") -> CounterEvidencePlan:
    plan = CounterEvidencePlan()
    if stage in {"预期交易", "事实验证但兑现分歧"} or (audit.has_l4 and not audit.has_l3):
        plan.rebuttals.append("价格可能已抢跑：市场交易的是预期而非已验证事实，公告/兑现日反而可能是分歧点")
    if not audit.has_l3:
        plan.rebuttals.append("L3 官方证据缺失：若公司在互动易口径保守/否认，或长期无公告跟进，逻辑高度直接受限")
        plan.downgrade_triggers.append("补查公告/互动易后仍无订单、认证、量产等硬事实 → 降级为叙事观察")
    if not audit.has_l4:
        plan.rebuttals.append("盘面未验证：市场尚未用真金白银选择这条逻辑，可能是市场早已看过并放弃的旧共识")
        plan.downgrade_triggers.append("放量日仍进不了强势股/新高/涨停队列 → 判定市场不认可")
    if audit.has_l3 and audit.has_l4:
        plan.rebuttals.append("事实与盘面同向时最大的反证是拥挤度：若成交占比过高且靠旧主线资金切换，属兑现风险而非增量扩散")
        plan.downgrade_triggers.append("高位放量滞涨/后排不跟 → 从加速定价降级为高位分歧")
    if not audit.layer_counts.get(LAYER_L2):
        plan.rebuttals.append("公司本体不清：收入占比/毛利弹性未验证，题材标签可能是市场强行贴上的弱关系")
        plan.downgrade_triggers.append("确认相关业务收入占比低/无客户落点 → 降级为题材外围")

    plan.verification_schedule = {
        "T+1": ["盘面确认：相对强度、是否进入新高/涨停/强势股队列，板块是否双红"],
        "T+3": ["持续性：边际量与双红能否连续维持，同链是否出现扩散或替代表达更强"],
        "T+5": ["证据升级：是否出现公告/互动易/订单等 L3 确认；相对基准超额与回撤半衰期是否恶化"],
    }
    return plan


# ---------------------------------------------------------------------------
# 4) 个股研究路径编排：StockResearchBrief
# ---------------------------------------------------------------------------

BRIEF_SECTION_ORDER = [
    "公司本体",
    "题材暴露",
    "证据硬度",
    "市场价值",
    "同链对比",
    "生命周期",
    "反证",
    "条件化结论",
]

_SECTION_ROUTES: list[tuple[str, tuple[str, ...]]] = [
    ("公司本体", ("主营", "收入结构", "毛利", "baseline", "产业链位置", "客户结构")),
    ("同链对比", ("替代", "二阶导", "同题材", "队列", "上游", "瓶颈", "核心层", "外围")),
    ("生命周期", ("生命周期", "阶段判断", "唤醒", "升温", "加速定价", "高位分歧", "衰退", "证伪退出")),
    ("题材暴露", ("题材", "概念", "命中概念", "暴露", "标签")),
]


@dataclass
class BriefSection:
    name: str
    points: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)


@dataclass
class StockResearchBrief:
    query: str
    question_type: str
    stage: str
    sections: list[BriefSection] = field(default_factory=list)
    audit: EvidenceAudit = field(default_factory=EvidenceAudit)
    telemetry: RetrievalTelemetry = field(default_factory=RetrievalTelemetry)
    counterevidence: CounterEvidencePlan = field(default_factory=CounterEvidencePlan)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "question_type": self.question_type,
            "stage": self.stage,
            "sections": [asdict(s) for s in self.sections],
            "evidence_audit": self.audit.to_dict(),
            "retrieval_telemetry": self.telemetry.to_dict(),
            "counterevidence": self.counterevidence.to_dict(),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_prompt_block(self) -> str:
        lines = [
            "## 个股研究简报骨架（视角必须全覆盖，输出自然成文，缺口要如实说明）",
            f"- 阶段判断：{self.stage or '未识别'}",
        ]
        for section in self.sections:
            lines.append(f"- {section.name}：")
            for p in section.points[:4]:
                lines.append(f"  - {p}")
            for g in section.gaps:
                lines.append(f"  - ⚠️缺口：{g}")
        return "\n".join(lines)


def build_stock_research_brief(
    query: str,
    question_type: str,
    stage: str,
    audit: EvidenceAudit,
    telemetry: RetrievalTelemetry,
    counterevidence: CounterEvidencePlan,
) -> StockResearchBrief:
    buckets: dict[str, list[str]] = {name: [] for name in BRIEF_SECTION_ORDER}
    for item in audit.items:
        target = _route_section(item)
        buckets[target].append(item.text)

    buckets["证据硬度"].insert(
        0,
        "证据层分布 " + ("、".join(f"{k}×{v}" for k, v in sorted(audit.layer_counts.items())) or "空")
        + f"；裁定档位：{audit.verdict}",
    )
    buckets["反证"].extend(counterevidence.rebuttals)
    buckets["条件化结论"].extend(counterevidence.downgrade_triggers)
    buckets["条件化结论"].extend(counterevidence.follow_up_lines())
    if stage:
        buckets["生命周期"].insert(0, f"阶段判断：{stage}")

    gap_map = {
        "公司本体": "缺主营/收入结构/毛利弹性：先补 baseline，不得用题材标签代替基本面",
        "题材暴露": "未识别题材/概念暴露：先确认市场给它贴了什么标签、标签与主营关系强弱",
        "证据硬度": "证据链为空：先跑本地检索与 L3 补查",
        "市场价值": "缺盘面/市场价值验证（CAR、相对强度、新高、承接）：不能只讲产业故事",
        "同链对比": "缺同链对比：未比较同题材更强核心、替代标的与上游瓶颈，无法判断它是否最优表达",
        "生命周期": "缺生命周期判断：无法回答市场交易到哪一段",
        "反证": "未生成反证：回答只有上涨逻辑属不合格样板",
        "条件化结论": "缺升级/降级/证伪条件：结论不可验证",
    }
    sections = []
    for name in BRIEF_SECTION_ORDER:
        points = buckets[name]
        gaps = [] if points else [gap_map[name]]
        sections.append(BriefSection(name=name, points=points, gaps=gaps))
    return StockResearchBrief(
        query=query,
        question_type=question_type,
        stage=stage,
        sections=sections,
        audit=audit,
        telemetry=telemetry,
        counterevidence=counterevidence,
    )


def _route_section(item: EvidenceAuditItem) -> str:
    for name, terms in _SECTION_ROUTES:
        if any(t in item.text for t in terms):
            return name
    if item.layer == LAYER_L3:
        return "证据硬度"
    if item.layer == LAYER_L4:
        return "市场价值"
    if item.layer == LAYER_L2:
        return "公司本体"
    return "题材暴露"
