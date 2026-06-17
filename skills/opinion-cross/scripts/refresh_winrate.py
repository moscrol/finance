#!/usr/bin/env python3
"""refresh_winrate: 一键刷新「卖方机构胜率榜」。

一条命令跑完两步：
  1) build_outcomes.py  重算 outcomes.jsonl（机构看多观点 → T+N 后验收益，
     日期自动取到今天，价格缓存只抓新交易日）；
  2) winrate_rank.py    按 source_id 聚合出最新机构胜率榜（默认 T+5 主口径 +
     T+10 视图）。

报告 markdown 默认写到仓外目录（分析产物，不提交）。供手动刷新或定时会话调用。

  python3 refresh_winrate.py [--vault <wiki>] [--benchmark sh000300]
                             [--min-calls 5] [--windows 5,10]
                             [--report-dir <dir>]
"""
from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(argv: list[str]) -> int:
    print(f"\n[RUN] {' '.join(argv)}", flush=True)
    return subprocess.run(argv).returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=None, help="KB wiki 路径；缺省走脚本内置解析")
    ap.add_argument("--benchmark", default="sh000300")
    ap.add_argument("--min-calls", type=int, default=5)
    ap.add_argument("--windows", default="5,10", help="逗号分隔，子集 of 3,5,7,10")
    ap.add_argument("--report-dir", default=None,
                    help="报告输出目录（仓外）；缺省 ~/kb_work/winrate")
    args = ap.parse_args()

    windows = []
    for w in args.windows.split(","):
        w = w.strip()
        if not w:
            continue
        if w not in {"3", "5", "7", "10"}:
            print(f"[ERR] window must be in 3/5/7/10, got {w}")
            return 2
        windows.append(int(w))
    if not windows:
        print("[ERR] no valid windows")
        return 2

    report_dir = (Path(args.report_dir).expanduser() if args.report_dir
                  else Path.home() / "kb_work" / "winrate")
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.date.today().isoformat()

    common = []
    if args.vault:
        common += ["--vault", args.vault]

    # step 1: rebuild outcomes.jsonl
    rc = run([sys.executable, str(HERE / "build_outcomes.py"), "--benchmark", args.benchmark, *common])
    if rc != 0:
        print(f"[ERR] build_outcomes failed rc={rc}")
        return rc

    # step 2: rank per window
    reports = []
    for w in windows:
        report = report_dir / f"winrate_T{w}_{stamp}.md"
        rc = run([sys.executable, str(HERE / "winrate_rank.py"),
                  "--window", str(w), "--min-calls", str(args.min_calls),
                  "--report", str(report), *common])
        if rc != 0:
            print(f"[ERR] winrate_rank T+{w} failed rc={rc}")
            return rc
        reports.append(report)

    print("\n[OK] refresh done. reports:")
    for r in reports:
        print(f"  [{r}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
