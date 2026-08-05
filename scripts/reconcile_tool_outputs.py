#!/usr/bin/env python3
"""对账历史 run：实际 fulfilled 的 output_id，以及绑它的工具（claim 命名空间）。

这是 Agent B 的配套对账门。Agent A 正在给工具加 ``produces`` 声明字段——声明说
「我这个工具能产出 output_id X」。但声明只是意图，不是事实：如果历史上从未有
claim 绑上过某个 output_id，那声明就是过度声明，会让 fail-open 预检误放行；
反过来，如果产出过但没声明，预检会漏抓。本脚本把「历史上实际发生了什么」从
台账里抽出来，成为 A 声明什么的事实依据。

刻意的实现选择——直接调生产门禁 ``evaluate_task_fulfillment`` 而不自造近似判定：

    fulfillment 判定里有一长串特例：unsoureceable outputs、forecast 特判、
    marker 要求、claim_type 映射……（见 task_fulfillment.py:375-496）。自造一套
    「output_id 出现在 claim_id 里就算 fulfilled」的近似的判据，会在这些特例上
    系统性偏差，产出一个看起来精确、实则测了另一套东西的覆盖率。直接 import
    生产代码运行，让「实际 fulfilled」的定义与门禁完全一致——脚本只负责把历史
    run 的散件拼成门禁需要的入参。

与 replay_operator_routing.py / attribute_synthesis_degrades.py 并列，理由相同：
下次对账需要同一份证据，不该重新造一遍抽取逻辑。语料目录的解析直接 import
replay_operator_routing 的 ``default_ledgers``，不重新实现——它修过一个
「FORESIGHT_USERS_DIR 把两个台账折叠成一个」的静默缩水缺陷，重写等于把那个坑
再挖一次。

用法::

    # 全量对账
    python3 scripts/reconcile_tool_outputs.py

    # 只看某个 output_id 的绑定明细
    python3 scripts/reconcile_tool_outputs.py --output-id direct_assessment

    # 后测窗口：只看某日期之后的 run
    python3 scripts/reconcile_tool_outputs.py --since 2026-08-05

    # 落 JSON 供 A 做双向差集
    python3 scripts/reconcile_tool_outputs.py --out /tmp/reconcile.json

    # 先问「够不够跑后测」，再决定要不要跑
    python3 scripts/reconcile_tool_outputs.py --since 2026-08-05 --readiness

只读：不改代码、不写库、不碰任何服务端口。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SELF_DIR = Path(__file__).resolve().parent
if str(SELF_DIR) not in sys.path:
    sys.path.insert(0, str(SELF_DIR))

# 复用回放脚本的语料解析：那里修过 FORESIGHT_USERS_DIR 把两个台账折叠成一个
# 的静默缩水缺陷，此处必须共用同一份实现而不是照抄。
from replay_operator_routing import default_ledgers  # noqa: E402

SELF_ROOT = Path(__file__).resolve().parents[1]

# 判定「能不能进入对账」的最小 run 完整性要求：同时有 answer_spec.json（claims +
# sources）、report.json（required_outputs）和 answer.md（正文）。缺任一就跳过，
# 不补、不猜——fulfillment 判定是三者缺一不可的合取。
_REQUIRED_FILES = ("answer_spec.json", "report.json", "answer.md")

# 后测窗口最少需要的 run 数。低于这个数时不阻止运行（用户可能只想看一眼），
# 但会在报告顶部显眼位置打印警告，避免拿 3 个 run 的结果当结论。
_READINESS_MIN_RUNS = 20


# ---------------------------------------------------------------------------
# 从 JSON 重构生产领域对象
# ---------------------------------------------------------------------------
#
# answer_spec.json 是 AnswerSpec.to_dict() 的序列化产物，但 AnswerSpec 没有
# from_dict。手动重建需要的三个 frozen dataclass：Claim、EvidenceRef、
# RequiredOutput。刻意不重建整个 AnswerSpec（CompanyAssessment 等嵌套结构对
# 对账无价值），只取门禁 evaluate_task_fulfillment 真正读的那些字段。


def _reconstruct_claim(raw: dict[str, Any]) -> Any:
    """从 JSON dict 重建 Claim 对象。"""
    from intelligence.services.answer_model import Claim, ClaimStatus

    status_str = str(raw.get("status", "candidate"))
    try:
        status = ClaimStatus(status_str)
    except ValueError:
        status = ClaimStatus.CANDIDATE

    return Claim(
        claim_id=str(raw.get("claim_id", "")),
        text=str(raw.get("text", "")),
        claim_type=str(raw.get("claim_type", "")),
        theme=str(raw.get("theme", "")),
        evidence_ids=tuple(raw.get("evidence_ids", [])),
        evidence_tier=str(raw.get("evidence_tier", "")),
        freshness=raw.get("freshness"),
        confidence=raw.get("confidence"),
        counter_evidence=tuple(raw.get("counter_evidence", [])),
        status=status,
        company=raw.get("company"),
    )


def _reconstruct_evidence_ref(raw: dict[str, Any]) -> Any:
    """从 JSON dict 重建 EvidenceRef 对象。"""
    from intelligence.services.answer_model import EvidenceRef

    return EvidenceRef(
        evidence_id=str(raw.get("evidence_id", "")),
        source=str(raw.get("source", "")),
        detail=str(raw.get("detail", "")),
        tier=str(raw.get("tier", "")),
        source_date=raw.get("source_date"),
        freshness=str(raw.get("freshness", "unknown")),
        content_hash=str(raw.get("content_hash", "")),
        source_revision=str(raw.get("source_revision", "")),
    )


def _collect_claims_from_spec(spec: dict[str, Any]) -> list[Any]:
    """从 answer_spec.json 的各 section 收集所有 Claim 对象。

    门禁 evaluate_answer_spec_fulfillment (task_fulfillment.py:499) 从
    summary / verified_facts / counter_evidence / gaps / triggers /
    candidate_facts / company_table.claims 这七个位置收集 claims。此处照搬
    同一个收集逻辑，确保对账与门禁看的是同一份 claim 集合。
    """
    claims: list[Any] = []
    seen_ids: set[str] = set()
    for section in (
        "summary",
        "verified_facts",
        "counter_evidence",
        "gaps",
        "triggers",
        "candidate_facts",
    ):
        for raw in spec.get(section, []):
            if isinstance(raw, dict):
                claim = _reconstruct_claim(raw)
                if claim.claim_id not in seen_ids:
                    claims.append(claim)
                    seen_ids.add(claim.claim_id)

    # company_table 的 claims 嵌在 CompanyAssessment 里
    for company_raw in spec.get("company_table", []):
        if not isinstance(company_raw, dict):
            continue
        for claim_raw in company_raw.get("claims", []):
            if isinstance(claim_raw, dict):
                claim = _reconstruct_claim(claim_raw)
                if claim.claim_id not in seen_ids:
                    claims.append(claim)
                    seen_ids.add(claim.claim_id)

    return claims


def _load_required_outputs(report: dict[str, Any]) -> list[Any]:
    """从 report.json 的 task_frame.required_outputs 重建 RequiredOutput 列表。

    report.json 存的是 output_id 字符串列表（不带 description）。门禁只用
    output_id 做匹配，description 仅出现在错误消息里，所以空串不影响判定。
    """
    from intelligence.services.research_contract import RequiredOutput

    raw_list = report.get("task_frame", {}).get("required_outputs", [])
    if not isinstance(raw_list, list):
        return []
    return [
        RequiredOutput(output_id=str(oid), description="")
        for oid in raw_list
        if isinstance(oid, str) and oid.strip()
    ]


# ---------------------------------------------------------------------------
# 单 run 处理
# ---------------------------------------------------------------------------


def _claim_namespace(claim_id: str) -> str:
    """claim_id 的命名空间（冒号前的前缀），用于标���生产工具。

    如 ``daily-review:fact:1`` → ``daily-review``，``generic:summary`` →
    ``generic``。这是「哪个工具产出了这条 claim」的代理维度——真正的工具名
    在 trace 的 route_skills 里有，但 claim_id 前缀与之高度相关且无额外开销。
    """
    if ":" in claim_id:
        return claim_id.split(":", 1)[0]
    return claim_id or "(empty)"


def _git_head(repo_root: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None if out.returncode == 0 else None


def _evaluate_single_run(run_dir: Path) -> dict[str, Any] | None:
    """对单个 run 做 fulfillment 判定，返回对账记录。

    返回 None 表示 run 缺少必要的文件（跳过）。返回 dict 时包含：
    - run_id, question, required_outputs (原始列表)
    - fulfilled: list of {output_id, namespaces, claim_ids}
    - unfulfilled: list of {output_id, status, gap}
    - claim_count, source_count
    """
    # 完整性检查
    for fname in _REQUIRED_FILES:
        if not (run_dir / fname).exists():
            return None

    try:
        spec = json.loads((run_dir / "answer_spec.json").read_text("utf-8"))
        report = json.loads((run_dir / "report.json").read_text("utf-8"))
        answer_text = (run_dir / "answer.md").read_text("utf-8")
        run_meta = json.loads((run_dir / "run.json").read_text("utf-8"))
    except (OSError, ValueError):
        return None

    required_outputs = _load_required_outputs(report)
    if not required_outputs:
        # 没 required_outputs 的 run（market_watch 等）没有对账意义
        return None

    claims = _collect_claims_from_spec(spec)
    sources = [
        _reconstruct_evidence_ref(raw)
        for raw in spec.get("sources", [])
        if isinstance(raw, dict)
    ]

    question = run_meta.get("question", "")
    run_id = run_meta.get("run_id", run_dir.name)

    # 调生产门禁
    from intelligence.services.task_fulfillment import (
        _claim_candidates,
        evaluate_task_fulfillment,
    )

    verdict = evaluate_task_fulfillment(
        question=question,
        required_outputs=tuple(required_outputs),
        answer_text=answer_text,
        claims=claims,
        sources=sources,
    )

    fulfilled: list[dict[str, Any]] = []
    unfulfilled: list[dict[str, Any]] = []

    for item in verdict.items:
        if item.status == "fulfilled":
            # 取回绑它的 claims，提取命名空间
            candidates = _claim_candidates(item.output_id, tuple(claims))
            bound_claims = [
                c for c in candidates if _claim_text_or_evidence_bound(
                    c, item, answer_text
                )
            ]
            namespaces = sorted(
                dict.fromkeys(_claim_namespace(c.claim_id) for c in bound_claims)
            ) if bound_claims else sorted(
                dict.fromkeys(
                    _claim_namespace(c.claim_id) for c in candidates
                )
            )
            claim_ids = [c.claim_id for c in (bound_claims or candidates)]
            fulfilled.append(
                {
                    "output_id": item.output_id,
                    "namespaces": namespaces,
                    "claim_ids": claim_ids,
                    "evidence_ids": list(item.evidence_ids),
                }
            )
        else:
            unfulfilled.append(
                {
                    "output_id": item.output_id,
                    "status": item.status,
                    "gap": item.gap,
                }
            )

    return {
        "run_id": run_id,
        "question": question,
        "task_type": run_meta.get("task_type"),
        "status": run_meta.get("status"),
        "created_at": run_meta.get("created_at"),
        "required_outputs": [ro.output_id for ro in required_outputs],
        "fulfilled": fulfilled,
        "unfulfilled": unfulfilled,
        "claim_count": len(claims),
        "source_count": len(sources),
    }


def _claim_text_or_evidence_bound(claim: Any, item: Any, answer_text: str) -> bool:
    """简化判定：claim 是否真的绑到了这个 fulfilled item。

    门禁内部的绑定逻辑很复杂（forecast 特判、unsouceable 特例等），但走到
    ``item.status == "fulfilled"`` 时，绑定已经发生。这里只做一个保守的
    过滤：claim 的 evidence_ids 与 item 的 evidence_ids 有交集，或者 claim
    的 claim_id 出现在 item 的 answer_spans 相关位置。
    """
    if item.evidence_ids and claim.evidence_ids:
        if set(claim.evidence_ids) & set(item.evidence_ids):
            return True
    # 没有证据交集时仍保留候选（门禁可能通过 marker 或 unsouceable 例外放行）
    return False


# ---------------------------------------------------------------------------
# 批量处理 + 聚合
# ---------------------------------------------------------------------------


def collect_runs(
    ledgers: list[Path], since: str | None = None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """遍历所有台账的 run 目录，对每个 run 做对账判定。

    返回 (records, stats)。stats 包含文件覆盖率、跳过原因等诊断信息。
    """
    records: list[dict[str, Any]] = []
    per_ledger: dict[str, dict[str, int]] = {}
    total_scanned = 0
    total_skipped_incomplete = 0
    total_skipped_no_ro = 0
    total_errors = 0

    for root in ledgers:
        ledger_name = str(root)
        if not root.exists():
            per_ledger[ledger_name] = {"exists": 0, "scanned": 0, "evaluated": 0}
            continue
        scanned = 0
        evaluated = 0
        for run_json_path in sorted(root.glob("*/runs/*/run.json")):
            total_scanned += 1
            scanned += 1
            run_dir = run_json_path.parent

            # --since 过滤（字符串前缀比较，与 attribute_synthesis_degrades 一致）
            if since:
                try:
                    meta = json.loads(run_json_path.read_text("utf-8"))
                except (OSError, ValueError):
                    total_errors += 1
                    continue
                created_at = str(meta.get("created_at", ""))
                if not created_at.startswith(since):
                    continue

            try:
                record = _evaluate_single_run(run_dir)
            except Exception:  # noqa: BLE001
                total_errors += 1
                continue

            if record is None:
                # 区分跳过原因
                has_spec = (run_dir / "answer_spec.json").exists()
                has_report = (run_dir / "report.json").exists()
                if has_spec and has_report:
                    total_skipped_no_ro += 1
                else:
                    total_skipped_incomplete += 1
                continue

            evaluated += 1
            records.append(record)

        per_ledger[ledger_name] = {
            "exists": 1,
            "scanned": scanned,
            "evaluated": evaluated,
        }

    stats = {
        "total_scanned": total_scanned,
        "total_evaluated": len(records),
        "skipped_incomplete": total_skipped_incomplete,
        "skipped_no_required_outputs": total_skipped_no_ro,
        "errors": total_errors,
        "per_ledger": per_ledger,
    }
    return records, stats


def aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    """聚合所有 run 的对账结果，产出「output_id × 工具命名空间」交叉表��"""
    # output_id → set of namespaces that ever fulfilled it
    output_namespaces: dict[str, set[str]] = defaultdict(set)
    # output_id → count of runs where it was fulfilled
    output_fulfilled_count: Counter[str] = Counter()
    # output_id → count of runs where it was required
    output_required_count: Counter[str] = Counter()
    # namespace → set of output_ids it ever bound
    namespace_outputs: dict[str, set[str]] = defaultdict(set)
    # namespace → total claim bindings
    namespace_binding_count: Counter[str] = Counter()
    # run-level fulfillment rate
    run_verdicts: Counter[str] = Counter()

    for rec in records:
        required = set(rec["required_outputs"])
        fulfilled_ids = {f["output_id"] for f in rec["fulfilled"]}

        for oid in required:
            output_required_count[oid] += 1

        for f in rec["fulfilled"]:
            oid = f["output_id"]
            output_fulfilled_count[oid] += 1
            output_namespaces[oid].update(f["namespaces"])
            for ns in f["namespaces"]:
                namespace_outputs[ns].add(oid)
                namespace_binding_count[ns] += 1

        if required:
            if required == fulfilled_ids:
                run_verdicts["all_fulfilled"] += 1
            elif fulfilled_ids:
                run_verdicts["partial"] += 1
            else:
                run_verdicts["none_fulfilled"] += 1

    return {
        "output_namespaces": {
            oid: sorted(ns_set) for oid, ns_set in sorted(output_namespaces.items())
        },
        "output_fulfilled_count": dict(output_fulfilled_count.most_common()),
        "output_required_count": dict(output_required_count.most_common()),
        "namespace_outputs": {
            ns: sorted(oid_set)
            for ns, oid_set in sorted(namespace_outputs.items())
        },
        "namespace_binding_count": dict(namespace_binding_count.most_common()),
        "run_verdicts": dict(run_verdicts),
    }


# ---------------------------------------------------------------------------
# 报告渲染
# ---------------------------------------------------------------------------


def render_report(
    records: list[dict[str, Any]],
    agg: dict[str, Any],
    stats: dict[str, Any],
    meta: dict[str, Any],
    output_filter: str | None,
    show_readiness: bool,
) -> str:
    lines: list[str] = []
    total = len(records)

    lines.append("=" * 78)
    lines.append("工具产出对账（历史 run fulfillment × claim 命名空间）")
    lines.append("=" * 78)
    lines.append(f"判别代码来自: {meta['repo']}" + (f" @ {meta['head']}" if meta.get("head") else ""))
    lines.append(f"扫描 run.json: {stats['total_scanned']}")
    lines.append(f"进入对账: {total}")
    for ledger, info in stats["per_ledger"].items():
        if info["exists"]:
            lines.append(
                f"  {ledger}: 扫描 {info['scanned']}, 对账 {info['evaluated']}"
            )
        else:
            lines.append(f"  {ledger}: 目录不存在")
    if stats["skipped_incomplete"]:
        lines.append(f"  跳过(缺文件): {stats['skipped_incomplete']}")
    if stats["skipped_no_required_outputs"]:
        lines.append(f"  跳过(无 required_outputs): {stats['skipped_no_required_outputs']}")
    if stats["errors"]:
        lines.append(f"  解析错误: {stats['errors']}")

    # 覆盖率警告
    coverage_pct = (total / stats["total_scanned"] * 100) if stats["total_scanned"] else 0
    lines.append(f"覆盖率: {total}/{stats['total_scanned']} ({coverage_pct:.1f}%)")
    if coverage_pct < 50:
        lines.append("  ⚠️ 覆盖率低于 50%——超过一半的 run 无法对账，结论不可靠")
    elif coverage_pct < 80:
        lines.append("  ⚠️ 覆盖率偏低，结论仅覆盖部分 run")

    # readiness 检查
    if show_readiness:
        lines.append("")
        lines.append("-" * 78)
        lines.append(f"后测就绪检查（阈值 {_READINESS_MIN_RUNS} run）")
        lines.append(f"  当前窗口 run 数: {total}")
        if total < _READINESS_MIN_RUNS:
            lines.append(f"  ⚠️ 不够——还差 {_READINESS_MIN_RUNS - total} 轮")
            lines.append("  样本太少时构成迁移看不出来，等攒够再跑")
        else:
            lines.append("  ✓ 够了，可以跑完整对账")
        lines.append("-" * 78)

    # run 级 verdict 概览
    rv = agg["run_verdicts"]
    lines.append("")
    lines.append("Run 级 fulfillment 概览:")
    lines.append(f"  全部 fulfilled: {rv.get('all_fulfilled', 0)}")
    lines.append(f"  部分 fulfilled: {rv.get('partial', 0)}")
    lines.append(f"  无 fulfilled:   {rv.get('none_fulfilled', 0)}")

    # output_id × 命名空间 交叉表
    lines.append("")
    lines.append("=" * 78)
    lines.append("output_id × 工具命名空间（实际 fulfilled 的绑定来源）")
    lines.append("=" * 78)

    output_ns = agg["output_namespaces"]
    fulfilled_count = agg["output_fulfilled_count"]
    required_count = agg["output_required_count"]

    if output_filter:
        # 只看指定 output_id 的明细
        lines.append(f"\n(过滤: output_id = {output_filter})")
        if output_filter not in output_ns:
            lines.append("  历史上从未 fulfilled 过这个 output_id")
        else:
            lines.append(
                f"  fulfilled {fulfilled_count.get(output_filter, 0)}"
                f" / {required_count.get(output_filter, 0)} 次"
            )
            lines.append(f"  绑定命名空间: {', '.join(output_ns[output_filter])}")
            lines.append("\n  逐 run 明细:")
            for rec in records:
                for f in rec["fulfilled"]:
                    if f["output_id"] == output_filter:
                        lines.append(f"    {rec['run_id']}:")
                        lines.append(f"      namespaces: {f['namespaces']}")
                        lines.append(f"      claim_ids: {f['claim_ids'][:5]}")
                        if f["evidence_ids"]:
                            lines.append(f"      evidence: {f['evidence_ids'][:5]}")
                        break
    else:
        # 全量交叉表
        all_output_ids = sorted(
            set(output_ns.keys()) | set(required_count.keys())
        )
        for oid in all_output_ids:
            ns_list = output_ns.get(oid, [])
            f_count = fulfilled_count.get(oid, 0)
            r_count = required_count.get(oid, 0)
            rate = f"{f_count}/{r_count}" if r_count else f"{f_count}/?"
            lines.append(f"\n  {oid}  (fulfilled {rate})")
            if ns_list:
                lines.append(f"    绑定工具: {', '.join(ns_list)}")
            else:
                lines.append("    绑定工具: (从未 fulfilled)")

    # 命名空间 → output_id 反向表
    lines.append("")
    lines.append("=" * 78)
    lines.append("工具命名空间 → 产出的 output_id（反向视角）")
    lines.append("=" * 78)
    ns_outputs = agg["namespace_outputs"]
    ns_counts = agg["namespace_binding_count"]
    for ns in sorted(ns_outputs.keys()):
        oid_list = ns_outputs[ns]
        lines.append(
            f"\n  {ns}  (绑定 {ns_counts.get(ns, 0)} 次, "
            f"覆盖 {len(oid_list)} 个 output_id)"
        )
        lines.append(f"    outputs: {', '.join(oid_list)}")

    lines.append("")
    lines.append("=" * 78)
    lines.append("口径限制（读结论前必读）")
    lines.append("=" * 78)
    lines.append(
        "1. 覆盖率由文件完整性决定：只有同时有 answer_spec.json + report.json + "
        "answer.md 的 run 才进入对账。早期 run 或异常 run 会被跳过。"
    )
    lines.append(
        "2. required_outputs 来自 report.json 的 task_frame，是 run 完成时的快照。"
        "如果 query_understanding 在 run 之后改过路由（如 _COMPARISON_RE 修复），"
        "历史 run 的 required_outputs 不会追溯更新。"
    )
    lines.append(
        "3. 工具维度用 claim_id 命名空间（冒号前缀）做代理，不是 route_skills 里的 "
        "skill_id。两者高度相关但不完全一致：generic: 命名空间来自 ask.py 的 "
        "确定性骨架，daily-review: 来自 daily-review skill，wiki: 来自知识图谱检索。"
    )
    lines.append(
        "4. fulfillment 判定直接调用生产门禁 evaluate_task_fulfillment，与线上 "
        "task_fulfillment.py 完全一致。如果门禁逻辑改了，重跑这个脚本即可，"
        "不需要同步修改。"
    )

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="对账历史 run 的 fulfilled output_id 及其工具绑定来源",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=SELF_ROOT,
        help="加载判别代码的工作树（默认: 脚本所在树的根）",
    )
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="只看 created_at 以此字符串开头的 run（字符串前缀比较，非时区解析）",
    )
    parser.add_argument(
        "--output-id",
        type=str,
        default=None,
        help="只看指定 output_id 的逐 run 绑定明细",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="把对账结果落 JSON 到指定路径",
    )
    parser.add_argument(
        "--readiness",
        action="store_true",
        help="只检查后测窗口是否够 run 数，不跑完整对账",
    )
    args = parser.parse_args()

    # 把判别代码的工作树加到 sys.path
    if str(args.repo) not in sys.path:
        sys.path.insert(0, str(args.repo))

    ledgers = default_ledgers()
    head = _git_head(args.repo)
    meta = {"repo": str(args.repo), "head": head}

    if args.readiness:
        # 只数 run 数，不做完整对账
        count = 0
        for root in ledgers:
            if not root.exists():
                continue
            for run_json in root.glob("*/runs/*/run.json"):
                if args.since:
                    try:
                        meta_raw = json.loads(run_json.read_text("utf-8"))
                    except (OSError, ValueError):
                        continue
                    if not str(meta_raw.get("created_at", "")).startswith(args.since):
                        continue
                count += 1
        print(f"后测窗口 run 数: {count}")
        if count < _READINESS_MIN_RUNS:
            print(f"⚠️ 不够——还差 {_READINESS_MIN_RUNS - count} 轮（阈值 {_READINESS_MIN_RUNS}）")
        else:
            print(f"✓ 够了（阈值 {_READINESS_MIN_RUNS}）")
        return 0

    records, stats = collect_runs(ledgers, since=args.since)
    agg = aggregate(records)

    report = render_report(
        records,
        agg,
        stats,
        meta,
        output_filter=args.output_id,
        show_readiness=False,
    )
    print(report)

    if args.out:
        payload = {
            "meta": meta,
            "stats": stats,
            "aggregate": agg,
            "records": records,
        }
        args.out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), "utf-8"
        )
        print(f"\nJSON 落盘: {args.out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
