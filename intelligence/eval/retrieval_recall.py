"""recall@k 尺子（slice 6）：离线度量「该召回的记忆有没有被召回」。

背景（agent book 第 3 章审计点名的缺口）：
    判卷说「证据不足」时，我们分不清是**检索不足**还是**题目超纲**——没有任何
    召回质量指标。本尺子补上最小版本：人工标注「这条 query 应该召回哪些记录」，
    离线跑检索通道，算 recall@k / hit@k。

口径（对齐生产语义，不发明新检索）：
    - 首个通道是 user_memory（[M] 块）：retrieved@k = `relevant_memory_records`
      在 limit=k 下实际会装进 [M] 块的记录（judgments + corrections 各至多 k 条，
      与生产一致）。记录身份 = 台账行的 ``ts``。
    - recall@k = |retrieved@k ∩ relevant| / |relevant|（宏平均按 case 等权）；
      hit@k = retrieved@k 是否命中任一 relevant。
    - 检索器可插拔（``RETRIEVERS`` 注册表）：kb_rag / evidence_search 等通道
      等有标注集后同一把尺子直接挂，不另建第二份口径。

标注集格式（JSONL，每行一个 case）：
    {"case_id": "m-001", "query": "液冷渗透率怎么看", "theme": "液冷",
     "relevant": ["2026-08-01T10:00:00", ...],   # 应召回记录的 ts
     "note": "可选备注"}

用法：
    python3 -m intelligence.eval.retrieval_recall --cases <标注集.jsonl> \
        [--retriever user_memory] [--users-root <台账目录>] [--k 1,3,5] [--json]

纪律：本尺子只读；分数低说明「召回不足」，分数高不说明「答案正确」——
    它度量的是检索层，不是推理层。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

DEFAULT_KS = (1, 3, 5)

# 检索器签名：(query, theme, entity, k, **kwargs) -> 有序 id 列表（截断到该通道的 k 语义）
Retriever = Callable[..., list[str]]


def user_memory_retriever(
    query: str,
    theme: str | None,
    entity: str | None,
    k: int,
    *,
    users_root: str | Path | None = None,
    user: str | None = None,
) -> list[str]:
    """[M] 块生产语义：limit=k 时 judgments/corrections 各至多 k 条实际入块记录的 ts。"""
    from intelligence.services.user_memory import relevant_memory_records

    recall = relevant_memory_records(
        query, theme, entity, user=user, limit=k, users_root=users_root
    )
    ids = [str(r.get("ts") or "").strip() for r in recall.judgments]
    ids += [str(r.get("ts") or "").strip() for r in recall.corrections]
    return [i for i in ids if i]


RETRIEVERS: dict[str, Retriever] = {
    "user_memory": user_memory_retriever,
}


def load_cases(path: str | Path) -> list[dict[str, Any]]:
    """读标注集 JSONL；跳过空行/注释行/坏行，query 或 relevant 缺失的 case 丢弃。"""
    p = Path(path).expanduser()
    cases: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(case, dict):
            continue
        query = str(case.get("query") or "").strip()
        relevant = [str(r).strip() for r in (case.get("relevant") or []) if str(r).strip()]
        if query and relevant:
            case["query"], case["relevant"] = query, relevant
            cases.append(case)
    return cases


def evaluate_cases(
    cases: list[dict[str, Any]],
    retriever: Retriever,
    ks: tuple[int, ...] = DEFAULT_KS,
    **retriever_kwargs: Any,
) -> dict[str, Any]:
    """逐 case 跑检索并汇总。返回含 per-case 明细与宏平均的报告 dict。"""
    per_case: list[dict[str, Any]] = []
    for case in cases:
        relevant = set(case["relevant"])
        row: dict[str, Any] = {
            "case_id": str(case.get("case_id") or f"case-{len(per_case) + 1}"),
            "query": case["query"],
            "relevant_count": len(relevant),
            "recall_at": {},
            "hit_at": {},
            "missed": {},
        }
        for k in ks:
            retrieved = retriever(
                case["query"],
                case.get("theme"),
                case.get("entity"),
                k,
                **retriever_kwargs,
            )
            hit_set = set(retrieved) & relevant
            row["recall_at"][k] = len(hit_set) / len(relevant)
            row["hit_at"][k] = bool(hit_set)
            row["missed"][k] = sorted(relevant - set(retrieved))
        per_case.append(row)
    report: dict[str, Any] = {
        "cases": len(per_case),
        "ks": list(ks),
        "recall_at": {},
        "hit_rate_at": {},
        "per_case": per_case,
    }
    for k in ks:
        if per_case:
            report["recall_at"][k] = sum(r["recall_at"][k] for r in per_case) / len(per_case)
            report["hit_rate_at"][k] = sum(1 for r in per_case if r["hit_at"][k]) / len(per_case)
        else:
            report["recall_at"][k] = None
            report["hit_rate_at"][k] = None
    return report


def render_report(report: dict[str, Any]) -> str:
    lines = [f"# retrieval recall 报告（{report['cases']} cases）"]
    lines.append("| k | recall@k（宏平均） | hit rate@k |")
    lines.append("|---|---|---|")
    for k in report["ks"]:
        r, h = report["recall_at"][k], report["hit_rate_at"][k]
        lines.append(
            f"| {k} | {r:.2%} | {h:.2%} |" if r is not None else f"| {k} | — | — |"
        )
    worst = [
        row for row in report["per_case"]
        if report["ks"] and row["recall_at"][max(report["ks"])] < 1.0
    ]
    if worst:
        lines.append("")
        lines.append(f"## 未完全召回的 case（k={max(report['ks'])}）")
        for row in worst:
            missed = "、".join(row["missed"][max(report["ks"])])
            lines.append(f"- {row['case_id']}「{row['query']}」漏召回：{missed}")
    lines.append("")
    lines.append(
        "- 读数纪律：分数度量**检索层召回**，不度量答案正确性；"
        "分数低先查标注是否过期（记录被归档/撤销后应更新标注），再查召回算法。"
    )
    return "\n".join(lines)


def _main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="recall@k 尺子（离线只读）")
    parser.add_argument("--cases", required=True, help="标注集 JSONL 路径")
    parser.add_argument(
        "--retriever", default="user_memory", choices=sorted(RETRIEVERS),
        help="检索通道（默认 user_memory）",
    )
    parser.add_argument("--users-root", default=None, help="台账目录（默认当前用户 userspace）")
    parser.add_argument("--user", default=None, help="用户 id")
    parser.add_argument("--k", default="1,3,5", help="逗号分隔的 k 值（默认 1,3,5）")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    args = parser.parse_args()
    ks = tuple(int(x) for x in args.k.split(",") if x.strip())
    cases = load_cases(args.cases)
    if not cases:
        print("标注集为空或全部无效（每行需含 query 与非空 relevant）")
        return 2
    report = evaluate_cases(
        cases,
        RETRIEVERS[args.retriever],
        ks=ks,
        users_root=args.users_root,
        user=args.user,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else render_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
