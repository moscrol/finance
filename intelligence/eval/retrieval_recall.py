"""recall@k 尺子（slice 6）：离线度量「该召回的记忆有没有被召回」。

背景（agent book 第 3 章审计点名的缺口）：
    判卷说「证据不足」时，我们分不清是**检索不足**还是**题目超纲**——没有任何
    召回质量指标。本尺子补上最小版本：人工标注「这条 query 应该召回哪些记录」，
    离线跑检索通道，算 recall@k / hit@k。

口径（对齐生产语义，不发明新检索；完整契约见 docs/retrieval-recall-at-k-contract.md）：
    - **生产 @k = 每通道 k，不是全局 top-k**（质检 Q2 收口）。
    - user_memory（[M] 块）：retrieved@k = `relevant_memory_records`
      在 limit=k 下实际会装进 [M] 块的记录（judgments + corrections 各至多 k 条，
      并集可达 2k，与生产一致）。旧标注身份 = ``ts``；新集可显式使用 stable 身份。
      评分前拒绝不可达或身份有歧义的标注，不自动删题或迁移台账。
    - experience_cards：retrieved@k = `select_relevant_cards(limit=k)` 的相关卡
      ``ts``（生产默认 k=3）；常驻卡不看 query、无条件入 prompt，不属检索召回。
    - kb_rag（W 源）：retrieved@k = `kb_rag.retrieve`（hybrid、require_fresh）
      命中按序去重后的前 k 个页面路径；命中身份 = 仓相对 ``file_path``
      （chunk_id 绑定索引 revision、重建即漂移，不作标注身份）。
    - recall@k = |retrieved@k ∩ relevant| / |relevant|（宏平均按 case 等权）；
      hit@k = retrieved@k 是否命中任一 relevant。
    - 检索器可插拔（``RETRIEVERS`` 注册表）：evidence_search 等通道
      等有标注集后同一把尺子直接挂，不另建第二份口径。

标注集格式（JSONL，每行一个 case）：
    {"case_id": "m-001", "channel": "user_memory", "query": "液冷渗透率怎么看",
     "theme": "液冷", "relevant": ["2026-08-01T10:00:00", ...],  # ts 或 file_path
     "note": "标注理由", "source_ref": "出处"}
    channel 缺省视作 user_memory；真实标注集：
    intelligence/eval/cases/retrieval_recall_v1.jsonl（20 条，S4）。

用法：
    python3 -m intelligence.eval.retrieval_recall --cases <标注集.jsonl> \
        [--retriever user_memory] [--channel user_memory] \
        [--users-root <台账目录>] [--kb-wiki <KB wiki 路径>] [--k 1,3,5] [--json]

    仓内自带合成夹具（不是真人标注，只证明尺子能跑）：
    python3 -m intelligence.eval.retrieval_recall \
        --cases intelligence/eval/fixtures/user_memory_recall/cases.jsonl \
        --users-root intelligence/eval/fixtures/user_memory_recall/ledgers

    user_memory 分档对照（2026-08-05 handoff §3 的三档 + 混合，每档报命中 / 非标注召回 / 延迟）：
    python3 -m intelligence.eval.retrieval_recall --cases <标注集> --users-root <某个用户的台账目录> \
        --tiers --embed-model builtin:char-bigram --embed-model BAAI/bge-small-zh-v1.5 [--min-sim 0.5]
    注意 ``--users-root`` 是**叶目录**（``$FORESIGHT_USERS_DIR/<user>``），给父目录会静默读出 0 命中。

纪律：本尺子只读；分数低说明「召回不足」，分数高不说明「答案正确」——
    它度量的是检索层，不是推理层。
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from intelligence.eval.memory_recall_labels import (
    InvalidMemoryLabels,
    memory_identity,
    require_memory_labels,
    require_unchanged_ledgers,
)

DEFAULT_KS = (1, 3, 5)
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "user_memory_recall"
FIXTURE_CASES = FIXTURE_DIR / "cases.jsonl"
FIXTURE_LEDGERS = FIXTURE_DIR / "ledgers"

# 检索器签名：(query, theme, entity, k, **kwargs) -> 有序 id 列表（截断到该通道的 k 语义）
Retriever = Callable[..., list[str]]


class MemoryRetrievalUnavailable(OSError):
    """The measured retrieval failed; a missing result is not a scored miss."""


def user_memory_retriever(
    query: str,
    theme: str | None,
    entity: str | None,
    k: int,
    *,
    users_root: str | Path | None = None,
    user: str | None = None,
    recall_mode: str | None = None,
    telemetry: dict[str, Any] | None = None,
    identity_mode: str = "ts",
) -> list[str]:
    """[M] 块生产语义：limit=k 时 judgments/corrections 各至多 k 条实际入块记录的 ts。

    ``recall_mode`` 为 None 时与生产同读环境变量；分档对照显式传 keyword / semantic / hybrid。
    """
    from intelligence.services.user_memory import relevant_memory_records

    try:
        recall = relevant_memory_records(
            query, theme, entity, user=user, limit=k, users_root=users_root,
            recall_mode=recall_mode, telemetry=telemetry, strict=True,
        )
    except (OSError, ValueError):
        raise MemoryRetrievalUnavailable("memory retrieval unavailable") from None
    ids = [memory_identity("judgment", r, identity_mode) for r in recall.judgments]
    ids += [memory_identity("correction", r, identity_mode) for r in recall.corrections]
    return [i for i in ids if i]


def experience_cards_retriever(
    query: str,
    theme: str | None,
    entity: str | None,
    k: int,
    *,
    users_root: str | Path | None = None,
    user: str | None = None,
) -> list[str]:
    """经验卡生产语义：``select_relevant_cards(limit=k)`` 实际入 prompt 的相关卡 ts。

    生产默认 k=3（``ask.py`` 不传 limit）。常驻卡（promoted/methodology 概览）
    不看 query、无条件入 prompt，不属「检索召回」，不计入本通道读数。
    """
    from intelligence.services import experience_cards

    if users_root is not None:
        path = Path(users_root).expanduser() / "experience_cards.jsonl"
    else:
        from intelligence import userspace

        path = userspace.user_space(user).experience_cards_path
    cards, _warn = experience_cards.load_cards(path)
    hit = experience_cards.select_relevant_cards(cards, query, limit=k)
    return [str(c.get("ts") or "").strip() for c in hit if str(c.get("ts") or "").strip()]


def kb_rag_retriever(
    query: str,
    theme: str | None,
    entity: str | None,
    k: int,
    *,
    kb_wiki: str | Path | None = None,
    kb_mode: str | None = None,
    kb_timeout: int | None = None,
) -> list[str]:
    """wiki RAG（W 源）生产语义：``kb_rag.retrieve``（require_fresh 契约同生产）
    命中按序去重后的前 k 个页面路径。

    命中身份 = 仓相对 ``file_path``（如 ``wiki/entities/飞凯材料.md``）。
    theme/entity 不参与——生产 W 源只发 query。通道不可用（无索引/守卫
    fail-closed/超时）时降级为空召回并在 stderr 留因，不让尺子崩。
    """
    from intelligence.services import kb_rag

    wiki = kb_wiki or os.environ.get("KNOWLEDGE_WIKI")
    res = kb_rag.retrieve(
        query,
        kb_wiki=wiki,
        k=k,
        mode=kb_mode or kb_rag.DEFAULT_RAG_MODE,
        timeout=int(kb_timeout or kb_rag.DEFAULT_RAG_TIMEOUT),
    )
    if not res.ok:
        print(f"[retrieval_recall] kb_rag 通道不可用：{res.warning}", file=sys.stderr)
        return []
    out: list[str] = []
    seen: set[str] = set()
    for h in res.hits:
        rel = str(h.file_path or "").strip()
        if rel and rel not in seen:
            seen.add(rel)
            out.append(rel)
    return out[:k]


RETRIEVERS: dict[str, Retriever] = {
    "user_memory": user_memory_retriever,
    "experience_cards": experience_cards_retriever,
    "kb_rag": kb_rag_retriever,
}

DEFAULT_CHANNEL = "user_memory"


def load_cases(path: str | Path, channel: str | None = None) -> list[dict[str, Any]]:
    """读标注集 JSONL；跳过空行/注释行/坏行，query 或 relevant 缺失的 case 丢弃。

    ``channel`` 给定时只保留该通道的 case；case 未写 channel 字段的按
    ``user_memory`` 算（兼容既有夹具）。
    """
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
        if channel and str(case.get("channel") or DEFAULT_CHANNEL) != channel:
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
    label_audit = None
    if retriever is user_memory_retriever and cases:
        label_audit = require_memory_labels(
            cases, users_root=retriever_kwargs.get("users_root"), user=retriever_kwargs.get("user"),
            identity_mode=retriever_kwargs.get("identity_mode", "ts"),
        )
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
    if label_audit is not None:
        require_unchanged_ledgers(
            label_audit, users_root=retriever_kwargs.get("users_root"), user=retriever_kwargs.get("user"),
        )
        report["label_audit"] = label_audit
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


def memory_tier_plan(embed_models: list[str]) -> list[dict[str, Any]]:
    """分档：T0 原始问句（不带结构化意图）· T1 现状（关键词 + 意图）· 每个模型各一档语义、一档混合。"""
    from intelligence.services.memory_semantic import BUILTIN_BIGRAM

    plan: list[dict[str, Any]] = [
        {"tier": "T0", "label": "原始问句 · 关键词", "mode": "keyword", "strip_subject": True, "model": None},
        {"tier": "T1", "label": "+结构化意图 · 关键词（现状）", "mode": "keyword", "strip_subject": False, "model": None},
    ]
    for index, model in enumerate(embed_models, start=1):
        kind = "字符二元组（非语义对照）" if model == BUILTIN_BIGRAM else f"语义 {model}"
        suffix = f"-{index}" if len(embed_models) > 1 else ""
        plan.append({"tier": f"T2{suffix}", "label": f"+{kind}", "mode": "semantic", "strip_subject": False, "model": model})
        plan.append({"tier": f"T3{suffix}", "label": f"混合：关键词 + {kind}补位", "mode": "hybrid", "strip_subject": False, "model": model})
    return plan


def compare_memory_tiers(
    cases: list[dict[str, Any]],
    *,
    k: int = 5,
    embed_models: list[str] | None = None,
    users_root: str | Path | None = None,
    user: str | None = None,
    identity_mode: str = "ts",
) -> dict[str, Any]:
    """user_memory 各档对照：命中 / 召回 / 非标注召回（假阳性上限）/ 延迟，外加逐 case 明细。

    语义档降级（模型没配、依赖没装、加载失败）时整档标「降级」，数字是关键词兜底的，不能当语义读。
    """
    import time

    from intelligence.services.memory_semantic import CACHE_DIR_ENV, MODEL_ENV

    label_audit = require_memory_labels(
        cases, users_root=users_root, user=user, identity_mode=identity_mode,
    )
    rows: list[dict[str, Any]] = []
    per_case: dict[str, dict[str, Any]] = {}
    saved = {key: os.environ.get(key) for key in (MODEL_ENV, CACHE_DIR_ENV)}
    # 本尺子只读：分档期间不写向量缓存（每档都现算，首查延迟因此含编码全部记录的时间）。
    os.environ[CACHE_DIR_ENV] = "off"
    try:
        for tier in memory_tier_plan(list(embed_models or [])):
            if tier["model"] is not None:
                os.environ[MODEL_ENV] = tier["model"]
            hits = recall_sum = false_positive = 0
            latencies: list[float] = []
            degraded: set[str] = set()
            for case in cases:
                relevant = set(case["relevant"])
                theme = None if tier["strip_subject"] else case.get("theme")
                entity = None if tier["strip_subject"] else case.get("entity")
                telemetry: dict[str, Any] = {}
                started = time.perf_counter()
                retrieved = user_memory_retriever(
                    case["query"], theme, entity, k, users_root=users_root, user=user,
                    recall_mode=tier["mode"], telemetry=telemetry,
                    identity_mode=identity_mode,
                )
                latencies.append((time.perf_counter() - started) * 1000)
                degraded |= {str(v["degraded"]) for v in telemetry.values() if isinstance(v, dict) and v.get("degraded")}
                found = set(retrieved) & relevant
                hits += bool(found)
                recall_sum += len(found) / len(relevant)
                extra = len(set(retrieved) - relevant)
                false_positive += extra
                case_id = str(case.get("case_id") or f"case-{len(per_case) + 1}")
                detail = per_case.setdefault(case_id, {
                    "case_id": case_id,
                    "query": case["query"],
                    "subject": str(case.get("theme") or ""),
                    "subject_chars": len(str(case.get("theme") or "")),
                    "relevant": len(relevant),
                    "tiers": {},
                })
                detail["tiers"][tier["tier"]] = {"found": len(found), "extra": extra}
            n = len(cases) or 1
            rows.append({
                **{key: tier[key] for key in ("tier", "label", "mode", "model")},
                "cases": len(cases),
                "hits": hits,
                "hit_rate": hits / n,
                "recall": recall_sum / n,
                "false_positives": false_positive,
                "first_ms": round(latencies[0], 1) if latencies else None,
                "rest_mean_ms": round(sum(latencies[1:]) / len(latencies[1:]), 1) if len(latencies) > 1 else None,
                "degraded": sorted(degraded),
            })
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    require_unchanged_ledgers(label_audit, users_root=users_root, user=user)
    return {"k": k, "cases": len(cases), "tiers": rows, "per_case": list(per_case.values()),
            "label_audit": label_audit}


def render_tiers(report: dict[str, Any]) -> str:
    k = report["k"]
    lines = [f"# user_memory 分档对照（{report['cases']} cases，k={k}）", ""]
    lines.append(f"| 档 | 说明 | hit@{k} | recall@{k} | 非标注召回（假阳性上限） | 首查 ms（含加载） | 其余均值 ms | 状态 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for row in report["tiers"]:
        status = "降级：" + "、".join(row["degraded"]) + "（数字是关键词兜底）" if row["degraded"] else "正常"
        rest = "—" if row["rest_mean_ms"] is None else row["rest_mean_ms"]
        lines.append(
            f"| {row['tier']} | {row['label']} | {row['hits']}/{row['cases']} | {row['recall']:.1%} | "
            f"{row['false_positives']} | {row['first_ms']} | {rest} | {status} |"
        )
    tiers = [row["tier"] for row in report["tiers"]]
    lines += ["", "## 逐 case（命中数/应召回数，括号里是非标注召回数）", ""]
    lines.append("| case | 路由主题 | 主题字数 | " + " | ".join(tiers) + " |")
    lines.append("|---|---|---|" + "---|" * len(tiers))
    for row in report["per_case"]:
        cells = [
            f"{row['tiers'][t]['found']}/{row['relevant']}（+{row['tiers'][t]['extra']}）" for t in tiers
        ]
        lines.append(f"| {row['case_id']} | {row['subject'] or '—'} | {row['subject_chars']} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "- 读数纪律：非标注召回 = 召回了但不在标注里的条数，是假阳性的**上限**（标注只列必召回）。",
        "- 语义档要比「字符二元组」对照好出足够多，才值得背模型加载成本；比不过就如实说（handoff §3 允许反向结论）。",
    ]
    return "\n".join(lines)


def _run() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="recall@k 尺子（离线只读）")
    parser.add_argument("--cases", required=True, help="标注集 JSONL 路径")
    parser.add_argument(
        "--retriever", default="user_memory", choices=sorted(RETRIEVERS),
        help="检索通道（默认 user_memory）",
    )
    parser.add_argument(
        "--channel", default=None,
        help="只跑标注集中该通道的 case（case 未写 channel 按 user_memory 算）；默认不过滤",
    )
    parser.add_argument("--users-root", default=None, help="台账目录（默认当前用户 userspace）")
    parser.add_argument("--user", default=None, help="用户 id")
    parser.add_argument(
        "--memory-identity", choices=("ts", "stable"), default="ts",
        help="user_memory 标注身份：旧集 ts；新集显式 stable（台账类型:记录id）",
    )
    parser.add_argument("--kb-wiki", default=None, help="KB wiki 路径（默认 KNOWLEDGE_WIKI 环境变量）")
    parser.add_argument("--kb-mode", default=None, help="kb_rag 检索模式（默认 hybrid）")
    parser.add_argument(
        "--kb-timeout", type=int, default=None,
        help="kb_rag 单次检索超时秒（默认走 kb_rag.DEFAULT_RAG_TIMEOUT=90；冷启动 hybrid 建议 180）",
    )
    parser.add_argument("--k", default="1,3,5", help="逗号分隔的 k 值（默认 1,3,5）")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    parser.add_argument(
        "--tiers", action="store_true",
        help="user_memory 分档对照（原始问句 / 现状 / 语义 / 混合），k 取 --k 的最大值",
    )
    parser.add_argument(
        "--embed-model", action="append", default=[],
        help="分档里语义档用的本地模型，可重复；builtin:char-bigram 是零依赖的非语义对照",
    )
    parser.add_argument("--min-sim", type=float, default=None, help="语义相似度下限（默认 0.5）")
    args = parser.parse_args()
    ks = tuple(int(x) for x in args.k.split(",") if x.strip())
    cases = load_cases(args.cases, channel=args.channel)
    if not cases:
        print("标注集为空或全部无效（每行需含 query 与非空 relevant；--channel 过滤后可能为空）")
        return 2
    if args.tiers:
        if args.retriever != "user_memory":
            print("--tiers 只支持 user_memory 通道")
            return 2
        if args.min_sim is not None:
            from intelligence.services.memory_semantic import MIN_SIM_ENV

            os.environ[MIN_SIM_ENV] = str(args.min_sim)
        memory_cases = [c for c in cases if str(c.get("channel") or DEFAULT_CHANNEL) == "user_memory"]
        tiers = compare_memory_tiers(
            memory_cases, k=max(ks), embed_models=args.embed_model,
            users_root=args.users_root, user=args.user,
            identity_mode=args.memory_identity,
        )
        print(json.dumps(tiers, ensure_ascii=False, indent=2) if args.json else render_tiers(tiers))
        return 0
    if args.retriever == "kb_rag":
        retriever_kwargs: dict[str, Any] = {
            "kb_wiki": args.kb_wiki,
            "kb_mode": args.kb_mode,
            "kb_timeout": args.kb_timeout,
        }
    else:
        retriever_kwargs = {"users_root": args.users_root, "user": args.user}
        if args.retriever == "user_memory":
            retriever_kwargs["identity_mode"] = args.memory_identity
    report = evaluate_cases(
        cases,
        RETRIEVERS[args.retriever],
        ks=ks,
        **retriever_kwargs,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else render_report(report))
    return 0


def _main() -> int:
    try:
        return _run()
    except InvalidMemoryLabels as exc:
        print(json.dumps({"status": "invalid_memory_labels", "label_audit": exc.report}, ensure_ascii=False, indent=2))
        return 2
    except MemoryRetrievalUnavailable:
        print(json.dumps({"status": "memory_retrieval_unavailable"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(_main())
