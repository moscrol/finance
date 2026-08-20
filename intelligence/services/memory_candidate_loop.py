"""user_memory 离线候选更新链（书距 S6）：台账 → 规则化候选 → memory_gate → 留档。

对照 ai-agent-book 第 8 章「在线只记录证据 → 离线生成候选更新 → 独立验证后发布 →
可回滚」：在线记录证据已齐（corrections / checkpoints / verdicts / interactions），
入口门禁已有（``memory_gate`` fail-closed）。缺的是「候选**产生**」这一步的自动化——
本模块把它补上，且**不改门禁判据、不改检索器、不做在线学习**：

1. 离线扫描 per-user 台账（经既有 loader，归档/撤销的记录不参与）；
2. v1 两条保守规则产生候选（宁缺勿滥，产出率进报告）：
   - ``repeated_correction``：同一原则文本（规范化后相同 = 同一主题且同向）出现
     ≥2 条非晋升产物的纠偏 → 候选 ``user_preference``；
   - ``verdict_overturned``：同一 checkpoint 先有机判终态、后被人工终态改判为不同
     结论（翻案）→ 候选 ``decision_lesson``；
3. 每条候选提交既有 ``MemoryGate.decide``（本模块**没有任何绕过门禁的写路径**）：
   - 接受 → 经 ``record_validated_preference`` / ``record_validated_judgment``
     落 durable 层（这两个适配器本身要求 gate 决定书绑定内容哈希）；
   - 拒绝 → 只留档，带 gate 理由；
4. 候选无论接受与否都追加到 ``users/<id>/memory_candidates.jsonl``（append-only，
   按稳定 id 幂等——同一台账重跑零新候选），每条带**归因链**
   ``attribution = {source_record_ids, rule, generated_at}``，回答「这条经验从哪来」。

来源记录定位符（S8 落地记录级 id 前的过渡格式，见 Q3）：
``<ledger>:<ts>#<sha256(canonical_json)[:12]>``；checkpoints 已有稳定 id，直接用
``checkpoints:<id>``。

生命周期一页见 ``docs/learning/memory-candidate-lifecycle.md``。
本模块只用标准库 + 本仓 services，可离线运行、可独立单测。
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from intelligence import userspace
from intelligence.services import checkpoints, corrections, interactions, judgments
from intelligence.services.memory_gate import MemoryCandidate, MemoryGate

SCHEMA_VERSION = "1.0"
CANDIDATE_RECORD_TYPE = "memory_candidate"
CANDIDATES_FILENAME = "memory_candidates.jsonl"

RULE_REPEATED_CORRECTION = "repeated_correction"
RULE_VERDICT_OVERTURNED = "verdict_overturned"
REPEAT_THRESHOLD = 2

_VERDICT_CN = {"hit": "命中", "partial": "半对", "miss": "落空"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _norm(text: Any) -> str:
    return re.sub(r"\s+", "", str(text or "")).lower()


def _canonical_sha12(record: dict[str, Any]) -> str:
    raw = json.dumps(record, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _source_ref(ledger: str, record: dict[str, Any], *, ts_key: str = "ts") -> str:
    ts = str(record.get(ts_key) or "").strip()
    return f"{ledger}:{ts}#{_canonical_sha12(record)}"


def _candidate_id(*parts: object) -> str:
    raw = "|".join(str(part) for part in parts)
    return f"memcand-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def _read_raw_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    rows: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _append_jsonl_once(path: Path, record: dict[str, Any]) -> bool:
    """按 ``id`` 幂等追加（与 forecast_learning 同构：flock + 先读后写）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f".{path.name}.lock")
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        identity = str(record.get("id") or "")
        if identity and any(
            str(row.get("id") or "") == identity for row in _read_raw_jsonl(path)
        ):
            return False
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    return True


def _written_candidate_ids(*ledger_paths: Path) -> set[str]:
    """durable 台账里已带 ``promotion.candidate_id`` 的集合（崩溃窗口恢复用）。

    读原始行、不走状态过滤：问题是「这条候选写没写过」，与它当前是否被归档无关
    （归档后再重写等于复活，必须避免）。
    """
    out: set[str] = set()
    for path in ledger_paths:
        for rec in _read_raw_jsonl(path):
            promo = rec.get("promotion")
            if isinstance(promo, dict) and str(promo.get("candidate_id") or "").strip():
                out.add(str(promo["candidate_id"]).strip())
    return out


