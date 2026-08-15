"""user_memory 离线候选更新链（S6）：扩 forecast_learning_loop 骨架到记忆平面。

对照 agent book 第 8 章「在线只记录证据 → 离线生成候选 → 验证后发布 → 可回滚」：
在线记录证据的台账已齐（corrections / checkpoints / verdicts / interactions），
缺的是「候选」这一层。本模块把 `forecast_learning_loop` 在双盲复盘平面上的
同一骨架（候选与正式能力隔离、门禁批准、拒绝也留档）接到 user_memory 平面：

1. **离线扫描**用户台账（`.foresight/` 即 ``users/<id>/`` 目录，见 userspace）；
2. **规则化候选生成**（v1，宁缺勿滥）：
   - ``repeated_correction_same_theme``：同一主题 ≥2 条同向 correction
     （方向键 = 归一化 principle/correction 文本，相等或包含视为同向）；
   - ``verdict_overturned_by_user``：同一 checkpoint 的机判终态 verdict
     被之后的人工终态 verdict 翻案（verdict 值不同）；
3. **提交既有 memory_gate** 走 candidate→accepted 晋升（本模块不复制判据、
   不改判据）；accepted 的候选只经 gate 认证写入口落盘：
   - ``user_correction`` → :func:`corrections.record_validated_preference`；
   - ``decision_lesson`` → :func:`judgments.record_validated_judgment`；
   两个写入口内部都经 :func:`memory_gate.promotion_metadata` 把内容 SHA-256
   与 gate 决定绑死——**没有绕过 gate 的直写路径**（单测钉住）；
4. **全部候选留档**到 ``users/<id>/memory_candidates.jsonl``（append-only），
   每行带完整归因链 ``{source_record_ids, trigger_rule, generated_at}`` 与
   gate 决定（拒绝的带理由）——回答「这条经验从哪来」，回滚时可反查。

幂等：candidate_id 由「规则 + 晋升锚点 + 内容 SHA-256」稳定派生；已在档的
candidate_id 不再重产。同一台账重跑第二次零新候选。

生命周期：produced → gated(accepted/rejected) → （既有）invalidated
（accepted 记录之后仍可用 memory_status 归档/撤销，本模块不新增退出语义）。

本模块只用标准库，不依赖 duckdb / 联网，可离线运行、可独立单测。
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from intelligence.services import corrections as corrections_svc
from intelligence.services import interactions as interactions_svc
from intelligence.services.checkpoints import (
    TERMINAL_VERDICTS,
    load_checkpoints,
    load_verdicts,
)
from intelligence.services.corrections import record_validated_preference
from intelligence.services.judgments import record_validated_judgment
from intelligence.services.memory_gate import MemoryCandidate, MemoryGate

SCHEMA_VERSION = "1.0"
CANDIDATES_FILENAME = "memory_candidates.jsonl"
CANDIDATE_RECORD_TYPE = "memory_candidate"

RULE_REPEATED_CORRECTION = "repeated_correction_same_theme"
RULE_VERDICT_OVERTURNED = "verdict_overturned_by_user"

# 同一主题内触发候选所需的同向 correction 条数（v1 判据，spec §3）。
MIN_SAME_DIRECTION_CORRECTIONS = 2
# 方向键短于该长度时只认相等，不认包含（避免「配额」这类短词把不同向的并成一簇）。
_MIN_CONTAINMENT_KEY_LEN = 4


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _norm(text: Any) -> str:
    return re.sub(r"\s+", "", str(text or "")).lower()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _candidate_id(*parts: str) -> str:
    return f"mc-{_sha256('|'.join(parts))[:16]}"


@dataclass(frozen=True)
class CandidateProposal:
    """一条规则化产出的候选（还没过 gate）。

    ``source_record_ids`` 是归因链主体：``correction:<ts>`` / ``checkpoint:<id>``
    / ``verdict:<id>@<checked_at>``，与各台账现行记录身份口径一致（Q3 未改前
    corrections 的身份就是 ts）。
    """

    candidate_id: str
    kind: str  # user_correction | decision_lesson
    content: str
    trigger_rule: str
    source_record_ids: tuple[str, ...]
    themes: tuple[str, ...] = ()
    stocks: tuple[str, ...] = ()
    correction_ts: str = ""
    checkpoint_id: str = ""


def _direction_key(record: dict[str, Any]) -> str:
    """一条 correction 的「方向键」：principle 优先（最该被记住的部分），否则 correction。"""
    return _norm(record.get("principle") or record.get("correction"))


def _same_direction(key_a: str, key_b: str) -> bool:
    if not key_a or not key_b:
        return False
    if key_a == key_b:
        return True
    shorter, longer = sorted((key_a, key_b), key=len)
    if len(shorter) < _MIN_CONTAINMENT_KEY_LEN:
        return False
    return shorter in longer


def _correction_anchor_content(record: dict[str, Any]) -> str:
    """晋升内容 = 锚点记录的 principle（优先）或 correction 原文。

    必须逐字取自台账原文：gate 的 correction 判据要求内容与 correction_ts
    指向的那条记录逐字匹配，改写一个字都过不了门。
    """
    principle = str(record.get("principle") or "").strip()
    return principle or str(record.get("correction") or "").strip()


def _repeated_correction_proposals(
    records: list[dict[str, Any]],
) -> list[CandidateProposal]:
    """v1 规则一：同一主题 ≥2 条同向 correction → 产一条 user_correction 候选。"""
    by_theme: dict[str, list[dict[str, Any]]] = {}
    theme_labels: dict[str, str] = {}
    for rec in records:
        if not isinstance(rec, dict):
            continue
        # promotion 行是本回路自己的产物（accepted 写回），不再作规则输入，防自增殖。
        if rec.get("promotion"):
            continue
        if not str(rec.get("ts") or "").strip():
            continue
        for theme in rec.get("themes") or []:
            theme_norm = _norm(theme)
            if not theme_norm:
                continue
            by_theme.setdefault(theme_norm, []).append(rec)
            theme_labels.setdefault(theme_norm, str(theme).strip())

    proposals: dict[str, CandidateProposal] = {}
    for theme_norm in sorted(by_theme):
        clusters: list[dict[str, Any]] = []
        for rec in sorted(by_theme[theme_norm], key=lambda r: str(r.get("ts") or "")):
            key = _direction_key(rec)
            if not key:
                continue
            for cluster in clusters:
                if _same_direction(cluster["key"], key):
                    cluster["members"].append(rec)
                    break
            else:
                clusters.append({"key": key, "members": [rec]})
        for cluster in clusters:
            members = cluster["members"]
            if len(members) < MIN_SAME_DIRECTION_CORRECTIONS:
                continue
            anchor = members[-1]
            content = _correction_anchor_content(anchor)
            anchor_ts = str(anchor.get("ts") or "").strip()
            if not content or not anchor_ts:
                continue
            candidate_id = _candidate_id(
                RULE_REPEATED_CORRECTION, anchor_ts, _sha256(content)
            )
            source_ids = tuple(
                f"correction:{str(m.get('ts') or '').strip()}" for m in members
            )
            existing = proposals.get(candidate_id)
            if existing is not None:
                # 同一对记录带多个主题标签时合并归因，不重复产候选。
                merged_sources = tuple(
                    dict.fromkeys(existing.source_record_ids + source_ids)
                )
                merged_themes = tuple(
                    dict.fromkeys(existing.themes + (theme_labels[theme_norm],))
                )
                proposals[candidate_id] = CandidateProposal(
                    candidate_id=candidate_id,
                    kind="user_correction",
                    content=content,
                    trigger_rule=RULE_REPEATED_CORRECTION,
                    source_record_ids=merged_sources,
                    themes=merged_themes,
                    correction_ts=anchor_ts,
                )
                continue
            proposals[candidate_id] = CandidateProposal(
                candidate_id=candidate_id,
                kind="user_correction",
                content=content,
                trigger_rule=RULE_REPEATED_CORRECTION,
                source_record_ids=source_ids,
                themes=(theme_labels[theme_norm],),
                correction_ts=anchor_ts,
            )
    return [proposals[key] for key in sorted(proposals)]


def _find_overturn(
    verdict_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """按台账追加顺序找「机判终态在前、人工终态在后且值不同」的最近一次翻案。"""
    last_auto: dict[str, Any] | None = None
    overturn: tuple[dict[str, Any], dict[str, Any]] | None = None
    for row in verdict_rows:
        verdict = str(row.get("verdict") or "")
        if verdict not in TERMINAL_VERDICTS:
            continue
        if row.get("auto"):
            last_auto = row
        elif last_auto is not None and verdict != str(last_auto.get("verdict")):
            overturn = (last_auto, row)
    return overturn


def _overturned_verdict_proposals(
    checkpoints: list[dict[str, Any]],
    verdicts: list[dict[str, Any]],
) -> list[CandidateProposal]:
    """v1 规则二：机判 verdict 被用户翻案 → 产一条 decision_lesson 候选。"""
    checkpoint_by_id = {str(c.get("id") or ""): c for c in checkpoints if c.get("id")}
    verdicts_by_id: dict[str, list[dict[str, Any]]] = {}
    for row in verdicts:
        cid = str(row.get("id") or "").strip()
        if cid:
            verdicts_by_id.setdefault(cid, []).append(row)

    proposals: list[CandidateProposal] = []
    for cid in sorted(verdicts_by_id):
        checkpoint = checkpoint_by_id.get(cid)
        if checkpoint is None:
            continue  # 悬空 verdict 无 claim 可引用，不产候选（相邻缺陷另行登记）
        overturn = _find_overturn(verdicts_by_id[cid])
        if overturn is None:
            continue
        auto_row, manual_row = overturn
        claim = str(checkpoint.get("claim") or "").strip()
        category = str(checkpoint.get("category") or "").strip() or "未分类"
        auto_verdict = str(auto_row.get("verdict"))
        manual_verdict = str(manual_row.get("verdict"))
        content = (
            f"回检翻案（{category}）：可证伪点「{claim}」机判 {auto_verdict} "
            f"被人工改判 {manual_verdict}；下次同类判断先复核机检规格与证据口径，"
            f"再采信自动回检结论。"
        )
        candidate_id = _candidate_id(RULE_VERDICT_OVERTURNED, cid, _sha256(content))
        source_ids = (
            f"checkpoint:{cid}",
            f"verdict:{cid}@{str(auto_row.get('checked_at') or '').strip()}",
            f"verdict:{cid}@{str(manual_row.get('checked_at') or '').strip()}",
        )
        proposals.append(
            CandidateProposal(
                candidate_id=candidate_id,
                kind="decision_lesson",
                content=content,
                trigger_rule=RULE_VERDICT_OVERTURNED,
                source_record_ids=source_ids,
                themes=tuple(
                    str(t).strip() for t in (checkpoint.get("themes") or []) if str(t).strip()
                ),
                stocks=tuple(
                    str(s).strip() for s in (checkpoint.get("stocks") or []) if str(s).strip()
                ),
                checkpoint_id=cid,
            )
        )
    return proposals


def generate_candidates(
    corrections: list[dict[str, Any]],
    checkpoints: list[dict[str, Any]],
    verdicts: list[dict[str, Any]],
) -> list[CandidateProposal]:
    """纯函数：从台账记录产出全部 v1 候选（确定性排序，未过 gate）。"""
    return _repeated_correction_proposals(corrections) + _overturned_verdict_proposals(
        checkpoints, verdicts
    )


def load_candidate_archive(path: str | Path) -> list[dict[str, Any]]:
    """读取候选留档（append-only JSONL）。文件不存在时返回空列表。"""
    p = Path(path).expanduser()
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("record_type") == CANDIDATE_RECORD_TYPE:
            rows.append(row)
    return rows


def _append_archive_row(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


@dataclass
class LoopPaths:
    """一个用户目录下本回路读写的全部文件（读台账，写候选档 + 经 gate 的晋升）。"""

    root: Path
    corrections: Path = field(init=False)
    judgments: Path = field(init=False)
    checkpoints: Path = field(init=False)
    verdicts: Path = field(init=False)
    interactions: Path = field(init=False)
    archive: Path = field(init=False)

    def __post_init__(self) -> None:
        self.root = Path(self.root).expanduser()
        self.corrections = self.root / "corrections.jsonl"
        self.judgments = self.root / "judgments.jsonl"
        self.checkpoints = self.root / "checkpoints.jsonl"
        self.verdicts = self.root / "verdicts.jsonl"
        self.interactions = self.root / "interactions.jsonl"
        self.archive = self.root / CANDIDATES_FILENAME


def run_loop(
    user_root: str | Path,
    *,
    dry_run: bool = False,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """跑一轮离线候选更新：扫描 → 规则产候选 → gate 裁决 → 留档/晋升。

    幂等：已在档的 candidate_id 直接跳过。``dry_run=True`` 时不写任何文件，
    summary 里的 ``candidates`` 是「本会落盘」的行。
    """
    paths = LoopPaths(root=Path(user_root))
    correction_records, _ = corrections_svc.load_corrections(paths.corrections, window=0)
    checkpoint_records, _ = load_checkpoints(paths.checkpoints)
    verdict_records, _ = load_verdicts(paths.verdicts)
    interaction_records, _ = interactions_svc.load_interactions(paths.interactions, window=0)

    proposals = generate_candidates(correction_records, checkpoint_records, verdict_records)
    archived_ids = {
        str(row.get("candidate_id") or "") for row in load_candidate_archive(paths.archive)
    }

    gate = MemoryGate()
    stamp = generated_at or _now_iso()
    new_rows: list[dict[str, Any]] = []
    accepted = rejected = skipped_existing = 0

    for proposal in proposals:
        if proposal.candidate_id in archived_ids:
            skipped_existing += 1
            continue
        candidate = MemoryCandidate(
            candidate_id=proposal.candidate_id,
            kind=proposal.kind,  # type: ignore[arg-type]
            content=proposal.content,
            checkpoint_id=proposal.checkpoint_id,
            correction_ts=proposal.correction_ts,
        )
        decision = gate.decide(
            candidate,
            checkpoints=checkpoint_records,
            verdicts=verdict_records,
            corrections=correction_records,
        )
        row: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "record_type": CANDIDATE_RECORD_TYPE,
            "candidate_id": proposal.candidate_id,
            "kind": proposal.kind,
            "content": proposal.content,
            "trigger_rule": proposal.trigger_rule,
            "source_record_ids": list(proposal.source_record_ids),
            "themes": list(proposal.themes),
            "generated_at": stamp,
            "status": "accepted" if decision.eligible else "rejected",
            "gate": decision.to_dict(),
        }
        if decision.eligible:
            accepted += 1
            if not dry_run:
                # 唯一落 durable 层的路径：gate 认证写入口（内部经 promotion_metadata
                # 把内容 SHA-256 与决定绑死）。本模块不直写 corrections/judgments。
                if proposal.kind == "user_correction":
                    _, promoted = record_validated_preference(
                        paths.corrections,
                        preference=proposal.content,
                        decision=decision,
                        themes=list(proposal.themes),
                    )
                    row["promoted_to"] = paths.corrections.name
                else:
                    _, promoted = record_validated_judgment(
                        paths.judgments,
                        memo=proposal.content,
                        decision=decision,
                        themes=list(proposal.themes),
                        stocks=list(proposal.stocks),
                    )
                    row["promoted_to"] = paths.judgments.name
                row["promoted_ts"] = promoted["ts"]
        else:
            rejected += 1
        if not dry_run:
            _append_archive_row(paths.archive, row)
        new_rows.append(row)

    return {
        "user_dir": str(paths.root),
        "dry_run": dry_run,
        "scanned": {
            "corrections": len(correction_records),
            "checkpoints": len(checkpoint_records),
            "verdicts": len(verdict_records),
            "interactions": len(interaction_records),
        },
        "proposed": len(proposals),
        "skipped_existing": skipped_existing,
        "new": len(new_rows),
        "accepted": accepted,
        "rejected": rejected,
        "archive_path": str(paths.archive),
        "candidates": new_rows,
    }


def trace_candidate(
    archive_rows: list[dict[str, Any]],
    *,
    candidate_id: str | None = None,
    content_sha256: str | None = None,
) -> list[dict[str, Any]]:
    """归因反查：按 candidate_id 或内容 SHA-256 找候选档行（含来源记录 ids）。

    accepted 经验（corrections/judgments 里带 ``promotion`` 的行）自带
    ``promotion.candidate_id`` 与 ``promotion.content_sha256``，任一都能一步反查。
    """
    wanted_id = str(candidate_id or "").strip()
    wanted_sha = str(content_sha256 or "").strip().lower()
    if not wanted_id and not wanted_sha:
        raise ValueError("trace 需要 candidate_id 或 content_sha256 之一")
    out: list[dict[str, Any]] = []
    for row in archive_rows:
        if wanted_id and str(row.get("candidate_id") or "") == wanted_id:
            out.append(row)
            continue
        gate = row.get("gate") if isinstance(row.get("gate"), dict) else {}
        if wanted_sha and str(gate.get("content_sha256") or "").lower() == wanted_sha:
            out.append(row)
    return out


__all__ = [
    "CANDIDATES_FILENAME",
    "CANDIDATE_RECORD_TYPE",
    "CandidateProposal",
    "LoopPaths",
    "MIN_SAME_DIRECTION_CORRECTIONS",
    "RULE_REPEATED_CORRECTION",
    "RULE_VERDICT_OVERTURNED",
    "SCHEMA_VERSION",
    "generate_candidates",
    "load_candidate_archive",
    "run_loop",
    "trace_candidate",
]
