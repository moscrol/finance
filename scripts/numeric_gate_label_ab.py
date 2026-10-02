#!/usr/bin/env python3
"""数值门标签 A/B 回放：给存证 episode 的证据「模拟改标签」，看待核说明消失 / 新增了哪些。

用途：finance_query 改字段标签（比如给百分数字段补上 ``%``）之前，在全部存证 run 上量一次
影响。#986 / #988 的「950 个存证 run A/B」就是这件事，本脚本把它固化成一条命令。

两臂，数值门都用当前代码（``_novel_numeric_condition_tokens``，公开稿里「待核：…未在证据中
找到出处」的来源）：

- **原样**：存证证据不动。
- **改标签**：只把指定数据集的 finance_query 证据卡里、指定的字段名换成新名，再跑一次。
  ``content_hash`` 不变、绑定照旧——模拟的是「同一张卡、新标签」，不是另一张卡。

读法（#988 口径）：**新增必须为 0**；消失的逐条看，应当都是照实复述。
原样臂跨版本对照：在基线树和改动树上各跑一次 ``--json``，再用 ``--baseline`` 比两份原样臂；
只改标签、没动数值门时两份应当逐 run 相同。

只读 ``continuous-episode.json``：不调模型、不改 run、不起服务。存证重建复用
``scripts/judge_loss_point_replay.py`` 的 ``_rebuild_outcome``（保留结构化观察值，与生产一致）。

退出码：0 = 新增 0（且给了 ``--baseline`` 时原样臂无漂移）；1 = 有新增待核或原样臂漂移；
2 = 一个存证都没找到，或参数不合法。

用法::

    # 默认：FORESIGHT_USERS_DIR 下全部用户，改标签集为 2026-09-30 质检那三处
    python scripts/numeric_gate_label_ab.py
    python scripts/numeric_gate_label_ab.py --users default --since 20260901
    # 直接给存证目录或文件（递归找 continuous-episode.json）
    python scripts/numeric_gate_label_ab.py docs/verification/2026-09-21-judge-mode-k3/evidence
    # 自定义改标签（可重复）；给了就不再用默认集
    python scripts/numeric_gate_label_ab.py --relabel market_daily:强势股加权涨幅=强势股加权涨幅%
    # 原样臂跨版本对照
    python scripts/numeric_gate_label_ab.py --json base.json        # 在基线树上
    python scripts/numeric_gate_label_ab.py --baseline base.json    # 在改动树上
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable, Mapping, NamedTuple

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from intelligence.services.episode_semantic_verifier import (  # noqa: E402
    _novel_numeric_condition_tokens,
    _numbered_sentences,
)
from intelligence.services.episode_verifier import verify_episode_outcome  # noqa: E402
from intelligence.services.finance_query import _DATASETS  # noqa: E402
from intelligence.services.research_contract import ResearchTaskContract  # noqa: E402

RECEIPT_NAME = "continuous-episode.json"


class Relabel(NamedTuple):
    dataset: str
    old: str
    new: str


# 2026-09-30 部件质检「内容正确性」一行：三个百分数字段的标签补上 %（PR #10）。
DEFAULT_RELABELS = (
    Relabel("market_daily", "强势股加权涨幅", "强势股加权涨幅%"),
    Relabel("market_daily", "强势股成交占比", "强势股成交占比%"),
    Relabel("sector_period_rank_daily", "区间涨幅", "区间涨幅%"),
)

_RELABEL_ARG_RE = re.compile(r"^(?P<dataset>[a-z0-9_]+):(?P<old>[^=]+)=(?P<new>.+)$")


def parse_relabel(raw: str) -> Relabel:
    """``dataset:旧字段名=新字段名`` → Relabel；数据集必须是 finance_query 注册过的。"""

    match = _RELABEL_ARG_RE.match(raw.strip())
    if match is None:
        raise ValueError(f"--relabel 要写成 dataset:旧名=新名，收到 {raw!r}")
    item = Relabel(match["dataset"], match["old"].strip(), match["new"].strip())
    if item.dataset not in _DATASETS:
        raise ValueError(f"finance_query 没有数据集 {item.dataset!r}")
    if not item.old or not item.new or item.old == item.new:
        raise ValueError(f"旧名和新名都不能为空，也不能相同：{raw!r}")
    return item


def _load_replay_module():
    """存证重建与 judge_loss_point_replay 共用一份实现，不另抄一套。"""

    name = "judge_loss_point_replay"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def evidence_dataset(item: Any) -> str | None:
    """finance_query 证据卡属于哪个数据集；别的工具一律 None（本脚本只模拟它的标签）。

    新存证看 ``independent_key=duckdb:<dataset>:<日期>``；老存证没有这个键，退回标题：
    标题是「数据集中文名（日期）」。
    """

    if getattr(item, "tool", "") != "finance_query":
        return None
    key = getattr(item, "independent_key", "") or ""
    if key.startswith("duckdb:"):
        parts = key.split(":")
        if len(parts) >= 3 and parts[1] in _DATASETS:
            return parts[1]
    title = getattr(item, "title", "") or ""
    for name, definition in _DATASETS.items():
        if title == definition.label or title.startswith(definition.label + "（"):
            return name
    return None


def relabel_detail(detail: str, relabels: Iterable[Relabel]) -> str:
    """只换**完整字段名**：前面是行首或分隔符、后面紧跟 = / : 。

    ``近5日区间涨幅=…`` 不是 ``区间涨幅``，不动；值和别的字段一律不动。
    """

    for item in relabels:
        pattern = re.compile(
            r"(?P<pre>^|[；;\n])(?P<ws>\s*)" + re.escape(item.old) + r"(?P<sep>\s*[=:：])"
        )
        detail = pattern.sub(lambda m, new=item.new: f"{m['pre']}{m['ws']}{new}{m['sep']}", detail)
    return detail


def relabel_evidence(evidence: tuple[Any, ...], relabels: tuple[Relabel, ...]) -> tuple[tuple[Any, ...], int]:
    """按数据集分发改标签；返回新证据元组与「实际被改动的卡数」。content_hash 原样保留。"""

    by_dataset: dict[str, list[Relabel]] = {}
    for item in relabels:
        by_dataset.setdefault(item.dataset, []).append(item)
    touched = 0
    rebuilt = []
    for item in evidence:
        dataset = evidence_dataset(item)
        targets = by_dataset.get(dataset or "")
        if targets:
            detail = relabel_detail(item.detail, targets)
            if detail != item.detail:
                touched += 1
                item = replace(item, detail=detail)
        rebuilt.append(item)
    return tuple(rebuilt), touched


def _doubts(verified: Any) -> tuple[dict[int, tuple[str, ...]], dict[int, str]]:
    sentences = _numbered_sentences(verified.outcome.draft)
    texts = {int(s["index"]): str(s.get("text") or "") for s in sentences if isinstance(s.get("index"), int)}
    return _novel_numeric_condition_tokens(sentences, verified), texts


def _diff(
    before: Mapping[int, tuple[str, ...]],
    after: Mapping[int, tuple[str, ...]],
    texts: Mapping[int, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    gone: list[dict[str, Any]] = []
    added: list[dict[str, Any]] = []
    for index in sorted(set(before) | set(after)):
        old, new = Counter(before.get(index, ())), Counter(after.get(index, ()))
        removed = list((old - new).elements())
        appeared = list((new - old).elements())
        if removed:
            gone.append({"index": index, "sentence": texts.get(index, ""), "tokens": removed})
        if appeared:
            added.append({"index": index, "sentence": texts.get(index, ""), "tokens": appeared})
    return gone, added


def _user_of(path: Path) -> str:
    # 标准布局 <users_root>/<user>/runs/<run_id>/continuous-episode.json
    if len(path.parents) >= 3 and path.parents[1].name == "runs":
        return path.parents[2].name
    return "-"


def replay_ab(path: Path, relabels: tuple[Relabel, ...]) -> dict[str, Any]:
    """一个存证 → 两臂的待核数与差异。存证形状漂移时记错误，不假装重放成功。"""

    row: dict[str, Any] = {
        "run": path.parent.name,
        "user": _user_of(path),
        "path": str(path),
        "question": "",
        "error": None,
        "touched_evidence": 0,
        "asis": {},
        "relabeled": {},
        "disappeared": [],
        "new": [],
    }
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
        row["question"] = str((receipt.get("task_frame") or {}).get("raw_question") or "")[:60]
        contract = ResearchTaskContract.from_dict(receipt.get("contract") or {})
        outcome = _load_replay_module()._rebuild_outcome(receipt.get("outcome") or {})
        verified = verify_episode_outcome(contract, outcome)
        before, texts = _doubts(verified)
        evidence, touched = relabel_evidence(tuple(verified.outcome.evidence), relabels)
        after = before
        if touched:
            after, _ = _doubts(replace(verified, outcome=replace(verified.outcome, evidence=evidence)))
        gone, added = _diff(before, after, texts)
        row.update(
            touched_evidence=touched,
            asis={str(k): list(v) for k, v in sorted(before.items())},
            relabeled={str(k): list(v) for k, v in sorted(after.items())},
            disappeared=gone,
            new=added,
        )
    except Exception as exc:  # noqa: BLE001 — 逐个存证兜底，汇总里点名
        row["error"] = f"{type(exc).__name__}: {exc}"[:200]
    return row


def iter_receipts(
    paths: list[Path],
    *,
    users_root: Path | None,
    users: list[str] | None,
    since: str | None,
) -> list[Path]:
    found: list[Path] = []
    if paths:
        for path in paths:
            if path.is_file():
                found.append(path)
            elif path.is_dir():
                found.extend(sorted(path.rglob(RECEIPT_NAME)))
    elif users_root is not None and users_root.is_dir():
        names = users or sorted(p.name for p in users_root.iterdir() if (p / "runs").is_dir())
        for user in names:
            found.extend(sorted((users_root / user / "runs").glob(f"run_*/{RECEIPT_NAME}")))
    if since:
        found = [p for p in found if not p.parent.name.startswith("run_") or p.parent.name[4:12] >= since]
    return found


def compare_baseline(rows: list[dict[str, Any]], baseline_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """原样臂逐 run 对比（基线树 vs 改动树）。只比两边都重放成功的 run。"""

    base = {(r["user"], r["run"]): r for r in baseline_rows}
    here = {(r["user"], r["run"]): r for r in rows}
    drift = []
    for key in sorted(set(base) & set(here)):
        b, h = base[key], here[key]
        if b.get("error") or h.get("error"):
            continue
        if b.get("asis") != h.get("asis"):
            drift.append({"user": key[0], "run": key[1], "baseline": b.get("asis"), "current": h.get("asis")})
    return {
        "drift": drift,
        "only_in_baseline": sorted(f"{u}/{r}" for u, r in set(base) - set(here)),
        "only_in_current": sorted(f"{u}/{r}" for u, r in set(here) - set(base)),
    }


def _count(items: list[dict[str, Any]]) -> int:
    return sum(len(item["tokens"]) for item in items)


def _print_items(title: str, rows: list[dict[str, Any]], key: str, limit: int) -> None:
    shown = 0
    for row in rows:
        for item in row[key]:
            if shown == 0:
                print(title)
            if limit and shown >= limit:
                print("  ……其余略（--show 0 看全部）")
                return
            tokens = "、".join(f"「{t}」" for t in item["tokens"])
            sentence = item["sentence"].replace("\n", " ")
            print(f"  {row['user']}/{row['run']} 句{item['index']}：{tokens} ← {sentence[:90]}")
            shown += 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*", help="存证文件或目录（递归找 continuous-episode.json）；不给就扫 users 根目录")
    parser.add_argument("--users-root", default=None, help="users 根目录；默认 FORESIGHT_USERS_DIR 或 ~/.local/share/finance-workbench/users")
    parser.add_argument("--users", default=None, help="逗号分隔用户名；默认根目录下全部有 runs/ 的用户")
    parser.add_argument("--since", default=None, help="run id 里的日期下限 YYYYMMDD")
    parser.add_argument("--relabel", action="append", default=[], help="dataset:旧字段名=新字段名，可重复；给了就不用默认集")
    parser.add_argument("--json", default=None, help="逐 run 结果写成 JSON 文件")
    parser.add_argument("--baseline", default=None, help="另一棵树上 --json 的输出：比两份原样臂")
    parser.add_argument("--show", type=int, default=50, help="逐条列出的上限（0 = 全部）")
    args = parser.parse_args(argv)

    try:
        relabels = tuple(parse_relabel(raw) for raw in args.relabel) or DEFAULT_RELABELS
    except ValueError as exc:
        print(f"参数错误：{exc}", file=sys.stderr)
        return 2
    users = [u.strip() for u in args.users.split(",") if u.strip()] if args.users else None
    users_root = None
    if not args.paths:
        users_root = (
            Path(args.users_root).expanduser() if args.users_root else _load_replay_module()._default_users_root()
        )
    receipts = iter_receipts(
        [Path(p).expanduser() for p in args.paths], users_root=users_root, users=users, since=args.since
    )
    if not receipts:
        where = ", ".join(args.paths) if args.paths else str(users_root)
        print(f"没找到任何 {RECEIPT_NAME}（{where}）", file=sys.stderr)
        return 2

    rows = [replay_ab(path, relabels) for path in receipts]
    ok = [r for r in rows if not r["error"]]
    errors = [r for r in rows if r["error"]]
    touched_runs = [r for r in ok if r["touched_evidence"]]
    asis_total = sum(len(tokens) for r in ok for tokens in r["asis"].values())
    after_total = sum(len(tokens) for r in ok for tokens in r["relabeled"].values())
    gone_total = sum(_count(r["disappeared"]) for r in ok)
    new_total = sum(_count(r["new"]) for r in ok)

    scope = ", ".join(args.paths) if args.paths else f"{users_root}（用户：{', '.join(users) if users else '全部'}）"
    print(f"存证 episode：{len(rows)} 个；重放失败 {len(errors)} 个；范围 {scope}；since {args.since or '-'}")
    print("改标签：" + "；".join(f"{r.dataset}「{r.old}」→「{r.new}」" for r in relabels))
    print(
        f"涉及证据卡 {sum(r['touched_evidence'] for r in ok)} 张，分布在 {len(touched_runs)} 个 run"
    )
    print(f"原样臂待核 {asis_total} 处 → 改标签臂待核 {after_total} 处：消失 {gone_total} 处，新增 {new_total} 处")
    for row in errors[:10]:
        print(f"  重放失败 {row['user']}/{row['run']}：{row['error']}")
    if len(errors) > 10:
        print(f"  ……另有 {len(errors) - 10} 个重放失败（--json 看全部）")
    _print_items("消失（逐条确认是照实复述）：", ok, "disappeared", args.show)
    _print_items("新增（必须为 0）：", ok, "new", args.show)

    verdict = 0 if new_total == 0 else 1
    if args.baseline:
        baseline_rows = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        result = compare_baseline(rows, baseline_rows)
        print(
            f"原样臂对照 {args.baseline}：漂移 {len(result['drift'])} 个 run；"
            f"只在基线 {len(result['only_in_baseline'])} 个，只在本次 {len(result['only_in_current'])} 个"
        )
        for item in result["drift"][:10]:
            print(f"  漂移 {item['user']}/{item['run']}：基线 {item['baseline']} → 本次 {item['current']}")
        if result["drift"]:
            verdict = 1
    if args.json:
        Path(args.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"逐 run 结果 → {args.json}")
    if verdict == 0:
        print("✅ 新增 0" + ("、原样臂无漂移" if args.baseline else ""))
    else:
        print("❌ 有新增待核或原样臂漂移，逐条看上面")
    return verdict


if __name__ == "__main__":
    raise SystemExit(main())
