#!/usr/bin/env python3
"""判官修复 01 · 任务 1：对存证 episode 回放候选结果 → 结构核验 → 语义准入 → 判官 → 修复 → 发布，标出首个损失点。

只读 ``continuous-episode.json``，不调模型、不改 run、不起服务。

两层口径分开：

- **结构核验用当前代码重放**（确定性）：从存证重建 ``ResearchTaskContract`` 与
  ``AgentOutcome``，再跑 ``verify_episode_outcome`` 与语义准入 ``_can_semantically_
  release_partial``。存证里的 ``structural_verifier`` 是当时那版代码的结论，两列
  并排，差异就是本分支对真实题的效果（判官修复 01 第一刀：extra binding 连坐）。
- **语义层只读存证**：判官是 LLM，离线不能重放；``judge_status`` / ``sentence_
  verdicts`` / ``gap_output_ids`` / ``public_answer`` 长度直接取存证。

首个损失点（闭集，按管线顺序取最早一层）::

    L0_no_evidence        候选结果为空——检索前丢弃 / 零证据，不是判官的错
    L1_structural_block   结构核验后不可放行——判官没看到草稿（含 unknown_output_binding 连坐）
    L2_judge_unavailable  结构放行了，判官不可用——窗耗尽 / provider 挂 / 备链也挂
    L3_judge_rejected     判官拒稿且删句修复失败——gap 模板
    L4_repair_loss        判官后发布 partial——删句 / 槽位降级 / 语义 gap 输出
    L5_delivered          completed 发布，无损失

历史 run 可能缺字段（``sentence_verdicts`` 2026-09-03 起才落盘）；缺则记 None，不报 0。

用法::

    python3 scripts/judge_loss_point_replay.py --users linxiaoqi5111,default --since 20260825
    python3 scripts/judge_loss_point_replay.py --runs @docs/.../progress/01-frozen-runs.txt --markdown
    python3 scripts/judge_loss_point_replay.py --runs run_20260828_170910_375000 --json out.json
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from intelligence.services.agent_research import AgentEvidence, ProviderTrace  # noqa: E402
from intelligence.services.agent_runtime import (  # noqa: E402
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    OutputEvidenceBinding,
)
from intelligence.services.episode_semantic_verifier import (  # noqa: E402
    _can_semantically_release_partial,
)
from intelligence.services.episode_verifier import verify_episode_outcome  # noqa: E402
from intelligence.services.research_contract import ResearchTaskContract  # noqa: E402

_CODE_RE = re.compile(r"^code=([a-z_]+)")
LOSS_POINTS = (
    "L0_no_evidence",
    "L1_structural_block",
    "L2_judge_unavailable",
    "L3_judge_rejected",
    "L4_repair_loss",
    "L5_delivered",
)


def _default_users_root() -> Path:
    raw = os.environ.get("FORESIGHT_USERS_DIR")
    if raw and raw.strip():
        return Path(raw.strip()).expanduser()
    return Path.home() / ".local/share/finance-workbench/users"


def _build(cls, payload: Mapping[str, Any], **overrides: Any):
    """按 dataclass 字段名过滤存证字典，list → tuple；多余键（遥测）丢弃。"""

    names = {field.name for field in dataclasses.fields(cls)}
    kwargs: dict[str, Any] = {}
    for key, value in payload.items():
        if key not in names:
            continue
        kwargs[key] = tuple(value) if isinstance(value, list) else value
    kwargs.update(overrides)
    return cls(**kwargs)


def _rebuild_outcome(payload: Mapping[str, Any]) -> AgentOutcome:
    evidence = tuple(
        _build(AgentEvidence, item, observations=())
        for item in payload.get("evidence") or []
    )
    traces = tuple(_build(ProviderTrace, item) for item in payload.get("traces") or [])
    bindings = tuple(
        _build(OutputEvidenceBinding, item) for item in payload.get("bindings") or []
    )
    usage = _build(AgentUsage, payload.get("usage") or {})
    task_hash = str(payload.get("task_frame_hash") or "")
    common = dict(
        task_frame_hash=task_hash,
        status=payload.get("status"),
        draft=str(payload.get("draft") or ""),
        evidence=evidence,
        traces=traces,
        gaps=tuple(payload.get("gaps") or ()),
        stop_reason=str(payload.get("stop_reason") or "unknown"),
        bindings=bindings,
        usage=usage,
        plan=None,
    )
    try:
        events = tuple(
            _build(EpisodeEvent, item) for item in payload.get("events") or []
        )
        return AgentOutcome(events=events, **common)
    except Exception:
        # 存证事件序可能不满足当前 runtime 的开场校验；结构核验不读 events，
        # 退回最小锚定事件，不影响重放结论。
        return AgentOutcome(
            events=(EpisodeEvent(1, "task", {"task_frame_hash": task_hash}),),
            **common,
        )


def _codes(issues: Any) -> list[str]:
    """issue 收据 → code。2026-08 中旬之前的存证是自由文本，退回截断原文，不丢。"""

    found: list[str] = []
    for issue in issues or []:
        text = str(issue)
        match = _CODE_RE.match(text)
        token = match.group(1) if match else "text:" + text[:40]
        if token not in found:
            found.append(token)
    return found


def _verdict_counts(sv: Mapping[str, Any]) -> dict[str, int] | None:
    verdicts = sv.get("sentence_verdicts")
    if not isinstance(verdicts, list):
        return None
    counter = Counter(str(item.get("decision") or "?") for item in verdicts if isinstance(item, dict))
    return dict(counter)


def replay_receipt(path: Path) -> dict[str, Any]:
    receipt = json.loads(path.read_text(encoding="utf-8"))
    run_id = path.parent.name
    user = path.parents[2].name
    frame = receipt.get("task_frame") or {}
    contract_payload = receipt.get("contract") or {}
    outcome_payload = receipt.get("outcome") or {}
    archived_st = receipt.get("structural_verifier") or {}
    sv = receipt.get("semantic_verifier") or {}
    row: dict[str, Any] = {
        "run": run_id,
        "user": user,
        "question": str(frame.get("raw_question") or "")[:60],
        "tier": contract_payload.get("research_tier"),
        "question_type": contract_payload.get("question_type"),
        "stop_reason": outcome_payload.get("stop_reason"),
        "evidence": len(outcome_payload.get("evidence") or []),
        "bindings": len(outcome_payload.get("bindings") or []),
        "draft_chars": len(str(outcome_payload.get("draft") or "")),
        "public_chars": len(str(sv.get("public_answer") or "")),
        "archived_structural": archived_st.get("verified_status"),
        "archived_codes": _codes(archived_st.get("issues")),
        "archived_missing": list(archived_st.get("missing_outputs") or []),
        "judge_status": sv.get("judge_status"),
        "semantic_status": sv.get("status"),
        "judge_attempted": (
            sv.get("judge_attempt_index") is not None
            or bool(sv.get("exc_class"))
            or sv.get("timeout_asked") is not None
        ),
        "rejected_claims": len(sv.get("rejected_claim_indexes") or []),
        "gap_output_ids": list(sv.get("gap_output_ids") or []),
        "repair_withheld": sv.get("repair_withheld"),
        "repair_collapsed_to_stub": sv.get("repair_collapsed_to_stub"),
        "sentence_verdicts": _verdict_counts(sv),
        # V11 判官引导回检索（2026-09-09 起落盘）；老存证无此键 → None，不报 skipped。
        "v11_outcome": sv.get("v11_outcome"),
        "v11_skip_reason": sv.get("v11_skip_reason"),
        "repair": f"{receipt.get('repair_attempts')}/{receipt.get('repair_cycles')}",
        "replayed_structural": None,
        "replayed_codes": None,
        "replayed_missing": None,
        "extension_outputs": None,
        "replayed_releasable": None,
        "replay_error": None,
    }
    try:
        contract = ResearchTaskContract.from_dict(contract_payload)
        outcome = _rebuild_outcome(outcome_payload)
        verified = verify_episode_outcome(contract, outcome)
        row["replayed_structural"] = verified.verified_status
        # 与 archived_codes 同口径去重（按 code），否则「存证 vs 重放」会把重复码数成差异。
        row["replayed_codes"] = list(
            dict.fromkeys(item.code.value for item in verified.issue_items)
        )
        row["replayed_missing"] = list(verified.missing_outputs)
        # 基线代码没有 extension_outputs（本分支新增）；同一脚本要能在基线树上跑出对照臂。
        row["extension_outputs"] = list(getattr(verified, "extension_outputs", ()))
        row["replayed_releasable"] = bool(
            verified.verified_status == "completed"
            or _can_semantically_release_partial(verified)
        )
    except Exception as exc:  # 存证形状漂移：记错误，不假装重放成功
        row["replay_error"] = f"{type(exc).__name__}: {exc}"[:160]
    row["first_loss"] = classify_first_loss(row)
    row["structural_delta"] = (
        None
        if row["replayed_structural"] is None
        else row["archived_structural"] != row["replayed_structural"]
        or sorted(row["archived_codes"]) != sorted(row["replayed_codes"] or [])
    )
    return row


def classify_first_loss(row: Mapping[str, Any]) -> str:
    if row["evidence"] == 0:
        return "L0_no_evidence"
    structural = row["replayed_structural"] or row["archived_structural"]
    if structural in {"failed", "clarification"}:
        return "L1_structural_block"
    releasable = row["replayed_releasable"]
    if structural != "completed" and releasable is False:
        return "L1_structural_block"
    if row["semantic_status"] == "completed":
        return "L5_delivered"
    if row["judge_status"] == "unavailable":
        return "L2_judge_unavailable"
    if row["judge_status"] == "rejected":
        return "L3_judge_rejected"
    if row["semantic_status"] is None:
        return "L1_structural_block" if structural != "completed" else "L2_judge_unavailable"
    return "L4_repair_loss"


def _iter_receipts(root: Path, users: list[str], since: str | None, runs: set[str] | None):
    for user in users:
        runs_dir = root / user / "runs"
        if not runs_dir.is_dir():
            continue
        for path in sorted(runs_dir.glob("run_*/continuous-episode.json")):
            run_id = path.parent.name
            if runs is not None and run_id not in runs:
                continue
            if since and run_id[4:12] < since:
                continue
            yield path


def _parse_runs(raw: str | None) -> set[str] | None:
    if not raw:
        return None
    if raw.startswith("@"):
        lines = Path(raw[1:]).read_text(encoding="utf-8").splitlines()
        return {line.strip().split()[0] for line in lines if line.strip() and not line.startswith("#")}
    return {item.strip() for item in raw.split(",") if item.strip()}


def _markdown(rows: list[dict[str, Any]]) -> str:
    head = (
        "| run | 题 | 证据 | 存证结构 | 重放结构 | 准入 | 判官 | 语义 | 拒句 | gap 输出 | V11 | 草稿→公开 | 首个损失点 |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|"
    )
    lines = [head]
    for row in rows:
        lines.append(
            "| {run} | {q} | {ev} | {ast}{ac} | {rst}{rc} | {rel} | {js} | {ss} | {rej} | {gap} | {v11} | {d}→{p} | {loss} |".format(
                run=row["run"].replace("run_", ""),
                q=row["question"].replace("|", "/")[:28],
                ev=row["evidence"],
                ast=row["archived_structural"],
                ac=("(" + ",".join(row["archived_codes"]) + ")") if row["archived_codes"] else "",
                rst=row["replayed_structural"] or row["replay_error"] or "-",
                rc=("(" + ",".join(row["replayed_codes"]) + ")") if row["replayed_codes"] else "",
                rel={True: "放行", False: "挡", None: "-"}[row["replayed_releasable"]],
                js=row["judge_status"],
                ss=row["semantic_status"],
                rej=row["rejected_claims"],
                gap=",".join(row["gap_output_ids"]) or "-",
                v11=(
                    "-"
                    if row["v11_outcome"] is None
                    else f"{row['v11_outcome']}/{row['v11_skip_reason'] or ''}".rstrip("/")
                ),
                d=row["draft_chars"],
                p=row["public_chars"],
                loss=row["first_loss"],
            )
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--users", default="linxiaoqi5111,default")
    parser.add_argument("--runs-dir", default=None, help="users 根目录；默认 FORESIGHT_USERS_DIR 或 ~/.local/share/finance-workbench/users")
    parser.add_argument("--since", default=None, help="run id 里的日期下限 YYYYMMDD")
    parser.add_argument("--runs", default=None, help="逗号分隔 run id，或 @文件（每行一个 run id，# 开头忽略）")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--json", default=None, help="把逐题行写成 JSON 文件")
    parser.add_argument("--markdown", action="store_true", help="逐题 markdown 表")
    parser.add_argument("--only-loss", action="store_true", help="只列有损失的题（非 L5）")
    args = parser.parse_args(argv)

    root = Path(args.runs_dir).expanduser() if args.runs_dir else _default_users_root()
    users = [item.strip() for item in args.users.split(",") if item.strip()]
    runs = _parse_runs(args.runs)
    rows = [replay_receipt(path) for path in _iter_receipts(root, users, args.since, runs)]
    if args.limit:
        rows = rows[-args.limit :]
    if runs is not None:
        missing = runs - {row["run"] for row in rows}
        if missing:
            print(f"未找到 {len(missing)} 个 run: {sorted(missing)}", file=sys.stderr)

    shown = [row for row in rows if not args.only_loss or row["first_loss"] != "L5_delivered"]
    summary = Counter(row["first_loss"] for row in rows)
    print(f"episodes={len(rows)} users={users} since={args.since or '-'}")
    for key in LOSS_POINTS:
        print(f"  {key:22} {summary.get(key, 0)}")
    changed = [row for row in rows if row["structural_delta"]]
    errors = [row for row in rows if row["replay_error"]]
    extensions = [row for row in rows if row["extension_outputs"]]
    print(
        f"structural replay: changed_vs_archived={len(changed)} extension_outputs_seen={len(extensions)} replay_errors={len(errors)}"
    )
    for row in changed[:20]:
        print(
            f"  Δ {row['run']} archived={row['archived_structural']}{row['archived_codes']} "
            f"replayed={row['replayed_structural']}{row['replayed_codes']} releasable={row['replayed_releasable']}"
        )
    if args.markdown:
        print()
        print(_markdown(shown))
    if args.json:
        Path(args.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"rows → {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
