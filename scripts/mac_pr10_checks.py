#!/usr/bin/env python3
"""PR #10 合并前与收尾的 Mac 侧核验：一条命令跑完只读检查，出一份可以贴回来的摘要。

为什么有它：云端沙箱连不到生产 Mac（出网只放行 GitHub / PyPI），而剩下的核验都要用
生产库、真实答题存档和真台账。这里把它们串成一条命令，只读、各步互不拖累，
摘要只写计数和判定、不写台账正文和回答原句（细节留在本机日志里）。

步骤（每步独立超时，失败只记失败、不中断后面）：

1. 换库锁平台自检（``check_swap_lock_platform.py``）；
2. 百分数字段量纲：先 APFS ``cp -c`` 克隆生产库（秒级、零额外占盘；克隆不成就直接只读打开，
   不做整份拷贝），再跑 ``check_percent_units.py``，跑完删克隆；
3. 标签 A/B 回放（``numeric_gate_label_ab.py``，扫 ``FORESIGHT_USERS_DIR`` 全部用户）；
4. 生效模型准入（含子分支）抽查最近的运行：默认每个运行按它自己 ``configure`` 里配置的模型判
   （回查「以为 A 实际 B」）；给 ``--expect-model`` 则统一按那个模型判；
5. 记忆召回分档（关键词现状 vs 字符二元组对照；给了 ``--embed-model`` 再加语义档）；
6. 工具调用按数据集统计（``audit_episode_tool_outcomes.py --by-dataset``）；
7. 台账体检（``prediction_ledger_status.py``）；
8. 可选 ``--full-tests``：本机等价 CI（ruff + 全量 pytest，二三十分钟）。

用法（在本分支的 worktree 里，用主检出的解释器）::

    export FORESIGHT_USERS_DIR=...        # 与生产同一个
    <主检出>/.venv-workbench/bin/python scripts/mac_pr10_checks.py \\
        --db <主检出>/db/market_feature_store.duckdb --out /tmp/pr10-checks [--full-tests]

产物：``<out>/summary.md``（可以贴回来）与 ``<out>/logs/*.txt``（完整输出，含回答原句，留在本机）。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
PY = sys.executable


def _run(name: str, argv: list[str], out: Path, timeout: int, env: dict[str, str] | None = None) -> dict[str, Any]:
    log = out / "logs" / f"{name}.txt"
    started = time.monotonic()
    try:
        proc = subprocess.run(
            argv, cwd=REPO, capture_output=True, text=True, timeout=timeout,
            env={**os.environ, **(env or {})},
        )
        code, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        code, stdout, stderr = None, exc.stdout or "", f"超时（>{timeout}s）"
        stdout = stdout.decode() if isinstance(stdout, bytes) else stdout
    seconds = round(time.monotonic() - started, 1)
    log.write_text(f"$ {' '.join(argv)}\n# exit={code} seconds={seconds}\n\n{stdout}\n--- stderr ---\n{stderr}", encoding="utf-8")
    return {"name": name, "exit": code, "seconds": seconds, "stdout": stdout, "stderr": stderr, "log": str(log)}


def _tail(text: str, n: int) -> list[str]:
    return [line for line in text.strip().splitlines() if line.strip()][-n:]


def step_swap_lock(out: Path) -> tuple[dict[str, Any], list[str]]:
    r = _run("01-swap-lock", [PY, "scripts/check_swap_lock_platform.py"], out, 120,
             {"FWP_ALLOW_ANY_PYTHON": "1"})
    return r, _tail(r["stdout"], 3)


def step_units(out: Path, db: Path | None) -> tuple[dict[str, Any], list[str]]:
    if db is None or not db.is_file():
        return {"name": "02-units", "exit": None, "seconds": 0, "log": ""}, [f"跳过：库不存在（--db {db}）"]
    tmp = Path(tempfile.mkdtemp(prefix="pr10-units-"))
    clone = tmp / db.name
    target, note = db, "直接只读打开生产库"
    try:
        if subprocess.run(["cp", "-c", str(db), str(clone)], capture_output=True).returncode == 0:
            target, note = clone, "对 APFS 克隆副本只读跑（cp -c）"
        r = _run("02-units", [PY, "scripts/check_percent_units.py", "--db", str(target)], out, 300)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    table = [line for line in r["stdout"].splitlines() if line.startswith("|") or line.startswith("- ")]
    return r, [note, *table]


def step_replay(out: Path) -> tuple[dict[str, Any], list[str]]:
    detail = out / "logs" / "03-replay-rows.json"
    r = _run("03-replay", [PY, "scripts/numeric_gate_label_ab.py", "--json", str(detail), "--show", "0"], out, 3600)
    keep = [
        line for line in r["stdout"].splitlines()
        if line.startswith(("存证 episode", "改标签", "涉及证据卡", "原样臂", "✅", "❌"))
    ]
    return r, keep + ["逐条（消失 / 新增的原句）只在本机：logs/03-replay.txt"]


def step_admission(out: Path, users_root: Path, since: str, expect: str | None) -> tuple[dict[str, Any], list[str]]:
    runs = sorted(
        p for p in users_root.glob("*/runs/run_*") if p.is_dir() and p.name[4:12] >= since
        and (p / "continuous-episode.json").is_file()
    )
    if not runs:
        return {"name": "04-admission", "exit": None, "seconds": 0, "log": ""}, [f"跳过：{since} 以来没有 continuous 运行"]
    want = ["--expect-model", expect] if expect else ["--expect-configured"]
    r = _run("04-admission", [PY, "scripts/check_model_admission.py", *want, "--json", *map(str, runs)], out, 900)
    try:
        payload = json.loads(r["stdout"])
    except ValueError:
        return r, ["输出不是 JSON，见日志"]
    counts: dict[str, int] = {}
    branch_unproven = 0
    served: dict[str, int] = {}
    pairs: dict[str, int] = {}
    for item in payload["results"]:
        counts[item["verdict"]] = counts.get(item["verdict"], 0) + 1
        branch_unproven += int(item.get("branch_unproven") or 0)
        for name, n in item["served"].items():
            served[name] = served.get(name, 0) + n
        configured = "/".join(item.get("expected") or []) or "（未配置）"
        actual = "/".join(sorted(item["served"])) or "（无）"
        key = f"配置 {configured} → 实际 {actual}"
        pairs[key] = pairs.get(key, 0) + 1
    basis = f"统一期望 {expect}" if expect else "各按自己 configure 里配置的模型"
    return r, [
        f"{since} 以来 {len(runs)} 个运行，{basis}：" + "、".join(f"{k} {v}" for k, v in sorted(counts.items())),
        *[f"- {key}：{n} 个运行" for key, n in sorted(pairs.items(), key=lambda kv: -kv[1])[:8]],
        "实际服务过的模型（按 turn 计）：" + ("、".join(f"{k}×{v}" for k, v in sorted(served.items())) or "无"),
        f"调用过模型却没带回生效模型的子分支：{branch_unproven}（episode store：{payload.get('episode_store') or '未用'}）",
    ]


def step_recall(out: Path, users_root: Path, user: str, models: list[str]) -> tuple[dict[str, Any], list[str]]:
    argv = [PY, "-m", "intelligence.eval.retrieval_recall", "--cases", "intelligence/eval/cases/retrieval_recall_v1.jsonl",
            "--users-root", str(users_root / user), "--tiers", "--embed-model", "builtin:char-bigram"]
    for model in models:
        argv += ["--embed-model", model]
    r = _run("05-recall", argv, out, 900)
    rows: list[str] = []
    for line in r["stdout"].splitlines():
        if line.startswith("| case |"):
            rows.append("")  # 两张表之间空一行，否则 markdown 会把它们粘成一张
        if line.startswith("|"):
            rows.append(line)
    return r, rows


def step_tools(out: Path, users_root: Path) -> tuple[dict[str, Any], list[str]]:
    dirs = sorted(str(p) for p in users_root.glob("*/runs") if p.is_dir())
    if not dirs:
        return {"name": "06-tools", "exit": None, "seconds": 0, "log": ""}, ["跳过：没有 runs 目录"]
    r = _run("06-tools", [PY, "scripts/audit_episode_tool_outcomes.py", "--by-dataset", *dirs], out, 1800)
    return r, _tail(r["stdout"], 40)


def step_ledger(out: Path) -> tuple[dict[str, Any], list[str]]:
    today = dt.date.today().isoformat()
    r = _run("07-ledger", [PY, "scripts/prediction_ledger_status.py", "--as-of", today], out, 300)
    sheet = _run("07b-ledger-worksheet", [PY, "scripts/prediction_ledger_status.py", "--as-of", today, "--worksheet"], out, 300)
    head = [line for line in sheet["stdout"].splitlines()[:5] if line.strip()]
    return r, [*_tail(r["stdout"], 25), "", *head, "分诊表全文：logs/07b-ledger-worksheet.txt"]


def step_full_tests(out: Path) -> tuple[dict[str, Any], list[str]]:
    lint = _run("08a-ruff", [PY, "-m", "ruff", "check", "."], out, 600)
    tests = _run("08b-pytest", [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider"], out, 3600)
    return tests, [f"ruff exit {lint['exit']}：{' '.join(_tail(lint['stdout'], 1))}", *_tail(tests["stdout"], 3)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=None, help="生产 DuckDB；默认 MARKET_FEATURE_STORE_DB")
    parser.add_argument("--out", type=Path, required=True, help="输出目录（摘要 + 本机日志）")
    parser.add_argument("--recall-user", default="linxiaoqi5111", help="记忆召回标注集对应的用户目录名")
    parser.add_argument("--embed-model", action="append", default=[], help="语义档本地模型（需已装 sentence-transformers）")
    parser.add_argument("--admission-since", default="20260916", help="准入抽查的 run 日期下限 YYYYMMDD")
    parser.add_argument("--expect-model", default=None, help="准入抽查统一按这个模型判；默认各按自己 configure 里配置的模型")
    parser.add_argument("--full-tests", action="store_true", help="另跑本机等价 CI（二三十分钟）")
    args = parser.parse_args(argv)

    raw_users = os.environ.get("FORESIGHT_USERS_DIR", "").strip()
    if not raw_users:
        print("先 export FORESIGHT_USERS_DIR（与生产同一个），否则会读到仓库里的空目录。", file=sys.stderr)
        return 2
    users_root = Path(raw_users).expanduser()
    db = args.db or (Path(os.environ["MARKET_FEATURE_STORE_DB"]).expanduser() if os.environ.get("MARKET_FEATURE_STORE_DB") else None)
    (args.out / "logs").mkdir(parents=True, exist_ok=True)
    head = subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()

    steps = [
        ("换库锁平台自检", lambda: step_swap_lock(args.out)),
        ("百分数字段量纲（同日原值反算）", lambda: step_units(args.out, db)),
        ("标签 A/B 回放（合并前：新增必须为 0）", lambda: step_replay(args.out)),
        ("生效模型准入抽查（含子分支）", lambda: step_admission(args.out, users_root, args.admission_since, args.expect_model)),
        ("记忆召回分档", lambda: step_recall(args.out, users_root, args.recall_user, args.embed_model)),
        ("工具调用按数据集", lambda: step_tools(args.out, users_root)),
        ("台账体检", lambda: step_ledger(args.out)),
    ]
    if args.full_tests:
        steps.append(("本机等价 CI", lambda: step_full_tests(args.out)))

    lines = [f"# PR #10 Mac 核验摘要（{dt.datetime.now():%Y-%m-%d %H:%M}，分支提交 {head}）", ""]
    for title, fn in steps:
        try:
            result, summary = fn()
        except Exception as exc:  # noqa: BLE001 — 一步坏了不拖累后面
            result, summary = {"exit": "error", "seconds": 0}, [f"{type(exc).__name__}: {exc}"]
        lines += [f"## {title}（exit {result.get('exit')}，{result.get('seconds')}s）", "", *summary, ""]
        print(f"· {title}：exit {result.get('exit')}", flush=True)
    summary_path = args.out / "summary.md"
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n摘要 → {summary_path}（可以贴回来）；完整日志 → {args.out / 'logs'}（含原句，留在本机）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
