"""Daily Agent 专用 Answer Contract。

Canonical Daily Agent JSON 中的结构化事实（题材、优先级、生命周期、盘面指标、
证据缺口、建议动作）直接进入 typed EvidenceAtom 与语义命题 claim，
不经过通用 `_module_fact_lines()` 的字符串扁平化，也不保存最终中文文案。
最终措辞由 Grounded Composer 在证据边界内生成。
"""

from __future__ import annotations

from collections.abc import Mapping

from intelligence.services import answer_model
from intelligence.services.research_contract import EvidenceAtom
from intelligence.workbench_skills.contracts import SkillAnswerContract

DAILY_AGENT_PRESENTATION_KIND = answer_model.DAILY_AGENT_PRESENTATION_KIND

_MAX_THEMES_PER_GROUP = 6
_MAX_GAP_CLAIMS = 8
_MAX_TRIGGER_CLAIMS = 8
_MAX_ACTIONS = 8

_CLASSIFICATION_LABELS = {
    "old_logic_wakeup": "旧逻辑重新活跃",
    "new_logic_candidate": "新逻辑候选",
    "data_gap": "数据待补",
    "noise_or_unconfirmed": "待确认信号",
}

_QUEUE_LABELS = {
    "today_do_ima": "补题材研究",
    "today_find_official_evidence": "补官方证据",
    "today_wait_market_validation": "等待市场验证",
    "today_downgrade_or_watch": "降级观察",
}

_MARKET_METRIC_KEYS = ("涨停数", "新高数", "触发信号数", "强势股数")

# 内部研究流水线术语 → 用户可读的市场语言。
# 顺序敏感：长 token 在前，避免「L2 基线」被拆成「L2」+「基线」两次替换。
_JARGON_REWRITES: tuple[tuple[str, str], ...] = (
    ("L2_baseline", "公司基本面基础资料"),
    ("L3_official", "公告、调研等官方硬证据"),
    ("L2 基线", "公司基本面基础资料"),
    ("L3 官方验证", "公告、调研等官方硬证据"),
    ("L2基线", "公司基本面基础资料"),
    ("L3官方验证", "公告、调研等官方硬证据"),
    ("L2", "公司基本面基础资料"),
    ("L3", "公告、调研等官方硬证据"),
    ("IMA", "题材深度研究"),
)

_STATUS_REWRITES = {
    "盘面触发待解释": "盘面已异动，但还没找到对应的消息面解释",
    "旧逻辑待验证": "旧逻辑被重新炒作，但尚未被新证据确认",
}


def _plain(text: str) -> str:
    for token, replacement in _JARGON_REWRITES:
        text = text.replace(token, replacement)
    return text


def _plain_status(text: str) -> str:
    return _STATUS_REWRITES.get(text, _plain(text))


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _strings(value: object, *, limit: int | None = None) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    items = tuple(
        item.strip() for item in value if isinstance(item, str) and item.strip()
    )
    return items if limit is None else items[:limit]


def _number(value: object) -> float | int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def _theme_name(candidate: Mapping[str, object]) -> str:
    return _text(candidate.get("matched_theme")) or _text(candidate.get("query"))


