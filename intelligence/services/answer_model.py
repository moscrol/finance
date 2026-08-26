"""Structured adjudication and presentation boundary for research answers."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from hashlib import sha256
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path

from intelligence.services.metric_spec import bind_measured_value
from intelligence.services.recall_audit import count_independent_sources
from intelligence.services.research_contract import (
    EvidenceAtom,
    StageArtifact,
    StructuredClaim,
)

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "theme_research_specs.json"
_CITATION_RE = re.compile(r"\[([A-Z]\d+)\]")
_DATE_RE = re.compile(r"\b20\d{2}[-/.年]\d{1,2}(?:[-/.月]\d{1,2}日?)?\b")
_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9])[-+]?\d+(?:\.\d+)?(?![A-Za-z0-9])"
)
_NUMBER_WITH_UNIT_RE = re.compile(
    r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?\s*"
    r"(?:%|pct|bp|亿元|亿|万|家|只|日|天|周|年|月|元|倍|个|点)"
)
_COMPANY_RE = re.compile(
    r"[\u4e00-\u9fff]{2,10}(?:股份|集团|银行|证券)"
)
# _COMPANY_RE 向左最多吞 10 个汉字，会把公司名前面的虚词一起吞进来：证据里写的是
# 「三环集团拟最高10亿元回购股份」，正文写「其中三环集团…」，匹配出的却是
# 「其中三环集团」，`not in allowed_text` 成立，于是报「增加证据外公司」。这些前缀
# 本身不是名字的一部分，剥掉后再比一次。
_COMPANY_NAME_PREFIXES: tuple[str, ...] = (
    "其中",
    "包括",
    "例如",
    "比如",
    "涉及",
    "以及",
    "含",
    "如",
    "和",
    "与",
    "及",
)
_ALLOWED_METHODOLOGY_ENGINEERING_TERMS = frozenset(
    {
        "RAG",
        "retrieval",
        "rerank",
        "DuckDB",
        "baseline",
        "Provider",
        "internal",
        "registry",
    }
)


def _company_is_known(company: str, allowed_text: str) -> bool:
    """公司名是否已在证据里出现（容忍被吞进来的前置虚词）。

    只剥已知虚词，且剥完仍要是个像样的名字（至少 2 个汉字 + 后缀词）。真正新出现的
    公司剥不出任何在证据里的形式，仍然照报。
    """

    if company in allowed_text:
        return True
    return any(
        company.startswith(prefix)
        and len(company) - len(prefix) >= 4
        and company[len(prefix) :] in allowed_text
        for prefix in _COMPANY_NAME_PREFIXES
    )


_CERTAINTY_PROMOTION_TERMS = (
    "已证实",
    "已确认",
    "确定无疑",
    "必然",
    "已经兑现",
)
_ENGINEERING_TERMS = (
    "graph_only",
    "exposure_only",
    "L1_L3_candidate",
    "capacity_industry",
    "market_context",
    "knowledge_evidence",
    "MarketAdapter.",
    "snapshot/export",
    "DuckDB",
    "retrieval",
    "rerank",
    "Run ID",
    "run_id",
    "Daily Review",
    "RAG",
    "baseline",
    "multi-source",
    "人工 review",
    "Provider",
    "concept_graph",
    "entity_exposures",
    "evidence_index",
    "evidence_count",
    "registry",
    "internal",
)


def _engineering_leaks(
    text: str,
    answer_spec: AnswerSpec | None,
    *,
    allowed_profiles: frozenset[str],
    allowed_terms: frozenset[str] | None = None,
) -> tuple[str, ...]:
    profile = getattr(answer_spec, "presentation_profile", None)
    allow = (
        (allowed_terms or _ALLOWED_METHODOLOGY_ENGINEERING_TERMS)
        if profile in allowed_profiles
        else frozenset()
    )
    return tuple(
        term for term in _ENGINEERING_TERMS if term in text and term not in allow
    )


def _drop_engineering_leak_lines(
    answer: str,
    answer_spec: AnswerSpec | None,
    *,
    allowed_profiles: frozenset[str],
    allowed_terms: frozenset[str] | None = None,
) -> str:
    leaked = _engineering_leaks(
        answer,
        answer_spec,
        allowed_profiles=allowed_profiles,
        allowed_terms=allowed_terms,
    )
    if not leaked:
        return answer
    return "\n".join(
        line
        for line in answer.splitlines()
        if not any(term in line for term in leaked)
    )


_STRUCTURED_CLAIM_MARKER_RE = re.compile(
    r"<!--\s*claim_id=(?P<claim_id>[^;]+);\s*"
    r"evidence_atom_ids=(?P<atom_ids>[^;]*);\s*"
    r"claim_type=(?P<claim_type>fact|inference|expectation)\s*-->"
)
_GROUNDED_CLAIM_MARKER_RE = re.compile(
    r"<!--\s*claim_ids=(?P<claim_ids>[^;>]+);\s*"
    r"evidence_atom_ids=(?P<atom_ids>[^;>]*);\s*"
    r"claim_type=(?P<claim_type>fact|candidate|inference|expectation|gap)"
    r"\s*-->"
)
# 标注残片兜底：只认「带标注键名的注释碎块」，不碰普通正文。
#
# 完整标注正则只匹配形状完好的 `<!-- claim_ids=…; …; claim_type=… -->`。
# 模型偶尔把一条标注写成两行（08-01 验收 C4 实测：公开正文尾部漏出
# `claim_type=candidate -->`）——此时逐行剥离两半都认不出：前半有头没尾、
# 后半有尾没头。两个分支分别接住这两半：`<!--` + 标注键名（到 --> 或行尾），
# 以及 标注键名 + `-->`。键名带 `=` 是硬条件，正文里单说「claim_type 这个词」
# 不会被误删。
_GROUNDED_MARKER_RESIDUE_RE = re.compile(
    r"<!--[^<>]*?\b(?:claim_ids?|evidence_atom_ids|claim_type)=[^<>]*?(?:-->|$)"
    r"|\b(?:claim_ids?|evidence_atom_ids|claim_type)=[^<>\n]*?-->",
    re.MULTILINE,
)
_PRESENTER_REPLACEMENTS = (
    ("仅有 graph_only 关联", "仅有概念关联，尚无公司级证据"),
    (
        "知识图谱未命中该词：可能是新词/别名未登记，建议先 concept-ingest 或 disclosure-archive 补证",
        "知识库尚未识别这个题材或别名，需要补充题材定义，并核对公告、年报等公司资料",
    ),
    ("公司本体不清", "公司业务关联度不清晰"),
    ("逻辑高度直接受限", "这条逻辑的直接性将明显下降"),
    ("事实、推测与待验证边界：", "当前的事实边界是："),
    ("观点有效期：", "复核时间："),
    ("L3 官方证据缺失", "缺少公告等公司级硬证据"),
    ("MarketAdapter.get_double_red_themes", "板块涨幅与边际成交数据"),
    ("MarketAdapter.get_theme_stock_signals", "题材个股盘面数据"),
    ("MarketAdapter.get_new_high_directions", "新高方向盘面数据"),
    ("MarketAdapter.get_limit_heat_themes", "涨停热度盘面数据"),
    ("MarketAdapter.get_limit_advance_themes", "连板晋级盘面数据"),
    ("MarketAdapter.get_capacity_sectors", "行业成交容量数据"),
    ("score_detail.new_high_direction", "新高方向信号"),
    ("score_detail.new_high_cluster", "新高个股集中信号"),
    ("score_detail.limit_advance_cluster", "连板晋级信号"),
    ("score_detail.capacity_industry", "行业成交容量信号"),
    ("score_detail.double_red", "涨幅与边际成交同步转强信号"),
    ("score_detail.limit_heat", "涨停热度信号"),
    ("new_high_direction", "新高方向确认"),
    ("new_high_cluster", "新高个股集中"),
    ("limit_advance_cluster", "连板晋级集中"),
    ("capacity_industry", "成交容量居前"),
    ("double_red", "涨幅与边际成交同步转强"),
    ("limit_heat", "涨停热度集中"),
    ("market_context", "市场环境"),
    ("knowledge_evidence", "知识库候选资料"),
    ("super_capacity", "超大成交容量"),
    ("long_tail", "长尾候选"),
    ("graph_only", "仅有概念关联，未发现公司级证据"),
    ("exposure_only", "仅有概念关联，未发现公司级证据"),
    ("L1_L3_candidate", "候选资料，需公告或年报确认"),
    ("L1/L2/L3/L4", "行业资料、公司资料、公告硬证据和盘面信号"),
    ("L3 evidence tools", "公告等公司级证据核验工具"),
    ("L1", "行业资料"),
    ("L2", "公司基础资料"),
    ("L3", "公告等硬证据"),
    ("L4", "盘面信号"),
    ("disclosure-archive → apply", "公告与年报核验"),
    ("disclosure-archive", "公告与年报核验"),
    ("concept-ingest", "补充题材概念登记"),
    ("evidence_index.json", "公司证据资料"),
    ("evidence_index", "证据索引"),
    ("entity_exposures.json", "公司题材关联资料"),
    ("concept_graph.json", "题材关系资料"),
    ("wiki hybrid RAG", "知识库语义检索"),
    ("wiki entity", "知识库公司资料"),
    ("wiki 向量", "知识库语义检索"),
    ("experience_cards", "历史纠偏和优秀样板"),
    ("answer_quality", "多视角质检"),
    ("iFinD baseline", "iFinD 基础资料"),
    ("multi-source", "多来源交叉核验"),
    ("人工 review", "人工复核"),
    ("sanity check", "合理性校验"),
    ("baseline", "基础资料"),
    ("Provider", "数据提供方"),
    ("RAG", "语义检索"),
    ("registry", "工具目录"),
    ("DuckDB", "本地市场数据库"),
    ("snapshot/export", "历史盘面快照"),
)
_SIGNAL_INTERPRETATIONS = (
    (
        "涨幅与边际成交同步转强",
        "说明上涨同时得到新增成交支持，关注度并非只靠缩量拉升",
    ),
    (
        "新高方向确认",
        "说明一批个股正在突破近期高点，板块强度已经开始扩散",
    ),
    (
        "新高个股集中",
        "说明强势不只集中在单一龙头，板块内部出现了一定共振",
    ),
    (
        "涨停热度集中",
        "说明短线资金参与度较高，同时也要警惕拥挤后的分歧",
    ),
    (
        "连板晋级集中",
        "说明短线接力意愿较强，但持续性仍要看后续承接",
    ),
    (
        "成交容量居前",
        "说明这个方向能够承接较大成交，但容量大不等于公司逻辑已经兑现",
    ),
    (
        "市场环境",
        "它只是本轮判断所处的整体市场背景，不代表题材已经获得公司级验证",
    ),
)

_HARD_EVIDENCE_TIERS = frozenset(
    {
        "l3",
        "l3_official",
        "公告",
        "官方",
        "公司公告",
        "年报",
        "半年报",
        "季报",
        "定期报告",
        "互动易",
        "交易所",
    }
)


# Daily Agent 专用契约：Grounded Composer 担任正式 Presenter，保留 LLM 最终措辞。
DAILY_AGENT_PRESENTATION_KIND = "daily_agent_grounded"


class ClaimStatus(str, Enum):
    VERIFIED = "verified"
    CANDIDATE = "candidate"
    INFERRED = "inferred"
    MISSING = "missing"
    CONFLICT = "conflict"


class CompanyTier(str, Enum):
    CORE = "core"
    CANDIDATE = "candidate"
    PERIPHERAL = "peripheral"


@dataclass(frozen=True)
class EvidenceRef:
    evidence_id: str
    source: str
    detail: str = ""
    tier: str = ""
    source_date: str | None = None
    freshness: str = "unknown"
    # 来源跨度级溯源（P2）：内容 hash 与索引来源版本，由 Citation 传播——
    # 同一 evidence_id 在不同索引版本下可被区分，为后续冲突消解提供锚点。
    content_hash: str = ""
    source_revision: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "source": self.source,
            "detail": self.detail,
            "tier": self.tier,
            "source_date": self.source_date,
            "freshness": self.freshness,
            "content_hash": self.content_hash,
            "source_revision": self.source_revision,
        }


@dataclass(frozen=True)
class Claim:
    claim_id: str
    text: str
    claim_type: str
    theme: str
    evidence_ids: tuple[str, ...] = ()
    evidence_tier: str = ""
    freshness: str | None = None
    confidence: float | None = None
    counter_evidence: tuple[str, ...] = ()
    status: ClaimStatus = ClaimStatus.CANDIDATE
    company: str | None = None
    independent_source_count: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "claim_type": self.claim_type,
            "theme": self.theme,
            "evidence_ids": list(self.evidence_ids),
            "evidence_tier": self.evidence_tier,
            "freshness": self.freshness,
            "confidence": self.confidence,
            "counter_evidence": list(self.counter_evidence),
            "status": self.status.value,
            "company": self.company,
            "independent_source_count": self.independent_source_count,
        }


@dataclass(frozen=True)
class CompanyCandidate:
    company: str
    ticker: str = ""
    chain_stage: str = "待确认"
    directness: str = "待确认"
    requested_tier: CompanyTier = CompanyTier.CANDIDATE
    evidence_layer: str = ""


@dataclass(frozen=True)
class CompanyAssessment:
    company: str
    ticker: str
    chain_stage: str
    directness: str
    tier: CompanyTier
    claims: tuple[Claim, ...] = ()
    evidence_gaps: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "company": self.company,
            "ticker": self.ticker,
            "chain_stage": self.chain_stage,
            "directness": self.directness,
            "tier": self.tier.value,
            "claims": [claim.to_dict() for claim in self.claims],
            "evidence_gaps": list(self.evidence_gaps),
        }


@dataclass(frozen=True)
class ThemeResearchSpec:
    theme: str
    pack_id: str
    definition: str
    chain_stages: tuple[str, ...]
    company_scope: str
    as_of: str | None
    evidence_requirements: tuple[str, ...]
    counter_evidence_requirements: tuple[str, ...]
    trigger_conditions: tuple[str, ...]
    verification_actions: tuple[str, ...]
    focus_entities: tuple[str, ...]
    requested_sections: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "theme": self.theme,
            "pack_id": self.pack_id,
            "definition": self.definition,
            "chain_stages": list(self.chain_stages),
            "company_scope": self.company_scope,
            "as_of": self.as_of,
            "evidence_requirements": list(self.evidence_requirements),
            "counter_evidence_requirements": list(self.counter_evidence_requirements),
            "trigger_conditions": list(self.trigger_conditions),
            "verification_actions": list(self.verification_actions),
            "focus_entities": list(self.focus_entities),
            "requested_sections": list(self.requested_sections),
        }

    def to_prompt_block(self) -> str:
        lines = [
            "## 通用题材研究协议",
            f"- 题材：{self.theme}",
            f"- 定义：{self.definition}",
            f"- 产业链：{' → '.join(self.chain_stages)}",
            f"- 公司映射：{self.company_scope}",
            f"- 证据要求：{'；'.join(self.evidence_requirements)}",
            f"- 反证要求：{'；'.join(self.counter_evidence_requirements)}",
            f"- 触发条件：{'；'.join(self.trigger_conditions)}",
            f"- 核验动作：{'；'.join(self.verification_actions)}",
        ]
        if self.focus_entities:
            lines.append(
                f"- 优先核验公司：{'、'.join(self.focus_entities)}"
                "（仅作为检索种子，不代表核心结论）"
            )
        if self.as_of:
            lines.insert(2, f"- 日期口径：{self.as_of}")
        return "\n".join(lines)


@dataclass(frozen=True)
class QualityIssue:
    code: str
    severity: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass(frozen=True)
class AnswerQualityReport:
    issues: tuple[QualityIssue, ...] = ()

    @property
    def passed(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(frozen=True)
class DecisionBrief:
    direct_answer: str
    core_tension: str
    supports: tuple[str, ...]
    counterevidence: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()
    upgrade_conditions: tuple[str, ...] = ()
    downgrade_conditions: tuple[str, ...] = ()
    # 产业链/公司映射。原先没有这个槽位：registry 里 12 条 company: claim 无处可放，
    # brief 只好丢掉，而 Grounded Composer 是「围绕 DecisionBrief 回答」的，
    # 于是 12 家有名有姓的候选一家都进不了正文，chain_mapping 这个必需输出
    # 也就永远无法满足——整份答案被 fail-closed 换成「请补充数据源」。
    chain_mapping: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "direct_answer": self.direct_answer,
            "core_tension": self.core_tension,
            "supports": list(self.supports),
            "counterevidence": list(self.counterevidence),
            "unknowns": list(self.unknowns),
            "upgrade_conditions": list(self.upgrade_conditions),
            "downgrade_conditions": list(self.downgrade_conditions),
            "chain_mapping": list(self.chain_mapping),
        }

    def to_prompt_block(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass(frozen=True)
class GroundingJudgeReport:
    passed: bool
    rejected_sentence_indexes: tuple[int, ...] = ()
    issues: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "rejected_sentence_indexes": list(
                self.rejected_sentence_indexes
            ),
            "issues": list(self.issues),
        }


@dataclass(frozen=True)
class GroundedComposerShadow:
    status: str
    decision_brief: DecisionBrief | None = None
    raw_answer: str | None = None
    repaired_answer: str | None = None
    presented_answer: str | None = None
    deterministic_issues: tuple[QualityIssue, ...] = ()
    judge_report: GroundingJudgeReport | None = None
    judge_raw: str | None = None
    # judge 报的序号（``judge_report.rejected_sentence_indexes``）与**实际执行**的
    # 序号（``resolve_judge_sentence_indexes`` 的返回）会不一样：引文定位优先、
    # 越界序号被丢、条数不足时并回原序号。两者不落在同一个地方，就没人能一眼看出
    # 「judge 判否了，但被否的句子还在稿里」。2026-08-26 那次 fail-open 正是靠拿
    # 归档件逐段重放才定位到——这个字段把那件事变成读一行 trace。
    judge_applied_sentence_indexes: tuple[int, ...] = ()
    provider: str | None = None
    model: str | None = None
    # provider/model 记的是 **composer** 的。judge 走独立 provider 时（
    # ``LLM_JUDGE_BACKEND``）这两个字段与 judge 无关——照着它判 judge 用了谁，
    # 曾连续三轮把 grok-cli 的 URLError 误标成 zhipu 故障。
    judge_provider: str | None = None
    judge_model: str | None = None
    failure_reason: str | None = None
    elapsed_ms: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "decision_brief": (
                self.decision_brief.to_dict()
                if self.decision_brief is not None
                else None
            ),
            "raw_answer": self.raw_answer,
            "repaired_answer": self.repaired_answer,
            "presented_answer": self.presented_answer,
            "deterministic_issues": [
                issue.to_dict() for issue in self.deterministic_issues
            ],
            "judge_report": (
                self.judge_report.to_dict()
                if self.judge_report is not None
                else None
            ),
            "judge_raw": self.judge_raw,
            "judge_reported_sentence_indexes": (
                list(self.judge_report.rejected_sentence_indexes)
                if self.judge_report is not None
                else []
            ),
            "judge_applied_sentence_indexes": list(
                self.judge_applied_sentence_indexes
            ),
            "provider": self.provider,
            "model": self.model,
            "judge_provider": self.judge_provider,
            "judge_model": self.judge_model,
            "failure_reason": self.failure_reason,
            "elapsed_ms": self.elapsed_ms,
        }


@dataclass(frozen=True)
class GroundedSentence:
    sentence_index: int
    text: str
    claim_ids: tuple[str, ...]
    evidence_atom_ids: tuple[str, ...]
    claim_type: str


@dataclass(frozen=True)
class AnswerSpec:
    research_spec: ThemeResearchSpec
    summary: tuple[Claim, ...]
    verified_facts: tuple[Claim, ...]
    company_table: tuple[CompanyAssessment, ...]
    counter_evidence: tuple[Claim, ...]
    gaps: tuple[Claim, ...]
    triggers: tuple[Claim, ...]
    next_actions: tuple[str, ...]
    sources: tuple[EvidenceRef, ...]
    system_notices: tuple[str, ...]
    # 候选证据通道（P0 修复）：agent 补检索 / Web 兜底 / 模块召回 / W7 资讯等
    # 「检索到但未达硬证据门槛」的 claim。此前这些证据只进 evidence_chain 展示层、
    # 不进 registry，合成层在白名单契约下无法合法引用——长尾检索花了预算却是死证据。
    # 进入本通道的 claim 保持 CANDIDATE 状态，composer 只能以待验证口吻使用。
    candidate_facts: tuple[Claim, ...] = ()
    prompt_constraints: tuple[str, ...] = ()
    presentation_kind: str = "theme_research"
    presentation_title: str = ""
    presentation_profile: str = "theme"
    research_artifacts: tuple[StageArtifact, ...] = ()
    research_evidence_atoms: tuple[EvidenceAtom, ...] = ()
    quality: AnswerQualityReport = field(default_factory=AnswerQualityReport)

    def to_dict(self) -> dict[str, object]:
        return {
            "research_spec": self.research_spec.to_dict(),
            "summary": [claim.to_dict() for claim in self.summary],
            "verified_facts": [claim.to_dict() for claim in self.verified_facts],
            "company_table": [company.to_dict() for company in self.company_table],
            "counter_evidence": [claim.to_dict() for claim in self.counter_evidence],
            "gaps": [claim.to_dict() for claim in self.gaps],
            "triggers": [claim.to_dict() for claim in self.triggers],
            "candidate_facts": [claim.to_dict() for claim in self.candidate_facts],
            "next_actions": list(self.next_actions),
            "sources": [source.to_dict() for source in self.sources],
            "system_notices": list(self.system_notices),
            "prompt_constraints": list(self.prompt_constraints),
            "presentation_kind": self.presentation_kind,
            "presentation_title": self.presentation_title,
            "presentation_profile": self.presentation_profile,
            "research_artifacts": [
                artifact.to_dict() for artifact in self.research_artifacts
            ],
            "research_evidence_atoms": [
                atom.to_dict() for atom in self.research_evidence_atoms
            ],
            "quality": self.quality.to_dict(),
        }

    def to_prompt_block(self) -> str:
        if self.presentation_profile in {"causal", "methodology", "review", "general"}:
            lines = [
                "## AnswerSpec（本轮事实边界，禁止增加未列出的事实、公司和数字）",
                "### 直接回答任务",
            ]
            lines.extend(_prompt_claim(claim) for claim in self.summary)
            if self.verified_facts or self.candidate_facts:
                lines.append("### 可回查依据")
                lines.extend(
                    _prompt_claim(claim)
                    for claim in (*self.verified_facts, *self.candidate_facts)
                )
            if self.counter_evidence or self.gaps:
                lines.append("### 证据边界")
                lines.extend(
                    _prompt_claim(claim)
                    for claim in (*self.counter_evidence, *self.gaps)
                )
            if self.next_actions:
                lines.append("### 下一步验证")
                lines.extend(f"- {action}" for action in self.next_actions)
            if self.sources:
                lines.append("### 来源索引")
                lines.extend(
                    f"- {source.source} [{source.evidence_id}]"
                    + (f" — {source.detail}" if source.detail else "")
                    for source in self.sources
                )
            registry_block = structured_claim_registry_block(self)
            if registry_block:
                lines.append("### 结构化 claim registry（正文必须绑定）")
                lines.append(registry_block)
            return "\n".join(lines)
        lines = [
            "## AnswerSpec（唯一事实边界，禁止增加未列出的事实、公司和数字）",
            "### 三行结论",
        ]
        lines.extend(_prompt_claim(claim) for claim in self.summary)
        lines.append("### 已核验事实")
        lines.extend(_prompt_claim(claim) for claim in self.verified_facts)
        lines.append("### 公司判断")
        for company in self.company_table:
            claim_ids = ",".join(
                evidence_id
                for claim in company.claims
                for evidence_id in claim.evidence_ids
            )
            lines.append(
                f"- {company.company}｜{company.tier.value}｜{company.directness}"
                f"｜证据={claim_ids or '无'}｜缺口={'；'.join(company.evidence_gaps) or '无'}"
            )
        lines.append("### 反证与缺口")
        lines.extend(_prompt_claim(claim) for claim in (*self.counter_evidence, *self.gaps))
        if self.candidate_facts:
            lines.append("### 候选证据（检索可回查，但未达硬证据门槛，不得写成已确认事实）")
            lines.extend(_prompt_claim(claim) for claim in self.candidate_facts)
        lines.append("### 触发条件与核验动作")
        lines.extend(_prompt_claim(claim) for claim in self.triggers)
        lines.extend(f"- {action}" for action in self.next_actions)
        if self.prompt_constraints:
            lines.append("### 运行约束（用于日期、问题规划和检索前置门，不是新增事实）")
            lines.extend(self.prompt_constraints)
        if self.sources:
            lines.append("### 来源索引")
            lines.extend(
                f"- {source.source} [{source.evidence_id}]"
                + (f" — {source.detail}" if source.detail else "")
                for source in self.sources
            )
        artifact_lines = _research_artifact_prompt_lines(self.research_artifacts)
        if artifact_lines:
            lines.append("### 必需研究输出")
            lines.extend(artifact_lines)
        registry_block = structured_claim_registry_block(self)
        if registry_block:
            lines.append("### 结构化 claim registry（正文必须绑定）")
            lines.append(registry_block)
            lines.append(
                "marker 只供机器核验；保留自然措辞，事实句绑定合法 EvidenceAtom，"
                "无法绑定的句子直接删除或改成明确的证据缺口。"
            )
        return "\n".join(lines)


def build_deterministic_decision_brief(
    answer_spec: AnswerSpec,
) -> DecisionBrief | None:
    """Project an eight-field DecisionBrief without a provider call.

    Seven fields are direct projections from the structured answer contract.
    ``core_tension`` is deliberately a deterministic template over the leading
    support and counter/gap claim; it is not mislabeled as a lossless projection.
    """

    def unique_claims(*groups: tuple[Claim, ...]) -> tuple[Claim, ...]:
        seen: set[str] = set()
        selected: list[Claim] = []
        for claim in (claim for group in groups for claim in group):
            if not claim.claim_id or claim.claim_id in seen:
                continue
            seen.add(claim.claim_id)
            selected.append(claim)
        return tuple(selected)

    support_claims = tuple(
        claim
        for claim in unique_claims(
            answer_spec.summary,
            answer_spec.verified_facts,
        )
        if claim.evidence_ids and claim.status is not ClaimStatus.MISSING
    )
    if not support_claims:
        return None

    counter_claims = unique_claims(answer_spec.counter_evidence)
    gap_claims = unique_claims(answer_spec.gaps)
    trigger_claims = unique_claims(answer_spec.triggers)
    all_claims = unique_claims(
        answer_spec.summary,
        answer_spec.verified_facts,
        tuple(
            claim
            for company in answer_spec.company_table
            for claim in company.claims
        ),
        answer_spec.counter_evidence,
        answer_spec.gaps,
        answer_spec.triggers,
        answer_spec.candidate_facts,
    )
    chain_claims = tuple(
        claim
        for claim in all_claims
        if claim.claim_id.split(":", 1)[0].casefold()
        in {"company", "chain", "exposure"}
    )

    leading_support = support_claims[0]
    if counter_claims:
        core_tension = (
            f"当前判断的主要支撑是「{leading_support.text}」；"
            f"主要反证是「{counter_claims[0].text}」。"
        )
    elif gap_claims:
        core_tension = (
            f"当前判断的主要支撑是「{leading_support.text}」；"
            f"关键证据缺口是「{gap_claims[0].text}」。"
        )
    elif trigger_claims:
        core_tension = (
            f"当前判断的主要支撑是「{leading_support.text}」；"
            f"后续需由「{trigger_claims[0].text}」继续验证。"
        )
    else:
        core_tension = (
            f"当前判断的主要支撑是「{leading_support.text}」；"
            "仍需在后续验证窗口复核其持续性。"
        )

    brief = DecisionBrief(
        direct_answer=leading_support.text,
        core_tension=core_tension,
        supports=tuple(claim.claim_id for claim in support_claims),
        counterevidence=tuple(claim.claim_id for claim in counter_claims),
        unknowns=tuple(claim.claim_id for claim in gap_claims),
        upgrade_conditions=tuple(claim.claim_id for claim in trigger_claims),
        downgrade_conditions=tuple(
            claim.claim_id
            for claim in unique_claims(counter_claims, gap_claims)
        ),
        chain_mapping=tuple(claim.claim_id for claim in chain_claims),
    )
    validated, issues = parse_decision_brief(
        json.dumps(brief.to_dict(), ensure_ascii=False),
        answer_spec,
    )
    if validated is None or any(issue.severity == "error" for issue in issues):
        return None
    return validated


def resolve_theme_research_spec(
    query: str,
    matched_theme: str | None = None,
    config_path: Path = CONFIG_PATH,
) -> ThemeResearchSpec:
    doc = _load_config(config_path)
    default = _mapping(doc.get("default"))
    packs = doc.get("packs")
    selected = default
    pack_rows = packs if isinstance(packs, list) else []
    search_text = f"{query} {matched_theme or ''}".lower()
    for row in pack_rows:
        pack = _mapping(row)
        aliases = _strings(pack.get("aliases"))
        if any(alias.lower() in search_text for alias in aliases):
            selected = {**default, **pack}
            break
    theme = _theme_name(query, matched_theme, _strings(selected.get("aliases")))
    date_match = _DATE_RE.search(query)
    return ThemeResearchSpec(
        theme=theme,
        pack_id=str(selected.get("pack_id") or "generic_theme"),
        definition=str(selected.get("definition") or ""),
        chain_stages=_strings(selected.get("chain_stages")),
        company_scope=str(selected.get("company_scope") or ""),
        as_of=date_match.group(0) if date_match else None,
        evidence_requirements=_strings(selected.get("evidence_requirements")),
        counter_evidence_requirements=_strings(selected.get("counter_evidence")),
        trigger_conditions=_strings(selected.get("triggers")),
        verification_actions=_strings(selected.get("verification_actions")),
        focus_entities=_strings(selected.get("focus_entities")),
        requested_sections=(
            "definition",
            "industry_chain",
            "company_mapping",
            "direct_evidence",
            "counter_evidence",
            "triggers",
            "verification_actions",
        ),
    )


def resolve_answer_profile(
    query: str,
    matched_theme: str | None = None,
    profile: str = "theme",
) -> ThemeResearchSpec:
    """Return the smallest research contract for a presentation profile.

    Generic causal/methodology questions must not inherit the theme pack's
    industry-chain/company schema merely because they have no dedicated skill.
    The existing theme resolver remains the authoritative path for actual
    theme/company research.
    """
    normalized = str(profile or "theme").strip().lower()
    if normalized in {"theme", "company", "financial"}:
        return resolve_theme_research_spec(query, matched_theme)
    title = matched_theme or query.strip()[:80] or "通用研究"
    section_map = {
        "causal": (
            "direct_answer",
            "mechanism",
            "external_trigger",
            "evidence_boundary",
            "validation",
        ),
        "methodology": (
            "direct_answer",
            "principle",
            "tradeoffs",
            "example",
            "next_step",
        ),
        "review": (
            "direct_answer",
            "strengths",
            "gaps",
            "next_step",
        ),
        "general": (
            "direct_answer",
            "supporting_evidence",
            "gaps",
            "validation",
        ),
    }
    return ThemeResearchSpec(
        theme=title,
        pack_id=f"generic_{normalized or 'general'}",
        definition="",
        chain_stages=(),
        company_scope="",
        as_of=None,
        evidence_requirements=(),
        counter_evidence_requirements=(),
        trigger_conditions=(),
        verification_actions=(),
        focus_entities=(),
        requested_sections=section_map.get(normalized, section_map["general"]),
    )


def make_claim(
    *,
    claim_id: str,
    text: str,
    claim_type: str,
    theme: str,
    status: ClaimStatus,
    evidence_tier: str = "",
    company: str | None = None,
    confidence: float | None = None,
    freshness: str | None = None,
    evidence_ids: tuple[str, ...] | None = None,
) -> Claim:
    cleaned = _clean_line(text)
    ids = evidence_ids if evidence_ids is not None else tuple(_CITATION_RE.findall(text))
    return Claim(
        claim_id=claim_id,
        text=cleaned,
        claim_type=claim_type,
        theme=theme,
        evidence_ids=tuple(dict.fromkeys(ids)),
        evidence_tier=evidence_tier,
        freshness=freshness,
        confidence=confidence,
        status=status,
        company=company,
        independent_source_count=count_independent_sources((cleaned,)),
    )


def build_company_assessments(
    candidates: list[CompanyCandidate],
    claims: list[Claim],
) -> tuple[CompanyAssessment, ...]:
    assessments: list[CompanyAssessment] = []
    for candidate in candidates:
        company_claims = tuple(claim for claim in claims if claim.company == candidate.company)
        verified = any(
            claim_has_hard_company_evidence(claim)
            for claim in company_claims
        )
        if candidate.requested_tier == CompanyTier.PERIPHERAL:
            tier = CompanyTier.PERIPHERAL
        elif candidate.requested_tier == CompanyTier.CORE and verified:
            tier = CompanyTier.CORE
        else:
            tier = CompanyTier.CANDIDATE
        gaps: list[str] = []
        if not company_claims:
            gaps.append("未发现与该公司直接绑定的证据")
        elif not verified:
            gaps.append("候选资料需公告、年报、订单或客户证据确认")
        assessments.append(
            CompanyAssessment(
                company=candidate.company,
                ticker=candidate.ticker,
                chain_stage=candidate.chain_stage,
                directness=candidate.directness,
                tier=tier,
                claims=company_claims,
                evidence_gaps=tuple(gaps),
            )
        )
    return tuple(assessments)


def is_hard_evidence_tier(
    evidence_tier: str,
    evidence_ids: tuple[str, ...] = (),
) -> bool:
    tier = evidence_tier.strip().lower()
    return bool(
        evidence_ids
        and (
            tier in _HARD_EVIDENCE_TIERS
            or tier.startswith("l3")
            or any(
                evidence_id.upper().startswith("L3")
                for evidence_id in evidence_ids
            )
        )
    )


def claim_has_hard_evidence(claim: Claim) -> bool:
    return bool(
        claim.status == ClaimStatus.VERIFIED
        and is_hard_evidence_tier(
            claim.evidence_tier,
            claim.evidence_ids,
        )
    )


def claim_has_hard_company_evidence(claim: Claim) -> bool:
    return bool(
        claim.company
        and claim.status == ClaimStatus.VERIFIED
        and claim_has_hard_evidence(claim)
    )


def claim_has_resolved_hard_company_evidence(
    claim: Claim,
    sources: tuple[EvidenceRef, ...],
) -> bool:
    source_by_id = {
        source.evidence_id: source
        for source in sources
    }
    return bool(
        claim_has_hard_company_evidence(claim)
        and any(
            evidence_id in source_by_id
            and is_hard_evidence_tier(
                source_by_id[evidence_id].tier,
                (evidence_id,),
            )
            for evidence_id in claim.evidence_ids
        )
    )


def _soften_certainty_text(text: str) -> str:
    uncertain = "\x00UNCERTAIN\x00"
    return (
        str(text or "")
        .replace("不确定", uncertain)
        .replace("确定性", "证据可验证程度")
        .replace("必然", "可能")
        .replace("肯定", "可能")
        .replace("已证实", "已有证据支持")
        .replace("确定", "待验证")
        .replace(uncertain, "不确定")
    )


def finalize_answer_spec(answer_spec: AnswerSpec) -> AnswerSpec:
    governed = apply_claim_evidence_policy(answer_spec)
    return replace(governed, quality=evaluate_answer_spec(governed))


def apply_claim_evidence_policy(answer_spec: AnswerSpec) -> AnswerSpec:
    softened = False

    def govern(claim: Claim) -> Claim:
        nonlocal softened
        if claim_has_hard_evidence(claim):
            return claim
        text = _soften_certainty_text(claim.text)
        if text == claim.text:
            return claim
        softened = True
        return replace(claim, text=text)

    summary = tuple(govern(claim) for claim in answer_spec.summary)
    verified_facts = tuple(
        govern(claim) for claim in answer_spec.verified_facts
    )
    companies: list[CompanyAssessment] = []
    for company in answer_spec.company_table:
        governed_claims = tuple(govern(claim) for claim in company.claims)
        tier = company.tier
        gaps = company.evidence_gaps
        if tier == CompanyTier.CORE and not any(
            claim_has_resolved_hard_company_evidence(
                claim,
                answer_spec.sources,
            )
            for claim in governed_claims
        ):
            tier = CompanyTier.CANDIDATE
            gaps = tuple(
                dict.fromkeys(
                    (
                        *gaps,
                        "公司级证据未解析到官方来源，暂不列为核心",
                    )
                )
            )
        companies.append(
            replace(
                company,
                tier=tier,
                claims=governed_claims,
                evidence_gaps=gaps,
            )
        )
    counter_evidence = tuple(
        govern(claim) for claim in answer_spec.counter_evidence
    )
    gaps = tuple(govern(claim) for claim in answer_spec.gaps)
    triggers = tuple(govern(claim) for claim in answer_spec.triggers)
    candidate_facts = tuple(
        govern(claim) for claim in answer_spec.candidate_facts
    )
    notices = answer_spec.system_notices
    if softened:
        notices = tuple(
            dict.fromkeys(
                (
                    *notices,
                    "弱证据硬措辞已按证据门槛降级为条件化表述。",
                )
            )
        )
    return replace(
        answer_spec,
        summary=summary,
        verified_facts=verified_facts,
        company_table=tuple(companies),
        counter_evidence=counter_evidence,
        gaps=gaps,
        triggers=triggers,
        candidate_facts=candidate_facts,
        system_notices=notices,
    )


def evaluate_answer_spec(answer_spec: AnswerSpec, max_chars: int = 8000) -> AnswerQualityReport:
    issues: list[QualityIssue] = []
    for claim in answer_spec.summary:
        if claim.status != ClaimStatus.MISSING and not claim.evidence_ids:
            issues.append(
                QualityIssue(
                    "unbound_summary_claim",
                    "error",
                    f"结论未绑定证据：{claim.text[:48]}",
                )
            )
    for claim in answer_spec.verified_facts:
        if not claim.evidence_ids:
            issues.append(
                QualityIssue(
                    "unbound_verified_claim",
                    "error",
                    f"已核验结论未绑定证据：{claim.text[:48]}",
                )
            )
    if any(claim.status != ClaimStatus.VERIFIED for claim in answer_spec.verified_facts):
        issues.append(
            QualityIssue(
                "candidate_promoted_to_fact",
                "error",
                "候选、推测或冲突主张进入 verified_facts。",
            )
        )
    for company in answer_spec.company_table:
        if company.tier == CompanyTier.CORE and not any(
            claim_has_resolved_hard_company_evidence(
                claim,
                answer_spec.sources,
            )
            for claim in company.claims
        ):
            issues.append(
                QualityIssue(
                    "core_company_without_verified_evidence",
                    "error",
                    f"{company.company} 被列为核心，但没有公司级已核验证据。",
                )
            )
    all_claims = _all_answer_claims(answer_spec)
    if any(
        _soften_certainty_text(claim.text) != claim.text
        and not claim_has_hard_evidence(claim)
        for claim in all_claims
    ):
        issues.append(
            QualityIssue(
                "weak_evidence_hard_certainty",
                "error",
                "弱证据主张包含硬确定性措辞。",
            )
        )
    # 缺口主张说的是「本轮还缺什么」，不下结论，也不可能把回答绑定到别的题材——
    # 而污染判定要防的正是后者（真实事故：问科创50支撑位返回半导体/AI 算力题材
    # 模板）。跨轮沿用研究上下文时，同一句缺口会既以本轮题材、又以上一轮题材各出
    # 一条：实测个股深挖追问里 gap:6（theme=英维克）与 gap:7（theme=液冷）正文
    # 一字不差，仅题材不同。把 MISSING 主张也算进来，那条残留题材就会让 17 条
    # 主张里 16 条同题材的答案整份判污染，被渲染层 fail-closed 成缺口页，连带丢掉
    # 已经绑定证据的公司事实。
    asserted_claims = tuple(
        claim for claim in all_claims if claim.status != ClaimStatus.MISSING
    )
    if any(
        claim.theme != answer_spec.research_spec.theme for claim in asserted_claims
    ):
        issues.append(
            QualityIssue(
                "theme_contamination",
                "error",
                "存在绑定到其他题材的主张。",
            )
        )
    status_by_key: dict[tuple[str, str | None], set[ClaimStatus]] = {}
    for claim in all_claims:
        key = (_normalize(claim.text), claim.company)
        status_by_key.setdefault(key, set()).add(claim.status)
    if any(
        ClaimStatus.VERIFIED in statuses and ClaimStatus.CONFLICT in statuses
        for statuses in status_by_key.values()
    ):
        issues.append(
            QualityIssue(
                "contradictory_claim_status",
                "error",
                "同一主张同时被标为已核验和冲突。",
            )
        )
    normalized = [_normalize(claim.text) for claim in all_claims if _normalize(claim.text)]
    duplicate_count = len(normalized) - len(set(normalized))
    if normalized and duplicate_count / len(normalized) > 0.2:
        issues.append(
            QualityIssue(
                "high_repetition",
                "warning",
                "主张重复率超过 20%。",
            )
        )
    visible_text = "\n".join(
        [
            *(humanize(claim.text) for claim in all_claims),
            *(humanize(action) for action in answer_spec.next_actions),
        ]
    )
    allowed_profiles = {"methodology", "review", "general", "causal"}
    leaked = [
        term
        for term in _ENGINEERING_TERMS
        if term in visible_text
        and not (
            answer_spec.presentation_profile in allowed_profiles
            and term
            in {
                "RAG",
                "retrieval",
                "rerank",
                "DuckDB",
                "baseline",
                "Provider",
                "internal",
                "registry",
            }
        )
    ]
    if leaked:
        issues.append(
            QualityIssue(
                "engineering_term_leak",
                "error",
                f"用户层出现内部术语：{'、'.join(leaked)}",
            )
        )
    if len(visible_text) > max_chars:
        issues.append(
            QualityIssue(
                "answer_too_long",
                "warning",
                f"默认展示内容超过 {max_chars} 字。",
            )
        )
    if not answer_spec.summary:
        issues.append(QualityIssue("missing_summary", "error", "缺少三行结论。"))
    if not answer_spec.gaps and not answer_spec.counter_evidence:
        issues.append(
            QualityIssue("missing_gaps", "error", "缺少最大缺口或反证。")
        )
    if not answer_spec.next_actions:
        issues.append(
            QualityIssue("missing_next_actions", "error", "缺少下一步核验动作。")
        )
    if (
        any(claim.company for claim in answer_spec.verified_facts)
        and any("未形成可验证的公司级来源" in notice for notice in answer_spec.system_notices)
    ):
        issues.append(
            QualityIssue(
                "evidence_notice_contradiction",
                "error",
                "存在已核验事实时仍声明未形成可验证的公司级来源。",
            )
        )
    return AnswerQualityReport(tuple(issues))


def _research_artifact_prompt_lines(
    artifacts: tuple[StageArtifact, ...],
) -> list[str]:
    lines: list[str] = []
    for artifact in artifacts:
        if not artifact.required_output:
            continue
        lines.append(
            f"- {artifact.stage}: status={artifact.status}; "
            f"evidence_atom_ids={','.join(artifact.evidence_atom_ids) or '无'}; "
            f"payload={json.dumps(artifact.payload, ensure_ascii=False, sort_keys=True)}"
        )
    if lines:
        lines.append(
            "- 上述 required output 即使数据不足也必须保留对应标题并披露缺口；"
            "禁止补写无来源数字概率。"
        )
    return lines


_OWNER_STAGE_HEADINGS = {
    "company_master": "公司本体",
    "company_evidence": "公司级证据块",
    "financial_transmission": "财务传导",
    "market_choice": "市场选择",
    "counterevidence": "反证与证伪",
    "report_period": "报告期间",
    "financial_metrics": "财务指标",
    "segment_disclosure": "分部披露",
    "prior_period_comparison": "前期比较",
    "original_disclosure": "原始披露",
    "event_facts": "事件事实",
    "external_news": "外部资讯快照",
    "impact_transmission": "影响传导",
    "substitutes_and_harmed_directions": "受益、替代与受损方向",
}

# 标题白名单：LLM 输出的 Markdown 标题 / <summary> 只能使用固定小节名或研究主体名。
# 背景（P0 修复）：_is_nonclaim_line 把标题排除在 claim 校验外、present 层又原样保留，
# 意味着「## 招商银行今年利润已翻倍」可以携带无证据事实直达用户。此处收口：
# 标题不是自由文本，超出白名单 ∪ 主体名的标题按未验证内容处理（校验报 issue、
# repair 剔除、present 兜底剔除）。
_ALLOWED_HEADING_TEXTS = frozenset(
    {
        "结论",
        "直接回答",
        "核心判断",
        "核心矛盾",
        "题材怎么理解",
        "为什么这样判断",
        "证据",
        "关键证据",
        "证据链",
        "支撑依据",
        "公司证据",
        "核心公司",
        "候选与外围公司",
        "候选证据",
        "反证",
        "反证与缺口",
        "风险",
        "主要风险",
        "风险与缺口",
        "缺口",
        "证据缺口",
        "证据边界",
        "条件边界",
        "观察条件",
        "触发条件",
        "升级条件",
        "降级条件",
        "升级、降级与证伪条件",
        "下一步验证",
        "下一步如何验证",
        "验证路径",
        "后续验证点",
        "交易含义",
        "数据说明",
        "数据边界",
        "来源",
        "来源与证据边界",
        "盘面判断",
        "盘面信号",
        "公司判断",
        "情景树",
        "历史类似窗口",
        "3–6 个月中期赔率的证据",
        "综合判断",
        "总结",
        "小结",
        "研究结论",
        "展开来源和数据说明",
        "展开来源和数据边界",
        *_OWNER_STAGE_HEADINGS.values(),
    }
)
_HEADING_SEGMENT_SPLIT_RE = re.compile(r"[：:·｜|]+")
_SUMMARY_TAG_RE = re.compile(r"<summary[^>]*>(.*?)</summary>", re.DOTALL)
_FACT_LIKE_HEADING_RE = re.compile(
    r"(?:\d|%|％|亿元|万元|同比|环比|涨|跌|增长|下降|翻倍|已确认|已签|"
    r"供应商|客户|订单|合同|中标|认证|量产|独家|市占率|收入|利润)"
)


def _normalize_heading_text(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "")).strip("：:。！!？?")


_ALLOWED_HEADING_NORMALIZED = frozenset(
    _normalize_heading_text(text) for text in _ALLOWED_HEADING_TEXTS
)


def _heading_line_text(line: str) -> str | None:
    """返回该行的标题文本；非标题/非 summary 行返回 None。"""
    stripped = line.strip()
    if stripped.startswith("#"):
        return stripped.lstrip("#").strip()
    summary = _SUMMARY_TAG_RE.search(stripped)
    if summary is not None:
        return summary.group(1).strip()
    return None


def _allowed_heading_subjects(answer_spec: AnswerSpec) -> frozenset[str]:
    subjects: set[str] = {
        answer_spec.research_spec.theme,
        answer_spec.presentation_title,
    }
    for claim in _all_answer_claims(answer_spec):
        if claim.company:
            subjects.add(claim.company)
        if claim.theme:
            subjects.add(claim.theme)
    for company in answer_spec.company_table:
        subjects.add(company.company)
    # 本轮契约点名要求的输出，其描述就是合法的小节标签：prompt 里要求模型覆盖
    # 「继续下跌情景：触发条件、支持证据与观察窗口」，模型照做之后门禁再判它
    # 「标题包含未绑定的事实性内容」（因为含「跌」字），等于系统自己跟自己打架。
    # prompt_constraints 的形式是 "output_id：描述"，取描述并按分段登记。
    for constraint in answer_spec.prompt_constraints:
        description = str(constraint).split("：", 1)[-1]
        subjects.add(description)
        subjects.update(_HEADING_SEGMENT_SPLIT_RE.split(description))
    return frozenset(
        _normalize_heading_text(subject) for subject in subjects if subject
    )


def _is_disallowed_heading(
    heading_text: str,
    subjects: frozenset[str],
) -> bool:
    normalized = _normalize_heading_text(heading_text)
    if not normalized:
        return False
    segments = [
        segment
        for segment in _HEADING_SEGMENT_SPLIT_RE.split(normalized)
        if segment
    ]
    return any(
        segment not in _ALLOWED_HEADING_NORMALIZED and segment not in subjects
        for segment in segments
    )


def _heading_fact_corpus(
    answer_spec: AnswerSpec | None,
) -> tuple[str, frozenset[str]]:
    """整份 AnswerSpec 可用的事实语料：所有 claim 文本 + 其证据明细。

    标题不带 claim marker，没有「本句绑定了谁」可查，所以用整份 registry 作为
    可用语料——正文句用的是逐句绑定的那一份，标题只能用全份。
    """

    if answer_spec is None:
        return "", frozenset()
    atoms = evidence_atoms_from_answer_spec(answer_spec)
    text = "\n".join(
        _claim_validation_text(claim, atoms)
        for claim in _all_answer_claims(answer_spec)
    )
    normalized = re.sub(r"\s+", "", _expanded_date_text(text))
    numbers = frozenset(
        _normalize_number_token(token)
        for token in _NUMBER_RE.findall(normalized)
    )
    return normalized, numbers


def _heading_requires_fact_binding(
    heading_text: str,
    *,
    allowed_text: str = "",
    allowed_numbers: frozenset[str] = frozenset(),
) -> bool:
    """Only fact-like headings stay hard-gated; narrative headings are advisory.

    Headings are not claim-bound, so a title such as “利润已翻倍” must still be
    rejected.  A structural title such as “为什么检索会跑偏” carries no factual
    assertion and should not force every answer back into a global whitelist.

    走私的定义是「标题用了证据里没有的事实词或数字」，不是「标题里出现了涨/跌
    这种字」。原先只跑一个字符级正则，于是「核心矛盾：放量下跌与外部利好的博弈」
    因为含「跌」被判 error —— 而「放量下跌」正是已绑定 claim 的忠实概括
    （指数 -0.62%、成交放量、跌停 74 家）。给出语料时改判「这些事实词在证据里
    有没有出处」，正文句用的本来就是同一把尺。不给语料时保持旧行为。
    """

    text = _normalize_heading_text(heading_text)
    if re.search(r"(?:为什么|怎么|如何|机制|原因|影响|路径|方法|证据|边界|问题)$", text):
        return False
    if not _FACT_LIKE_HEADING_RE.search(text):
        return False
    if not allowed_text and not allowed_numbers:
        return True
    unbound_markers = [
        marker
        for marker in {
            match.group(0) for match in _FACT_LIKE_HEADING_RE.finditer(text)
        }
        if not marker.isdigit() and marker not in allowed_text
    ]
    unbound_numbers = [
        token
        for token in _NUMBER_RE.findall(text)
        if _normalize_number_token(token) not in allowed_numbers
    ]
    return bool(unbound_markers or unbound_numbers)


def _heading_gate_issues(
    answer: str,
    answer_spec: AnswerSpec,
    *,
    code: str,
    severity: str,
    fact_severity: str | None = None,
) -> tuple[QualityIssue, ...]:
    subjects = _allowed_heading_subjects(answer_spec)
    allowed_text, allowed_numbers = _heading_fact_corpus(answer_spec)
    issues: list[QualityIssue] = []
    for line in answer.splitlines():
        heading = _heading_line_text(line)
        if heading is None:
            continue
        if _is_disallowed_heading(heading, subjects):
            fact_like = _heading_requires_fact_binding(
                heading,
                allowed_text=allowed_text,
                allowed_numbers=allowed_numbers,
            )
            issues.append(
                QualityIssue(
                    code,
                    (fact_severity or severity) if fact_like else severity,
                    (
                        "标题包含未绑定的事实性内容"
                        if fact_like
                        else "标题不在建议标题集合中"
                    )
                    + f"：{heading[:48]}",
                )
            )
    return tuple(issues)


def _drop_disallowed_headings(answer: str, answer_spec: AnswerSpec | None) -> str:
    subjects = (
        _allowed_heading_subjects(answer_spec)
        if answer_spec is not None
        else frozenset()
    )
    allowed_text, allowed_numbers = _heading_fact_corpus(answer_spec)
    kept: list[str] = []
    for line in answer.splitlines():
        heading = _heading_line_text(line)
        if (
            heading is not None
            and _is_disallowed_heading(heading, subjects)
            and _heading_requires_fact_binding(
                heading,
                allowed_text=allowed_text,
                allowed_numbers=allowed_numbers,
            )
        ):
            continue
        kept.append(line)
    return "\n".join(kept)


def _render_owner_stage_artifacts(answer_spec: AnswerSpec) -> list[str]:
    artifacts = [
        artifact
        for artifact in answer_spec.research_artifacts
        if artifact.stage in _OWNER_STAGE_HEADINGS
        and (
            artifact.required_output
            or (
                artifact.stage == "external_news"
                and artifact.payload.get("items")
            )
        )
    ]
    if not artifacts:
        return []
    atoms = evidence_atoms_from_answer_spec(answer_spec)
    lines: list[str] = []
    for artifact in artifacts:
        lines.extend(("", f"## {_OWNER_STAGE_HEADINGS[artifact.stage]}"))
        payload = artifact.payload
        rendered = False

        if artifact.stage == "company_master":
            company = str(payload.get("company") or "").strip()
            ticker = str(payload.get("ticker") or "").strip()
            if company:
                lines.append(
                    f"- 主体：{company}"
                    + (f"（{ticker}）" if ticker else "")
                    + f"；数据截止：{payload.get('as_of') or '待核验'}。"
                )
                rendered = True
        elif artifact.stage == "report_period":
            periods = payload.get("report_periods")
            source_dates = payload.get("source_dates")
            period_rows = (
                [str(item) for item in periods if str(item).strip()]
                if isinstance(periods, list)
                else []
            )
            date_rows = (
                [str(item) for item in source_dates if str(item).strip()]
                if isinstance(source_dates, list)
                else []
            )
            if period_rows or date_rows or payload.get("as_of"):
                lines.append(
                    "- 报告期："
                    + ("、".join(period_rows) if period_rows else "待核验")
                    + "；来源日期："
                    + ("、".join(date_rows) if date_rows else "待核验")
                    + f"；数据截止：{payload.get('as_of') or '待核验'}。"
                )
                rendered = True
        elif artifact.stage == "original_disclosure":
            sources = payload.get("sources")
            if isinstance(sources, list):
                for index, source in enumerate(sources[:4]):
                    if not isinstance(source, dict):
                        continue
                    evidence_id = str(source.get("evidence_id") or "")
                    atom_ids = tuple(
                        atom.atom_id
                        for atom in atoms
                        if atom.source_id == evidence_id
                    )
                    lines.append(
                        f"- {source.get('source') or '来源待核验'}"
                        + (
                            f"：{source.get('detail')}"
                            if source.get("detail")
                            else ""
                        )
                        + _artifact_claim_marker(
                            f"{artifact.stage}-{index}",
                            atom_ids,
                            "fact",
                        )
                    )
                    rendered = True
        elif artifact.stage == "external_news":
            rows = payload.get("items")
            if isinstance(rows, list):
                for index, row in enumerate(rows[:4]):
                    if not isinstance(row, dict):
                        continue
                    title = str(row.get("title") or "").strip()
                    if not title:
                        continue
                    snippet = str(row.get("snippet") or "").strip()
                    atom_ids = tuple(
                        atom.atom_id
                        for atom in atoms
                        if atom.source_id == f"E{index + 1}"
                        and atom.metric == "external_web_snapshot"
                    )
                    lines.append(
                        f"- {title}：{snippet or '搜索结果未提供摘要'}"
                        f"（{row.get('url') or '链接缺失'}；"
                        f"抓取于 {row.get('fetched_at') or '未知时间'}，"
                        "外部快照 L1，仅作背景线索）"
                        + _artifact_claim_marker(
                            f"{artifact.stage}-{index}",
                            atom_ids,
                            "hypothesis",
                        )
                    )
                    rendered = True

        for key in (
            "claims",
            "metrics",
            "segments",
            "comparisons",
            "facts",
            "directions",
        ):
            rows = payload.get(key)
            if not isinstance(rows, list):
                continue
            for index, row in enumerate(rows[:4]):
                if not isinstance(row, dict):
                    continue
                text = str(row.get("text") or "").strip()
                if not text:
                    continue
                evidence_ids = {
                    str(item)
                    for item in row.get("evidence_ids", ())
                    if str(item).strip()
                }
                atom_ids = tuple(
                    atom.atom_id
                    for atom in atoms
                    if atom.source_id in evidence_ids
                )
                has_l3 = any(
                    atom.atom_id in atom_ids
                    and (
                        atom.source_id.startswith("L3")
                        or atom.evidence_tier in {"L3", "公告", "官方"}
                    )
                    for atom in atoms
                )
                claim_type = (
                    "fact"
                    if row.get("status") == ClaimStatus.VERIFIED.value
                    else "hypothesis"
                )
                lines.append(
                    f"- {_soften_without_l3(text, has_l3)}"
                    + _artifact_claim_marker(
                        f"{artifact.stage}-{index}",
                        atom_ids,
                        claim_type,
                    )
                )
                rendered = True
            break

        event_brief = payload.get("event_brief")
        if isinstance(event_brief, dict):
            steps = event_brief.get("steps")
            if isinstance(steps, list):
                for step in steps[:4]:
                    if not isinstance(step, dict):
                        continue
                    points = step.get("points")
                    gaps = step.get("gaps")
                    details = [
                        str(item)
                        for item in (
                            points if isinstance(points, list) else []
                        )
                        if str(item).strip()
                    ]
                    if not details:
                        details = [
                            f"缺数：{item}"
                            for item in (
                                gaps if isinstance(gaps, list) else []
                            )
                            if str(item).strip()
                        ]
                    if details:
                        lines.append(
                            f"- {step.get('name') or '传导步骤'}："
                            + "；".join(details[:2])
                        )
                        rendered = True

        if not rendered:
            reason = artifact.degrade_reason or "该阶段暂无可回查数据"
            lines.append(f"- 缺数：{humanize(reason)}。")
    return lines


def _render_research_artifacts(answer_spec: AnswerSpec) -> list[str]:
    required = {
        artifact.stage: artifact
        for artifact in answer_spec.research_artifacts
        if artifact.required_output
    }
    if not required:
        return []
    source_ids = {source.evidence_id for source in answer_spec.sources}
    has_l3 = any(
        source_id.startswith(("L3", "W", "R"))
        for source_id in source_ids
    )
    lines = _render_owner_stage_artifacts(answer_spec)

    midterm = required.get("market_lifecycle")
    if midterm is not None:
        lines.append("## 3–6 个月中期赔率的证据")
        trends = midterm.payload.get("trends")
        if isinstance(trends, list) and trends:
            for index, trend in enumerate(trends[:4]):
                if not isinstance(trend, dict):
                    continue
                atom_ids = midterm.evidence_atom_ids[index : index + 1]
                lines.append(
                    "- "
                    + "；".join(
                        (
                            str(
                                trend.get("theme")
                                or answer_spec.research_spec.theme
                            ),
                            f"覆盖 {trend.get('days', '—')} 个交易日",
                            f"双红 {trend.get('double_red_days', '—')} 天",
                            f"成交额 {trend.get('amount_trend', '—')}",
                            f"拥挤度分位 {trend.get('crowding_pct', '—')}",
                        )
                    )
                    + _artifact_claim_marker(
                        f"midterm-{index}",
                        atom_ids,
                        "fact",
                    )
                )
        else:
            lines.append(
                "当前缺少可用的多日趋势或拥挤度数据，"
                "不能用当日强度替代 3–6 个月判断。"
            )

    analogs = required.get("historical_analogs")
    if analogs is not None:
        lines.extend(("", "## 历史类似窗口"))
        themes = analogs.payload.get("themes")
        rendered = 0
        if isinstance(themes, list):
            for theme in themes:
                if not isinstance(theme, dict):
                    continue
                analog_rows = theme.get("analogs")
                if not isinstance(analog_rows, list):
                    continue
                for analog in analog_rows[:3]:
                    if not isinstance(analog, dict):
                        continue
                    lines.append(
                        f"- {theme.get('theme', answer_spec.research_spec.theme)}："
                        f"{analog.get('start_date', '—')} 至 "
                        f"{analog.get('end_date', '—')}，"
                        f"形态距离 {analog.get('distance', '—')}；"
                        "后续只作为历史事实，不外推为概率。"
                        + _artifact_claim_marker(
                            f"analog-{rendered}",
                            analogs.evidence_atom_ids[
                                rendered : rendered + 1
                            ],
                            "fact",
                        )
                    )
                    rendered += 1
        if rendered == 0:
            lines.append(
                "当前历史样本不足或未找到可比窗口；该区块保留为数据缺口，"
                "不由模型凭印象补写案例。"
            )

    scenario = required.get("scenario_tree")
    if scenario is not None:
        lines.extend(("", "## 情景树"))
        branches = scenario.payload.get("branches")
        if isinstance(branches, list) and branches:
            for branch in branches:
                if not isinstance(branch, dict):
                    continue
                triggers = branch.get("triggers")
                trigger_text = (
                    "；".join(
                        _soften_without_l3(str(trigger), has_l3)
                        for trigger in triggers
                    )
                    if isinstance(triggers, list)
                    else "等待可观察信号"
                )
                conclusion = _soften_without_l3(
                    str(branch.get("conclusion") or ""),
                    has_l3,
                )
                lines.append(
                    f"- **{branch.get('label', '条件分支')}**"
                    f"（可能性：{branch.get('likelihood', '待验证')}）："
                    f"{trigger_text} → {conclusion}"
                )
        else:
            lines.append(
                "情景变量不足，暂不判断分支概率；"
                "需要先补齐可观察、可证伪的触发条件。"
            )
        lines.append("- 不提供无来源数字概率；分支只随新证据升级或降级。")

    counter = required.get("counterevidence")
    if counter is not None:
        lines.extend(("", "## 升级、降级与证伪条件"))
        upgrade = counter.payload.get("upgrade_conditions")
        downgrade = counter.payload.get(
            "downgrade_and_falsification_conditions"
        )
        if isinstance(upgrade, list) and upgrade:
            lines.append("**升级条件：**")
            lines.extend(
                f"- {_soften_without_l3(str(item.get('text') or ''), has_l3)}"
                for item in upgrade[:3]
                if isinstance(item, dict)
            )
        else:
            lines.append(
                "**升级条件：** 补齐公告、订单、经营兑现或连续盘面验证后再上调。"
            )
        if isinstance(downgrade, list) and downgrade:
            lines.append("**降级/证伪条件：**")
            lines.extend(
                f"- {_soften_without_l3(str(item.get('text') or ''), has_l3)}"
                for item in downgrade[:4]
                if isinstance(item, dict)
            )
        else:
            lines.append(
                "**降级/证伪条件：** 关键事实长期缺席或公开信息否定当前映射。"
            )
    return lines


def _soften_without_l3(text: str, has_l3: bool) -> str:
    if has_l3:
        return humanize(text)
    softened = text.replace("必然", "可能").replace("确定", "待验证")
    return humanize(softened)


def _artifact_claim_marker(
    claim_id: str,
    atom_ids: tuple[str, ...],
    claim_type: str,
) -> str:
    if not atom_ids:
        return ""
    return (
        f" <!-- claim_id={claim_id}; "
        f"evidence_atom_ids={','.join(atom_ids)}; "
        f"claim_type={claim_type} -->"
    )


def _render_evidence_gap_answer(answer_spec: AnswerSpec) -> str:
    """P0 fail-closed 出口：质检 error 未通过时的证据缺口短答。

    不渲染原 AnswerSpec（其结论/公司表/题材主张已被判定不可信），
    只输出：用户问题主题、明确的缺口声明、缺什么数据、下一步。
    禁止携带其他题材结构、公司公告、图谱统计等模板内容。
    """
    theme = humanize(answer_spec.presentation_title or answer_spec.research_spec.theme)
    lines = [f"# {theme}", ""]
    missing_claims = [
        humanize(claim.text)
        for claim in answer_spec.summary
        if claim.status == ClaimStatus.MISSING and claim.text.strip()
    ]
    if missing_claims:
        lines.extend(f"{text}" for text in missing_claims[:2])
    else:
        lines.append(
            "本轮检索与核验未能形成可靠、可回查的研究结论，"
            "为避免输出未经证据绑定的判断，本次不给出定性结论。"
        )
    gap_texts = [
        humanize(gap.text) for gap in answer_spec.gaps if gap.text.strip()
    ]
    if gap_texts:
        lines.extend(["", "**缺少的数据/证据：**"])
        lines.extend(f"- {text}" for text in gap_texts[:5])
    lines.extend(
        [
            "",
            "请补充数据源或稍后重试；数据补齐后本问题可以重新计算/研究。",
        ]
    )
    return "\n".join(lines)


def _fallback_claim_text(text: str) -> str:
    """Clean a candidate claim for the last-resort human answer."""
    value = humanize(str(text or "")).strip()
    value = re.sub(r"\s*\[[A-Za-z0-9_,: -]+\]\s*$", "", value).strip()
    value = re.sub(r"\s*\[(?:\s*[,，]\s*)+\]\s*$", "", value).strip()
    if "：" in value:
        prefix, suffix = value.split("：", 1)
        if suffix.startswith(prefix):
            value = suffix
    return value


def render_decision_brief_fallback(
    brief: DecisionBrief | None,
    answer_spec: AnswerSpec | None = None,
    *,
    verified_only: bool = False,
) -> str:
    """Render the best verified short answer when natural synthesis fails.

    This renderer intentionally has no generic-theme headings, candidate-source
    dump, claim markers or internal run state.  It is a smaller and safer exit
    than the retired marker composer, not another LLM fallback.
    """
    # Grounded 门禁失败时，调用方传 verified_only=True：
    # “主要依据”只展示已验证且已绑定 EvidenceAtom 的事实。
    # 普通 generic deterministic renderer 仍可显式展示待验证线索，
    # 避免把“可见候选”和“门禁失败”两个契约混在一起。
    support_pool = (
        answer_spec.verified_facts
        if answer_spec is not None and verified_only
        else (
            (*answer_spec.verified_facts, *answer_spec.candidate_facts)
            if answer_spec is not None
            else ()
        )
    )
    support_claims = {
        claim.claim_id: _fallback_claim_text(claim.text)
        for claim in support_pool
        if claim.claim_id
        and (
            not verified_only
            or (claim.status == ClaimStatus.VERIFIED and claim.evidence_ids)
        )
        and _fallback_claim_text(claim.text)
    }

    def resolve(
        items: tuple[str, ...],
        registry: dict[str, str],
    ) -> list[str]:
        return [
            registry[item]
            for item in items
            if item in registry and registry[item]
        ]

    lines: list[str] = []
    if (
        answer_spec is not None
        and answer_spec.presentation_kind != "generic_research"
        and answer_spec.presentation_title
    ):
        lines.append(f"# {humanize(answer_spec.presentation_title)}")
    direct = _fallback_claim_text(brief.direct_answer) if brief else ""
    if not direct and answer_spec is not None and answer_spec.summary:
        direct = _fallback_claim_text(answer_spec.summary[0].text)
    if direct:
        lines.extend(
            ["", "## 当前判断", f"{direct}"]
            if lines
            else ["## 当前判断", f"{direct}"]
        )

    supports = resolve(brief.supports if brief else (), support_claims)
    if not supports and answer_spec is not None:
        supports = [
            _fallback_claim_text(claim.text)
            for claim in support_pool
            if (
                not verified_only
                or (claim.status == ClaimStatus.VERIFIED and claim.evidence_ids)
            )
            and _fallback_claim_text(claim.text)
        ][:3]
    if supports:
        lines.extend(["", "## 主要依据", *[f"- {item}" for item in dict.fromkeys(supports)]])

    unknown_claims = {
        claim.claim_id: _fallback_claim_text(claim.text)
        for claim in (answer_spec.gaps if answer_spec is not None else ())
        if claim.claim_id and _fallback_claim_text(claim.text)
    }
    unknowns = resolve(brief.unknowns if brief else (), unknown_claims)
    if not unknowns and answer_spec is not None:
        unknowns = [
            _fallback_claim_text(claim.text)
            for claim in _pin_recall_audit_claims(answer_spec.gaps[:3], answer_spec)
            if _fallback_claim_text(claim.text)
        ]
    if unknowns:
        lines.extend(["", "## 证据边界", *[f"- {item}" for item in dict.fromkeys(unknowns)]])
    next_actions = [
        humanize(action).strip()
        for action in (answer_spec.next_actions[:3] if answer_spec is not None else ())
        if humanize(action).strip()
    ]
    if next_actions:
        lines.extend(
            ["", "## 下一验证", *[f"- {item}" for item in dict.fromkeys(next_actions)]]
        )
    return "\n".join(lines).strip() or "当前没有足够可回查证据形成可靠定性。"


def _render_market_technical_answer(answer_spec: AnswerSpec) -> str:
    """技术位专属投影：不注入产业链/公司研究模板。"""

    lines: list[str] = []
    notices = _dedupe(answer_spec.system_notices)
    if notices:
        lines.extend([humanize(notices[0]), ""])
    title = humanize(
        answer_spec.presentation_title or answer_spec.research_spec.theme
    )
    lines.extend([f"# {title}", "", "## 技术位判断"])
    for claim in answer_spec.summary[:3]:
        lines.append(f"- {_present_summary_claim(claim)}")

    facts = _dedupe_claims(answer_spec.verified_facts)
    if facts:
        lines.extend(["", "## 计算依据"])
        lines.extend(f"- {_present_supporting_fact(claim)}" for claim in facts[:10])

    boundaries = _dedupe_claims(
        (*answer_spec.counter_evidence, *answer_spec.gaps, *answer_spec.triggers)
    )
    if boundaries:
        lines.extend(["", "## 失效条件与缺口"])
        lines.extend(f"- {_present_claim(claim)}" for claim in boundaries[:6])

    actions = _dedupe(answer_spec.next_actions)
    if actions:
        lines.extend(["", "## 后续验证"])
        lines.extend(f"- {humanize(action)}" for action in actions[:4])

    visible_sources = tuple(
        source for source in answer_spec.sources if source.evidence_id != "BASE"
    )
    if visible_sources:
        lines.extend(["", "<details><summary>展开来源</summary>", ""])
        lines.append("\n".join(
            f"- [{source.evidence_id}] {humanize(source.source)}：{humanize(source.detail)}"
            for source in visible_sources
        ))
        lines.extend(["", "</details>"])
    return "\n".join(lines)


def _render_generic_research_answer(answer_spec: AnswerSpec) -> str:
    """长尾 Owner 的最小动态投影，不把候选证据渲染成固定研究模板。"""
    return render_decision_brief_fallback(None, answer_spec)


def quality_requires_fail_closed(answer_spec: AnswerSpec) -> bool:
    """判断质检结果是否要求 fail-closed 出口。

    两类硬失败不得按原样渲染：
    1. theme_contamination —— 回答绑定到了别的题材（真实事故：问科创50支撑位
       返回半导体/AI 算力题材模板）；
    2. 结论未绑定证据且全卷没有任何带证据的已核验事实 —— 即回答没有覆盖
       用户问题的 verified claim，属于纯模板。
    仅有 INFERRED 总结但携带已核验事实的正常答案不受影响。
    """
    if answer_spec.presentation_kind == DAILY_AGENT_PRESENTATION_KIND:
        # 研究雷达是多题材容器，跨题材主张是设计使然，不算污染。
        return False
    error_codes = {
        issue.code
        for issue in answer_spec.quality.issues
        if issue.severity == "error"
    }
    if "theme_contamination" in error_codes:
        if answer_spec.presentation_kind == "generic_research":
            # Generic Owner 的候选来源可能跨主题；专属 renderer 只显示“待核验”
            # 线索，不把候选事实当 verified claim，因此不应被 Base Finance 的
            # 单主题规则误判为可出站研究结论。
            error_codes.discard("theme_contamination")
        else:
            return True
    if "unbound_summary_claim" in error_codes and not any(
        claim.status == ClaimStatus.VERIFIED and claim.evidence_ids
        for claim in answer_spec.verified_facts
    ):
        if answer_spec.presentation_kind == "generic_research" and any(
            claim.evidence_ids for claim in answer_spec.summary
        ):
            return False
        return True
    return False


def render_answer_spec(answer_spec: AnswerSpec) -> str:
    answer_spec = apply_claim_evidence_policy(answer_spec)
    if answer_spec.presentation_kind == "evidence_gap":
        return _render_evidence_gap_answer(answer_spec)
    if answer_spec.presentation_kind == "market_technical":
        if quality_requires_fail_closed(answer_spec):
            return _render_evidence_gap_answer(answer_spec)
        return _render_market_technical_answer(answer_spec)
    if answer_spec.presentation_kind == "generic_research":
        if quality_requires_fail_closed(answer_spec):
            return _render_evidence_gap_answer(answer_spec)
        return _render_generic_research_answer(answer_spec)
    # P0 fail-closed：质检判定题材污染 / 纯模板（无任何已核验证据支撑）的
    # AnswerSpec 不得按原样渲染成研究结论——此前这里直接放行，导致题材
    # 污染模板以 verified_fallback 姿态返回给用户。
    if quality_requires_fail_closed(answer_spec):
        return _render_evidence_gap_answer(answer_spec)
    if answer_spec.presentation_kind in {
        "base_finance",
        DAILY_AGENT_PRESENTATION_KIND,
    }:
        return _apply_certainty_gate(
            _render_base_finance_answer_spec(answer_spec),
            answer_spec,
        )

    lines: list[str] = []
    notices = _dedupe(answer_spec.system_notices)
    if notices:
        lines.append(humanize(notices[0]))
        lines.append("")
    title = (
        humanize(answer_spec.presentation_title)
        if answer_spec.presentation_title
        else f"{humanize(answer_spec.research_spec.theme)}：研究结论"
    )
    lines.append(f"# {title}")
    lines.extend(["", "## 核心判断"])
    for index, claim in enumerate(answer_spec.summary[:3]):
        if index:
            lines.append("")
        lines.append(
            f"**{_summary_label(claim)}：** {_present_summary_claim(claim)}"
        )
    chain = " → ".join(humanize(stage) for stage in answer_spec.research_spec.chain_stages)
    lines.extend(["", "## 题材怎么理解"])
    if chain:
        lines.append(
            f"这条产业链可以按“{chain}”来拆。"
            f"{humanize(answer_spec.research_spec.company_scope)}"
        )
    else:
        lines.append(
            "本轮研究配置尚未给出可靠的产业链拆分，"
            "需要先补齐上下游环节，再讨论公司受益关系。"
        )
    lines.extend(["", "## 为什么这样判断"])
    visible_facts = _dedupe_claims(answer_spec.verified_facts)
    if visible_facts:
        lines.append("本轮可回查的数据主要给出以下信号：")
        lines.extend(
            f"- {_present_supporting_fact(claim)}" for claim in visible_facts[:5]
        )
    else:
        lines.append(
            "本轮没有形成可回查的盘面或公司级事实，因此只能保留题材框架，"
            "不能据此判断资金共识或公司受益关系。"
        )
    artifact_lines = _render_research_artifacts(answer_spec)
    if artifact_lines:
        lines.extend(("", *artifact_lines))
    lines.extend(["", "## 公司证据"])
    if answer_spec.company_table:
        core_companies = tuple(
            company
            for company in answer_spec.company_table
            if company.tier == CompanyTier.CORE
        )
        candidate_companies = tuple(
            company
            for company in answer_spec.company_table
            if company.tier != CompanyTier.CORE
        )
        if core_companies:
            lines.append(
                f"本轮有 {len(core_companies)} 家公司达到核心分层，"
                "其余公司仍需按公开披露逐项核对。"
            )
        else:
            lines.append(
                "以下公司只是一份待核验清单，不等于核心受益者。"
                "只有公告、年报、官网产品资料或客户订单，才能把公司与题材直接绑定。"
            )
        if core_companies:
            lines.extend(
                [
                    "",
                    "### 核心公司",
                    "| 公司 | 产业链位置 | 直接性 | 分层 | 证据状态 |",
                    "| --- | --- | --- | --- | --- |",
                ]
            )
            lines.extend(
                _company_table_row(company, answer_spec.sources)
                for company in core_companies
            )
        if candidate_companies:
            lines.extend(
                [
                    "",
                    "### 候选与外围公司",
                    "以下条目只用于后续核验，不与核心公司混排。",
                    "",
                    "| 公司 | 产业链位置 | 直接性 | 分层 | 证据状态 |",
                    "| --- | --- | --- | --- | --- |",
                ]
            )
            lines.extend(
                _company_table_row(company, answer_spec.sources)
                for company in candidate_companies
            )
    else:
        lines.append(
            "目前没有公司达到可展示的证据门槛。题材框架可以继续研究，"
            "但还不能据此确认任何一家公司的直接受益关系。"
        )
    lines.extend(["", "## 反证与缺口"])
    lines.append("目前最需要警惕的是以下反证和证据缺口：")
    risk_claims = _dedupe_claims((*answer_spec.counter_evidence, *answer_spec.gaps))
    for claim in _pin_recall_audit_claims(risk_claims[:4], answer_spec):
        lines.append(f"- {_present_claim(claim)}")
    lines.extend(["", "## 下一步如何验证"])
    verified_keys = {
        _normalize(claim.text) for claim in _dedupe_claims(answer_spec.verified_facts)
    }
    future_triggers = [
        humanize(claim.text)
        for claim in _dedupe_claims(answer_spec.triggers)
        if _normalize(claim.text) not in verified_keys
    ]
    if future_triggers:
        lines.append(
            "**判断升级需要：** "
            + "；".join(future_triggers[:3]).rstrip("。")
            + "。"
        )
    actions = _dedupe(answer_spec.next_actions)
    review_window = next(
        (action for action in actions if action.startswith("复核时间：")),
        "",
    )
    if review_window:
        lines.append(f"**{review_window}**")
    if any(
        company.tier == CompanyTier.CORE
        and any(claim.status == ClaimStatus.VERIFIED for claim in company.claims)
        for company in answer_spec.company_table
    ):
        lines.append("建议按下面的顺序核验；已有公司级材料仍需持续复核业务贡献和兑现节奏：")
    else:
        lines.append("建议按下面的顺序核验；公司级证据出现前，不把候选升级为核心：")
    ordered_actions = [
        action for action in actions if not action.startswith("复核时间：")
    ]
    for index, action in enumerate(ordered_actions[:4], start=1):
        lines.append(f"{index}. {action}")
    detail_lines: list[str] = []
    if answer_spec.sources:
        detail_lines.extend(["### 来源与证据边界"])
        detail_lines.extend(_present_sources(answer_spec.sources))
    if len(notices) > 1:
        detail_lines.extend(["", "### 数据说明"])
        detail_lines.extend(f"- {humanize(notice)}" for notice in notices[1:])
    if detail_lines:
        lines.extend(["", "<details><summary>展开来源和数据说明</summary>", ""])
        lines.extend(detail_lines)
        lines.extend(["", "</details>"])
    return _apply_certainty_gate(
        "\n".join(lines).rstrip() + "\n",
        answer_spec,
    )


def _apply_certainty_gate(text: str, answer_spec: AnswerSpec) -> str:
    del answer_spec
    return text


def _render_base_finance_answer_spec(answer_spec: AnswerSpec) -> str:
    notices = _dedupe(answer_spec.system_notices)
    summary = _dedupe_claims(answer_spec.summary)
    facts = _dedupe_claims(answer_spec.verified_facts)
    risks = _dedupe_claims((*answer_spec.counter_evidence, *answer_spec.gaps))
    conditions = _dedupe_claims(answer_spec.triggers)
    actions = _dedupe(answer_spec.next_actions)

    direct = (
        _present_summary_claim(summary[0])
        if summary
        else "当前证据不足，暂时不能形成可靠定性。"
    )
    strongest = (
        humanize(facts[0].text)
        if facts
        else "本轮没有形成可回查的硬证据，结论只能保持待验证。"
    )
    risk = (
        _present_claim(risks[0])
        if risks
        else "暂未发现足以改变结论的反证，但仍需等待下一验证窗口。"
    )
    boundary = (
        _present_claim(conditions[0])
        if conditions
        else "若关键证据或市场条件发生反向变化，当前判断应立即降级。"
    )
    next_step = actions[0] if actions else "补齐核心数据后重新裁决。"

    lines: list[str] = []
    if notices:
        lines.extend((humanize(notices[0]), ""))
    lines.extend(
        (
            f"# {humanize(answer_spec.presentation_title or answer_spec.research_spec.theme)}",
            "",
            "## 结论",
            f"**直接定性：** {direct}",
            f"**最强证据：** {strongest}",
            f"**主要风险：** {risk}",
            f"**条件边界：** {boundary}",
            f"**下一步验证：** {humanize(next_step)}",
        )
    )
    lines.extend(
        f"**补充判断：** {_present_summary_claim(claim)}"
        for claim in summary[1:3]
    )
    if len(facts) > 1:
        lines.extend(("", "## 支撑依据"))
        lines.extend(
            f"- {humanize(claim.text)}" for claim in facts[1:6]
        )
    artifact_lines = _render_owner_stage_artifacts(answer_spec)
    if artifact_lines:
        lines.extend(artifact_lines)
    if len(risks) > 1:
        lines.extend(("", "## 风险与缺口"))
        lines.extend(f"- {_present_claim(claim)}" for claim in risks[1:5])
    if len(actions) > 1:
        lines.extend(("", "## 验证路径"))
        lines.extend(
            f"{index}. {humanize(action)}"
            for index, action in enumerate(actions[1:5], start=1)
        )
    detail_lines: list[str] = []
    if answer_spec.sources:
        detail_lines.extend(("### 来源", *_present_sources(answer_spec.sources)))
    if len(notices) > 1:
        detail_lines.extend(
            ("", "### 数据边界", *(f"- {humanize(item)}" for item in notices[1:]))
        )
    if detail_lines:
        lines.extend(("", "<details><summary>展开来源和数据边界</summary>", ""))
        lines.extend(detail_lines)
        lines.extend(("", "</details>"))
    return "\n".join(lines).rstrip() + "\n"


def repair_llm_answer(
    answer: str,
    answer_spec: AnswerSpec,
    *,
    min_chars: int = 80,
) -> str | None:
    del min_chars
    if not any(
        issue.severity == "error"
        for issue in validate_llm_answer(answer, answer_spec)
    ):
        return answer
    return None


# 派生 EvidenceAtom 的 period 字段承载来源 claim 的 freshness 三态；
# 真实报告期（如 "2026H1"）不会与这两个哨兵值撞名。
_STALE_EVIDENCE_PERIODS = frozenset({"superseded", "invalidated"})

# 降桶标注文案。它出现在**正文里**，不是 warnings 里——警告是给工程师看的台账，
# 用户读到的仍是一句语气笃定的结论。降级要让读答案的人看见才算降级。
STALE_EVIDENCE_TIER_NOTE = "（待核验：所据证据已被取代或证伪）"
SINGLE_SOURCE_NOTE = "（单源）"
_CONCLUSIVE_SINGLE_SOURCE_TYPES = frozenset({"company_evidence", "theme_evidence"})


def _is_conclusive_single_source(claim: Claim) -> bool:
    """结论性 claim 且独立来源恰好 1。抽不出文档名（0）不算单源。"""
    return (
        claim.status == ClaimStatus.VERIFIED
        and claim.claim_type in _CONCLUSIVE_SINGLE_SOURCE_TYPES
        and claim.independent_source_count == 1
    )


def _single_source_note(claim: Claim) -> str:
    return SINGLE_SOURCE_NOTE if _is_conclusive_single_source(claim) else ""


def _claim_rests_only_on_stale_evidence(
    claim: "StructuredClaim",
    atom_registry: dict[str, "EvidenceAtom"],
) -> bool:
    """事实 claim 是否**只**绑了已被取代/已证伪的证据原子。

    这一条不是形式问题：ID 写错、少标 marker 都不代表内容错，而「拿已被推翻的
    证据当当前事实」本身就是内容错。门禁（``llm_fact_only_superseded_evidence``）
    与展示层降桶标注共用这一个判据——单一真本源，改判据两处同时变，不会一处
    报警另一处不标。
    """

    if claim.claim_type != "fact" or not claim.evidence_atom_ids:
        return False
    bound_atoms = [
        atom_registry[atom_id]
        for atom_id in claim.evidence_atom_ids
        if atom_id in atom_registry
    ]
    return bool(bound_atoms) and all(
        atom.period in _STALE_EVIDENCE_PERIODS for atom in bound_atoms
    )


def stale_evidence_claim_ids(
    answer: str,
    answer_spec: AnswerSpec,
) -> frozenset[str]:
    """答案里哪些 claim 该被降桶标注（只绑了已取代/已证伪证据的事实）。"""

    atom_registry = {
        atom.atom_id: atom
        for atom in evidence_atoms_from_answer_spec(answer_spec)
    }
    structured_claims, _ = parse_structured_claims(answer)
    return frozenset(
        claim.claim_id
        for claim in structured_claims
        if _claim_rests_only_on_stale_evidence(claim, atom_registry)
    )


def validate_llm_answer(answer: str, answer_spec: AnswerSpec) -> tuple[QualityIssue, ...]:
    issues: list[QualityIssue] = []
    leaked = _engineering_leaks(
        answer,
        answer_spec,
        allowed_profiles=frozenset({"methodology", "review", "general", "causal"}),
    )
    if leaked:
        issues.append(
            QualityIssue(
                "llm_engineering_term_leak",
                "warning",
                f"LLM 输出内部术语：{'、'.join(leaked)}",
            )
        )
    # 标题走私检查：warning 级（不触发整答退稿），展示层会兜底剔除违规标题。
    issues.extend(
        _heading_gate_issues(
            answer,
            answer_spec,
            code="llm_unverified_heading",
            severity="warning",
            fact_severity="warning",
        )
    )
    atoms = evidence_atoms_from_answer_spec(answer_spec)
    atom_registry = {atom.atom_id: atom for atom in atoms}
    claim_registry = {
        claim.claim_id: claim for claim in _all_answer_claims(answer_spec)
    }
    structured_claims, unbound_lines = parse_structured_claims(answer)
    # 这里保持诚实：文本里确实没有 marker，就照报。**「要不要拿它问罪」不归这层管**
    # ——本函数有三个消费方（旧合成链、市场复盘散文契约、followup 合并），后两个
    # 故意钉着这条码当观测信号。契约有没有真的下达给模型，只有调用方知道，
    # 处置在 ask_synthesis。（一版把判据写成全局标志放在这里，全量测试当场抓出
    # 另外两个消费方被误伤。）
    if unbound_lines:
        issues.append(
            QualityIssue(
                "llm_missing_claim_binding",
                "warning",
                "LLM 正文存在未绑定 claim-ID/EvidenceAtom 的内容。",
            )
        )
    for claim in structured_claims:
        source_claim = claim_registry.get(claim.claim_id)
        if source_claim is None:
            issues.append(
                QualityIssue(
                    "llm_invalid_claim_id",
                    "warning",
                    f"LLM 使用无效 claim ID：{claim.claim_id}",
                )
            )
            continue
        allowed_atom_ids = set(_atom_ids_for_claim(source_claim, atoms))
        invalid_atom_ids = tuple(
            atom_id
            for atom_id in claim.evidence_atom_ids
            if atom_id not in atom_registry or atom_id not in allowed_atom_ids
        )
        if invalid_atom_ids:
            issues.append(
                QualityIssue(
                    "llm_invalid_evidence_atom_id",
                    "warning",
                    "LLM 使用无效 EvidenceAtom ID："
                    + "、".join(invalid_atom_ids),
                )
            )
        expected_type = _structured_claim_type(source_claim)
        if claim.claim_type != expected_type:
            issues.append(
                QualityIssue(
                    "llm_claim_type_mismatch",
                    "warning",
                    f"{claim.claim_id} 应为 {expected_type}，"
                    f"实际为 {claim.claim_type}",
                )
            )
        if claim.claim_type == "fact" and not claim.evidence_atom_ids:
            issues.append(
                QualityIssue(
                    "llm_fact_without_evidence_atom",
                    "warning",
                    f"事实 claim {claim.claim_id} 未绑定 EvidenceAtom。",
                )
            )
        if _claim_rests_only_on_stale_evidence(claim, atom_registry):
            issues.append(
                QualityIssue(
                    "llm_fact_only_superseded_evidence",
                    "warning",
                    f"事实 claim {claim.claim_id} 只绑定了已被取代/已证伪的证据原子，"
                    "不能作为当前事实陈述。",
                )
            )
    return tuple(issues)


def evidence_atoms_from_answer_spec(
    answer_spec: AnswerSpec,
) -> tuple[EvidenceAtom, ...]:
    sources = {source.evidence_id: source for source in answer_spec.sources}
    research_atoms = (
        answer_spec.research_evidence_atoms
        if isinstance(answer_spec, AnswerSpec)
        else ()
    )
    atoms: list[EvidenceAtom] = list(research_atoms)
    seen: set[str] = {atom.atom_id for atom in atoms}
    for claim in _all_answer_claims(answer_spec):
        for evidence_id in claim.evidence_ids:
            atom_id = _evidence_atom_id(claim.claim_id, evidence_id)
            if atom_id in seen:
                continue
            seen.add(atom_id)
            source = sources.get(evidence_id)
            bound = bind_measured_value(claim.text)
            provenance: dict[str, object] = {
                "claim_id": claim.claim_id,
                "source": source.source if source is not None else "",
                "detail": source.detail if source is not None else "",
                "content_hash": (
                    source.content_hash if source is not None else ""
                ),
                "source_revision": (
                    source.source_revision if source is not None else ""
                ),
            }
            if bound is not None and bound[3]:
                provenance.update(bound[3])
            atoms.append(
                EvidenceAtom(
                    atom_id=atom_id,
                    claim_text=claim.text,
                    entity_id=claim.company,
                    metric=bound[0] if bound is not None else None,
                    value=bound[1] if bound is not None else None,
                    unit=bound[2] if bound is not None else None,
                    period=claim.freshness,
                    evidence_tier=claim.evidence_tier,
                    source_id=evidence_id,
                    source_date=source.source_date if source is not None else None,
                    provenance=provenance,
                )
            )
    return tuple(atoms)


def structured_claim_registry_block(answer_spec: AnswerSpec) -> str:
    atoms = evidence_atoms_from_answer_spec(answer_spec)
    lines: list[str] = []
    for claim in _all_answer_claims(answer_spec):
        claim_type = _structured_claim_type(claim)
        atom_ids = _atom_ids_for_claim(claim, atoms)
        if claim_type == "fact" and not atom_ids:
            continue
        lines.append(
            f"- {claim.text} "
            f"<!-- claim_id={claim.claim_id}; "
            f"evidence_atom_ids={','.join(atom_ids)}; "
            f"claim_type={claim_type} -->"
        )
    return "\n".join(lines)


def _grounded_registry_priority(
    claim: Claim,
    answer_spec: AnswerSpec,
    query: str,
) -> float:
    """Rank the model-facing claim window without mutating the audit record."""

    if claim in answer_spec.summary:
        score = 100.0
    elif claim in answer_spec.verified_facts:
        score = 90.0
    elif claim in answer_spec.counter_evidence:
        score = 82.0
    elif claim in answer_spec.gaps:
        score = 80.0
    elif claim in answer_spec.triggers:
        score = 72.0
    elif claim.status == ClaimStatus.VERIFIED:
        score = 68.0
    else:
        score = 50.0
    tier = str(claim.evidence_tier or "").lower()
    if tier.startswith(("l3", "official", "公告")):
        score += 24.0
    elif tier.startswith(("l4", "structured", "market")):
        score += 18.0
    elif tier.startswith("l2"):
        score += 12.0
    normalized_claim = _normalize(claim.text)
    for token in re.findall(
        r"[A-Za-z][A-Za-z0-9_.-]{1,}|[\u4e00-\u9fff]{2,6}",
        str(query or ""),
    ):
        if _normalize(token) in normalized_claim:
            score += min(8.0, len(token) * 0.8)
    return score


def grounded_claim_registry_block(
    answer_spec: AnswerSpec,
    *,
    query: str = "",
    max_chars: int | None = None,
) -> str:
    atoms = evidence_atoms_from_answer_spec(answer_spec)
    rows: list[tuple[float, int, str]] = []
    for index, claim in enumerate(_all_answer_claims(answer_spec)):
        claim_atoms = tuple(
            atom
            for atom in atoms
            if atom.provenance.get("claim_id") == claim.claim_id
        )
        line = json.dumps(
            {
                "claim_id": claim.claim_id,
                "claim_type": _grounded_claim_type(claim),
                "text": claim.text,
                "theme": claim.theme,
                "company": claim.company,
                "evidence_atoms": [atom.to_dict() for atom in claim_atoms],
            },
            ensure_ascii=False,
        )
        rows.append(
            (
                _grounded_registry_priority(claim, answer_spec, query),
                index,
                line,
            )
        )
    if max_chars is None or max_chars <= 0:
        return "\n".join(line for _score, _index, line in rows)
    # P4/P6: rank first, then enforce one global prompt budget.  Skipped rows
    # remain in AnswerSpec/EvidenceAtom audit storage and provider traces.
    rows.sort(key=lambda row: (-row[0], row[1]))
    selected: list[str] = []
    used_chars = 0
    for _score, _index, line in rows:
        cost = len(line) + (1 if selected else 0)
        if used_chars + cost > max_chars:
            continue
        selected.append(line)
        used_chars += cost
    # 告知而非隐藏。原先超预算的行被静默丢弃，模型无从知道 registry 还有别的
    # claim——而门禁 task_fulfillment 看的是 answer_spec 全集，两边不对称。
    # 马书 ch28「不足四」讲的正是这个：CC 大结果截断时会写明「Full output saved
    # to…」，作者同时指出**告知 ≠ 模型会去读**，但我们连告知都没有。
    # 实测 10 个 0731 run 里 2 个超窗（最大 71 条入窗 54、丢 17 条），两个 run
    # 都仍判 complete，所以这是潜在不对称而不是已发生的故障——补一行告知是零
    # 成本的那一半，上 LLM 选择不划算。
    dropped = len(rows) - len(selected)
    if dropped > 0:
        note = (
            f'{{"note":"另有 {dropped} 条 claim 因窗口预算未纳入；'
            f'不要臆测它们的内容，需要时按缺口处理"}}'
        )
        # 告知行本身也要进预算，否则一边写预算一边超预算。挤不下就再让出
        # 一条最低分的 claim——但**绝不动最后一条**：证据才是目的，告知是元数据，
        # 预算紧到二选一时留证据。放不下就整条不写，退回今天的静默截断。
        while len(selected) > 1 and used_chars + len(note) + 1 > max_chars:
            used_chars -= len(selected.pop()) + 1
            dropped += 1
            note = (
                f'{{"note":"另有 {dropped} 条 claim 因窗口预算未纳入；'
                f'不要臆测它们的内容，需要时按缺口处理"}}'
            )
        if used_chars + len(note) + (1 if selected else 0) <= max_chars:
            selected.append(note)
    return "\n".join(selected)


def parse_decision_brief(
    answer: str,
    answer_spec: AnswerSpec,
) -> tuple[DecisionBrief | None, tuple[QualityIssue, ...]]:
    payload = _extract_json_object(answer)
    if payload is None:
        return None, (
            QualityIssue(
                "decision_brief_invalid_json",
                "error",
                "DecisionBrief 不是合法 JSON 对象。",
            ),
        )
    allowed_claim_ids = {
        claim.claim_id for claim in _all_answer_claims(answer_spec)
    }
    atom_owner = {
        atom.atom_id: str(atom.provenance.get("claim_id", ""))
        for atom in evidence_atoms_from_answer_spec(answer_spec)
    }

    def canonical_claim_id(raw_id: str) -> str:
        if raw_id in allowed_claim_ids:
            return raw_id
        owner = atom_owner.get(raw_id, "")
        return owner if owner in allowed_claim_ids else raw_id

    def text_value(key: str) -> str:
        value = payload.get(key)
        return value.strip() if isinstance(value, str) else ""

    def id_list(key: str) -> tuple[str, ...]:
        value = payload.get(key)
        if not isinstance(value, list):
            return ()
        return tuple(
            dict.fromkeys(
                canonical_claim_id(str(item).strip())
                for item in value
                if str(item).strip()
            )
        )

    brief = DecisionBrief(
        direct_answer=text_value("direct_answer"),
        core_tension=text_value("core_tension"),
        supports=id_list("supports"),
        counterevidence=id_list("counterevidence"),
        unknowns=id_list("unknowns"),
        upgrade_conditions=id_list("upgrade_conditions"),
        downgrade_conditions=id_list("downgrade_conditions"),
        chain_mapping=id_list("chain_mapping"),
    )
    # chain_mapping 交给模型「挑对家族」是不可靠的：实测它填了 data:D4:*（主线板块
    # 数据），而 registry 里明明有 12 条 company: claim。家族是可确定识别的，就用
    # 确定性方式收口——模型只负责措辞，不负责选证据族。
    chain_claim_ids = tuple(
        claim.claim_id
        for claim in _all_answer_claims(answer_spec)
        if claim.claim_id.split(":", 1)[0].casefold() in {"company", "chain", "exposure"}
    )
    if chain_claim_ids:
        kept = tuple(
            claim_id for claim_id in brief.chain_mapping if claim_id in chain_claim_ids
        )
        brief = replace(brief, chain_mapping=kept or chain_claim_ids)
    elif brief.chain_mapping:
        # registry 里根本没有产业链族，模型填什么都是错的，直接清空而不是放行。
        brief = replace(brief, chain_mapping=())

    issues: list[QualityIssue] = []
    if not brief.direct_answer:
        issues.append(
            QualityIssue(
                "decision_brief_missing_direct_answer",
                "error",
                "DecisionBrief 缺少 direct_answer。",
            )
        )
    if not brief.core_tension:
        issues.append(
            QualityIssue(
                "decision_brief_missing_core_tension",
                "error",
                "DecisionBrief 缺少 core_tension。",
            )
        )
    if not brief.supports:
        issues.append(
            QualityIssue(
                "decision_brief_missing_supports",
                "error",
                "DecisionBrief 缺少支持判断的 claim。",
            )
        )
    referenced_ids = tuple(
        dict.fromkeys(
            (
                *brief.supports,
                *brief.counterevidence,
                *brief.unknowns,
                *brief.upgrade_conditions,
                *brief.downgrade_conditions,
                *brief.chain_mapping,
            )
        )
    )
    invalid_ids = tuple(
        claim_id
        for claim_id in referenced_ids
        if claim_id not in allowed_claim_ids
    )
    if invalid_ids:
        filtered_supports = tuple(
            claim_id
            for claim_id in brief.supports
            if claim_id in allowed_claim_ids
        )
        if filtered_supports:
            brief = DecisionBrief(
                direct_answer=brief.direct_answer,
                core_tension=brief.core_tension,
                supports=filtered_supports,
                counterevidence=tuple(
                    claim_id
                    for claim_id in brief.counterevidence
                    if claim_id in allowed_claim_ids
                ),
                unknowns=tuple(
                    claim_id
                    for claim_id in brief.unknowns
                    if claim_id in allowed_claim_ids
                ),
                upgrade_conditions=tuple(
                    claim_id
                    for claim_id in brief.upgrade_conditions
                    if claim_id in allowed_claim_ids
                ),
                downgrade_conditions=tuple(
                    claim_id
                    for claim_id in brief.downgrade_conditions
                    if claim_id in allowed_claim_ids
                ),
                # 漏了这个字段的话，只要出现一个无效 id，整份产业链映射会被静默清空。
                chain_mapping=tuple(
                    claim_id
                    for claim_id in brief.chain_mapping
                    if claim_id in allowed_claim_ids
                ),
            )
        else:
            issues.append(
                QualityIssue(
                    "decision_brief_invalid_claim_id",
                    "error",
                    "DecisionBrief 使用无效 claim ID："
                    + "、".join(invalid_ids),
                )
            )
    if issues:
        return None, tuple(issues)
    return brief, ()


def _merge_orphan_grounded_markers(answer: str) -> str:
    """把单独成行的 claim marker 归并到前一行正文。

    composer 模型有时把 ``<!-- claim_ids=... -->`` 写在句子的下一行而非行内，
    逐行解析会把正文判为未绑定、marker 判为空句，导致修复后只剩标题。
    """
    merged: list[str] = []
    for raw_line in answer.splitlines():
        line = raw_line.strip()
        marker = _GROUNDED_CLAIM_MARKER_RE.search(line)
        if (
            marker is not None
            and not _GROUNDED_CLAIM_MARKER_RE.sub("", line).strip()
            and merged
        ):
            prev = merged[-1].rstrip()
            if (
                prev
                and not _is_nonclaim_line(prev.strip())
                and _GROUNDED_CLAIM_MARKER_RE.search(prev) is None
            ):
                merged[-1] = f"{prev} {marker.group(0)}"
                continue
        merged.append(raw_line)
    return "\n".join(merged)


def canonicalize_grounded_claim_ids(answer: str, answer_spec: AnswerSpec) -> str:
    """把 marker 的 claim_ids 里混入的 EvidenceAtom id 换成它所属的 claim id。

    composer 经常把同一个 atom id 同时写进 claim_ids 和 evidence_atom_ids：
      <!-- claim_ids=summary:definition,atom-4f0c5f5ec8d2;
           evidence_atom_ids=atom-4f0c5f5ec8d2; claim_type=inference -->
    atom id 不是合法 claim id，于是整句判无效、确定性修复失败、整份答案被丢弃。
    实测被丢掉的是一份 2127 字、逐家写清 12 家候选公司环节/层级/缺口的好答案，
    毙掉它的只是一个字段串位。

    atom id 唯一指向它的所属 claim，所以这是可确定还原的笔误，不是无出处的引用。
    parse_decision_brief 早就对 brief 做了同样的规范化（canonical_claim_id），
    这里只是把同一条规则补到 composer 侧。
    """
    allowed = {claim.claim_id for claim in _all_answer_claims(answer_spec)}
    owner = {
        atom.atom_id: str(atom.provenance.get("claim_id", ""))
        for atom in evidence_atoms_from_answer_spec(answer_spec)
    }

    def rewrite(match: re.Match[str]) -> str:
        raw_ids = [
            item.strip()
            for item in re.split(r"[,，、\s]+", match.group("claim_ids"))
            if item.strip()
        ]
        mapped: list[str] = []
        for raw_id in raw_ids:
            if raw_id in allowed:
                mapped.append(raw_id)
                continue
            resolved = owner.get(raw_id, "")
            if resolved in allowed:
                mapped.append(resolved)
            else:
                mapped.append(raw_id)
        deduped = list(dict.fromkeys(mapped))
        if deduped == raw_ids:
            return match.group(0)
        return (
            f"<!-- claim_ids={','.join(deduped)}; "
            f"evidence_atom_ids={match.group('atom_ids')}; "
            f"claim_type={match.group('claim_type')} -->"
        )

    return _GROUNDED_CLAIM_MARKER_RE.sub(rewrite, answer)


def rebind_entity_claim_ids(answer: str, answer_spec: AnswerSpec) -> str:
    """一句话讲某家公司、却绑在没提这家公司的聚合 claim 上时，改绑到它自己的 claim。

    registry 里常常同时有聚合 claim 和逐家 claim：``gap:1``「12 家公司仅有间接或候选
    证据，未达到公司级硬证据门槛」，以及 ``gap:6``「华灿光电 证据 2026-06-04 已超
    45 天…」。composer 把聚合展开成一家一行是合理写法，但它把 8 行全绑回了聚合，
    于是每一行都判 ``cross_subject``「混入未绑定主体」，repair 再把这 8 行删掉——
    删掉的正好是 chain_mapping 这个必需输出要的东西。

    实测 run_20260731_103917_565944：8 条 cross_subject 里 6 条属于这种绑错，对应
    公司的 claim 就在 registry 里；另外 2 条（易天股份、智立方）registry 里根本没有，
    那是真的凭空添加，不在本函数处理范围内，仍旧照报。

    改绑到确实提到该主体的 claim，比绑在没提它的聚合上更准确，不是放宽。只在
    「整句只提到一个已知主体」且「该主体唯一对应一条 claim」且「当前绑定的 claim
    都没提到它」时才动手，任一条不满足就原样保留。
    """

    claims = _all_answer_claims(answer_spec)
    registry = {claim.claim_id: claim for claim in claims}
    atoms = evidence_atoms_from_answer_spec(answer_spec)
    known_entities = {
        value
        for value in (
            *(claim.company for claim in claims if claim.company),
            *(atom.entity_id for atom in atoms if atom.entity_id),
        )
        if value
    }
    if not known_entities:
        return answer
    # 显式带 company 字段的 claim 优先于「正文里顺带提到」的：华灿光电既是
    # company_table 那条的主体，也出现在「华灿光电 证据已超 45 天」这条时效 gap 的
    # 文本里。前者是这家公司的画像，后者只是提到它，绑定该落在前者。
    by_field: dict[str, set[str]] = {}
    by_text: dict[str, set[str]] = {}
    for claim in claims:
        for entity in known_entities:
            if entity == (claim.company or ""):
                by_field.setdefault(entity, set()).add(claim.claim_id)
            elif entity in claim.text:
                by_text.setdefault(entity, set()).add(claim.claim_id)
    unique_owner: dict[str, str] = {}
    for entity in known_entities:
        for candidates in (by_field.get(entity), by_text.get(entity)):
            # 同一层级里有多条时无法确定该绑哪条，不猜。
            if candidates and len(candidates) == 1:
                unique_owner[entity] = next(iter(candidates))
                break
    if not unique_owner:
        return answer

    def rewrite(line: str) -> str:
        marker = _GROUNDED_CLAIM_MARKER_RE.search(line)
        if marker is None:
            return line
        body = _GROUNDED_CLAIM_MARKER_RE.sub("", line)
        named = [entity for entity in unique_owner if entity in body]
        if len(named) != 1:
            return line
        target_id = unique_owner[named[0]]
        bound = [
            item.strip()
            for item in re.split(r"[,，、\s]+", marker.group("claim_ids"))
            if item.strip()
        ]
        if target_id in bound:
            return line
        if any(
            named[0] in registry[claim_id].text
            or named[0] == (registry[claim_id].company or "")
            for claim_id in bound
            if claim_id in registry
        ):
            return line
        target = registry[target_id]
        atom_ids = _atom_ids_for_claim(target, atoms)
        return line.replace(
            marker.group(0),
            f"<!-- claim_ids={target_id}; "
            f"evidence_atom_ids={','.join(atom_ids)}; "
            f"claim_type={_grounded_claim_type(target)} -->",
        )

    return "\n".join(rewrite(line) for line in answer.splitlines())


def parse_grounded_sentences(
    answer: str,
) -> tuple[tuple[GroundedSentence, ...], tuple[str, ...]]:
    sentences: list[GroundedSentence] = []
    unbound_lines: list[str] = []
    for raw_line in _merge_orphan_grounded_markers(answer).splitlines():
        line = raw_line.strip()
        if not line or _is_nonclaim_line(line):
            continue
        marker = _GROUNDED_CLAIM_MARKER_RE.search(line)
        if marker is None:
            unbound_lines.append(line)
            continue
        claim_ids = tuple(
            item.strip()
            for item in re.split(r"[,，、\s]+", marker.group("claim_ids"))
            if item.strip()
        )
        atom_ids = tuple(
            item.strip()
            for item in re.split(r"[,，、\s]+", marker.group("atom_ids"))
            if item.strip() and item.strip() != "无"
        )
        _prefix, text = _line_prefix_and_text(
            _GROUNDED_CLAIM_MARKER_RE.sub("", line)
        )
        sentences.append(
            GroundedSentence(
                sentence_index=len(sentences) + 1,
                text=text,
                claim_ids=claim_ids,
                evidence_atom_ids=atom_ids,
                claim_type=marker.group("claim_type").lower(),
            )
        )
    return tuple(sentences), tuple(unbound_lines)


def validate_grounded_composer_answer(
    answer: str,
    answer_spec: AnswerSpec,
) -> tuple[QualityIssue, ...]:
    issues: list[QualityIssue] = []
    leaked = _engineering_leaks(
        answer,
        answer_spec,
        allowed_profiles=frozenset({"methodology", "review"}),
        allowed_terms=frozenset(
            {
                "RAG",
                "retrieval",
                "rerank",
                "DuckDB",
                "baseline",
                "Provider",
                "internal",
            }
        ),
    )
    if leaked:
        issues.append(
            QualityIssue(
                "grounded_composer_engineering_term_leak",
                "warning",
                f"影子答案输出内部术语：{'、'.join(leaked)}",
            )
        )
    # 白名单现在是写作建议：非事实性自定义标题只告警、不退稿；标题内若夹带
    # 数字、业绩、订单、客户确认等未绑定事实，仍按 error 硬拦。
    issues.extend(
        _heading_gate_issues(
            answer,
            answer_spec,
            code="grounded_composer_unverified_heading",
            severity="warning",
            fact_severity="error",
        )
    )
    atoms = evidence_atoms_from_answer_spec(answer_spec)
    atom_registry = {atom.atom_id: atom for atom in atoms}
    claim_registry = {
        claim.claim_id: claim for claim in _all_answer_claims(answer_spec)
    }
    known_entities = {
        value
        for value in (
            *(
                claim.company
                for claim in claim_registry.values()
                if claim.company
            ),
            *(atom.entity_id for atom in atoms if atom.entity_id),
        )
        if value
    }
    known_themes = {
        claim.theme for claim in claim_registry.values() if claim.theme
    }
    sentences, unbound_lines = parse_grounded_sentences(answer)
    if unbound_lines:
        issues.append(
            QualityIssue(
                "grounded_composer_missing_binding",
                "error",
                "影子答案存在未绑定 claim/EvidenceAtom 的正文。",
            )
        )
    if not sentences:
        issues.append(
            QualityIssue(
                "grounded_composer_empty",
                "error",
                "影子答案没有可验证正文。",
            )
        )
    for sentence in sentences:
        source_claims = tuple(
            claim_registry[claim_id]
            for claim_id in sentence.claim_ids
            if claim_id in claim_registry
        )
        invalid_claim_ids = tuple(
            claim_id
            for claim_id in sentence.claim_ids
            if claim_id not in claim_registry
        )
        if not sentence.claim_ids or invalid_claim_ids:
            issues.append(
                QualityIssue(
                    "grounded_composer_invalid_claim_id",
                    "error",
                    f"第 {sentence.sentence_index} 句使用无效 claim ID："
                    + "、".join(invalid_claim_ids or ("空",)),
                )
            )
            continue
        allowed_atom_ids = {
            atom_id
            for claim in source_claims
            for atom_id in _atom_ids_for_claim(claim, atoms)
        }
        invalid_atom_ids = tuple(
            atom_id
            for atom_id in sentence.evidence_atom_ids
            if atom_id not in atom_registry or atom_id not in allowed_atom_ids
        )
        if invalid_atom_ids:
            issues.append(
                QualityIssue(
                    "grounded_composer_invalid_evidence_atom_id",
                    "error",
                    f"第 {sentence.sentence_index} 句使用无效 EvidenceAtom ID："
                    + "、".join(invalid_atom_ids),
                )
            )
        if sentence.claim_type == "fact":
            if not sentence.evidence_atom_ids:
                issues.append(
                    QualityIssue(
                        "grounded_composer_fact_without_evidence",
                        "error",
                        f"第 {sentence.sentence_index} 句事实未绑定 EvidenceAtom。",
                    )
                )
            if any(
                _grounded_claim_type(claim) != "fact"
                for claim in source_claims
            ):
                issues.append(
                    QualityIssue(
                        "grounded_composer_promoted_to_fact",
                        "error",
                        f"第 {sentence.sentence_index} 句把非事实 claim 升级为事实。",
                    )
                )
        source_types = {
            _grounded_claim_type(claim) for claim in source_claims
        }
        if (
            sentence.claim_type in {"candidate", "gap"}
            and sentence.claim_type not in source_types
        ):
            issues.append(
                QualityIssue(
                    "grounded_composer_claim_type_mismatch",
                    "error",
                    f"第 {sentence.sentence_index} 句的 claim_type 与证据边界不符。",
                )
            )
        bound_atoms = tuple(
            atom_registry[atom_id]
            for atom_id in sentence.evidence_atom_ids
            if atom_id in atom_registry and atom_id in allowed_atom_ids
        )
        allowed_text = "\n".join(
            _claim_validation_text(claim, bound_atoms)
            for claim in source_claims
        )
        normalized_allowed_text = re.sub(
            r"\s+",
            "",
            _expanded_date_text(allowed_text),
        )
        allowed_numbers = {
            _normalize_number_token(token)
            for token in _NUMBER_RE.findall(normalized_allowed_text)
        }
        negative_magnitude = any(
            term in sentence.text
            for term in ("下跌", "下降", "回落", "萎缩", "收缩", "减少")
        )
        new_dates = sorted(
            {
                token
                for token in _DATE_RE.findall(sentence.text)
                if re.sub(r"\s+", "", token) not in normalized_allowed_text
            }
        )
        if new_dates:
            issues.append(
                QualityIssue(
                    "grounded_composer_added_date",
                    "error",
                    f"第 {sentence.sentence_index} 句增加证据外日期："
                    + "、".join(new_dates[:5]),
                )
            )
        new_numbers = sorted(
            {
                token for token in _DATE_RE.findall(sentence.text)
                if re.sub(r"\s+", "", token) not in normalized_allowed_text
            }
            | {
                token
                for token in _NUMBER_RE.findall(sentence.text)
                if (
                    _normalize_number_token(token) not in allowed_numbers
                    and not (
                        negative_magnitude
                        and not _normalize_number_token(token).startswith("-")
                        and f"-{_normalize_number_token(token)}"
                        in allowed_numbers
                    )
                )
            }
        )
        if new_numbers:
            issues.append(
                QualityIssue(
                    "grounded_composer_added_number",
                    "error",
                    f"第 {sentence.sentence_index} 句增加证据外数字："
                    + "、".join(new_numbers[:5]),
                )
            )
        new_companies = sorted(
            {
                company
                for company in _COMPANY_RE.findall(sentence.text)
                if not _company_is_known(company, allowed_text)
            }
        )
        if new_companies:
            issues.append(
                QualityIssue(
                    "grounded_composer_added_company",
                    "error",
                    f"第 {sentence.sentence_index} 句增加证据外公司："
                    + "、".join(new_companies[:5]),
                )
            )
        cross_entities = sorted(
            entity
            for entity in known_entities
            if entity in sentence.text and entity not in allowed_text
        )
        cross_themes = sorted(
            theme
            for theme in known_themes
            if theme in sentence.text and theme not in allowed_text
        )
        if cross_entities or cross_themes:
            issues.append(
                QualityIssue(
                    "grounded_composer_cross_subject",
                    "error",
                    f"第 {sentence.sentence_index} 句混入未绑定主体："
                    + "、".join((*cross_entities, *cross_themes)[:5]),
                )
            )
        if sentence.claim_type != "fact":
            promoted = tuple(
                term
                for term in _CERTAINTY_PROMOTION_TERMS
                if term in sentence.text
            )
            if promoted:
                issues.append(
                    QualityIssue(
                        "grounded_composer_promoted_certainty",
                        "error",
                        f"第 {sentence.sentence_index} 句越界提升确定性："
                        + "、".join(promoted),
                    )
                )
    return tuple(issues)


def ensure_chain_mapping_section(
    answer: str,
    answer_spec: AnswerSpec,
    brief: DecisionBrief | None,
) -> str:
    """DecisionBrief 点名了产业链映射，正文却没写时，确定性补上这一节。

    为什么不是继续调提示词：这条链上凡是靠提示词驱动的都失败了——owner 的
    output_contract 压根不进 composer 的提示词、composer 自己的「必须逐个写出」
    条款被无视；凡是确定性收口的都成功了——事实行预算轮转、brief 的 claim 家族
    选定。必需输出不该依赖模型遵从。

    这不是放宽门禁：正文里确实缺产业链段落是事实，这里是把已经在 AnswerSpec 里、
    已经被 brief 点名的证据补进正文，不是把缺的判成有。层级原样保留，候选仍是候选。
    """
    if brief is None or not brief.chain_mapping:
        return answer
    registry = {claim.claim_id: claim for claim in _all_answer_claims(answer_spec)}
    claims = [registry[cid] for cid in brief.chain_mapping if cid in registry]
    if not claims:
        return answer
    stripped = _GROUNDED_CLAIM_MARKER_RE.sub("", answer)
    if any(humanize(claim.text) and humanize(claim.text) in stripped for claim in claims):
        return answer

    detail = {
        company.company: company
        for company in answer_spec.company_table
        if company.company
    }
    atoms = evidence_atoms_from_answer_spec(answer_spec)
    lines = ["", "## 产业链映射（候选，未获硬证据确认）"]
    for claim in claims:
        company = detail.get(str(claim.company or "")) or next(
            (item for item in answer_spec.company_table if item.company and item.company in claim.text),
            None,
        )
        bits: list[str] = []
        if company is not None:
            stage = humanize(company.chain_stage)
            if stage and stage != "待确认":
                bits.append(stage)
            bits.append(_company_tier_label(company.tier))
            if company.evidence_gaps:
                bits.append(f"缺{humanize(company.evidence_gaps[0])}")
        suffix = f"（{'｜'.join(bits)}）" if bits else ""
        atom_ids = _atom_ids_for_claim(claim, atoms)
        claim_type = _grounded_claim_type(claim)
        if claim_type == "fact" and not atom_ids:
            claim_type = "candidate"
        lines.append(
            f"- {humanize(claim.text)}{suffix} "
            f"<!-- claim_ids={claim.claim_id}; "
            f"evidence_atom_ids={','.join(atom_ids)}; "
            f"claim_type={claim_type} -->"
        )
    return (answer.rstrip() + "\n" + "\n".join(lines)).strip()


def present_grounded_composer_answer(
    answer: str,
    answer_spec: AnswerSpec | None = None,
) -> str:
    # 展示边界兜底：违规标题在此确定性剔除（validate/repair 之外的最后一道）。
    cleaned = _drop_disallowed_headings(
        _merge_orphan_grounded_markers(answer),
        answer_spec,
    )
    # 先整文剥完整标注，再剥残片，最后才逐行 rstrip。原先只做逐行剥离：
    # 标注正则的字符类本可以跨行匹配，但按行切开后「跨两行的标注」两半都
    # 认不出来，残片原样进公开正文（08-01 验收 C4 泄漏 `claim_type=candidate -->`
    # 的机制就是这个）。整文一遍 + 残片兜底，两类都收掉。
    without_markers = _GROUNDED_MARKER_RESIDUE_RE.sub(
        "",
        _GROUNDED_CLAIM_MARKER_RE.sub("", cleaned),
    )
    stripped = "\n".join(
        line.rstrip() for line in without_markers.splitlines()
    ).strip()
    return _drop_engineering_leak_lines(
        stripped,
        answer_spec,
        allowed_profiles=frozenset({"methodology", "review"}),
        allowed_terms=frozenset(
            {
                "RAG",
                "retrieval",
                "rerank",
                "DuckDB",
                "baseline",
                "Provider",
                "internal",
            }
        ),
    )


def repair_grounded_composer_answer(
    answer: str,
    answer_spec: AnswerSpec,
    *,
    rejected_sentence_indexes: tuple[int, ...] = (),
    drop_invalid: bool = False,
) -> str | None:
    atoms = evidence_atoms_from_answer_spec(answer_spec)
    claim_registry = {
        claim.claim_id: claim for claim in _all_answer_claims(answer_spec)
    }
    rejected = set(rejected_sentence_indexes)
    heading_subjects = _allowed_heading_subjects(answer_spec)
    heading_text_corpus, heading_numbers = _heading_fact_corpus(answer_spec)
    repaired_lines: list[str] = []
    sentence_index = 0
    # 上一句正文是否被丢弃。丢句会让下一句的「反之/但/因此」失去前件，正文读起来
    # 就是从半截开始的。标题行不清除这个标记：删掉的句子和幸存句之间插一个小标题，
    # 悬空关系照样存在。
    previous_sentence_dropped = False
    for raw_line in _merge_orphan_grounded_markers(answer).splitlines():
        line = raw_line.strip()
        if not line or _is_nonclaim_line(line):
            heading = _heading_line_text(line)
            if (
                heading is not None
                and _is_disallowed_heading(heading, heading_subjects)
                and _heading_requires_fact_binding(
                    heading,
                    allowed_text=heading_text_corpus,
                    allowed_numbers=heading_numbers,
                )
            ):
                continue
            repaired_lines.append(raw_line)
            continue
        marker = _GROUNDED_CLAIM_MARKER_RE.search(raw_line)
        if marker is None:
            previous_sentence_dropped = True
            continue
        sentence_index += 1
        claim_ids = tuple(
            item.strip()
            for item in re.split(r"[,，、\s]+", marker.group("claim_ids"))
            if item.strip()
        )
        source_claim = next(
            (
                claim_registry[claim_id]
                for claim_id in claim_ids
                if claim_id in claim_registry
            ),
            None,
        )
        if source_claim is None:
            atom_owner = {
                atom.atom_id: str(atom.provenance.get("claim_id", ""))
                for atom in atoms
            }
            source_claim = next(
                (
                    claim_registry[atom_owner[claim_id]]
                    for claim_id in claim_ids
                    if atom_owner.get(claim_id, "") in claim_registry
                ),
                None,
            )
        if source_claim is None:
            previous_sentence_dropped = True
            continue
        line_issues = validate_grounded_composer_answer(
            raw_line,
            answer_spec,
        )
        if not line_issues and sentence_index not in rejected:
            if previous_sentence_dropped:
                raw_line = _strip_backref_connective(raw_line)
                if not raw_line.strip():
                    continue
            repaired_lines.append(raw_line)
            previous_sentence_dropped = False
            continue
        if drop_invalid:
            previous_sentence_dropped = True
            continue
        atom_ids = _atom_ids_for_claim(source_claim, atoms)
        claim_type = _grounded_claim_type(source_claim)
        if claim_type == "fact" and not atom_ids:
            return None
        prefix, _text = _line_prefix_and_text(
            _GROUNDED_CLAIM_MARKER_RE.sub("", raw_line)
        )
        repaired_lines.append(
            f"{prefix}{humanize(source_claim.text)} "
            f"<!-- claim_ids={source_claim.claim_id}; "
            f"evidence_atom_ids={','.join(atom_ids)}; "
            f"claim_type={claim_type} -->"
        )
        # 用 claim 原文顶替，句子没有消失，后一句的前件仍在。
        previous_sentence_dropped = False
    repaired = "\n".join(repaired_lines).strip()
    if drop_invalid and not _GROUNDED_CLAIM_MARKER_RE.search(repaired):
        return None
    if any(
        issue.severity == "error"
        for issue in validate_grounded_composer_answer(
            repaired,
            answer_spec,
        )
    ):
        return None
    return repaired


def parse_grounding_judge_report(
    answer: str,
    *,
    sentence_count: int,
) -> GroundingJudgeReport | None:
    payload = _extract_json_object(answer)
    if payload is None:
        return None
    rejected_raw = payload.get("rejected_sentence_indexes")
    if not isinstance(rejected_raw, list):
        return None
    # 越界句号只丢那一条，不作废整份判定。
    #
    # 原本任何一个越界值都 return None，整份判定连同答案一起被丢弃。实测
    # run_20260731_034344_300179：确定性 repair 先把 8 句删成 5 句，judge 按自己的
    # 数法报了第 5、7 句，7 越界 —— 于是连有效的第 5 句一起作废，failure_reason
    # 记成 judge_output_invalid，整份答案换成 fallback。审稿器给出了真实判定，
    # 系统既没用上它、又拿它当作丢弃答案的理由。
    #
    # 只保留可定位的句号是**更严**而不是更松：第 5 句现在会真的被修掉，
    # 而不是整份答案被替换掉。
    rejected: list[int] = []
    for value in rejected_raw:
        if not isinstance(value, bool) and isinstance(value, int):
            if 1 <= value <= sentence_count:
                rejected.append(value)
    if payload.get("passed") is False and not rejected:
        # 判否但没有任何可执行句号：无法定位问题句，不能当作通过，继续 fail closed。
        return None
    issues_raw = payload.get("issues")
    issues = (
        tuple(
            str(item).strip()
            for item in issues_raw
            if str(item).strip()
        )
        if isinstance(issues_raw, list)
        else ()
    )
    passed = payload.get("passed")
    if not isinstance(passed, bool):
        return None
    if passed == bool(rejected):
        return None
    return GroundingJudgeReport(
        passed=passed,
        rejected_sentence_indexes=tuple(dict.fromkeys(rejected)),
        issues=issues,
    )


# judge 的 issue 里引用原文时用的引号，几种都见过。必须同种引号才配对：允许
# 「"开头 '结尾」会让整串错位一格——实测 reason 本身被 " 包着、内部引文用 '，
# 混配时抽出来的是「将盘后的回购/增持公告直接定性为」这种跨引号的碎片，一条都定位不到。
# 各种引号分别扫描，避免一次 finditer 把整段 reason 当成一条引文吃掉。
_JUDGE_QUOTE_PATTERNS = tuple(
    re.compile(rf"{opening}([^{opening}{closing}]{{6,120}}){closing}")
    for opening, closing in (("「", "」"), ("『", "』"), ("“", "”"), ("‘", "’"))
) + (
    re.compile(r"'([^']{6,120})'"),
    re.compile(r'"([^"]{6,120})"'),
)
_JUDGE_ISSUE_INDEX_RE = re.compile(r"sentence_index['\"]?\s*[:=]\s*(\d+)")


def _judge_issue_quotes(text: str) -> list[str]:
    """按长度降序返回 issue 里的引文——越长越具体，越不容易撞上别的句子。"""

    quotes: list[str] = []
    for pattern in _JUDGE_QUOTE_PATTERNS:
        quotes.extend(pattern.findall(text))
    return sorted(dict.fromkeys(quotes), key=len, reverse=True)


def resolve_judge_sentence_indexes(
    report: GroundingJudgeReport,
    sentences: tuple[GroundedSentence, ...],
) -> tuple[int, ...]:
    """按 issue 里引用的原文定位问题句，而不是信 judge 报的序号。

    harness 按「带 marker 的正文行」编号，judge 按自己的读法编号，两边对不上。实测
    run_20260731_034344_300179：judge 收到 5 句、报的是第 5 和第 7 句，而它引用的原文
    「外围强势可能对A股相关板块形成情绪传导」在第 4 句、「能否扭转弱势取决于增量资金…」
    在第 1 句。偏移量还不固定。照序号修 = 删掉第 5 句，两条真正越界的反而留着——
    看板里「judge 报 index 2、描述的却是第 3 句」说的就是这件事。

    引文能唯一定位到某一句时以引文为准；定位不了才退回它自己报的序号；两者都没有时
    退回原来的 rejected_sentence_indexes（judge 只给序号不给理由的旧格式）。

    **定位到的条数少于 judge 报的条数时，差额必须退回它自己报的序号**——否则
    等于我们替 judge 撤回了它没能引原文的那几条驳回。实测
    run_20260826_021909_393039：judge 收到 4 句、判否并报 [2, 3]，两个序号都对
    （2=「注册获批类可直接对应产品上市资格」，3=「…含恒瑞同日的多条批件」）。
    issue 1 带「」引文、定位到第 2 句；issue 2 写的是中文「句3」且不带引号，
    引文匹配空手、``_JUDGE_ISSUE_INDEX_RE`` 只认字面 ``sentence_index: N``
    也匹配不上。于是 ``resolved={2}`` 非空、老实现直接 return，第 3 句的驳回
    被整条吞掉——那句原样上了公开稿。**一条 issue 引了原文，就把另一条没引
    原文的驳回吃掉了。**

    方向上宁可过严：多删一句是可读性损失，漏删一句是把 judge 点名越界的内容
    发出去，后者才是 #397「拒收兜底不得出稿」要防的那件事。
    """

    valid = {sentence.sentence_index for sentence in sentences}
    reported_indexes = tuple(
        index for index in report.rejected_sentence_indexes if index in valid
    )
    resolved: set[int] = set()
    for issue in report.issues:
        text = str(issue)
        located: int | None = None
        for quote in _judge_issue_quotes(text):
            owners = [
                sentence.sentence_index
                for sentence in sentences
                if quote in sentence.text
            ]
            if len(owners) == 1:
                located = owners[0]
                break
        if located is not None:
            resolved.add(located)
            continue
        reported = _JUDGE_ISSUE_INDEX_RE.search(text)
        if reported is not None and int(reported.group(1)) in valid:
            resolved.add(int(reported.group(1)))
    # 按**条数**判是否有 issue 没落地，而不是按「resolved 是否为空」。后者只在
    # 一条都定位不到时才回退，定位到一条就把其余全丢——这正是上面那个现场。
    if len(resolved) < len(reported_indexes):
        resolved.update(reported_indexes)
    if resolved:
        return tuple(sorted(resolved))
    return reported_indexes


def parse_structured_claims(
    answer: str,
) -> tuple[tuple[StructuredClaim, ...], tuple[str, ...]]:
    claims: list[StructuredClaim] = []
    unbound_lines: list[str] = []
    for raw_line in answer.splitlines():
        line = raw_line.strip()
        if not line or _is_nonclaim_line(line):
            continue
        marker = _STRUCTURED_CLAIM_MARKER_RE.search(line)
        if marker is None:
            unbound_lines.append(line)
            continue
        claim_text = _STRUCTURED_CLAIM_MARKER_RE.sub("", line).strip()
        atom_ids = tuple(
            item.strip()
            for item in re.split(r"[,，、\s]+", marker.group("atom_ids"))
            if item.strip() and item.strip() != "无"
        )
        claims.append(
            StructuredClaim(
                claim_id=marker.group("claim_id").strip(),
                claim=claim_text,
                evidence_atom_ids=atom_ids,
                claim_type=marker.group("claim_type"),
            )
        )
    return tuple(claims), tuple(unbound_lines)


def present_llm_answer(answer: str, answer_spec: AnswerSpec) -> str:
    claim_registry = {
        claim.claim_id: claim for claim in _all_answer_claims(answer_spec)
    }
    # claim 契约答案（含 marker）里的标题不是自由文本：违规标题在展示边界剔除。
    # 无 marker 的纯散文契约（如市场复盘）不在此约束内，由各自的合成契约治理。
    if _STRUCTURED_CLAIM_MARKER_RE.search(answer):
        answer = _drop_disallowed_headings(answer, answer_spec)
    # 只绑了已取代/已证伪证据的事实：不退稿，但降桶——在正文里标出来，
    # 让读答案的人看见它是待核验线索而不是当前结论。
    stale_claim_ids = stale_evidence_claim_ids(answer, answer_spec)
    rendered_lines: list[str] = []
    for raw_line in answer.splitlines():
        marker = _STRUCTURED_CLAIM_MARKER_RE.search(raw_line)
        if marker is None:
            rendered_lines.append(raw_line)
            continue
        claim_id = marker.group("claim_id").strip()
        source_claim = claim_registry.get(claim_id)
        if source_claim is None:
            continue
        prefix = ""
        stripped = raw_line.strip()
        if stripped.startswith("- "):
            prefix = "- "
        else:
            numbered = re.match(r"(\d+[.)]\s+)", stripped)
            if numbered is not None:
                prefix = numbered.group(1)
        tier_note = (
            STALE_EVIDENCE_TIER_NOTE if claim_id in stale_claim_ids else ""
        )
        rendered_lines.append(
            f"{prefix}{humanize(source_claim.text)}{tier_note}"
            f"{_single_source_note(source_claim)}"
        )
    rendered = "\n".join(rendered_lines).strip()
    return _drop_engineering_leak_lines(
        rendered,
        answer_spec,
        allowed_profiles=frozenset({"methodology", "review", "general", "causal"}),
    )


def _all_answer_claims(answer_spec: AnswerSpec) -> tuple[Claim, ...]:
    return tuple(
        dict.fromkeys(
            (
                *answer_spec.summary,
                *answer_spec.verified_facts,
                *answer_spec.counter_evidence,
                *answer_spec.gaps,
                *answer_spec.triggers,
                *answer_spec.candidate_facts,
                *(
                    claim
                    for company in answer_spec.company_table
                    for claim in company.claims
                ),
            )
        )
    )


def _evidence_atom_id(claim_id: str, evidence_id: str) -> str:
    digest = sha256(f"{claim_id}:{evidence_id}".encode()).hexdigest()[:12]
    return f"atom-{digest}"


def _atom_ids_for_claim(
    claim: Claim,
    atoms: tuple[EvidenceAtom, ...],
) -> tuple[str, ...]:
    return tuple(
        atom.atom_id
        for atom in atoms
        if atom.provenance.get("claim_id") == claim.claim_id
    )


def _structured_claim_type(claim: Claim) -> str:
    if claim.status == ClaimStatus.VERIFIED:
        return "fact"
    if claim.status == ClaimStatus.INFERRED:
        return "inference"
    return "expectation"


def _grounded_claim_type(claim: Claim) -> str:
    if claim.status == ClaimStatus.VERIFIED:
        return "fact"
    if claim.status == ClaimStatus.INFERRED:
        return "inference"
    if claim.status == ClaimStatus.MISSING:
        return "gap"
    if claim.status in {ClaimStatus.CANDIDATE, ClaimStatus.CONFLICT}:
        return "candidate"
    return "expectation"


def _is_nonclaim_line(line: str) -> bool:
    return bool(
        line.startswith("#")
        or line.startswith("<details")
        or line.startswith("</details")
        or line.startswith("<summary")
        or line == "（非投资建议）"
    )


def _line_prefix_and_text(line: str) -> tuple[str, str]:
    stripped = line.strip()
    if stripped.startswith("- "):
        return "- ", stripped[2:].strip()
    numbered = re.match(r"(\d+[.)]\s+)(.*)", stripped)
    if numbered is not None:
        return numbered.group(1), numbered.group(2).strip()
    return "", stripped


# 回指连接词：以它开头的句子在语义上依赖前一句。judge 判掉前一句、repair 直接删掉
# 之后，这一句就成了没有前件的「反之，……」「但……」，用户读到的是半截话。
#
# 实测两次：一次答案开头就是悬空的「但」；一次（run_20260731_024144_312047）judge
# 判掉第 5 句「若次日跌停收缩…则技术性修复更可信」，第 6 句「反之，如果仅仅依靠权重
# 股拉升指数…」被保留，于是小标题下面第一句就是「反之」，前面什么都没有。
#
# 长的排在前面，避免「但是」被当成「但」、「与此相反」被当成「相反」。
_BACKREF_CONNECTIVES: tuple[str, ...] = (
    "与此相反",
    "相比之下",
    "反过来说",
    "反过来",
    "另一方面",
    "同样地",
    "同理",
    "反之",
    "相反",
    "然而",
    "但是",
    "不过",
    "因此",
    "所以",
    "于是",
    "否则",
    "但",
)
# 开头两个字碰巧相同，但不是转折连接词。
_BACKREF_FALSE_FRIENDS: tuple[str, ...] = ("但凡", "但愿", "但书")
_BACKREF_TRAILING_PUNCT = "，,、：:； ;"


def _strip_backref_connective(line: str) -> str:
    """删掉失去前件的回指连接词，句子其余部分原样保留。

    只在前一句确实被删掉时调用。删连接词而不是连带删掉整句：这一句本身是合规的、
    有绑定的内容，因为前一句被判掉就跟着丢，等于让一次 judge 拒绝吃掉两句话。

    返回空串表示这一行去掉连接词后没有正文了，调用方按整行丢弃处理。
    """

    prefix, text = _line_prefix_and_text(line)
    if text.startswith(_BACKREF_FALSE_FRIENDS):
        return line
    for connective in _BACKREF_CONNECTIVES:
        if not text.startswith(connective):
            continue
        remainder = text[len(connective) :].lstrip(_BACKREF_TRAILING_PUNCT)
        if not remainder or remainder.startswith("<!--"):
            return ""
        return f"{prefix}{remainder}"
    return line


def _claim_validation_text(
    claim: Claim,
    atoms: tuple[EvidenceAtom, ...],
) -> str:
    values = [
        claim.text,
        claim.theme,
        claim.company or "",
        claim.freshness or "",
        *claim.counter_evidence,
    ]
    for atom in atoms:
        values.extend(
            (
                atom.claim_text,
                atom.entity_id or "",
                atom.metric or "",
                str(atom.value) if atom.value is not None else "",
                atom.unit or "",
                atom.period or "",
                atom.source_date or "",
                " ".join(
                    str(value)
                    for key, value in atom.provenance.items()
                    if key != "claim_id"
                ),
            )
        )
    return "\n".join(value for value in values if value)


def _extract_json_object(text: str) -> dict[str, object] | None:
    stripped = text.strip()
    fence = re.search(
        r"```(?:json)?\s*(\{.*\})\s*```",
        stripped,
        re.DOTALL,
    )
    if fence is not None:
        stripped = fence.group(1)
    else:
        braces = re.search(r"\{.*\}", stripped, re.DOTALL)
        if braces is not None:
            stripped = braces.group(0)
    try:
        payload = json.loads(stripped)
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _normalize_number_token(token: str) -> str:
    normalized = token.strip()
    sign = ""
    if normalized.startswith(("+", "-")):
        sign, normalized = normalized[0], normalized[1:]
    integer, dot, fraction = normalized.partition(".")
    integer = integer.lstrip("0") or "0"
    fraction = fraction.rstrip("0")
    if sign == "+":
        sign = ""
    if integer == "0" and not fraction:
        sign = ""
    return f"{sign}{integer}{dot if fraction else ''}{fraction}"


def _expanded_date_text(text: str) -> str:
    expanded = text
    for year, month, day in re.findall(
        r"\b(20\d{2})-(\d{2})-(\d{2})\b",
        text,
    ):
        month_number = int(month)
        day_number = int(day)
        expanded += (
            f"\n{year}年{month_number}月{day_number}日"
            f"\n{month_number}月{day_number}日"
        )
    return expanded


def humanize(text: str) -> str:
    rendered = str(text or "")
    # 丢掉呈现层状态前缀（[missing]），但保留 KC-05 反方标记 [反]。
    rendered = re.sub(r"^\[(?!反\])[^\]]+\]\s*", "", rendered)
    rendered = re.sub(
        r"\b(20\d{2}-\d{2}-\d{2})-theme-candidates\.json\b",
        r"\1 题材候选快照",
        rendered,
    )
    for internal, public in _PRESENTER_REPLACEMENTS:
        rendered = rendered.replace(internal, public)
    rendered = re.sub(
        r"\b(?:fact|dim|feature|config)_[a-z0-9_]+\b",
        "本地结构化数据",
        rendered,
        flags=re.I,
    )
    rendered = re.sub(r"\bevidence_count\s*=\s*\d+\b", "", rendered, flags=re.I)
    rendered = re.sub(r"\bretrieval\b", "资料核验", rendered, flags=re.I)
    rendered = re.sub(r"\brerank\b", "相关性复核", rendered, flags=re.I)
    rendered = rendered.replace("检索失败", "该资料源本轮不可用，未用于结论")
    rendered = re.sub(r"\[([A-Z]\d+)\]", "", rendered)
    rendered = re.sub(
        r"(?<![\d.])-?\d+\.\d{4,}(?!\d)",
        lambda match: _format_decimal(match.group(0)),
        rendered,
    )
    rendered = re.sub(
        r"^信号\s+([^（]+)（-?\d+(?:\.\d+)?）：",
        r"\1：",
        rendered,
    )
    rendered = re.sub(
        r"市场占比(\d+(?:\.\d+)?)(?![%\d.])",
        r"市场占比\1%",
        rendered,
    )
    rendered = rendered.replace("容量前三=True", "且属于成交容量前三")
    rendered = rendered.replace("容量前三=False", "但未进入成交容量前三")
    rendered = re.sub(r"\bTrue\b", "是", rendered)
    rendered = re.sub(r"\bFalse\b", "否", rendered)
    rendered = rendered.replace("本地 本地市场数据库", "本地市场数据库")
    rendered = rendered.replace("盘面快照或导出数据", "历史盘面快照")
    rendered = re.sub(r"\s{2,}", " ", rendered)
    return rendered.strip()


def _load_config(path: Path) -> dict[str, object]:
    try:
        loaded: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _theme_name(query: str, matched_theme: str | None, aliases: tuple[str, ...]) -> str:
    quoted = re.search(r"[“《\"]([^”》\"]{2,40})[”》\"]", query)
    if quoted:
        return quoted.group(1).strip()
    for alias in sorted(aliases, key=len, reverse=True):
        if alias.lower() in query.lower():
            return alias
    return matched_theme or "未命名题材"


def _clean_line(text: str) -> str:
    return humanize(str(text or "").replace("\x00SUB\x00", "").strip(" -"))


def _normalize(text: str) -> str:
    return re.sub(r"[\W_]+", "", humanize(text).lower())


def _pin_recall_audit_claims(
    shown: Sequence[Claim],
    answer_spec: AnswerSpec,
) -> tuple[Claim, ...]:
    """前窗截断后仍把召回自评四问缺口钉进答案，避免被风险句挤掉。"""
    pinned = list(shown)
    seen = {_normalize(claim.text) for claim in pinned}
    for claim in answer_spec.gaps:
        if not claim.text.startswith("召回自评："):
            continue
        key = _normalize(claim.text)
        if key in seen:
            continue
        pinned.append(claim)
        seen.add(key)
    return tuple(pinned)


def _prompt_claim(claim: Claim) -> str:
    evidence = ",".join(claim.evidence_ids) or "无"
    company = f"｜公司={claim.company}" if claim.company else ""
    return (
        f"- [{claim.status.value}] {claim.text}{company}"
        f"｜证据={evidence}｜层级={claim.evidence_tier or '未评级'}"
    )


def _present_claim(claim: Claim) -> str:
    rendered = humanize(claim.text)
    if rendered.startswith("召回自评："):
        return rendered
    prefix = {
        ClaimStatus.VERIFIED: "",
        ClaimStatus.CANDIDATE: "当前判断（待验证）：",
        ClaimStatus.INFERRED: "",
        ClaimStatus.MISSING: "还缺：",
        ClaimStatus.CONFLICT: "风险：",
    }[claim.status]
    return prefix + rendered


def _present_summary_claim(claim: Claim) -> str:
    return humanize(claim.text)


def _summary_label(claim: Claim) -> str:
    if claim.claim_id == "summary:definition":
        return "题材是什么"
    if claim.claim_id in {"summary:market", "summary:market-gap"}:
        return "盘面判断"
    if claim.claim_id == "summary:company":
        return "公司判断"
    if claim.claim_id == "summary:company-gap":
        return "证据边界"
    return {
        ClaimStatus.VERIFIED: "已核验结论",
        ClaimStatus.CANDIDATE: "当前判断",
        ClaimStatus.INFERRED: "研究判断",
        ClaimStatus.MISSING: "证据边界",
        ClaimStatus.CONFLICT: "主要风险",
    }[claim.status]


def _present_supporting_fact(claim: Claim) -> str:
    rendered = humanize(claim.text).rstrip("。")
    label, separator, detail = rendered.partition("：")
    interpretation = next(
        (
            meaning
            for signal, meaning in _SIGNAL_INTERPRETATIONS
            if signal in label
        ),
        "",
    )
    if separator:
        statement = f"**{label}：** {detail.rstrip('。')}"
    else:
        statement = rendered
    if interpretation:
        statement += (
            f"。这{interpretation}"
            if interpretation.startswith("说明")
            else f"。{interpretation}"
        )
    statement = statement.rstrip("。") + "。"
    note = _single_source_note(claim)
    if note:
        statement = statement.rstrip("。") + note + "。"
    return statement


def _company_tier_label(tier: CompanyTier) -> str:
    return {
        CompanyTier.CORE: "核心",
        CompanyTier.CANDIDATE: "候选",
        CompanyTier.PERIPHERAL: "外围",
    }[tier]


def _company_directness_label(directness: str) -> str:
    return {
        "core": "直接",
        "direct": "直接",
        "strong": "较直接",
        "related": "相关",
        "indirect": "间接",
        "peripheral": "间接",
        "weak": "较间接",
    }.get(str(directness).strip().lower(), humanize(directness))


def _company_evidence_label(
    company: CompanyAssessment,
    sources: tuple[EvidenceRef, ...],
) -> str:
    if any(
        claim_has_resolved_hard_company_evidence(claim, sources)
        for claim in company.claims
    ):
        return "已绑定公司级硬证据"
    if company.claims:
        return "候选资料，需公告或年报确认"
    return "仅有概念关联，未发现公司级证据"


def _company_table_row(
    company: CompanyAssessment,
    sources: tuple[EvidenceRef, ...],
) -> str:
    return (
        "| "
        + " | ".join(
            (
                company.company
                + (f"（{company.ticker}）" if company.ticker else ""),
                humanize(company.chain_stage),
                _company_directness_label(company.directness),
                _company_tier_label(company.tier),
                _company_evidence_label(company, sources),
            )
        )
        + " |"
    )


def _dedupe(items: tuple[str, ...] | list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        cleaned = humanize(item)
        cleaned = re.sub(r"^(?:核验动作|下一步|建议)[:：]\s*", "", cleaned)
        key = _normalize(cleaned)
        if not cleaned or not key or key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def _dedupe_claims(items: tuple[Claim, ...]) -> tuple[Claim, ...]:
    seen: set[str] = set()
    result: list[Claim] = []
    for claim in items:
        key = _normalize(claim.text)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(claim)
    return tuple(result)


def _format_decimal(value: str) -> str:
    number = round(float(value), 2)
    if number.is_integer():
        return str(int(number))
    return f"{number:.2f}".rstrip("0").rstrip(".")


def _present_sources(sources: tuple[EvidenceRef, ...]) -> list[str]:
    grouped: dict[tuple[str, str], list[str]] = {}
    for source in sources:
        source_name = humanize(source.source)
        detail = humanize(source.detail)
        key = (source_name, detail)
        grouped.setdefault(key, []).append(source.evidence_id)
    rows: list[str] = []
    for (source_name, detail), evidence_ids in grouped.items():
        label = _format_evidence_ids(evidence_ids)
        prefix = f"[{label}] " if label else ""
        rows.append(prefix + source_name + (f" — {detail}" if detail else ""))
    return [f"- {row}" for row in rows]


def _format_evidence_ids(evidence_ids: list[str]) -> str:
    unique_ids = list(dict.fromkeys(evidence_ids))
    if unique_ids == ["ONTOLOGY"]:
        return "研究框架"
    if len(unique_ids) == 1:
        return unique_ids[0]
    parsed = [re.fullmatch(r"([A-Z])(\d+)", evidence_id) for evidence_id in unique_ids]
    if all(match is not None for match in parsed):
        prefixes = {match.group(1) for match in parsed if match is not None}
        numbers = [int(match.group(2)) for match in parsed if match is not None]
        if (
            len(prefixes) == 1
            and numbers == list(range(numbers[0], numbers[0] + len(numbers)))
        ):
            prefix = prefixes.pop()
            return f"{prefix}{numbers[0]}–{prefix}{numbers[-1]}"
    return "、".join(unique_ids)
