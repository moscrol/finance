#!/usr/bin/env python3
"""把历史 run 的「合成降级」按原因归因，量化某个预算门槛的爆炸半径。

用途：改 grounded 合成预算（root_seconds / synthesis_reserve_seconds /
minimum_two_phase_entry_seconds）之前，先用真实台账回答「这个门槛到底挡掉了
多少轮」。2026-08-05 的第一次测算就靠它把「97 门槛结构上必然失败」和「所以
它最重要」拆开：结构上必然失败是真的，但台账说它至今只真正挡过 2 轮，因为
它 08-03 才上线；同期 deadline_exceeded 是 11% 的 run、48% 的降级、且从
07-16 起就一直如此。优先级由后者决定。

与 replay_operator_routing.py 并列，理由相同：下次改预算需要同一份证据，
不该重新造一遍探测脚本。语料目录的解析直接 import 那个模块，不重新实现——
它里面修过一个「静默缩水」缺陷（见该文件 CANONICAL_LEDGERS 注释），重写一遍
等于把那个坑再挖一次。

================================================================================
三条口径限制。读结论之前必须知道，否则会拿这些数当成比它们本身更硬的证据。
================================================================================

限制 1：分桶是对 degrade 自由文本做正则，不是运行时的 reason code。
    运行时确实有归一化的 reason_code（ask_synthesis._record_synthesis_phase
    -> SynthesisPhase.reason_code），但它走 trace 通道，且只覆盖极少数 run
    （见限制 2）。run.json 的 degrades 是给人看的自由文本，同一种故障在不同
    版本里措辞不同（「已降级为模板」/「已降级回结构化合成」/「已降级为可核验
    短答」）。所以本脚本的分桶是**事后语义归类**，不是权威分类。BUCKETS 里
    的正则来自 299 个 run 跑出的 83 种真实字样，但新版本换措辞后会漏桶——
    脚本会把未命中任何桶的 degrade 单独列出来，别忽略那一段。

限制 2：remaining_ms_at_entry / phases 遥测晚于大部分历史 run。
    这个字段只存在于 trace.jsonl / stream.jsonl 的
    synthesis_diagnostic.phases 下（**不在 run.json 里**，早期版本没有这段
    遥测）。2026-08-05 实测覆盖 11/300 个 run，降级 run 里只有 10/63。
    所以「入口剩余预算的中位数」这类统计的 n 只有 10，它描述的是最近两天的
    少数 run，不是全量历史。脚本因此**强制**先打印覆盖率再打印分位数，并在
    覆盖率低于 --coverage-warn-below 时给出显式警告。
    这条不是洁癖：拿 n=10 的中位数当全量结论，和一份跑在错误语料上却退出码
    为 0 的「全绿」报告是同一种假证据。

限制 3：静默放行会让 provider 类故障被低估——但预算类不会。
    ask_synthesis.py 只在影子状态**不可放行**时才追加 degrade 文本
    （见 _PROMOTABLE_SHADOW_STATUSES 与其下游的 warnings.append）。
    judge_outage_released 在可放行集合里，所以「judge 因 provider 瞬时故障
    缺席、正文带警示放行」的那些轮**不会**在 degrades 里留痕，本脚本看不见。
    -> provider_unavailable 桶是下界，不是真值。

    预算类相反，已钉死为真值：
      - composer 段：compose_remaining < minimum_two_phase_entry_seconds 时
        落 _record_synthesis_phase(status="skipped",
        reason=_INSUFFICIENT_BUDGET_REASON)，并把同一 reason 写进
        GroundedComposerShadow(status="composer_unavailable")；该状态不在可
        放行集合里，degrade 必然写出。
      - judge 段：_phase_slice_collapsed 为真时 judge_reason 同样是
        _INSUFFICIENT_BUDGET_REASON，而它被**刻意排除**在
        _TRANSIENT_JUDGE_REASONS 之外（该处注释写明这是 fail-closed 的一类），
        于是 _judge_outage_release 返回 None、状态落 judge_unavailable，
        同样不可放行 -> degrade 必然写出。
    -> admission_denied 桶是真值。它数小是因为 grounded_deep profile 由
       4ca15db1（2026-08-03）才引入，此前这条分支在结构上无法触发；不是漏记。

限制 4：一条 degrade 只归一个桶，且归属对 BUCKETS 的顺序敏感。
    classify() 是「首个命中即返回」，所以同时含「超过共享截止时间」与
    「HTTP 429」的一条文本只会计入 deadline_exceeded。这是刻意的：一条 degrade
    描述的是一次失败，重复计数会让各桶之和超过降级总数、看起来像故障变多了。
    代价是桶间存在归属竞争——2026-08-05 用更宽的 provider 正则先匹配时，同一份
    台账给出的是 deadline=33 / provider=20，收紧顺序后是 deadline=28 /
    provider=22。**两个都不是错的，但只有写明顺序的那个可复现**。所以改
    BUCKETS 顺序等于改口径，跨版本比较前先确认顺序没动。
    run 级仍可落多桶（一轮里 brief/composer/judge 各自的失败原因可能不同），
    这是有意保留的：它反映的是「这一轮踩了几种坑」。

限制 5：--since 是字符串前缀比较，不解析时区。
    created_at 形如 ``2026-08-05T23:15:54+08:00``，本地台账至今只有 +08:00 一种
    偏移，所以字典序等价于时间序，比较起来既便宜又不引入 dateutil 依赖。**但
    一旦台账里混入别的时区偏移，这个比较就是错的**：``...T23:00+09:00`` 会被排
    在 ``...T22:00+08:00`` 之后，而真实时刻更早。届时必须换成真正的 datetime
    解析，不要在这个前缀比较上继续打补丁。

用法::

    # 全量归因
    python3 scripts/attribute_synthesis_degrades.py

    # 只看某个桶命中的具体 run，并落 JSON 供下次对照
    python3 scripts/attribute_synthesis_degrades.py --bucket admission_denied \
        --out /tmp/synth-degrades.json

    # 后测：只看生产切到 8ccca8ca 之后的样本。不加 --since 的话，19 轮新样本会
    # 被 300 轮历史稀释——admission_denied 从 2 变 3 在全量口径里是 0.3 个百分点，
    # 在 20 轮窗口里是 5 个，而那正是要验的构成迁移。
    python3 scripts/attribute_synthesis_degrades.py --since 2026-08-05T23:15

    # 先问「够不够跑后测」，再决定要不要跑
    python3 scripts/attribute_synthesis_degrades.py --since 2026-08-05T23:15 --readiness

只读：不改代码、不写库、不碰任何服务端口。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path
from typing import Any, Iterable

SELF_DIR = Path(__file__).resolve().parent
if str(SELF_DIR) not in sys.path:
    sys.path.insert(0, str(SELF_DIR))

# 复用回放脚本的语料解析：那里修过 FORESIGHT_USERS_DIR 把两个台账折叠成一个
# 的静默缩水缺陷，此处必须共用同一份实现而不是照抄。
from replay_operator_routing import default_ledgers  # noqa: E402

# 判定「这一轮出现过合成降级」的字样。刻意宽：宁可多收进来由分桶细分，也不要
# 在入口处漏掉一种措辞。脚本会把它打印出来，因为分母由它决定。
DEGRADE_PATTERN = re.compile(
    r"合成.{0,16}降级"
    r"|降级为模板"
    r"|降级回结构化"
    r"|降级为可核验短答"
    r"|未通过门禁或不可用"
    r"|llm_unavailable_template"
)

# 互斥分桶：按顺序首个命中者胜出。顺序即特异性——admission 的字样最具体，
# 放在最前；provider 兜底放最后，因为它的正则最宽。
BUCKETS: "OrderedDict[str, tuple[re.Pattern[str], str]]" = OrderedDict(
    [
        (
            "admission_denied",
            (
                re.compile(r"剩余预算不足|insufficient_budget"),
                "门槛挡门：预算不够，该段合成根本没发起",
            ),
        ),
        (
            "deadline_exceeded",
            (
                re.compile(r"超过共享截止时间|超过共享\s*deadline|deadline_exhausted"),
                "发起了但时间用尽：共享 deadline 在合成中途到点",
            ),
        ),
        (
            "gate_rejected",
            (
                re.compile(
                    r"quality_gate_rejected"
                    r"|judge_output_invalid"
                    r"|judge_rejected"
                    r"|brief_rejected"
                    r"|insufficient_grounded_body"
                    r"|no_valid_support_claims"
                    r"|ineligible_evidence"
                    r"|repair_failed"
                ),
                "合成出来了但质检拒收：门禁/语义审/修复链否掉了正文",
            ),
        ),
        (
            "provider_unavailable",
            (
                re.compile(
                    r"llm_unavailable"
                    r"|HTTP\s*\d{3}"
                    r"|TimeoutError"
                    r"|被截断"
                    r"|provider_stalled"
                    r"|provider_overloaded"
                    r"|rate_limited"
                    r"|empty_response"
                    r"|call_budget_exhausted"
                ),
                "provider 侧不可用/超时/限流（下界，见限制 3）",
            ),
        ),
    ]
)

PHASE_NAMES = frozenset({"brief", "composer", "judge"})
TELEMETRY_MARKER = "remaining_ms_at_entry"
TELEMETRY_FILES = ("trace.jsonl", "stream.jsonl")

# 后测的样本量下限。20 不是统计功效算出来的，是「构成迁移看不看得出来」的经验
# 门槛：admission_denied 从 2 变 3，在 300 轮全量里是 0.3 个百分点（噪声），在
# 20 轮窗口里是 5 个百分点（可见）。改这个数就是改「多少算够」的判据。
READINESS_THRESHOLD = 20


def iter_run_dirs(ledgers: Iterable[Path]) -> list[Path]:
    """<ledger>/<user>/runs/<run_id>/ 的并集，按真实路径去重后保序。"""
    out: list[Path] = []
    seen: set[Path] = set()
    for ledger in ledgers:
        if not ledger.exists():
            continue
        for run_json in sorted(ledger.glob("*/runs/*/run.json")):
            d = run_json.parent
            key = d.resolve()
            if key in seen:
                continue
            seen.add(key)
            out.append(d)
    return out


def load_runs(run_dirs: Iterable[Path]) -> tuple[list[dict[str, Any]], int]:
    records: list[dict[str, Any]] = []
    unreadable = 0
    for d in run_dirs:
        try:
            payload = json.loads((d / "run.json").read_text(encoding="utf-8"))
        except Exception:
            unreadable += 1
            continue
        if not isinstance(payload, dict):
            unreadable += 1
            continue
        degrades = payload.get("degrades")
        if not isinstance(degrades, list):
            degrades = []
        records.append(
            {
                "dir": d,
                "run_id": payload.get("run_id") or d.name,
                "created_at": payload.get("created_at") or "",
                "task_type": payload.get("task_type") or "",
                "question": (payload.get("question") or "").strip(),
                "degrades": [x for x in degrades if isinstance(x, str)],
            }
        )
    return records, unreadable


def filter_since(
    records: list[dict[str, Any]], since: str | None
) -> list[dict[str, Any]]:
    """按 created_at 截出 [since, ∞) 的窗口。见限制 5：字典序比较，不解析时区。

    created_at 缺失的 run 一律**排除**而不是保留：后测问的是「切换之后」，一条
    时间不明的记录既不能证明在窗口内、也不该混进分母。
    """
    if not since:
        return records
    return [r for r in records if r["created_at"] and r["created_at"] >= since]


def render_readiness(
    records: list[dict[str, Any]],
    *,
    since: str | None,
    threshold: int,
) -> str:
    """只回答一个问题：窗口内攒够样本了没有，还差几轮。"""
    lines: list[str] = []
    lines.append("=" * 82)
    lines.append("后测就绪度")
    lines.append("=" * 82)
    lines.append(f"  窗口: {since or '(全量，未指定 --since)'}")
    lines.append(f"  窗口内 run: {len(records)}")
    lines.append(f"  门槛: {threshold}")

    short = threshold - len(records)
    if short > 0:
        lines.append(f"  距门槛还差: {short} 轮  -> 还不够，别跑后测")
    else:
        lines.append(f"  距门槛还差: 0 轮（超出 {-short}）  -> 够了，可以跑归因看构成迁移")

    degraded = [
        r for r in records if any(DEGRADE_PATTERN.search(m) for m in r["degrades"])
    ]
    lines.append(f"  其中降级: {len(degraded)}/{len(records)}")
    if records:
        stamps = sorted(r["created_at"] for r in records if r["created_at"])
        if stamps:
            lines.append(f"  时间跨度: {stamps[0][:19]} .. {stamps[-1][:19]}")
    if 0 < len(records) < 5:
        lines.append("")
        lines.append("  !! n 太小，任何构成占比都不是信号。别拿它推断迁移。")
    lines.append("")
    return "\n".join(lines)


def classify(message: str) -> str | None:
    for name, (pattern, _desc) in BUCKETS.items():
        if pattern.search(message):
            return name
    return None


def walk_phases(node: Any) -> Iterable[dict[str, Any]]:
    """递归找出所有 grounded 段遥测条目。

    按结构识别而不是按固定路径取值：任何 name 属于 brief/composer/judge、
    且带 remaining_ms_at_entry 的 dict 都算。trace/stream 两条通道的外层包装
    不同（``$.output_summary`` vs ``$.payload.step.output_summary``），写死路径
    会漏掉一条。

    **必须解字符串**：``output_summary`` 自身是一个 JSON *字符串*，phases 埋在
    它内部（``$.output_summary<decoded>.diagnostic.phases[]``，注意键是
    ``diagnostic`` 而不是 dataclass 上的 ``synthesis_diagnostic``）。只对
    ``json.loads(line)`` 的结果做遍历会一个都抓不到——第一版就是这么写的，于是
    覆盖率打印成 0/300，而实际有 11 个 run 带遥测。一个把覆盖率报成 0 的
    覆盖率检查器，和一份跑在错误语料上却退出码 0 的「全绿」报告是同一种假证据。
    """
    if isinstance(node, dict):
        if node.get("name") in PHASE_NAMES and TELEMETRY_MARKER in node:
            yield node
        for value in node.values():
            yield from walk_phases(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk_phases(item)
    elif isinstance(node, str):
        # 只在确实含 marker 时才尝试解码，避免对每个字符串都 json.loads。
        if TELEMETRY_MARKER in node:
            try:
                decoded = json.loads(node)
            except Exception:
                return
            yield from walk_phases(decoded)


def collect_phase_telemetry(run_dir: Path) -> list[dict[str, Any]]:
    """从 trace/stream 里抽 phases 遥测；无则返回空列表。

    先做整文件 substring 预筛再逐行 parse：trace.jsonl 可以很大，而绝大多数
    run 根本没有这段遥测（见限制 2），全量 json.loads 是纯浪费。
    """
    found: dict[tuple[str, int, int], dict[str, Any]] = {}
    for filename in TELEMETRY_FILES:
        path = run_dir / filename
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if TELEMETRY_MARKER not in text:
            continue
        for line in text.splitlines():
            if TELEMETRY_MARKER not in line:
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            for phase in walk_phases(payload):
                # 同一段遥测会同时出现在 trace 和 stream，按内容去重。
                key = (
                    str(phase.get("name")),
                    int(phase.get("remaining_ms_at_entry") or 0),
                    int(phase.get("elapsed_ms") or 0),
                )
                found.setdefault(key, phase)
    return list(found.values())


def percentiles(values: list[int]) -> dict[str, int]:
    if not values:
        return {}
    ordered = sorted(values)

    def pick(q: float) -> int:
        idx = min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))
        return ordered[idx]

    return {
        "min": ordered[0],
        "p50": pick(0.5),
        "p90": pick(0.9),
        "max": ordered[-1],
    }


def render(
    records: list[dict[str, Any]],
    *,
    unreadable: int,
    ledgers: list[Path],
    telemetry: dict[str, list[dict[str, Any]]],
    coverage_warn_below: float,
    bucket_filter: str | None,
    show_runs: bool,
    since: str | None = None,
    total_before_filter: int | None = None,
) -> str:
    lines: list[str] = []
    total = len(records)
    degraded = [
        r for r in records if any(DEGRADE_PATTERN.search(m) for m in r["degrades"])
    ]

    lines.append("=" * 82)
    lines.append("合成降级归因（真实历史 run）")
    lines.append("=" * 82)
    for ledger in ledgers:
        mark = "" if ledger.exists() else "  [目录不存在]"
        lines.append(f"  台账 {ledger}{mark}")
    tail = f"（{unreadable} 个无法解析）" if unreadable else ""
    if since:
        scope = f"{total}"
        if total_before_filter is not None:
            scope += f" / 台账全量 {total_before_filter}"
        lines.append(f"时间窗: created_at >= {since}")
        lines.append(f"窗口内 run 数: {scope}{tail}")
        if total < READINESS_THRESHOLD:
            lines.append(
                f"  !! 窗口内只有 {total} 轮，低于 {READINESS_THRESHOLD} 轮门槛："
                "构成占比还不是信号（--readiness 可单独看）。"
            )
    else:
        lines.append(f"run 总数: {total}{tail}")
    lines.append(f"降级判定正则: {DEGRADE_PATTERN.pattern}")
    pct = (100.0 * len(degraded) / total) if total else 0.0
    lines.append(f"出现合成降级字样的 run: {len(degraded)}  ({pct:.1f}%)")
    lines.append("")

    # ---- 字段覆盖率：刻意排在所有分位数统计之前，见限制 2 ----
    with_tele = [r for r in records if telemetry.get(r["run_id"])]
    deg_with_tele = [r for r in degraded if telemetry.get(r["run_id"])]
    tele_pct = (100.0 * len(with_tele) / total) if total else 0.0
    deg_tele_pct = (100.0 * len(deg_with_tele) / len(degraded)) if degraded else 0.0

    lines.append("-" * 82)
    lines.append(f"字段覆盖率  {TELEMETRY_MARKER} / synthesis_diagnostic.phases")
    lines.append("-" * 82)
    lines.append(f"  全部 run : {len(with_tele)}/{total}  ({tele_pct:.1f}%)")
    lines.append(
        f"  降级 run : {len(deg_with_tele)}/{len(degraded)}  ({deg_tele_pct:.1f}%)"
    )
    if with_tele:
        stamps = sorted(r["created_at"] for r in with_tele if r["created_at"])
        if stamps:
            lines.append(f"  遥测时间窗: {stamps[0]} .. {stamps[-1]}")
    if deg_tele_pct < coverage_warn_below:
        lines.append("")
        lines.append("  !! 覆盖率偏低。下面任何按 remaining_ms 的分位数都只描述这个小样本，")
        lines.append("  !! 不能当全量历史结论——该字段晚于大部分历史 run（见文件头限制 2）。")
    lines.append("")

    entry_ms: dict[str, list[int]] = defaultdict(list)
    for rec in with_tele:
        for phase in telemetry[rec["run_id"]]:
            name = str(phase.get("name"))
            value = phase.get("remaining_ms_at_entry")
            if isinstance(value, int) and not isinstance(value, bool):
                entry_ms[name].append(value)
    if entry_ms:
        lines.append(
            f"入口剩余预算 remaining_ms_at_entry（n 见每行，样本={len(with_tele)} run）"
        )
        lines.append("-" * 82)
        for name in ("brief", "composer", "judge"):
            values = entry_ms.get(name) or []
            if not values:
                continue
            stats = percentiles(values)
            lines.append(
                f"  {name:<9} n={len(values):<4} "
                f"min={stats['min']:>7}  p50={stats['p50']:>7}  "
                f"p90={stats['p90']:>7}  max={stats['max']:>7}  (ms)"
            )
        lines.append("")

    # ---- 原因分桶 ----
    bucket_runs: dict[str, list[dict[str, Any]]] = {k: [] for k in BUCKETS}
    unbucketed: list[tuple[dict[str, Any], str]] = []
    for rec in degraded:
        hit: set[str] = set()
        for message in rec["degrades"]:
            if not DEGRADE_PATTERN.search(message):
                continue
            bucket = classify(message)
            if bucket is None:
                unbucketed.append((rec, message))
            else:
                hit.add(bucket)
        for bucket in hit:
            bucket_runs[bucket].append(rec)

    lines.append("=" * 82)
    lines.append(
        "原因分桶（一个 run 可落多桶：一轮里 brief/composer/judge 各自的失败原因可能不同）"
    )
    lines.append("=" * 82)
    for name, (_pattern, desc) in BUCKETS.items():
        runs = bucket_runs[name]
        of_all = (100.0 * len(runs) / total) if total else 0.0
        of_deg = (100.0 * len(runs) / len(degraded)) if degraded else 0.0
        stamps = sorted(r["created_at"] for r in runs if r["created_at"])
        first = stamps[0][:10] if stamps else "-"
        lines.append(
            f"  {name:<22} {len(runs):>3} run  占全部 {of_all:>5.1f}%  "
            f"占降级 {of_deg:>5.1f}%  最早 {first}"
        )
        lines.append(f"  {'':<22} {desc}")
    lines.append("")

    if unbucketed:
        lines.append(
            f"未命中任何桶: {len(unbucketed)} 条（措辞可能已变，BUCKETS 需要补正则）"
        )
        for rec, message in unbucketed[:12]:
            lines.append(f"  {rec['created_at'][:19]}  {rec['run_id']}")
            lines.append(f"      {message[:120]}")
        lines.append("")

    # ---- 时间分布：回答「一直如此，还是某次改动之后才开始」 ----
    by_day_total: Counter[str] = Counter()
    by_day_deg: Counter[str] = Counter()
    by_day_bucket: dict[str, Counter[str]] = {k: Counter() for k in BUCKETS}
    for rec in records:
        day = (rec["created_at"] or "")[:10]
        if day:
            by_day_total[day] += 1
    for rec in degraded:
        day = (rec["created_at"] or "")[:10]
        if day:
            by_day_deg[day] += 1
    for name, runs in bucket_runs.items():
        for rec in runs:
            day = (rec["created_at"] or "")[:10]
            if day:
                by_day_bucket[name][day] += 1

    lines.append("=" * 82)
    lines.append("按日分布（判断是长期如此还是某次改动引入）")
    lines.append("=" * 82)
    for day in sorted(by_day_total):
        n_total = by_day_total[day]
        n_deg = by_day_deg[day]
        share = (100.0 * n_deg / n_total) if n_total else 0.0
        detail = "  ".join(
            f"{name.split('_')[0]}={by_day_bucket[name][day]}"
            for name in BUCKETS
            if by_day_bucket[name][day]
        )
        lines.append(
            f"  {day}  降级 {n_deg:>3}/{n_total:<4} ({share:>5.1f}%)  {detail}"
        )
    lines.append("")

    if show_runs:
        wanted = [bucket_filter] if bucket_filter else list(BUCKETS)
        for name in wanted:
            runs = bucket_runs.get(name) or []
            lines.append("=" * 82)
            lines.append(f"[{name}]  n={len(runs)}")
            lines.append("=" * 82)
            for rec in sorted(runs, key=lambda r: r["created_at"]):
                lines.append(f"  {rec['created_at'][:19]}  {rec['run_id']}")
                if rec["question"]:
                    lines.append(f"      Q: {rec['question'][:100]}")
                for message in rec["degrades"]:
                    if DEGRADE_PATTERN.search(message) and classify(message) == name:
                        lines.append(f"      -> {message[:140]}")
            lines.append("")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="把历史 run 的合成降级按原因归因，量化预算门槛的爆炸半径。"
    )
    parser.add_argument(
        "--ledger",
        action="append",
        default=None,
        help=f"台账目录，可重复。默认: {', '.join(str(p) for p in default_ledgers())}",
    )
    parser.add_argument(
        "--bucket",
        default=None,
        choices=sorted(BUCKETS),
        help="只打印某个桶的 run 明细",
    )
    parser.add_argument("--out", default=None, help="把完整结果写成 JSON")
    parser.add_argument(
        "--coverage-warn-below",
        type=float,
        default=80.0,
        help="降级 run 的遥测覆盖率低于此百分比时打印显式警告（默认 80）",
    )
    parser.add_argument(
        "--no-runs", action="store_true", help="只看汇总，不打 run 明细"
    )
    parser.add_argument(
        "--since",
        default=None,
        help=(
            "只统计 created_at >= 此值的 run，ISO 前缀即可"
            "（如 2026-08-05T23:15）。字典序比较，见限制 5。"
        ),
    )
    parser.add_argument(
        "--readiness",
        action="store_true",
        help=f"只报「窗口内攒够没有、还差几轮」，门槛 {READINESS_THRESHOLD}",
    )
    parser.add_argument(
        "--readiness-threshold",
        type=int,
        default=READINESS_THRESHOLD,
        help=f"覆盖就绪度门槛（默认 {READINESS_THRESHOLD}）",
    )
    args = parser.parse_args(argv)

    if args.ledger:
        ledgers = [Path(p).expanduser() for p in args.ledger]
    else:
        ledgers = default_ledgers()

    run_dirs = iter_run_dirs(ledgers)
    if not run_dirs:
        print("没找到任何 run 目录，检查 --ledger 指向。", file=sys.stderr)
        return 2

    records, unreadable = load_runs(run_dirs)
    if not records:
        print("run 目录存在但 run.json 全部无法解析。", file=sys.stderr)
        return 2

    total_before_filter = len(records)
    records = filter_since(records, args.since)

    if args.readiness:
        print(
            render_readiness(
                records,
                since=args.since,
                threshold=args.readiness_threshold,
            )
        )
        return 0

    if not records:
        print(
            f"--since {args.since} 之后没有任何 run"
            f"（台账全量 {total_before_filter}）。",
            file=sys.stderr,
        )
        return 1

    telemetry: dict[str, list[dict[str, Any]]] = {}
    for rec in records:
        phases = collect_phase_telemetry(rec["dir"])
        if phases:
            telemetry[rec["run_id"]] = phases

    report = render(
        records,
        unreadable=unreadable,
        ledgers=ledgers,
        telemetry=telemetry,
        coverage_warn_below=args.coverage_warn_below,
        bucket_filter=args.bucket,
        show_runs=not args.no_runs,
        since=args.since,
        total_before_filter=total_before_filter,
    )
    print(report)

    if args.out:
        degraded = [
            r for r in records if any(DEGRADE_PATTERN.search(m) for m in r["degrades"])
        ]
        payload = {
            "ledgers": [str(p) for p in ledgers],
            "since": args.since,
            "run_total": len(records),
            "run_total_before_since_filter": total_before_filter,
            "unreadable": unreadable,
            "degrade_pattern": DEGRADE_PATTERN.pattern,
            "telemetry_coverage": {
                "field": TELEMETRY_MARKER,
                "runs_with_telemetry": len(telemetry),
                "runs_total": len(records),
                "degraded_with_telemetry": sum(
                    1 for r in degraded if telemetry.get(r["run_id"])
                ),
                "degraded_total": len(degraded),
            },
            "buckets": {
                name: [
                    {
                        "run_id": r["run_id"],
                        "created_at": r["created_at"],
                        "question": r["question"],
                        "degrades": [
                            m
                            for m in r["degrades"]
                            if DEGRADE_PATTERN.search(m) and classify(m) == name
                        ],
                    }
                    for r in degraded
                    if any(
                        DEGRADE_PATTERN.search(m) and classify(m) == name
                        for m in r["degrades"]
                    )
                ]
                for name in BUCKETS
            },
        }
        Path(args.out).expanduser().write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"完整结果 -> {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