@dataclass(frozen=True)
class LoopPaths:
    root: Path
    corrections: Path
    judgments: Path
    checkpoints: Path
    verdicts: Path
    interactions: Path
    candidates: Path


def loop_paths(
    user: str | None = None,
    users_root: str | Path | None = None,
) -> LoopPaths:
    """解析本环用到的全部台账路径；``users_root`` 供测试指向夹具目录。"""
    if users_root is not None:
        root = Path(users_root).expanduser()
        return LoopPaths(
            root=root,
            corrections=root / "corrections.jsonl",
            judgments=root / "judgments.jsonl",
            checkpoints=root / "checkpoints.jsonl",
            verdicts=root / "verdicts.jsonl",
            interactions=root / "interactions.jsonl",
            candidates=root / CANDIDATES_FILENAME,
        )
    us = userspace.user_space(user)
    return LoopPaths(
        root=us.root,
        corrections=us.corrections_path,
        judgments=us.judgments_path,
        checkpoints=us.checkpoints_path,
        verdicts=us.verdicts_path,
        interactions=us.interactions_path,
        candidates=us.root / CANDIDATES_FILENAME,
    )


# --------------------------------------------------------------------------- #
# v1 规则：候选生成（纯函数，只读记录列表，不落盘）
# --------------------------------------------------------------------------- #
def generate_repeated_correction_candidates(
    correction_records: list[dict[str, Any]],
    *,
    generated_at: str,
) -> list[dict[str, Any]]:
    """同一原则文本 ≥2 条非晋升产物的纠偏 → 候选 ``user_preference``。

    「同一主题 + 同向」的 v1 最保守操作化 = 规范化后文本相同（相同文本必然同主题
    同方向）。带 ``promotion`` 的记录是本环/门禁的产物，不算用户信号——否则一条
    原始纠偏加它的晋升副本就会自我放大成第二票。
    """
    groups: dict[str, list[tuple[dict[str, Any], str]]] = {}
    for rec in correction_records:
        if not isinstance(rec, dict) or rec.get("promotion"):
            continue
        text = str(rec.get("principle") or "").strip() or str(
            rec.get("correction") or ""
        ).strip()
        if not text:
            continue
        groups.setdefault(_norm(text), []).append((rec, text))

    out: list[dict[str, Any]] = []
    for norm_text, members in sorted(groups.items()):
        if len(members) < REPEAT_THRESHOLD:
            continue
        anchor_rec, anchor_text = max(
            members, key=lambda item: str(item[0].get("ts") or "")
        )
        themes: list[str] = []
        seen: set[str] = set()
        for rec, _text in members:
            for theme in rec.get("themes") or []:
                label = str(theme).strip()
                key = _norm(label)
                if label and key not in seen:
                    seen.add(key)
                    themes.append(label)
        out.append(
            {
                "id": _candidate_id(RULE_REPEATED_CORRECTION, norm_text),
                "rule": RULE_REPEATED_CORRECTION,
                "kind": "user_preference",
                "content": anchor_text,
                "correction_ts": str(anchor_rec.get("ts") or ""),
                "themes": themes,
                "attribution": {
                    "source_record_ids": [
                        _source_ref("corrections", rec) for rec, _text in members
                    ],
                    "rule": RULE_REPEATED_CORRECTION,
                    "generated_at": generated_at,
                },
            }
        )
    return out


