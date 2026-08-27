"""inherited_golden 的确定性观察生成器：把 B1/B2/B3 从「不可判」解锁。

失败形状
--------
2026-08-18 总验收：`inherit_from` 三题（B1/B2/B3）恒为 UNJUDGEABLE，理由
"historical acceptance trace lacks agent_eval TurnInput observations"。根因有两层：
① 验收工件此前没记 agent_eval 需要的观测面；② 就算记了，`agent_eval` 的引用
语法（``[S1]``/``[G2]``）与 Episode 引擎的公开稿语法（裸 ``E1`` / ``（E15）``）
已经分家，直接跑 `score_case` 会把语法漂移记成产品失败。

本模块按 acceptance_cases 里三题 pass_rule 的字面意图重建判定，全部确定性、
零 LLM，并逐轴携带成立条件：

- **闸（gating）四轴**：answered / 实体召回 ≥ golden 闸 / 引用真实性
  （episode 语法：被引 E 号必须落在 ``[1, evidence_retrieved]``，2026-08-18 两份
  28 题工件 23 个带引 turn 实证 0 违例）/ forbid_entities 与 forbid_phrases。
- **报告不闸**：免责声明（episode 公开稿不渲染「非投资建议」，同两份工件
  60/60 turn 实证为 0，是展示层全局行为不是这三题的毛病）、概念召回
  （agent_eval.score_case 本来就不闸它）、工具跨度（老工件没这个埋点；
  新工件有 ``tools_called`` 时照 golden 的 min/max 报告）。

产出是 `acceptance_truth_observations` sidecar（哈希绑定 run/cases/overlay），
经 `load_observation_artifact` 自检后才落盘——自检不过就不写，fail closed。
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from intelligence.eval.acceptance_observations import (
    canonical_artifact_hash,
    load_observation_artifact,
)
from intelligence.eval.acceptance_verdict import VERDICT_OVERLAY_PATH

REPO = Path(__file__).resolve().parents[2]

# 裸 E1 / [E1] / （E15）在词边界口径下都命中；含小数与年份的 "E" 前缀词不会。
EPISODE_CITE_RE = re.compile(r"\bE(\d+)\b")

_DISCLAIMER = "非投资建议"


def load_golden_spec(inherit_from: str, repo: Path | None = None) -> dict[str, Any]:
    """解析 ``path#case_id`` 形式的 inherit_from 并返回 golden case 字典。"""

    base = repo or REPO
    path_text, _, case_id = inherit_from.partition("#")
    if not case_id:
        raise ValueError(f"inherit_from 缺 '#case_id'：{inherit_from!r}")
    doc = json.loads((base / path_text).read_text(encoding="utf-8"))
    for case in doc.get("cases") or []:
        if str(case.get("id")) == case_id:
            return dict(case)
    raise ValueError(f"golden case {case_id!r} 不在 {path_text}")


def _cited_indexes(answer: str) -> list[int]:
    return [int(m) for m in EPISODE_CITE_RE.findall(answer or "")]