def _candidate_atoms(
    *,
    claim_id: str,
    theme: str,
    candidate: Mapping[str, object],
    classification: str,
    source: str,
    source_id: str,
    as_of: str | None,
) -> tuple[EvidenceAtom, ...]:
    lifecycle = _mapping(candidate.get("logic_lifecycle") or candidate.get("生命周期"))
    judgment = _mapping(candidate.get("research_judgment"))
    validation = _mapping(
        candidate.get("market_validation") or candidate.get("盘面验证")
    )
    market = _mapping(validation.get("当前盘面"))
    provenance_base = {
        "claim_id": claim_id,
        "source": source,
        "classification": classification,
    }

    def atom(
        field: str,
        claim_text: str,
        *,
        metric: str | None = None,
        value: str | int | float | None = None,
        unit: str | None = None,
        entity_id: str | None = None,
    ) -> EvidenceAtom:
        return EvidenceAtom(
            atom_id=f"{claim_id}:{field}",
            claim_text=claim_text,
            entity_id=entity_id or theme,
            metric=metric,
            value=value,
            unit=unit,
            period=as_of,
            evidence_tier="canonical",
            source_id=source_id,
            source_date=as_of,
            provenance={**provenance_base, "field": field},
        )

    atoms: list[EvidenceAtom] = []
    priority = _number(candidate.get("priority_score"))
    if priority is not None:
        atoms.append(
            atom(
                "priority",
                f"{theme} 当前研究优先级为 {priority}",
                metric="priority_score",
                value=priority,
            )
        )
    stage = _text(lifecycle.get("生命周期阶段"))
    if stage:
        atoms.append(
            atom(
                "lifecycle",
                f"{theme} 生命周期阶段为「{stage}」",
                metric="lifecycle_stage",
                value=stage,
            )
        )
        # 报告里的阶段词是八阶段诊断（读法层别名，工单 #21 剩余 / G-04）；旁边并排给出七段钦定词，
        # 让消费方能和旁路库 lifecycle_stage / 河的 stage 对象对上。翻译不到（不在任何词表）就不加，不猜。
        try:
            from intelligence.services.theme_stage_vocab import GAP, canonical_of

            tr = canonical_of(stage)
        except ValueError:
            tr = None
        if tr is not None and tr.canonical != GAP:
            atoms.append(
                atom(
                    "lifecycle_canonical",
                    f"{theme} 生命周期七段钦定词为「{tr.canonical}」"
                    + ("（八阶段一词对两段，按持续态取）" if tr.ambiguous else ""),
                    metric="lifecycle_stage_canonical",
                    value=tr.canonical,
                )
            )
    stage_change = _text(lifecycle.get("阶段变化"))
    if stage_change:
        atoms.append(
            atom(
                "lifecycle_change",
                f"{theme} 生命周期边际变化：{stage_change}",
                metric="lifecycle_change",
                value=stage_change,
            )
        )
    strength = _text(validation.get("盘面验证强度"))
    if strength:
        atoms.append(
            atom(
                "validation_strength",
                f"{theme} 盘面验证强度为「{strength}」",
                metric="validation_strength",
                value=strength,
            )
        )
    for key in _MARKET_METRIC_KEYS:
        value = _number(market.get(key))
        if value is not None:
            atoms.append(
                atom(
                    f"market:{key}",
                    f"{theme} 当前盘面{key}为 {value}",
                    metric=key,
                    value=value,
                    unit="只" if key in {"涨停数", "新高数", "强势股数"} else "类",
                )
            )
    changes = _mapping(validation.get("边际变化"))
    for key, raw in changes.items():
        delta = _number(raw)
        if delta is None:
            continue
        atoms.append(
            atom(
                f"delta:{key}",
                f"{theme} {key}相对上一观察日变化 {delta:+g}",
                metric=f"{key}边际变化",
                value=delta,
            )
        )
    status = _text(judgment.get("证据状态")) or _text(lifecycle.get("证据状态"))
    if status:
        atoms.append(
            atom(
                "evidence_status",
                f"{theme} 证据现状：{_plain_status(status)}",
                metric="evidence_status",
                value=status,
            )
        )
    for index, layer in enumerate(
        _strings(judgment.get("缺失证据层"), limit=4), start=1
    ):
        atoms.append(
            atom(
                f"gap:{index}",
                f"{theme} 目前还缺：{_plain(layer)}",
                metric="evidence_gap",
                value=layer,
            )
        )
    action = _text(judgment.get("建议动作"))
    if action:
        atoms.append(
            atom(
                "action",
                f"{theme} 下一步：{_plain(action)}",
                metric="action_code",
                value=action,
            )
        )
    for index, stock in enumerate(
        _strings(candidate.get("strong_stocks"), limit=5), start=1
    ):
        atoms.append(
            atom(
                f"stock:{index}",
                f"{stock} 属于 {theme} 当前强势股",
                metric="strong_stock",
                value=stock,
                entity_id=stock,
            )
        )
    return tuple(atoms)