def generate_verdict_overturned_candidates(
    checkpoint_records: list[dict[str, Any]],
    verdict_records: list[dict[str, Any]],
    *,
    generated_at: str,
) -> list[dict[str, Any]]:
    """机判终态被人工终态改判为不同结论（翻案）→ 候选 ``decision_lesson``。

    判定：该 checkpoint 的终态判序列里，最新一条是人工（``auto=False``）、其前
    存在机判（``auto=True``），且两者结论不同。人工复核结论相同（维持原判）或
    最新仍是机判都不算翻案。内容全部由台账字段确定性拼出，保证幂等。
    """
    by_id = {
        str(rec.get("id") or ""): rec
        for rec in checkpoint_records
        if isinstance(rec, dict) and rec.get("id")
    }
    terminals: dict[str, list[dict[str, Any]]] = {}
    for rec in verdict_records:
        if not isinstance(rec, dict):
            continue
        if rec.get("verdict") not in checkpoints.TERMINAL_VERDICTS:
            continue
        cid = str(rec.get("id") or "").strip()
        if cid:
            terminals.setdefault(cid, []).append(rec)

    out: list[dict[str, Any]] = []
    for cid in sorted(terminals):
        rows = terminals[cid]
        if len(rows) < 2:
            continue
        latest = rows[-1]
        if latest.get("auto"):
            continue
        prior_autos = [rec for rec in rows[:-1] if rec.get("auto")]
        if not prior_autos:
            continue
        machine = prior_autos[-1]
        machine_verdict = str(machine.get("verdict") or "")
        human_verdict = str(latest.get("verdict") or "")
        if machine_verdict == human_verdict:
            continue
        ck = by_id.get(cid)
        if ck is None:
            # 无 checkpoint 记录则拼不出教训正文；gate 侧同样会以
            # checkpoint_not_found 拒绝，这里直接不产候选。
            continue
        claim = str(ck.get("claim") or "").strip()
        category = str(ck.get("category") or "").strip()
        head = f"回检翻案（{category}）" if category else "回检翻案"
        content = (
            f"{head}：{claim}——机判「{_VERDICT_CN.get(machine_verdict, machine_verdict)}」"
            f"被人工改判「{_VERDICT_CN.get(human_verdict, human_verdict)}」"
        )
        reason = str(latest.get("reason") or "").strip()
        if reason:
            content += f"；人工理由：{reason}"
        out.append(
            {
                "id": _candidate_id(RULE_VERDICT_OVERTURNED, cid, content),
                "rule": RULE_VERDICT_OVERTURNED,
                "kind": "decision_lesson",
                "content": content,
                "checkpoint_id": cid,
                "themes": [str(t).strip() for t in ck.get("themes") or [] if str(t).strip()],
                "stocks": [str(s).strip() for s in ck.get("stocks") or [] if str(s).strip()],
                "attribution": {
                    "source_record_ids": [
                        f"checkpoints:{cid}",
                        _source_ref("verdicts", machine, ts_key="checked_at"),
                        _source_ref("verdicts", latest, ts_key="checked_at"),
                    ],
                    "rule": RULE_VERDICT_OVERTURNED,
                    "generated_at": generated_at,
                },
            }
        )
    return out


