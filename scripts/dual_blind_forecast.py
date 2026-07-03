#!/usr/bin/env python3
"""双盲同题答卷工装：输入冻结清单 + 机器可读答卷校验 + 跨期自动聚合。

对应 docs/learning/dual-blind-forecast-template.md 的三个改进点：

1. ``manifest``：答卷前先生成输入清单（DuckDB 截止日、材料文件 sha256、
   知识库 commit id），写入台账目录 ``<date>.manifest.json``。两份答卷
   必须引用同一份清单的 ``manifest_sha``，保证冻结输入一致（控制变量）。
2. ``validate``：校验机器可读答卷 ``<date>.answer.<agent>.json`` 的必填
   字段与 manifest 一致性；答卷 markdown 照旧给人读，JSON 给机器算。
3. ``aggregate``：跨期聚合所有答卷 + 回检数据，按 agent 输出标的池
   T+1/T+3 均值、跑赢比例、阈值命中率等长期统计（单期噪声大，看聚合）。
4. ``verdict``：盘后验证结果的唯一机器可读落点 ``<date>.verdict.json``。
   逐假设 {id, agent, verdict: hit/miss/partial/unverifiable, actual, evidence_ref}，
   假设 id 必须引用对应答卷的假设 id（答卷可选 ``hypotheses`` 字段；未声明时
   从 thresholds/picks 派生：market / direction / falsify / target:<code>）。
   落盘后同时把回检表渲染进当日 ``<date>.md`` 的自动生成标记区（md 不存在时跳过并提示）。
5. ``index``：从 manifest/answer/verdict 扫描生成状态总表，写入 ``index.md``
   的自动生成标记区（人写的导航区不动）。

用法::

    python3 scripts/dual_blind_forecast.py manifest --date 2026-07-03 \
        --perspective 2026-07-02 --material 复盘材料.md --material 卖方.md
    python3 scripts/dual_blind_forecast.py validate \
        docs/learning/forecast-review-ledger/2026-07-03.answer.codex.json
    python3 scripts/dual_blind_forecast.py aggregate [--json]
    python3 scripts/dual_blind_forecast.py verdict 草稿.json   # 校验后落盘 <date>.verdict.json
    python3 scripts/dual_blind_forecast.py index              # 重建 index.md 状态总表

只读 DuckDB / 材料文件；不联网。找不到 DuckDB 时 manifest 相应字段留空并 WARN。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
LEDGER_DIR = REPO / "docs" / "learning" / "forecast-review-ledger"
DB_PATH = REPO / "db" / "market_feature_store.duckdb"

ALLOWED_AGENTS = {"codex", "claude", "devin"}
REQUIRED_ANSWER_FIELDS = (
    "schema_version",
    "date",
    "agent",
    "manifest_sha",
    "stage",
    "main_judgment",
    "direction_ranking",
    "picks",
    "thresholds",
)
REQUIRED_PICK_FIELDS = ("code", "name", "strategy", "reason")
REQUIRED_THRESHOLD_FIELDS = ("market", "direction", "targets", "falsify")
VERDICT_VALUES = {"hit", "miss", "partial", "unverifiable"}
VERDICT_LABELS = {"hit": "✅ hit", "miss": "❌ miss", "partial": "⚠️ partial", "unverifiable": "❓ unverifiable"}
REQUIRED_VERDICT_FIELDS = ("id", "agent", "verdict")
INDEX_BEGIN = "<!-- BEGIN AUTO dual-blind-status 本表由 dual_blind_forecast.py index 生成，勿手改 -->"
INDEX_END = "<!-- END AUTO dual-blind-status -->"
VERDICT_BEGIN = "<!-- BEGIN AUTO dual-blind-verdict 本表由 dual_blind_forecast.py verdict 渲染，勿手改 -->"
VERDICT_END = "<!-- END AUTO dual-blind-verdict -->"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _duckdb_max_trade_date(db_path: Path) -> str | None:
    if not db_path.exists():
        return None
    try:
        import duckdb  # noqa: PLC0415 允许可选依赖延迟导入

        con = duckdb.connect(str(db_path), read_only=True)
        try:
            row = con.execute("SELECT max(trade_date) FROM daily_market").fetchone()
        finally:
            con.close()
        return str(row[0]) if row and row[0] is not None else None
    except Exception:
        return None


def _kb_commit(kb_root: Path | None) -> str | None:
    if kb_root is None or not kb_root.exists():
        return None
    try:
        out = subprocess.run(
            ["git", "-C", str(kb_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except Exception:
        return None


def manifest_path_for(date: str, ledger_dir: Path = LEDGER_DIR) -> Path:
    return ledger_dir / f"{date}.manifest.json"


def cmd_manifest(args: argparse.Namespace) -> int:
    ledger_dir = Path(args.ledger_dir).expanduser()
    ledger_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []

    materials: list[dict[str, str]] = []
    for raw in args.material or []:
        path = Path(raw).expanduser()
        if not path.exists():
            print(f"ERROR: 材料文件不存在：{path}", file=sys.stderr)
            return 2
        materials.append({"path": str(path), "sha256": _sha256(path)})

    db_path = Path(args.db).expanduser() if args.db else DB_PATH
    duckdb_cutoff = _duckdb_max_trade_date(db_path)
    if duckdb_cutoff is None:
        warnings.append(f"DuckDB 不可读（{db_path}），duckdb_cutoff 留空——答卷前请人工确认数据截止日")

    kb_root = Path(args.kb_root).expanduser() if args.kb_root else None
    kb_commit = _kb_commit(kb_root)
    if kb_root and kb_commit is None:
        warnings.append(f"知识库 commit 不可读（{kb_root}）")

    body = {
        "schema_version": "1.0",
        "date": args.date,
        "perspective_date": args.perspective,
        "duckdb_path": str(db_path),
        "duckdb_cutoff": duckdb_cutoff,
        "kb_root": str(kb_root) if kb_root else None,
        "kb_commit": kb_commit,
        "materials": materials,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "warnings": warnings,
    }
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True)
    body["manifest_sha"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    out_path = manifest_path_for(args.date, ledger_dir)
    out_path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for warn in warnings:
        print(f"WARN: {warn}", file=sys.stderr)
    print(f"manifest_sha: {body['manifest_sha']}")
    print(f"written: {out_path}")
    return 0


def validate_answer(answer_path: Path, *, ledger_dir: Path = LEDGER_DIR) -> list[str]:
    """返回错误列表；空列表 = 通过。"""
    errors: list[str] = []
    try:
        answer = json.loads(answer_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"JSON 解析失败：{exc}"]

    for field in REQUIRED_ANSWER_FIELDS:
        if not answer.get(field):
            errors.append(f"缺必填字段 {field}")
    if errors:
        return errors

    if str(answer["agent"]).lower() not in ALLOWED_AGENTS:
        errors.append(f"agent 应为 {sorted(ALLOWED_AGENTS)} 之一，实际 {answer['agent']}")

    picks = answer.get("picks") or []
    if not isinstance(picks, list) or not picks:
        errors.append("picks 应为非空列表")
    else:
        for i, pick in enumerate(picks):
            for field in REQUIRED_PICK_FIELDS:
                if not pick.get(field):
                    errors.append(f"picks[{i}] 缺字段 {field}")

    thresholds = answer.get("thresholds") or {}
    for field in REQUIRED_THRESHOLD_FIELDS:
        if not thresholds.get(field):
            errors.append(f"thresholds 缺字段 {field}（验证条件必须可证伪）")

    mpath = manifest_path_for(str(answer["date"]), ledger_dir)
    if not mpath.exists():
        errors.append(f"找不到输入清单 {mpath.name}——答卷前先跑 manifest 子命令")
    else:
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
        if answer["manifest_sha"] != manifest.get("manifest_sha"):
            errors.append(
                f"manifest_sha 不一致：答卷 {answer['manifest_sha']} vs 清单 {manifest.get('manifest_sha')}"
                "——输入未冻结或引用了旧清单"
            )
    return errors


def hypothesis_ids(answer: dict[str, Any]) -> set[str]:
    """答卷的合法假设 id 集合：优先用显式 hypotheses，否则从 thresholds/picks 派生。"""
    explicit = {str(h.get("id")) for h in answer.get("hypotheses") or [] if h.get("id")}
    if explicit:
        return explicit
    ids = {"market", "direction", "falsify"}
    for pick in answer.get("picks") or []:
        if pick.get("code"):
            ids.add(f"target:{pick['code']}")
    return ids


def answer_paths_for(date: str, ledger_dir: Path = LEDGER_DIR) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for path in sorted(ledger_dir.glob(f"{date}.answer.*.json")):
        agent = path.name.split(".answer.", 1)[1].rsplit(".json", 1)[0].lower()
        out[agent] = path
    return out


def verdict_path_for(date: str, ledger_dir: Path = LEDGER_DIR) -> Path:
    return ledger_dir / f"{date}.verdict.json"


def validate_verdict(draft: dict[str, Any], *, ledger_dir: Path = LEDGER_DIR) -> list[str]:
    """返回错误列表；空列表 = 通过。"""
    errors: list[str] = []
    date = str(draft.get("date") or "")
    if not date:
        return ["缺必填字段 date"]
    verdicts = draft.get("verdicts")
    if not isinstance(verdicts, list) or not verdicts:
        return ["verdicts 应为非空列表"]

    answers = answer_paths_for(date, ledger_dir)
    ids_by_agent: dict[str, set[str]] = {}
    for agent, path in answers.items():
        try:
            ids_by_agent[agent] = hypothesis_ids(json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:
            errors.append(f"答卷 {path.name} 不可读：{exc}")

    for i, entry in enumerate(verdicts):
        for field in REQUIRED_VERDICT_FIELDS:
            if not entry.get(field):
                errors.append(f"verdicts[{i}] 缺字段 {field}")
                continue
        agent = str(entry.get("agent") or "").lower()
        if agent and agent not in ids_by_agent:
            errors.append(
                f"verdicts[{i}] agent={agent} 无对应答卷 {date}.answer.{agent}.json——先有答卷再有验证"
            )
        elif agent and entry.get("id") and str(entry["id"]) not in ids_by_agent[agent]:
            errors.append(
                f"verdicts[{i}] id={entry['id']} 不在 {agent} 答卷假设集 {sorted(ids_by_agent[agent])} 内"
            )
        if entry.get("verdict") and str(entry["verdict"]) not in VERDICT_VALUES:
            errors.append(f"verdicts[{i}] verdict 应为 {sorted(VERDICT_VALUES)} 之一，实际 {entry['verdict']}")
        if str(entry.get("verdict")) in {"hit", "miss", "partial"} and not entry.get("actual"):
            errors.append(f"verdicts[{i}] 已裁定 {entry.get('verdict')} 必须填 actual（实际值/实际情况）")
    return errors


def cmd_verdict(args: argparse.Namespace) -> int:
    ledger_dir = Path(args.ledger_dir).expanduser()
    draft_path = Path(args.draft).expanduser()
    try:
        draft = json.loads(draft_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: 草稿 JSON 解析失败：{exc}", file=sys.stderr)
        return 2
    errors = validate_verdict(draft, ledger_dir=ledger_dir)
    if errors:
        for err in errors:
            print(f"ERROR {draft_path.name}: {err}")
        return 1
    body = {
        "schema_version": draft.get("schema_version") or "1.0",
        "date": draft["date"],
        "verdicts": draft["verdicts"],
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    out_path = verdict_path_for(str(draft["date"]), ledger_dir)
    out_path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK    written: {out_path}")
    md_path = render_verdict_md(body, ledger_dir=ledger_dir)
    if md_path is None:
        print(f"WARN: 当日台账 {draft['date']}.md 不存在，回检表未渲染", file=sys.stderr)
    else:
        print(f"OK    rendered: {md_path}")
    return 0


def build_verdict_table(verdict: dict[str, Any]) -> str:
    lines = [
        "| 假设 id | agent | 判定 | 实际 | 证据 |",
        "|---|---|---|---|---|",
    ]
    for entry in verdict.get("verdicts") or []:
        label = VERDICT_LABELS.get(str(entry.get("verdict") or ""), str(entry.get("verdict") or "—"))
        lines.append(
            f"| {entry.get('id') or '—'} | {entry.get('agent') or '—'} | {label} "
            f"| {entry.get('actual') or '—'} | {entry.get('evidence_ref') or '—'} |"
        )
    stats = _verdict_stats(verdict)
    summary = []
    for agent, bucket in sorted(stats.items()):
        judged = bucket["hit"] + bucket["miss"] + bucket["partial"]
        summary.append(f"{agent} {bucket['hit']}/{judged}" if judged else f"{agent} 0/0")
    lines += ["", f"> 命中率（hit/已裁定）：{'，'.join(summary) if summary else '—'}"]
    return "\n".join(lines)


def render_verdict_md(verdict: dict[str, Any], *, ledger_dir: Path = LEDGER_DIR) -> Path | None:
    """把 verdict 回检表写进当日 <date>.md 的自动生成标记区；md 不存在返回 None。"""
    md_path = ledger_dir / f"{verdict['date']}.md"
    if not md_path.exists():
        return None
    block = (
        f"{VERDICT_BEGIN}\n\n### 盘后验证回检表（脚本渲染，来源 {verdict['date']}.verdict.json）\n\n"
        f"{build_verdict_table(verdict)}\n\n{VERDICT_END}"
    )
    text = md_path.read_text(encoding="utf-8")
    if VERDICT_BEGIN in text and VERDICT_END in text:
        head, rest = text.split(VERDICT_BEGIN, 1)
        _, tail = rest.split(VERDICT_END, 1)
        text = head + block + tail
    else:
        text = text.rstrip("\n") + "\n\n" + block + "\n"
    md_path.write_text(text, encoding="utf-8")
    return md_path


def _verdict_stats(verdict: dict[str, Any]) -> dict[str, dict[str, int]]:
    """按 agent 统计 hit/miss/partial/unverifiable 个数。"""
    stats: dict[str, dict[str, int]] = {}
    for entry in verdict.get("verdicts") or []:
        agent = str(entry.get("agent") or "unknown").lower()
        bucket = stats.setdefault(agent, {v: 0 for v in sorted(VERDICT_VALUES)})
        value = str(entry.get("verdict") or "")
        if value in bucket:
            bucket[value] += 1
    return stats


def build_index_table(ledger_dir: Path = LEDGER_DIR) -> str:
    dates: set[str] = set()
    for pattern in ("*.manifest.json", "*.answer.*.json", "*.verdict.json"):
        for path in ledger_dir.glob(pattern):
            dates.add(path.name.split(".", 1)[0])
    lines = [
        "| 研判日 | manifest | 答卷 | 答卷校验 | 验证 | 命中率（hit/已裁定） |",
        "|---|---|---|---|---|---|",
    ]
    for date in sorted(dates, reverse=True):
        has_manifest = "✅" if manifest_path_for(date, ledger_dir).exists() else "—"
        answers = answer_paths_for(date, ledger_dir)
        answer_cell = ", ".join(sorted(answers)) if answers else "—"
        checks = []
        for agent, path in sorted(answers.items()):
            checks.append(f"{agent}:{'✅' if not validate_answer(path, ledger_dir=ledger_dir) else '❌'}")
        check_cell = " ".join(checks) if checks else "—"
        vpath = verdict_path_for(date, ledger_dir)
        if vpath.exists():
            try:
                stats = _verdict_stats(json.loads(vpath.read_text(encoding="utf-8")))
                rates = []
                for agent, bucket in sorted(stats.items()):
                    judged = bucket["hit"] + bucket["miss"] + bucket["partial"]
                    rate = f"{bucket['hit']}/{judged}" if judged else "0/0"
                    rates.append(f"{agent}:{rate}")
                verdict_cell, rate_cell = "✅", " ".join(rates) if rates else "—"
            except Exception:
                verdict_cell, rate_cell = "❌不可读", "—"
        else:
            verdict_cell, rate_cell = "—", "—"
        lines.append(f"| {date} | {has_manifest} | {answer_cell} | {check_cell} | {verdict_cell} | {rate_cell} |")
    if len(lines) == 2:
        lines.append("| （暂无机器可读台账文件） | — | — | — | — | — |")
    return "\n".join(lines)


def cmd_index(args: argparse.Namespace) -> int:
    ledger_dir = Path(args.ledger_dir).expanduser()
    index_path = ledger_dir / "index.md"
    block = f"{INDEX_BEGIN}\n\n## 机检状态总表（脚本生成）\n\n{build_index_table(ledger_dir)}\n\n{INDEX_END}"
    if index_path.exists():
        text = index_path.read_text(encoding="utf-8")
        if INDEX_BEGIN in text and INDEX_END in text:
            head, rest = text.split(INDEX_BEGIN, 1)
            _, tail = rest.split(INDEX_END, 1)
            text = head + block + tail
        else:
            text = text.rstrip("\n") + "\n\n" + block + "\n"
    else:
        text = "# 复盘推演回检台账\n\n" + block + "\n"
    index_path.write_text(text, encoding="utf-8")
    print(f"written: {index_path}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    ledger_dir = Path(args.ledger_dir).expanduser()
    failed = False
    for raw in args.answers:
        path = Path(raw).expanduser()
        errors = validate_answer(path, ledger_dir=ledger_dir)
        if errors:
            failed = True
            for err in errors:
                print(f"ERROR {path.name}: {err}")
        else:
            print(f"OK    {path.name}")
    return 1 if failed else 0


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def aggregate(ledger_dir: Path = LEDGER_DIR) -> dict[str, Any]:
    """聚合所有答卷 JSON（含人工/脚本回填的 recheck 块），按 agent 出长期统计。"""
    per_agent: dict[str, dict[str, Any]] = {}
    for answer_path in sorted(ledger_dir.glob("*.answer.*.json")):
        try:
            answer = json.loads(answer_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        agent = str(answer.get("agent") or "unknown").lower()
        stat = per_agent.setdefault(
            agent,
            {
                "answers": 0,
                "rechecked": 0,
                "pick_returns_t1": [],
                "pick_returns_t3": [],
                "beat_benchmark_t3": 0,
                "market_threshold_hits": 0,
                "market_threshold_checked": 0,
                "dates": [],
            },
        )
        stat["answers"] += 1
        stat["dates"].append(str(answer.get("date")))
        recheck = answer.get("recheck") or {}
        if not recheck:
            continue
        stat["rechecked"] += 1
        for key, bucket in (("pick_returns_t1", "pick_returns_t1"), ("pick_returns_t3", "pick_returns_t3")):
            values = recheck.get(key) or []
            stat[bucket].extend(float(v) for v in values)
        if recheck.get("beat_benchmark_t3"):
            stat["beat_benchmark_t3"] += 1
        if "market_threshold_hit" in recheck:
            stat["market_threshold_checked"] += 1
            if recheck["market_threshold_hit"]:
                stat["market_threshold_hits"] += 1

    agents: dict[str, Any] = {}
    for agent, stat in sorted(per_agent.items()):
        checked = stat["market_threshold_checked"]
        agents[agent] = {
            "answers": stat["answers"],
            "rechecked": stat["rechecked"],
            "dates": stat["dates"],
            "avg_pick_return_t1": _mean(stat["pick_returns_t1"]),
            "avg_pick_return_t3": _mean(stat["pick_returns_t3"]),
            "beat_benchmark_t3": stat["beat_benchmark_t3"],
            "market_threshold_hit_rate": (
                round(stat["market_threshold_hits"] / checked, 4) if checked else None
            ),
        }
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "ledger_dir": str(ledger_dir),
        "agents": agents,
        "notes": [
            "单期噪声大：answers < 10 的 agent 统计只作参考，不下结论。",
            "recheck 块由回检人/脚本按统一指标回填：pick_returns_t1/t3（标的池各标的收益%）、",
            "beat_benchmark_t3（标的池 T+3 是否跑赢基准）、market_threshold_hit（§5 市场阈值是否命中）。",
        ],
    }


def _render_aggregate_md(report: dict[str, Any]) -> str:
    lines = [
        "# 双盲答卷跨期聚合",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "| agent | 答卷数 | 已回检 | T+1 标的均值% | T+3 标的均值% | T+3 跑赢次数 | 市场阈值命中率 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for agent, stat in report["agents"].items():
        lines.append(
            f"| {agent} | {stat['answers']} | {stat['rechecked']} | "
            f"{stat['avg_pick_return_t1'] if stat['avg_pick_return_t1'] is not None else '-'} | "
            f"{stat['avg_pick_return_t3'] if stat['avg_pick_return_t3'] is not None else '-'} | "
            f"{stat['beat_benchmark_t3']} | "
            f"{stat['market_threshold_hit_rate'] if stat['market_threshold_hit_rate'] is not None else '-'} |"
        )
    lines += ["", "> " + " ".join(report["notes"])]
    return "\n".join(lines) + "\n"


def cmd_aggregate(args: argparse.Namespace) -> int:
    report = aggregate(Path(args.ledger_dir).expanduser())
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(_render_aggregate_md(report), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ledger-dir", default=str(LEDGER_DIR), help="台账目录；默认 docs/learning/forecast-review-ledger")
    sub = parser.add_subparsers(dest="command", required=True)

    p_manifest = sub.add_parser("manifest", help="答卷前生成输入冻结清单 <date>.manifest.json")
    p_manifest.add_argument("--date", required=True, help="研判日 YYYY-MM-DD（前瞻的目标日）")
    p_manifest.add_argument("--perspective", required=True, help="观察视角日 YYYY-MM-DD（站在哪天盘后）")
    p_manifest.add_argument("--material", action="append", default=[], help="冻结的复盘材料文件，可重复")
    p_manifest.add_argument("--db", default=None, help="DuckDB 路径；默认 db/market_feature_store.duckdb")
    p_manifest.add_argument("--kb-root", default=None, help="知识库仓根目录（记录其 HEAD commit）")
    p_manifest.set_defaults(func=cmd_manifest)

    p_validate = sub.add_parser("validate", help="校验机器可读答卷 <date>.answer.<agent>.json")
    p_validate.add_argument("answers", nargs="+", help="答卷 JSON 路径，可多个")
    p_validate.set_defaults(func=cmd_validate)

    p_aggregate = sub.add_parser("aggregate", help="跨期聚合所有答卷+回检，按 agent 出长期统计")
    p_aggregate.add_argument("--json", action="store_true", help="输出 JSON 而非 Markdown 表")
    p_aggregate.set_defaults(func=cmd_aggregate)

    p_verdict = sub.add_parser("verdict", help="校验验证草稿并落盘 <date>.verdict.json（盘后验证唯一写入口）")
    p_verdict.add_argument("draft", help="验证草稿 JSON：{date, verdicts:[{id, agent, verdict, actual, evidence_ref}]}")
    p_verdict.set_defaults(func=cmd_verdict)

    p_index = sub.add_parser("index", help="扫描台账目录，重建 index.md 的机检状态总表区块")
    p_index.set_defaults(func=cmd_index)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