def _candidate_proposition(
    theme: str,
    candidate: Mapping[str, object],
    classification: str,
) -> str:
    lifecycle = _mapping(candidate.get("logic_lifecycle") or candidate.get("生命周期"))
    judgment = _mapping(candidate.get("research_judgment"))
    validation = _mapping(
        candidate.get("market_validation") or candidate.get("盘面验证")
    )
    market = _mapping(validation.get("当前盘面"))
    parts = [f"分类={_CLASSIFICATION_LABELS.get(classification, classification)}"]
    stage = _text(lifecycle.get("生命周期阶段"))
    if stage:
        parts.append(f"生命周期={stage}")
    strength = _text(validation.get("盘面验证强度"))
    if strength:
        parts.append(f"盘面验证强度={strength}")
    for key in ("涨停数", "新高数"):
        value = _number(market.get(key))
        if value is not None:
            parts.append(f"{key}={value}")
    status = _text(judgment.get("证据状态")) or _text(lifecycle.get("证据状态"))
    if status:
        parts.append(f"证据现状={_plain_status(status)}")
    stocks = _strings(candidate.get("strong_stocks"), limit=3)
    if stocks:
        parts.append(f"强势股={'、'.join(stocks)}")
    return f"{theme}：{'；'.join(parts)}"


def build_daily_agent_answer_contract(
    payload: Mapping[str, object],
    *,
    source: str,
    as_of: str | None,
    warnings: list[str],
    retrieval_plan: tuple[str, ...],
    output_contract: tuple[str, ...],
) -> SkillAnswerContract | None:
    decision = _mapping(payload.get("decision"))
    queue = _mapping(payload.get("research_queue"))
    if not decision and not queue:
        return None
    title = "研究雷达"
    source_id = "K1"
    sources = (
        answer_model.EvidenceRef(
            evidence_id=source_id,
            source="Canonical Daily Agent",
            detail=source,
            tier="canonical",
            source_date=as_of,
        ),
    )
    atoms: list[EvidenceAtom] = []
    verified: list[answer_model.Claim] = []
    counter: list[answer_model.Claim] = []
    gap_claims: list[answer_model.Claim] = []
    trigger_claims: list[answer_model.Claim] = []
    classification_counts: dict[str, int] = {}

    for classification in _CLASSIFICATION_LABELS:
        candidates = decision.get(classification)
        if not isinstance(candidates, list):
            continue
        mappings = [item for item in candidates if isinstance(item, Mapping)]
        classification_counts[classification] = len(mappings)
        for candidate in mappings[:_MAX_THEMES_PER_GROUP]:
            theme = _theme_name(candidate)
            if not theme:
                continue
            claim_id = f"daily-agent:theme:{classification}:{theme}"
            claim = answer_model.make_claim(
                claim_id=claim_id,
                text=_candidate_proposition(theme, candidate, classification),
                claim_type="daily_agent_theme",
                theme=theme,
                status=(
                    answer_model.ClaimStatus.VERIFIED
                    if classification
                    in {"old_logic_wakeup", "new_logic_candidate"}
                    else answer_model.ClaimStatus.CANDIDATE
                ),
                evidence_tier="canonical",
                evidence_ids=(source_id,),
            )
            if classification in {"old_logic_wakeup", "new_logic_candidate"}:
                verified.append(claim)
            else:
                counter.append(claim)
            atoms.extend(
                _candidate_atoms(
                    claim_id=claim_id,
                    theme=theme,
                    candidate=candidate,
                    classification=classification,
                    source=source,
                    source_id=source_id,
                    as_of=as_of,
                )
            )
            judgment = _mapping(candidate.get("research_judgment"))
            for index, layer in enumerate(
                _strings(judgment.get("缺失证据层"), limit=4), start=1
            ):
                if len(gap_claims) >= _MAX_GAP_CLAIMS:
                    break
                gap_claims.append(
                    answer_model.make_claim(
                        claim_id=f"{claim_id}:gap:{index}",
                        text=f"{theme} 目前还缺：{_plain(layer)}",
                        claim_type="daily_agent_gap",
                        theme=theme,
                        status=answer_model.ClaimStatus.MISSING,
                        evidence_tier="canonical",
                        evidence_ids=(source_id,),
                    )
                )
            action = _text(judgment.get("建议动作"))
            if action and len(trigger_claims) < _MAX_TRIGGER_CLAIMS:
                trigger_claims.append(
                    answer_model.make_claim(
                        claim_id=f"{claim_id}:action",
                        text=f"{theme} 下一步核验动作：{_plain(action)}",
                        claim_type="daily_agent_action",
                        theme=theme,
                        status=answer_model.ClaimStatus.INFERRED,
                        evidence_tier="canonical",
                        evidence_ids=(source_id,),
                    )
                )

    queue_summary = _mapping(queue.get("summary"))
    queue_counts = {
        key: _number(queue_summary.get(key)) for key in _QUEUE_LABELS
    }
    total = _number(queue_summary.get("total"))
    summary_parts = [
        f"{_CLASSIFICATION_LABELS[key]} {count} 个"
        for key, count in classification_counts.items()
        if count
    ]
    if total is not None:
        summary_parts.append(f"今日研究队列共 {total:g} 项")
    summary_parts.extend(
        f"{_QUEUE_LABELS[key]} {value:g} 项"
        for key, value in queue_counts.items()
        if value
    )
    if not summary_parts and not verified and not counter:
        return None
    summary_claim = answer_model.make_claim(
        claim_id="daily-agent:summary",
        text=(
            f"截至 {as_of}，研究雷达结构：{'；'.join(summary_parts)}"
            if as_of
            else f"研究雷达结构：{'；'.join(summary_parts)}"
        ),
        claim_type="daily_agent_summary",
        theme=title,
        status=answer_model.ClaimStatus.VERIFIED,
        evidence_tier="canonical",
        evidence_ids=(source_id,),
    )

    actions: list[str] = []
    for queue_key, label in _QUEUE_LABELS.items():
        entries = queue.get(queue_key)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, Mapping) or len(actions) >= _MAX_ACTIONS:
                break
            target = _text(entry.get("目标"))
            action = _text(entry.get("建议动作"))
            if target and action:
                actions.append(f"{label}｜{target}：{_plain(action)}")
            elif target:
                actions.append(f"{label}｜{target}")
    if not actions:
        actions.append("按今日研究队列优先级继续验证证据缺口。")

    if not gap_claims:
        gap_claims.append(
            answer_model.make_claim(
                claim_id="daily-agent:gap:scope",
                text="当前结论只覆盖 canonical 研究队列，未覆盖的信息保持未知。",
                claim_type="daily_agent_gap",
                theme=title,
                status=answer_model.ClaimStatus.MISSING,
            )
        )
    if not trigger_claims:
        trigger_claims.append(
            answer_model.make_claim(
                claim_id="daily-agent:trigger:default",
                text="若题材优先级、盘面验证强度或证据状态出现反向变化，当前判断应降级。",
                claim_type="daily_agent_trigger",
                theme=title,
                status=answer_model.ClaimStatus.INFERRED,
                evidence_ids=(source_id,),
            )
        )

    spec = answer_model.AnswerSpec(
        research_spec=answer_model.resolve_theme_research_spec(title, title),
        summary=(summary_claim,),
        verified_facts=tuple(verified),
        company_table=(),
        counter_evidence=tuple(counter),
        gaps=tuple(
            (
                *gap_claims,
                *(
                    answer_model.make_claim(
                        claim_id=f"daily-agent:warning:{index}",
                        text=warning,
                        claim_type="daily_agent_warning",
                        theme=title,
                        status=answer_model.ClaimStatus.MISSING,
                    )
                    for index, warning in enumerate(warnings, start=1)
                ),
            )
        ),
        triggers=tuple(trigger_claims),
        next_actions=tuple(actions),
        sources=sources,
        system_notices=(),
        prompt_constraints=(
            *(f"检索计划：{item}" for item in retrieval_plan),
            *(f"输出契约：{item}" for item in output_contract),
        ),
        presentation_kind=DAILY_AGENT_PRESENTATION_KIND,
        presentation_title=title,
        research_evidence_atoms=tuple(atoms),
    )
    return SkillAnswerContract(
        retrieval_plan=retrieval_plan,
        output_contract=output_contract,
        answer_spec=answer_model.finalize_answer_spec(spec),
    )