# --------------------------------------------------------------------------- #
# 主环：扫描 → 生成 → 门禁 → 留档/落盘
# --------------------------------------------------------------------------- #
def run_candidate_loop(
    *,
    user: str | None = None,
    users_root: str | Path | None = None,
    dry_run: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """跑一轮离线候选环，返回报告；``dry_run=True`` 时不写任何文件。

    幂等：候选 id 只由（规则, 规范化内容[, checkpoint id]）决定；已在候选台账的
    id 不再重产。晋升行带 ``promotion.candidate_id``，durable 台账里已有该 id 时
    跳过重写（两文件追加之间崩溃后的恢复路径）。
    """
    paths = loop_paths(user, users_root)
    generated_at = (now or _now()).isoformat(timespec="seconds")

    correction_records, _cw = corrections.load_corrections(paths.corrections, window=0)
    checkpoint_records, _kw = checkpoints.load_checkpoints(paths.checkpoints)
    verdict_records, _vw = checkpoints.load_verdicts(paths.verdicts)
    interaction_records, _iw = interactions.load_interactions(paths.interactions, window=0)

    produced = generate_repeated_correction_candidates(
        correction_records, generated_at=generated_at
    )
    produced += generate_verdict_overturned_candidates(
        checkpoint_records, verdict_records, generated_at=generated_at
    )

    existing_ids = {
        str(row.get("id") or "")
        for row in _read_raw_jsonl(paths.candidates)
        if row.get("record_type") == CANDIDATE_RECORD_TYPE
    }
    already_written = _written_candidate_ids(paths.corrections, paths.judgments)

    gate = MemoryGate()
    rows: list[dict[str, Any]] = []
    accepted = rejected = skipped_existing = 0
    for cand in produced:
        if cand["id"] in existing_ids:
            skipped_existing += 1
            continue
        decision = gate.decide(
            MemoryCandidate(
                candidate_id=cand["id"],
                kind=cand["kind"],
                content=cand["content"],
                checkpoint_id=str(cand.get("checkpoint_id") or ""),
                correction_ts=str(cand.get("correction_ts") or ""),
            ),
            checkpoints=checkpoint_records,
            verdicts=verdict_records,
            corrections=correction_records,
        )
        row: dict[str, Any] = {
            "record_type": CANDIDATE_RECORD_TYPE,
            "schema_version": SCHEMA_VERSION,
            "id": cand["id"],
            "ts": generated_at,
            "rule": cand["rule"],
            "kind": cand["kind"],
            "content": cand["content"],
            "content_sha256": decision.content_sha256,
            "status": "accepted" if decision.eligible else "rejected",
            "gate_reason": decision.reason,
            "gate_provenance": dict(decision.provenance),
            "attribution": cand["attribution"],
        }
        for key in ("correction_ts", "checkpoint_id"):
            if cand.get(key):
                row[key] = cand[key]
        if decision.eligible:
            accepted += 1
            target = (
                "judgments.jsonl"
                if cand["kind"] == "decision_lesson"
                else "corrections.jsonl"
            )
            row["written_to"] = target
            if not dry_run:
                if cand["id"] in already_written:
                    row["write_skipped"] = "already_written"
                elif target == "judgments.jsonl":
                    judgments.record_validated_judgment(
                        paths.judgments,
                        memo=cand["content"],
                        decision=decision,
                        themes=cand.get("themes"),
                        stocks=cand.get("stocks"),
                    )
                else:
                    corrections.record_validated_preference(
                        paths.corrections,
                        preference=cand["content"],
                        decision=decision,
                        themes=cand.get("themes"),
                    )
        else:
            rejected += 1
        if not dry_run:
            _append_jsonl_once(paths.candidates, row)
        rows.append(row)

    scanned = {
        "corrections": len(correction_records),
        "checkpoints": len(checkpoint_records),
        "verdicts": len(verdict_records),
        "interactions": len(interaction_records),
    }
    signals = scanned["corrections"] + scanned["verdicts"]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "dry_run": dry_run,
        "users_root": str(paths.root),
        "scanned": scanned,
        "produced": len(rows),
        "skipped_existing": skipped_existing,
        "accepted": accepted,
        "rejected": rejected,
        "production_rate": round(len(rows) / signals, 4) if signals else 0.0,
        "candidates": rows,
    }


def trace_candidate(
    query: str,
    *,
    user: str | None = None,
    users_root: str | Path | None = None,
) -> list[dict[str, Any]]:
    """归因反查：候选 id / 内容哈希前缀 / 晋升行 ts → 候选行（含来源记录 ids）。

    「给任一 accepted 经验查来源」的一步命令：durable 台账晋升行带
    ``promotion.candidate_id``，凭它（或该行的 ``ts``、``content_sha256`` 前缀）
    即可回到候选行的 ``attribution.source_record_ids``。
    """
    q = str(query or "").strip()
    if not q:
        return []
    paths = loop_paths(user, users_root)
    rows = [
        row
        for row in _read_raw_jsonl(paths.candidates)
        if row.get("record_type") == CANDIDATE_RECORD_TYPE
    ]
    matches = [row for row in rows if str(row.get("id") or "") == q]
    if not matches and 8 <= len(q) <= 64:
        lowered = q.lower()
        matches = [
            row
            for row in rows
            if str(row.get("content_sha256") or "").startswith(lowered)
        ]
    if not matches:
        candidate_ids: set[str] = set()
        for ledger in (paths.corrections, paths.judgments):
            for rec in _read_raw_jsonl(ledger):
                promo = rec.get("promotion")
                if (
                    isinstance(promo, dict)
                    and str(rec.get("ts") or "") == q
                    and str(promo.get("candidate_id") or "").strip()
                ):
                    candidate_ids.add(str(promo["candidate_id"]).strip())
        matches = [row for row in rows if str(row.get("id") or "") in candidate_ids]
    return matches


__all__ = [
    "CANDIDATES_FILENAME",
    "CANDIDATE_RECORD_TYPE",
    "RULE_REPEATED_CORRECTION",
    "RULE_VERDICT_OVERTURNED",
    "SCHEMA_VERSION",
    "generate_repeated_correction_candidates",
    "generate_verdict_overturned_candidates",
    "loop_paths",
    "run_candidate_loop",
    "trace_candidate",
]