def observe_case(
    case: Mapping[str, Any],
    golden: Mapping[str, Any],
    turns: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """对一个 inherit_from 用例产出 {state, reason, evidence_refs}。"""

    if not turns:
        return {
            "state": "unjudgeable",
            "reason": "run 里没有该题的 turn 记录",
            "evidence_refs": ["turn:0"],
        }

    failures: list[str] = []
    notes: list[str] = []
    unjudgeable: list[str] = []
    all_text = "\n".join(str(t.get("answer") or "") for t in turns)

    # 轴 1：answered
    for i, turn in enumerate(turns):
        if not str(turn.get("answer") or "").strip():
            failures.append(f"turn:{i} 未作答")

    # 轴 2：实体召回（golden 闸）
    expect_entities = [str(e) for e in (golden.get("expect_entities") or [])]
    gate = float(golden.get("entity_recall_gate", 0.5))
    if expect_entities:
        matched = [e for e in expect_entities if e in all_text]
        recall = len(matched) / len(expect_entities)
        if recall < gate:
            missing = [e for e in expect_entities if e not in all_text]
            failures.append(
                f"实体召回 {recall:.2f} < 闸 {gate:.2f}（缺：{'、'.join(missing)}）"
            )
        else:
            notes.append(f"实体召回 {recall:.2f}≥{gate:.2f}（{len(matched)}/{len(expect_entities)}）")

    # 轴 3：引用真实性（episode 语法：E 号 ∈ [1, evidence_retrieved]）
    for i, turn in enumerate(turns):
        cited = _cited_indexes(str(turn.get("answer") or ""))
        if not cited:
            continue
        retrieved = turn.get("evidence_retrieved")
        if retrieved is None:
            unjudgeable.append(
                f"turn:{i} 有 {len(cited)} 处 E 引用但工件缺 evidence_retrieved，引用真实性无法判"
            )
            continue
        retrieved = int(retrieved)
        dangling = sorted({n for n in cited if n < 1 or n > retrieved})
        if dangling:
            failures.append(
                f"turn:{i} 编造引用（E 号越过检索证据数 {retrieved}）："
                + "、".join(f"E{n}" for n in dangling)
            )
        else:
            notes.append(f"turn:{i} 引用 {len(cited)} 处全部落在 E1..E{retrieved}")

    # 轴 4：forbid 表（B3 的重点）
    false_attr = [e for e in (golden.get("forbid_entities") or []) if str(e) in all_text]
    if false_attr:
        failures.append("错配题材实体：" + "、".join(str(e) for e in false_attr))
    overclaims = [p for p in (golden.get("forbid_phrases") or []) if str(p) in all_text]
    if overclaims:
        failures.append("证据层级 overclaim：" + "、".join(str(p) for p in overclaims))

    # 报告不闸的三轴
    if golden.get("require_disclaimer", True):
        n_with = sum(1 for t in turns if _DISCLAIMER in str(t.get("answer") or ""))
        notes.append(
            f"免责声明轴按引擎语法降为报告项（episode 公开稿不渲染该句；本题 {n_with}/{len(turns)} turn 含）"
        )
    expect_concepts = [str(c) for c in (golden.get("expect_concepts") or [])]
    if expect_concepts:
        hit = sum(1 for c in expect_concepts if c in all_text)
        notes.append(f"概念召回 {hit}/{len(expect_concepts)}（agent_eval 本就不闸此轴）")
    tool_notes: list[str] = []
    for i, turn in enumerate(turns):
        tools = turn.get("episode_tools_called")
        if tools is None:
            continue
        lo = 0 if i > 0 else int(golden.get("min_tool_calls", 3))
        hi = int(golden.get("max_tool_calls", 40))
        mark = "在" if lo <= len(tools) <= hi else "越"
        tool_notes.append(f"turn:{i} 工具 {len(tools)} 次（{mark}界 [{lo},{hi}]）")
    if tool_notes:
        notes.append("工具跨度（报告项）：" + "；".join(tool_notes))
    else:
        notes.append("工具跨度：工件无 episode_tools_called 埋点，跳过（报告项）")

    if unjudgeable and not failures:
        state = "unjudgeable"
        reason = "；".join(unjudgeable + notes)
    elif failures:
        state = "fail"
        reason = "；".join(failures + notes)
    else:
        state = "pass"
        reason = "四闸轴全过：" + "；".join(notes)

    refs = [f"turn:{i}" for i in range(len(turns))]
    return {"state": state, "reason": reason[:1800], "evidence_refs": refs}


def build_truth_sidecar(
    run_path: Path,
    *,
    cases_path: Path,
    overlay_path: Path | None = None,
    repo: Path | None = None,
) -> dict[str, Any]:
    """对 run 里全部 inherit_from 用例出观察，包成可过校验的 sidecar 字典。"""

    overlay = overlay_path or VERDICT_OVERLAY_PATH
    run_doc = json.loads(run_path.read_text(encoding="utf-8"))
    cases_doc = json.loads(cases_path.read_text(encoding="utf-8"))
    run_cases = {
        str(item.get("case_id")): item
        for item in (run_doc.get("cases") or [])
        if isinstance(item, Mapping) and item.get("case_id")
    }

    observations: dict[str, Any] = {}
    for case in cases_doc.get("cases") or []:
        inherit_from = case.get("inherit_from")
        case_id = str(case.get("id"))
        if not inherit_from or case_id not in run_cases:
            continue
        golden = load_golden_spec(str(inherit_from), repo)
        turns = [t for t in (run_cases[case_id].get("turns") or []) if isinstance(t, Mapping)]
        observations[case_id] = {
            "truth_observations": {
                "inherited_golden": observe_case(case, golden, turns)
            }
        }
    if not observations:
        raise ValueError("run 里没有任何 inherit_from 用例，无观察可出")

    module_bytes = Path(__file__).read_bytes()
    payload: dict[str, Any] = {
        "format_version": 1,
        "artifact_kind": "acceptance_truth_observations",
        "created_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": {
            "run_path": _display_path(run_path),
            "run_sha256": _sha256_file(run_path),
            "cases_sha256": _sha256_file(cases_path),
            "overlay_sha256": _sha256_file(overlay),
        },
        "evaluator": {
            "id": f"inherited-golden-observer@{hashlib.sha256(module_bytes).hexdigest()[:12]}",
            "kind": "deterministic_script",
            "model": None,
            "independent": True,
        },
        # 判定规则全部在本模块源码里，rubric 哈希即模块文件哈希。
        "rubric_sha256": hashlib.sha256(module_bytes).hexdigest(),
        "case_observations": observations,
    }
    payload["artifact_sha256"] = canonical_artifact_hash(payload)
    return payload


def write_truth_sidecar(
    run_path: Path,
    output_path: Path,
    *,
    cases_path: Path,
    overlay_path: Path | None = None,
) -> dict[str, Any]:
    """生成 → 自检（load_observation_artifact）→ 落盘。自检不过不写。"""

    overlay = overlay_path or VERDICT_OVERLAY_PATH
    payload = build_truth_sidecar(run_path, cases_path=cases_path, overlay_path=overlay)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    try:
        load_observation_artifact(
            output_path,
            run_path=run_path,
            cases_path=cases_path,
            overlay_path=overlay,
        )
    except Exception:
        output_path.unlink(missing_ok=True)
        raise
    return payload


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve()))
    except ValueError:
        return str(path.resolve())
