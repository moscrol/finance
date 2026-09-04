#!/usr/bin/env python3
"""methodology_backtest —— 方法论回测 CLI（结构化历史标签层 + 规则编译 + 统计四态）。

    python scripts/methodology_backtest.py build-labels            # 主库只读 → 旁路库 history_labels
    python scripts/methodology_backtest.py outcomes                # 前瞻结果 3/5/7/10 日
    python scripts/methodology_backtest.py run methodology/rules/dual_red_streak3_continuation.v1.json
    python scripts/methodology_backtest.py scan --rules-dir methodology/rules     # 多条 + BH 校正
    python scripts/methodology_backtest.py report                  # 标签盘点 + 最近收据

路径：主库默认 ``MARKET_FEATURE_STORE_DB`` 或 ``db/market_feature_store.duckdb``（只读打开）；
旁路库默认与主库同目录 ``history_labels.duckdb``；收据落 ``methodology/receipts/``（gitignore，可重建）。

解释器一律 ``.venv-workbench/bin/python``（无 .pth，加载哪份代码由 cwd 决定）。

退出码：0 成功；2 输入 / 数据不可用（库不存在、规则不合法、旁路库未构建）；3 主库被写锁占用。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import date as date_cls
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import duckdb  # noqa: E402

from intelligence.services import checkpoints as ck  # noqa: E402
from intelligence.services.methodology_backtest.labels import build_labels  # noqa: E402
from intelligence.services.methodology_backtest.outcomes import DEFAULT_HORIZONS, build_outcomes  # noqa: E402
from intelligence.services.methodology_backtest.receipts import (  # noqa: E402
    build_receipt,
    build_scan_summary,
    write_receipt,
    write_scan_summary,
)
from intelligence.services.methodology_backtest.rules import Rule, RuleValidationError, load_rule  # noqa: E402
from intelligence.services.methodology_backtest.runner import (  # noqa: E402
    load_conditions,
    run_rule,
    scan_rules,
)
from intelligence.services.methodology_backtest.store import (  # noqa: E402
    default_labels_db_path,
    open_labels_db,
    read_meta,
)
from market_feature_store.db import DB_PATH as CANONICAL_DB_PATH  # noqa: E402
from market_feature_store.db import DatabaseLockedError  # noqa: E402

RULES_DIR = ROOT / "methodology" / "rules"
RECEIPTS_DIR = ROOT / "methodology" / "receipts"
MIN_N_ABLATION = (2, 10, 20)
EXIT_INPUT = 2
EXIT_LOCKED = 3


# --------------------------------------------------------------------------- #
# 环境自述（与 check_test_receipt.py 同判据：dirty 只看代码路径）
# --------------------------------------------------------------------------- #
def _git(*args: str) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def _code_dirt() -> list[str]:
    try:
        spec = json.loads((ROOT / "test-environment.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        spec = {}
    prefixes = tuple(spec.get("code_path_prefixes") or ())
    exceptions = tuple(spec.get("data_path_exceptions") or ())
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if out.returncode != 0:
        return []
    dirt: list[str] = []
    for line in out.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip().strip('"')
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if prefixes and not path.startswith(prefixes):
            continue
        if path.startswith(exceptions):
            continue
        dirt.append(path)
    return sorted(dirt)


def environment_block() -> dict:
    dirt = _code_dirt()
    return {
        "tree": str(ROOT),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD") or "(unknown)",
        "revision": _git("rev-parse", "--short", "HEAD") or "(unknown)",
        "dirty": bool(dirt),
        "dirty_code_paths": dirt[:20],
        "interpreter": sys.executable,
        "python_version": platform.python_version(),
        "duckdb_version": duckdb.__version__,
    }


def _today() -> str:
    return date_cls.today().isoformat()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- #
# min_n 消融（只读 calibrate，不改任何运行时值）
# --------------------------------------------------------------------------- #
def min_n_ablation(user_dir: Path) -> dict:
    """``min_n ∈ {2,10,20}`` 下「有标签类别数」——现有校准 render 只列 n >= min_n 的类别。"""
    cal, warnings = ck.load_calibration(user_dir / "checkpoints.jsonl", user_dir / "verdicts.jsonl")
    categories = [(s.category, s.n, s.hit_rate, s.reliability) for s in cal.by_category]
    by_min_n = {}
    for m in MIN_N_ABLATION:
        labeled = [c for c in categories if c[1] >= m]
        by_min_n[str(m)] = {
            "labeled_categories": len(labeled),
            "unlabeled_categories": len(categories) - len(labeled),
            "labeled_samples": sum(c[1] for c in labeled),
        }
    return {
        "what": "只读 calibrate 消融：DEFAULT_CALIBRATION_MIN_N 取 2/10/20 时还能给出可靠性标签的类别数（未改任何运行时值）",
        "user_dir": str(user_dir),
        "current_default_min_n": ck.DEFAULT_CALIBRATION_MIN_N,
        "scored_checkpoints": cal.scored,
        "pending": cal.pending,
        "unverifiable": cal.unverifiable,
        "categories_total": len(categories),
        "by_min_n": by_min_n,
        "categories": [
            {"category": c, "n": n, "hit_rate": round(r, 3), "reliability": rel} for c, n, r, rel in categories
        ],
        "warnings": warnings,
    }


# --------------------------------------------------------------------------- #
# 子命令
# --------------------------------------------------------------------------- #
def _print_build(report) -> None:
    d = report.to_dict()
    print(json.dumps(d, ensure_ascii=False, indent=2))


def cmd_build_labels(args) -> int:
    report = build_labels(args.db_path, args.labels_db)
    _print_build(report)
    return 0


def cmd_outcomes(args) -> int:
    horizons = tuple(int(x) for x in str(args.horizons).split(",") if x.strip())
    report = build_outcomes(args.db_path, args.labels_db, horizons=horizons)
    _print_build(report)
    return 0


def _load_rules(paths: list[str], rules_dir: str | None) -> list[tuple[Rule, Path]]:
    files: list[Path] = [Path(p) for p in paths]
    if rules_dir:
        files.extend(sorted(Path(rules_dir).expanduser().glob("*.v*.json")))
    if not files:
        raise SystemExit("没有规则：给规则文件路径或 --rules-dir")
    out: list[tuple[Rule, Path]] = []
    for f in files:
        out.append((load_rule(f), f.resolve()))
    return out


def _appendix(args) -> dict:
    appendix: dict = {}
    if getattr(args, "calibration_user_dir", None):
        appendix["min_n_ablation"] = min_n_ablation(Path(args.calibration_user_dir).expanduser())
    return appendix


def _print_readout(res, verdict_bh: str | None = None) -> None:
    rd = res.readout
    fmt = lambda x: "—" if x is None else f"{x * 100:.1f}%"  # noqa: E731
    line = (
        f"{res.rule.ref:<40} N={rd.n:<6} p={fmt(rd.p):>6} p0={fmt(rd.p0):>6} lift={fmt(rd.lift):>6} "
        f"Wilson=[{fmt(rd.lo)}, {fmt(rd.hi)}] halves={fmt(rd.p_first)}/{fmt(rd.p_second)} "
        f"→ {rd.verdict}"
    )
    if verdict_bh is not None and verdict_bh != rd.verdict:
        line += f" (BH: {verdict_bh})"
    print(line)


def cmd_run(args) -> int:
    rules = _load_rules([args.rule], None)
    rule, rule_path = rules[0]
    env = environment_block()
    appendix = _appendix(args)
    con = open_labels_db(args.labels_db, read_only=True)
    try:
        res = run_rule(con, rule, start=args.start, end=args.end)
    finally:
        con.close()
    receipt = build_receipt(
        res,
        rule_path=str(rule_path.relative_to(ROOT)) if rule_path.is_relative_to(ROOT) else str(rule_path),
        rule_sha256=_sha256(rule_path),
        environment=env,
        test_mode="single",
        appendix=appendix,
    )
    _print_readout(res)
    for note in res.readout.notes:
        print(f"  · {note}")
    if args.no_write:
        print(json.dumps(receipt["stats"], ensure_ascii=False, indent=2))
        return 0
    json_path, md_path = write_receipt(args.receipts_dir, receipt, date_str=_today())
    print(f"→ {json_path}\n→ {md_path}")
    return 0


def cmd_scan(args) -> int:
    loaded = _load_rules(args.rules, args.rules_dir)
    if len(loaded) < 2:
        print("scan 至少要 2 条规则（多重检验校正才有意义）；单条请用 run", file=sys.stderr)
        return EXIT_INPUT
    env = environment_block()
    appendix = _appendix(args)
    con = open_labels_db(args.labels_db, read_only=True)
    try:
        scan = scan_rules(con, [r for r, _ in loaded], start=args.start, end=args.end, q=args.q)
    finally:
        con.close()
    family = [r.ref for r, _ in loaded]
    receipt_paths: list[str | None] = []
    today = _today()
    for i, res in enumerate(scan.results):
        _print_readout(res, scan.verdicts_bh[i])
        bh = {
            "q": scan.q,
            "family": family,
            "p_value": scan.p_values[i],
            "adjusted_p": scan.adjusted_p[i],
            "rejected": scan.rejected[i],
            "verdict_bh": scan.verdicts_bh[i],
        }
        rule_path = loaded[i][1]
        receipt = build_receipt(
            res,
            rule_path=str(rule_path.relative_to(ROOT)) if rule_path.is_relative_to(ROOT) else str(rule_path),
            rule_sha256=_sha256(rule_path),
            environment=env,
            test_mode="scan",
            bh=bh,
            appendix=appendix,
        )
        if args.no_write:
            receipt_paths.append(None)
            continue
        json_path, _ = write_receipt(args.receipts_dir, receipt, date_str=today)
        receipt_paths.append(str(json_path))
    summary = build_scan_summary(scan, receipt_paths=receipt_paths, environment=env)
    if not args.no_write:
        json_path, md_path = write_scan_summary(args.receipts_dir, summary, date_str=today)
        print(f"→ {json_path}\n→ {md_path}")
    return 0


def cmd_report(args) -> int:
    labels_db = Path(args.labels_db).expanduser()
    if not labels_db.is_file():
        print(f"旁路库不存在：{labels_db}（先跑 build-labels）", file=sys.stderr)
        return EXIT_INPUT
    con = open_labels_db(labels_db, read_only=True)
    try:
        meta = read_meta(con)
        print(f"# 旁路库 {labels_db}")
        for kind, m in sorted(meta.items()):
            print(
                f"- {kind}: label_version={m['label_version']} source_max={m['source_max_trade_date']} "
                f"rows={m['row_count']} computed_at={m['computed_at']}"
                + (f" horizons={m['horizons']}" if m.get("horizons") else "")
            )
        rows = con.execute(
            """
            SELECT entity_type, label, COUNT(*), COUNT(value_num) + COUNT(value_text),
                   MIN(trade_date), MAX(trade_date)
            FROM history_labels GROUP BY 1, 2 ORDER BY 1, 2
            """
        ).fetchall()
        print("\n| 实体 | 标签 | 行数 | 非空 | 起 | 止 |\n|---|---|---:|---:|---|---|")
        for et, label, n, nn, lo, hi in rows:
            print(f"| {et} | {label} | {n} | {nn} | {lo} | {hi} |")
        gaps = con.execute("SELECT trade_date, zero_ratio, sector_rows FROM history_data_gaps ORDER BY 1").fetchall()
        print(f"\ndata_gap 日（{len(gaps)}）：" + (", ".join(f"{d}（零占比 {z:.1%}，{n} 行）" for d, z, n in gaps) or "本窗口无全零日"))
        if "outcomes" in meta:
            st = con.execute("SELECT status, COUNT(*) FROM history_outcomes GROUP BY 1 ORDER BY 1").fetchall()
            print("outcomes status：" + ", ".join(f"{s}={n}" for s, n in st))
        try:
            cond = load_conditions(con)
            print(f"成立条件一致性：labels/outcomes 同源（{cond['source_max_trade_date']}，{cond['label_version']}）")
        except RuntimeError as exc:
            print(f"成立条件一致性：✗ {exc}")
    finally:
        con.close()

    receipts_dir = Path(args.receipts_dir).expanduser()
    if receipts_dir.is_dir():
        print(f"\n# 最近收据（{receipts_dir}）")
        for folder in sorted(p for p in receipts_dir.iterdir() if p.is_dir()):
            files = sorted(folder.glob("*.json"))
            if not files:
                continue
            latest = files[-1]
            try:
                doc = json.loads(latest.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if folder.name == "scan":
                print(f"- scan/{latest.name}: {doc.get('family_size')} 条，q={doc.get('q')}")
                continue
            if args.rule and doc.get("rule", {}).get("rule_id") != args.rule:
                continue
            s = doc.get("stats", {})
            print(
                f"- {folder.name}/{latest.name}: {doc.get('verdict')} N={s.get('n')} p={s.get('p')} p0={s.get('p0')} "
                f"[{s.get('wilson_lo')}, {s.get('wilson_hi')}] source_max={doc.get('conditions', {}).get('source_max_trade_date')}"
            )
    return 0


# --------------------------------------------------------------------------- #
# argparse
# --------------------------------------------------------------------------- #
def _date_arg(value: str) -> str:
    try:
        return date_cls.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("日期必须是 YYYY-MM-DD") from exc


def _add_db_args(p: argparse.ArgumentParser, *, source: bool) -> None:
    if source:
        p.add_argument("--db-path", default=str(CANONICAL_DB_PATH), help="主库路径（只读打开），默认 MARKET_FEATURE_STORE_DB 或 db/ 主库")
    p.add_argument(
        "--labels-db",
        default=None,
        help="旁路库路径，默认与主库同目录的 history_labels.duckdb",
    )


def _add_run_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--from", dest="start", type=_date_arg, default=None, help="窗口起点 YYYY-MM-DD（默认日历起点）")
    p.add_argument("--to", dest="end", type=_date_arg, default=None, help="窗口终点 YYYY-MM-DD（默认日历终点）")
    p.add_argument("--receipts-dir", default=str(RECEIPTS_DIR), help="收据目录（默认 methodology/receipts）")
    p.add_argument("--no-write", action="store_true", help="只打印读数，不落收据")
    p.add_argument(
        "--calibration-user-dir",
        default=None,
        help="可选：含 checkpoints.jsonl / verdicts.jsonl 的用户目录，只读跑 min_n ∈ {2,10,20} 消融写进收据附录",
    )


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="方法论回测：标签层 / 前瞻结果 / 规则运行 / 扫描 / 报告")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build-labels", help="主库只读 → 旁路库 history_labels（可重建、幂等）")
    _add_db_args(b, source=True)
    b.set_defaults(func=cmd_build_labels)

    o = sub.add_parser("outcomes", help="前瞻结果表（需先 build-labels）")
    _add_db_args(o, source=True)
    o.add_argument("--horizons", default=",".join(str(h) for h in DEFAULT_HORIZONS), help="逗号分隔，默认 3,5,7,10")
    o.set_defaults(func=cmd_outcomes)

    r = sub.add_parser("run", help="跑一条规则，出收据（单次检验）")
    r.add_argument("rule", help="规则 JSON 路径 methodology/rules/<rule_id>.v<version>.json")
    _add_db_args(r, source=False)
    _add_run_args(r)
    r.set_defaults(func=cmd_run)

    s = sub.add_parser("scan", help="跑多条规则 + Benjamini–Hochberg 校正，出逐条收据与汇总")
    s.add_argument("rules", nargs="*", help="规则 JSON 路径（可多个）")
    s.add_argument("--rules-dir", default=None, help="目录下全部 *.v*.json")
    s.add_argument("--q", type=float, default=0.05, help="BH FDR 水平，默认 0.05")
    _add_db_args(s, source=False)
    _add_run_args(s)
    s.set_defaults(func=cmd_scan)

    rp = sub.add_parser("report", help="标签盘点 + 最近收据")
    _add_db_args(rp, source=False)
    rp.add_argument("--receipts-dir", default=str(RECEIPTS_DIR))
    rp.add_argument("--rule", default=None, help="只看某个 rule_id 的收据")
    rp.set_defaults(func=cmd_report)
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    if getattr(args, "labels_db", None) is None:
        args.labels_db = str(default_labels_db_path(getattr(args, "db_path", None)))
    try:
        return int(args.func(args) or 0)
    except DatabaseLockedError as exc:
        print(f"主库被写锁占用（夜跑 / 回填在写），稍后重试：{exc}", file=sys.stderr)
        return EXIT_LOCKED
    except RuleValidationError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_INPUT
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return EXIT_INPUT


if __name__ == "__main__":
    raise SystemExit(main())
