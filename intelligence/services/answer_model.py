"""Structured adjudication and presentation boundary for research answers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "theme_research_specs.json"
_CITATION_RE = re.compile(r"\[([A-Z]\d+)\]")
_DATE_RE = re.compile(r"\b20\d{2}[-/.年]\d{1,2}(?:[-/.月]\d{1,2}日?)?\b")
_NUMBER_WITH_UNIT_RE = re.compile(
    r"(?<![A-Za-z])\d+(?:\.\d+)?\s*(?:%|亿|万|家|只|日|天|年|月|元|倍|个)"
)
_COMPANY_RE = re.compile(
    r"[\u4e00-\u9fff]{2,10}(?:股份|科技|集团|电子|材料|信息|软件|智能|银行|证券)"
)
_ENGINEERING_TERMS = (
    "graph_only",
    "exposure_only",
    "L1_L3_candidate",
    "retrieval",
    "rerank",
    "Run ID",
    "run_id",
    "Daily Review",
)
_PRESENTER_REPLACEMENTS = (
    ("graph_only", "仅有概念关联，未发现公司级证据"),
    ("exposure_only", "仅有概念关联，未发现公司级证据"),
    ("L1_L3_candidate", "候选资料，需公告或年报确认"),
    ("L1/L2/L3/L4", "行业资料、公司资料、公告硬证据和盘面信号"),
    ("L1", "行业资料"),
    ("L2", "公司基础资料"),
    ("L3", "公告等硬证据"),
    ("L4", "盘面信号"),
    ("disclosure-archive → apply", "公告与年报核验"),
    ("disclosure-archive", "公告与年报核验"),
    ("concept-ingest", "补充题材概念登记"),
    ("evidence_index", "证据索引"),
    ("wiki 向量", "知识库语义检索"),
    ("DuckDB", "本地市场数据库"),
    ("snapshot/export", "盘面快照或导出数据"),
)


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

    def to_dict(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "source": self.source,
            "detail": self.detail,
            "tier": self.tier,
            "source_date": self.source_date,
            "freshness": self.freshness,
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
    prompt_constraints: tuple[str, ...] = ()
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
            "next_actions": list(self.next_actions),
            "sources": [source.to_dict() for source in self.sources],
            "system_notices": list(self.system_notices),
            "prompt_constraints": list(self.prompt_constraints),
            "quality": self.quality.to_dict(),
        }

    def to_prompt_block(self) -> str:
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
        return "\n".join(lines)


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
    )


def build_company_assessments(
    candidates: list[CompanyCandidate],
    claims: list[Claim],
) -> tuple[CompanyAssessment, ...]:
    assessments: list[CompanyAssessment] = []
    for candidate in candidates:
        company_claims = tuple(claim for claim in claims if claim.company == candidate.company)
        verified = any(claim.status == ClaimStatus.VERIFIED for claim in company_claims)
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


def finalize_answer_spec(answer_spec: AnswerSpec) -> AnswerSpec:
    return replace(answer_spec, quality=evaluate_answer_spec(answer_spec))


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
            claim.status == ClaimStatus.VERIFIED for claim in company.claims
        ):
            issues.append(
                QualityIssue(
                    "core_company_without_verified_evidence",
                    "error",
                    f"{company.company} 被列为核心，但没有公司级已核验证据。",
                )
            )
    all_claims = (
        *answer_spec.summary,
        *answer_spec.verified_facts,
        *answer_spec.counter_evidence,
        *answer_spec.gaps,
        *answer_spec.triggers,
    )
    if any(claim.theme != answer_spec.research_spec.theme for claim in all_claims):
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
    leaked = [term for term in _ENGINEERING_TERMS if term in visible_text]
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


def render_answer_spec(answer_spec: AnswerSpec) -> str:
    lines: list[str] = []
    notices = _dedupe(answer_spec.system_notices)
    if notices:
        lines.append(humanize(notices[0]))
        lines.append("")
    lines.append("## 三行结论")
    for claim in answer_spec.summary[:3]:
        lines.append(f"- {_present_claim(claim)}")
    lines.extend(["", "## 公司证据表"])
    if answer_spec.company_table:
        lines.extend(
            [
                "| 公司 | 产业链位置 | 直接性 | 分层 | 证据状态 |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for company in answer_spec.company_table:
            lines.append(
                "| "
                + " | ".join(
                    (
                        company.company + (f"（{company.ticker}）" if company.ticker else ""),
                        humanize(company.chain_stage),
                        humanize(company.directness),
                        _company_tier_label(company.tier),
                        _company_evidence_label(company),
                    )
                )
                + " |"
            )
    else:
        lines.append("- 未形成可展示的公司级证据表。")
    lines.extend(["", "## 最大缺口与反证"])
    risk_claims = _dedupe_claims((*answer_spec.counter_evidence, *answer_spec.gaps))
    for claim in risk_claims[:4]:
        lines.append(f"- {_present_claim(claim)}")
    lines.extend(["", "## 下一步核验"])
    for action in _dedupe(answer_spec.next_actions)[:4]:
        lines.append(f"- {humanize(action)}")
    detail_lines: list[str] = []
    if answer_spec.verified_facts:
        detail_lines.extend(["### 已核验事实"])
        detail_lines.extend(
            f"- {humanize(claim.text)}" for claim in _dedupe_claims(answer_spec.verified_facts)
        )
    if answer_spec.triggers:
        detail_lines.extend(["", "### 触发条件"])
        detail_lines.extend(
            f"- {humanize(claim.text)}" for claim in _dedupe_claims(answer_spec.triggers)
        )
    if answer_spec.sources:
        detail_lines.extend(["", "### 完整来源"])
        detail_lines.extend(
            f"- [{source.evidence_id}] {humanize(source.source)}"
            + (f" — {humanize(source.detail)}" if source.detail else "")
            for source in answer_spec.sources
        )
    if len(notices) > 1:
        detail_lines.extend(["", "### 检索状态"])
        detail_lines.extend(f"- {humanize(notice)}" for notice in notices[1:])
    if detail_lines:
        lines.extend(["", "<details><summary>展开盘面、来源与检索状态</summary>", ""])
        lines.extend(detail_lines)
        lines.extend(["", "</details>"])
    return "\n".join(lines).rstrip() + "\n"


def validate_llm_answer(answer: str, answer_spec: AnswerSpec) -> tuple[QualityIssue, ...]:
    allowed = render_answer_spec(answer_spec) + "\n" + answer_spec.to_prompt_block()
    issues: list[QualityIssue] = []
    leaked = [term for term in _ENGINEERING_TERMS if term in answer]
    if leaked:
        issues.append(
            QualityIssue(
                "llm_engineering_term_leak",
                "error",
                f"LLM 输出内部术语：{'、'.join(leaked)}",
            )
        )
    new_numbers = sorted(
        {
            token
            for token in (*_NUMBER_WITH_UNIT_RE.findall(answer), *_DATE_RE.findall(answer))
            if token not in allowed
        }
    )
    if new_numbers:
        issues.append(
            QualityIssue(
                "llm_added_number",
                "error",
                f"LLM 增加 AnswerSpec 中不存在的数字：{'、'.join(new_numbers[:5])}",
            )
        )
    allowed_companies = {company.company for company in answer_spec.company_table}
    new_companies = sorted(
        {
            company
            for company in _COMPANY_RE.findall(answer)
            if company not in allowed_companies and company not in allowed
        }
    )
    if new_companies:
        issues.append(
            QualityIssue(
                "llm_added_company",
                "error",
                f"LLM 增加 AnswerSpec 中不存在的公司：{'、'.join(new_companies[:5])}",
            )
        )
    if "已证实" in answer and not answer_spec.verified_facts:
        issues.append(
            QualityIssue(
                "llm_promoted_candidate",
                "error",
                "LLM 在没有 verified_facts 时使用了“已证实”。",
            )
        )
    return tuple(issues)


def humanize(text: str) -> str:
    rendered = str(text or "")
    rendered = re.sub(r"^\[[^\]]+\]\s*", "", rendered)
    for internal, public in _PRESENTER_REPLACEMENTS:
        rendered = rendered.replace(internal, public)
    rendered = rendered.replace("检索失败", "该资料源本轮不可用，未用于结论")
    rendered = re.sub(r"\[([A-Z]\d+)\]", "", rendered)
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
    return matched_theme or query.strip() or "未命名题材"


def _clean_line(text: str) -> str:
    return humanize(str(text or "").replace("\x00SUB\x00", "").strip(" -"))


def _normalize(text: str) -> str:
    return re.sub(r"[\W_]+", "", humanize(text).lower())


def _prompt_claim(claim: Claim) -> str:
    evidence = ",".join(claim.evidence_ids) or "无"
    company = f"｜公司={claim.company}" if claim.company else ""
    return (
        f"- [{claim.status.value}] {claim.text}{company}"
        f"｜证据={evidence}｜层级={claim.evidence_tier or '未评级'}"
    )


def _present_claim(claim: Claim) -> str:
    prefix = {
        ClaimStatus.VERIFIED: "",
        ClaimStatus.CANDIDATE: "候选判断：",
        ClaimStatus.INFERRED: "研究口径：",
        ClaimStatus.MISSING: "证据缺口：",
        ClaimStatus.CONFLICT: "反证：",
    }[claim.status]
    return prefix + humanize(claim.text)


def _company_tier_label(tier: CompanyTier) -> str:
    return {
        CompanyTier.CORE: "核心",
        CompanyTier.CANDIDATE: "候选",
        CompanyTier.PERIPHERAL: "外围",
    }[tier]


def _company_evidence_label(company: CompanyAssessment) -> str:
    if any(claim.status == ClaimStatus.VERIFIED for claim in company.claims):
        return "已绑定公司级硬证据"
    if company.claims:
        return "候选资料，需公告或年报确认"
    return "仅有概念关联，未发现公司级证据"


def _dedupe(items: tuple[str, ...] | list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        cleaned = humanize(item)
        key = _normalize(
            re.sub(r"^(?:核验动作|下一步|建议)[:：]\s*", "", cleaned)
        )
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
