#!/usr/bin/env python3
"""预测台账体检：只读，回答「迭代机制本身健不健康」。

已有三件工具各管一段，本脚本不重复它们：
``audit_ledger_spec_crosswalk.py`` 管 spec↔台账对账与重号，``claim_ledger_id.py`` 管取号，
``progress_observatory.py`` 只数 Open 表的 pending 个数。这里补的是它们都不看的四件事：

1. **fix_type 分布**：修补都堆在哪一层。2026-09-30 质检读数 HARNESS_FIX 占 Open 表 76%，
   而 ``SYSTEM_PROMPT_FIX`` 为 0、没有任何条目把问题归到模型本身——这个比例本身就是
   「只在一层找原因」的信号，但以前没人算过。
2. **pending 积压的年龄**：按 ID 里的日期算挂了多少天，超过阈值的单列（``--stale-days``），
   并按台账「过期规则」分三档：新鲜（≤14 天）/ 临期（15–30 天）/ 过期（>30 天，``--expire-days``）。
   过期 ≠ refuted（没测不等于判错）：过期行要么按「怎么验」重验，要么 outcome 写 ``expired``
   显式关闭。本脚本只读、不改任何行——它只负责把该处理的行点名。
3. **枚举外的 fix_type**：台账规则「只能取这 7 个值，不要发明新值」，此前靠自觉。
4. **refuted 连击**：台账规则「同类 fix_type 连续 ≥3 次 refuted → 停止再堆同类修补，
   升格质疑 HARNESS/架构层」，此前没有任何东西在数。按 ID 时间序、只看已结案条目。

Open 表的取行口径直接复用 ``audit_ledger_spec_crosswalk._ledger_rows``——两个脚本对
「哪些行算 Open」必须同一个答案。

退出码：默认 0（体检报告）；``--strict`` 时枚举外取值或连击告警 → 1。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

SELF_DIR = Path(__file__).resolve().parent
REPO_ROOT = SELF_DIR.parent
if str(SELF_DIR) not in sys.path:
    sys.path.insert(0, str(SELF_DIR))

from audit_ledger_spec_crosswalk import _ledger_rows  # noqa: E402

# 台账「记账规则」节的冻结枚举，原样照抄；新增须走 skill 的 known-gaps.md 晋升。
FIX_TYPES = (
    "SYSTEM_PROMPT_FIX",
    "TOOL_DESCRIPTION_FIX",
    "ROUTING_FIX",
    "DATA_CONTRACT_FIX",
    "HARNESS_FIX",
    "EVAL_ONLY",
    "NO_SYSTEM_FIX",
)
RESOLVED = frozenset({"confirmed", "refuted", "partially_confirmed"})
# 过期规则（docs/prediction-ledger.md 记账规则）：过期未验、显式关闭的 outcome。它不是结案，
# 不进 refuted 连击，也不进命中率的分母。
CLOSED_UNVERIFIED = "expired"
STREAK_ALERT = 3
DEFAULT_STALE_DAYS = 14
DEFAULT_EXPIRE_DAYS = 30
AGE_BUCKETS = ("fresh", "due", "expired")

_CELL_SPLIT = re.compile(r"(?<!\\)\|")
_TICKED = re.compile(r"`([^`]+)`")
_ID_DATE = re.compile(r"R-(\d{8})-\d{2}")
# 比 crosswalk 号型宽：用来把「在 Open 段、但号型不合规被豁免」的行单独点名，而不是静默丢掉。
_LOOSE_ROW = re.compile(r"^\|\s*`(R-[^`]+)`")


@dataclass(frozen=True)
class LedgerRow:
    rid: str
    fix_type: str
    outcome: str
    opened: str  # ISO 日期，取自 ID


def _cells(line: str) -> list[str]:
    parts = _CELL_SPLIT.split(line.strip())
    return [cell.strip() for cell in parts[1:-1]]


def _first_token(cell: str) -> str:
    """单元格的取值：有反引号取第一个反引号里的，否则取第一个词。

    台账常在取值后跟注解（``HARNESS_FIX``（候，W2b 未派）/ ``confirmed``（2026-09-xx …）），
    注解不是取值的一部分。
    """

    ticked = _TICKED.findall(cell)
    if ticked:
        return ticked[0].strip()
    head = re.split(r"[\s（(]", cell.replace("*", " ").strip(), maxsplit=1)[0]
    return head.strip("`")


def _fix_type(cells: list[str]) -> str:
    """取第 3 列；列被正文里未转义的 ``|`` 挤歪（不是 6 列）时，退回在整行找枚举值。"""

    value = _first_token(cells[2]) if len(cells) >= 3 else ""
    if value in FIX_TYPES or (value and len(cells) == 6):
        return value
    for cell in cells[1:-1]:
        for token in _TICKED.findall(cell) + cell.split():
            if token.strip("`") in FIX_TYPES:
                return token.strip("`")
    return value


def _outcome(cells: list[str]) -> str:
    return _first_token(cells[-1]) if cells else ""


def nonconforming_open_ids(root: Path) -> list[str]:
    """Open 段里号型不合规（带后缀 / 非数字序号）、被 crosswalk 口径豁免的行。"""

    _all_rows, open_rows = _ledger_rows(root)
    canonical = {rid for rid, _line in open_rows}
    found: list[str] = []
    in_open = False
    ledger = root / "docs" / "prediction-ledger.md"
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if line.startswith("### "):
            in_open = line.startswith("### Open")
        match = _LOOSE_ROW.match(line) if in_open else None
        if match and match.group(1) not in canonical:
            found.append(match.group(1))
    return found


def parse_open_rows(root: Path) -> list[LedgerRow]:
    _all_rows, open_rows = _ledger_rows(root)
    rows: list[LedgerRow] = []
    for rid, line in open_rows:
        cells = _cells(line)
        stamp = _ID_DATE.match(rid)
        opened = datetime.strptime(stamp.group(1), "%Y%m%d").date().isoformat() if stamp else ""
        rows.append(LedgerRow(rid, _fix_type(cells), _outcome(cells), opened))
    return rows


def refuted_streaks(rows: list[LedgerRow]) -> dict[str, dict[str, int]]:
    """每个 fix_type：已结案条目按 ID 时间序的「当前连续 refuted」与「历史最长」。"""

    result: dict[str, dict[str, int]] = {}
    for fix_type in sorted({row.fix_type for row in rows if row.fix_type}):
        current = longest = 0
        for row in sorted(rows, key=lambda item: item.rid):
            if row.fix_type != fix_type or row.outcome not in RESOLVED:
                continue
            current = current + 1 if row.outcome == "refuted" else 0
            longest = max(longest, current)
        result[fix_type] = {"current": current, "longest": longest}
    return result


def age_bucket(age_days: int | None, *, stale_days: int, expire_days: int) -> str:
    """pending 行的年龄档：fresh ≤ stale_days < due ≤ expire_days < expired；无日期单列。"""

    if age_days is None:
        return "undated"
    if age_days <= stale_days:
        return "fresh"
    if age_days <= expire_days:
        return "due"
    return "expired"


def verdict_summary(
    rows: list[LedgerRow], buckets: dict[str, list[LedgerRow]]
) -> dict[str, int]:
    """证实 / 部分证实 / 证伪 / 过期 / 待定 / 其他——六格相加恰好等于 Open 行数。

    过期 = pending 超过过期线（待处理）+ outcome 已写 ``expired``（已显式关闭）。
    """

    outcomes = Counter(row.outcome for row in rows)
    expired_open = len(buckets.get("expired", []))
    expired_closed = outcomes[CLOSED_UNVERIFIED]
    pending_live = outcomes["pending"] - expired_open
    named = (
        outcomes["confirmed"]
        + outcomes["partially_confirmed"]
        + outcomes["refuted"]
        + expired_open
        + expired_closed
        + pending_live
    )
    return {
        "confirmed": outcomes["confirmed"],
        "partially_confirmed": outcomes["partially_confirmed"],
        "refuted": outcomes["refuted"],
        "expired": expired_open + expired_closed,
        "expired_open": expired_open,
        "expired_closed": expired_closed,
        "pending": pending_live,
        "other": len(rows) - named,
    }


def build_report(
    root: Path, *, as_of: date, stale_days: int, expire_days: int = DEFAULT_EXPIRE_DAYS
) -> dict[str, object]:
    if expire_days < stale_days:
        raise ValueError(f"过期线 {expire_days} 天不能早于临期线 {stale_days} 天")
    rows = parse_open_rows(root)
    outcomes = Counter(row.outcome or "(空)" for row in rows)
    fix_types = Counter(row.fix_type or "(空)" for row in rows)
    pending = [row for row in rows if row.outcome == "pending"]

    def age(row: LedgerRow) -> int | None:
        return (as_of - date.fromisoformat(row.opened)).days if row.opened else None

    buckets: dict[str, list[LedgerRow]] = {}
    for row in pending:
        key = age_bucket(age(row), stale_days=stale_days, expire_days=expire_days)
        buckets.setdefault(key, []).append(row)
    bucket_counts = {key: len(buckets.get(key, [])) for key in AGE_BUCKETS}
    if buckets.get("undated"):
        bucket_counts["undated"] = len(buckets["undated"])
    expired_pending = sorted(
        ({"id": row.rid, "fix_type": row.fix_type, "age_days": age(row)} for row in buckets.get("expired", [])),
        key=lambda item: (-(item["age_days"] or 0), item["id"]),
    )

    stale = sorted(
        (
            {"id": row.rid, "fix_type": row.fix_type, "age_days": age(row)}
            for row in pending
            if (age(row) or 0) > stale_days
        ),
        key=lambda item: -(item["age_days"] or 0),
    )
    newest = max(rows, key=lambda row: row.rid) if rows else None
    streaks = refuted_streaks(rows)
    alerts = [
        {"fix_type": fix_type, **streak}
        for fix_type, streak in streaks.items()
        if streak["current"] >= STREAK_ALERT
    ]
    invalid = sorted(
        {row.fix_type for row in rows if row.fix_type and row.fix_type not in FIX_TYPES}
    )
    return {
        "as_of": as_of.isoformat(),
        "open_rows": len(rows),
        "outcomes": dict(outcomes.most_common()),
        "fix_types": dict(fix_types.most_common()),
        "pending": len(pending),
        "stale_days": stale_days,
        "stale_pending": stale,
        "expire_days": expire_days,
        "pending_age_buckets": bucket_counts,
        "expired_pending": expired_pending,
        "verdicts": verdict_summary(rows, buckets),
        "newest": {"id": newest.rid, "age_days": age(newest)} if newest else None,
        "invalid_fix_types": invalid,
        "missing_fix_type": [row.rid for row in rows if not row.fix_type],
        "nonconforming_ids": nonconforming_open_ids(root),
        "refuted_streaks": streaks,
        "streak_alerts": alerts,
        "rows": [asdict(row) for row in rows],
    }


def _pct(part: int, whole: int) -> str:
    return f"{part / whole:.0%}" if whole else "-"


def render(report: dict[str, object]) -> str:
    total = int(report["open_rows"])  # type: ignore[arg-type]
    outcomes: dict[str, int] = report["outcomes"]  # type: ignore[assignment]
    fix_types: dict[str, int] = report["fix_types"]  # type: ignore[assignment]
    stale: list[dict] = report["stale_pending"]  # type: ignore[assignment]
    newest = report["newest"]
    lines = [
        f"预测台账 Open 表：{total} 行（截至 {report['as_of']}）",
        "outcome：" + " · ".join(f"{k} {v}" for k, v in outcomes.items()),
        "fix_type：" + " · ".join(f"{k} {v}（{_pct(v, total)}）" for k, v in fix_types.items()),
    ]
    absent = [name for name in FIX_TYPES if name not in fix_types]
    if absent:
        lines.append("从未出现的 fix_type：" + "、".join(absent))
    if isinstance(newest, dict):
        lines.append(f"最新条目：{newest['id']}（{newest['age_days']} 天前）")
    lines.append(
        f"pending 超过 {report['stale_days']} 天：{len(stale)} / {report['pending']} 行"
        + (f"，最老 {stale[0]['id']}（{stale[0]['age_days']} 天）" if stale else "")
    )
    verdicts = report.get("verdicts")
    if isinstance(verdicts, dict):
        lines.append(
            f"结案口径：证实 {verdicts['confirmed']} · 部分证实 {verdicts['partially_confirmed']}"
            f" · 证伪 {verdicts['refuted']}"
            f" · 过期 {verdicts['expired']}（待处理 {verdicts['expired_open']} / 已关闭 {verdicts['expired_closed']}）"
            f" · 待定 {verdicts['pending']} · 其他 {verdicts['other']}"
        )
    ages = report.get("pending_age_buckets")
    if isinstance(ages, dict):
        stale_days, expire_days = report["stale_days"], report["expire_days"]
        line = (
            f"pending 年龄：新鲜（≤{stale_days} 天）{ages['fresh']}"
            f" · 临期（{int(stale_days) + 1}–{expire_days} 天）{ages['due']}"  # type: ignore[call-overload]
            f" · 过期（>{expire_days} 天）{ages['expired']}"
        )
        if ages.get("undated"):
            line += f" · 无日期 {ages['undated']}"
        lines.append(line)
    expired_rows = report.get("expired_pending") or []
    if expired_rows:
        head = "、".join(f"{r['id']}（{r['age_days']} 天）" for r in expired_rows[:5])  # type: ignore[index]
        lines.append(
            f"过期待处理 {len(expired_rows)} 行（过期≠证伪：重验，或 outcome 写 `{CLOSED_UNVERIFIED}` 显式关闭）："  # type: ignore[arg-type]
            + head
            + ("…" if len(expired_rows) > 5 else "")  # type: ignore[arg-type]
        )
    invalid = report["invalid_fix_types"]
    lines.append("枚举外 fix_type：" + ("、".join(invalid) if invalid else "无"))  # type: ignore[arg-type]
    missing = report["missing_fix_type"]
    if missing:
        lines.append(f"缺 fix_type 的行：{len(missing)}（{'、'.join(missing[:5])}…）")  # type: ignore[index]
    odd = report["nonconforming_ids"]
    if odd:
        lines.append(
            f"另有 {len(odd)} 行号型不合规、按 crosswalk 口径不计入上面的数："  # type: ignore[arg-type]
            + "、".join(odd)  # type: ignore[arg-type]
        )
    alerts = report["streak_alerts"]
    lines.append(
        f"refuted 连击 ≥{STREAK_ALERT}（台账规则：停止同类修补、升格质疑）："
        + ("、".join(f"{a['fix_type']}×{a['current']}" for a in alerts) if alerts else "无")  # type: ignore[union-attr]
    )
    return "\n".join(lines)


# ── 过期分诊表（--worksheet）──────────────────────────────────────────────
# 过期规则把「待定超过 30 天」单列出来，但每条要么重验、要么写明理由关成 expired——
# 这是逐条判断，不能机械批量（2026-10-01 试过：标志只覆盖 30/101，来源散在 78 组）。
# 分诊表只做两件机械的事，帮判断的人省时间：抄出「怎么验」，再列出开立日之后、文件名
# 带日期的文档里有没有再提到这个号（可能的后续证据）。它不改台账、不下结论。

_EXACT_ID = re.compile(r"(?<![\w-])(R-\d{8}-\d{2})(?![\w-])")
_NAME_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_LIVE_MARKERS = ("live", "Live", "切流", "生产", "8792", "真实对话", "真实题", "上线")


def verification_kind(how: str) -> str:
    """「怎么验」里写的是哪类证据：要生产读数 / 离线可验 / 未写明（只看关键词，是提示不是判定）。"""

    if any(marker in how for marker in _LIVE_MARKERS):
        return "要生产读数"
    if "离线" in how:
        return "离线可验"
    return "未写明"


def later_mentions(root: Path, ids: set[str]) -> dict[str, list[tuple[str, str]]]:
    """docs/ 下文件名带日期的 Markdown 里提到这些号的位置（台账本身不算）：号 → [(日期, 相对路径)]。"""

    found: dict[str, list[tuple[str, str]]] = {}
    docs = root / "docs"
    for path in sorted(docs.rglob("*.md")):
        if path.name == "prediction-ledger.md":
            continue
        stamp = _NAME_DATE.search(path.name)
        if stamp is None:
            continue
        hits = set(_EXACT_ID.findall(path.read_text(encoding="utf-8", errors="replace"))) & ids
        for rid in hits:
            found.setdefault(rid, []).append(("".join(stamp.groups()), str(path.relative_to(root))))
    return found


def build_worksheet(root: Path, report: dict[str, object]) -> list[dict[str, object]]:
    expired = list(report["expired_pending"])  # type: ignore[arg-type]
    _all_rows, open_rows = _ledger_rows(root)
    line_of = dict(open_rows)
    mentions = later_mentions(root, {str(item["id"]) for item in expired})
    rows = []
    for item in expired:
        rid = str(item["id"])
        cells = _cells(line_of.get(rid, ""))
        how = cells[4] if len(cells) == 6 else ""
        opened = rid[2:10]
        later = sorted((d, path) for d, path in mentions.get(rid, []) if d > opened)
        rows.append({
            "id": rid,
            "fix_type": item["fix_type"],
            "age_days": item["age_days"],
            "verification": verification_kind(how),
            "how": re.sub(r"\s+", " ", how.replace("**", ""))[:90],
            "later_mentions": len(later),
            "latest_mention": later[-1][1] if later else "",
        })
    return rows


def render_worksheet(rows: list[dict[str, object]], as_of: str) -> str:
    kinds = Counter(str(row["verification"]) for row in rows)
    with_later = sum(1 for row in rows if row["later_mentions"])
    lines = [
        f"# 过期待定分诊表（as-of {as_of}，{len(rows)} 条）",
        "",
        "- 「怎么验」写的证据类型：" + "、".join(f"{k} {v}" for k, v in sorted(kinds.items())),
        f"- 开立日之后有文档再提到这个号（可能的后续证据，先看它）：{with_later} 条；没有：{len(rows) - with_later} 条",
        "- 每条只有两种处理：重验后写 confirmed / refuted；或改成 `expired` 并写理由。过期≠证伪，不进连击。",
        "",
        "| 号 | fix_type | 天数 | 证据类型 | 后续提及 | 最近一处 | 怎么验（摘录） |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in sorted(rows, key=lambda r: (-int(r["later_mentions"] > 0), -int(r["age_days"] or 0))):
        how = str(row["how"]).replace("|", "/")
        lines.append(
            f"| {row['id']} | {row['fix_type']} | {row['age_days']} | {row['verification']} | "
            f"{row['later_mentions']} | {row['latest_mention'] or '—'} | {how} |"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="预测台账体检（只读）")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="仓库根（默认本仓）")
    parser.add_argument("--as-of", type=date.fromisoformat, default=None, help="按哪天算年龄，默认今天")
    parser.add_argument("--stale-days", type=int, default=DEFAULT_STALE_DAYS, help="新鲜/临期分界（天）")
    parser.add_argument("--expire-days", type=int, default=DEFAULT_EXPIRE_DAYS, help="临期/过期分界（天）")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON（含逐行明细）")
    parser.add_argument("--strict", action="store_true", help="枚举外取值或 refuted 连击告警时 exit 1")
    parser.add_argument(
        "--worksheet", action="store_true",
        help="只出过期待定的分诊表（怎么验 + 开立日之后的文档提及），给逐条重验或关闭用",
    )
    args = parser.parse_args(argv)
    ledger = args.root / "docs" / "prediction-ledger.md"
    if not ledger.is_file():
        print(f"找不到台账：{ledger}", file=sys.stderr)
        return 2
    if args.expire_days < args.stale_days:
        print(f"--expire-days（{args.expire_days}）不能小于 --stale-days（{args.stale_days}）", file=sys.stderr)
        return 2
    report = build_report(
        args.root,
        as_of=args.as_of or date.today(),
        stale_days=args.stale_days,
        expire_days=args.expire_days,
    )
    if args.worksheet:
        sheet = build_worksheet(args.root, report)
        print(json.dumps(sheet, ensure_ascii=False, indent=2) if args.json else render_worksheet(sheet, str(report["as_of"])))
        return 0
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else render(report))
    if args.strict and (report["invalid_fix_types"] or report["streak_alerts"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
