#!/usr/bin/env python3
"""06 号单批跑驱动：把冻结 12 题逐条发给一个 Workbench 旁车，收 smoke 收据。

提问走对话门（``POST /api/conversations`` → ``/messages``），复用仓内探针
``scripts/smoke_workbench_self_use.py``（形状同 2026-09-07 max 读数批跑的 run_web_arms.py），
不另写提问器。串行、每题一份 ``probe.json``；已有结果默认跳过，可续跑。

用法：
    .venv-workbench/bin/python scripts/cap06_run_batch.py --arm base --port 8811 \
        [--cases C1-...,S1-...] [--timeout 900] [--out-root ~/.finance-runtime/cap06-20260909/arms]
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "intelligence/eval/fixtures/adaptive-research-06.questions.json"
PROBE = REPO / "scripts/smoke_workbench_self_use.py"
# 探针用本驱动器自己的解释器（仓规：主树 .venv-workbench）；不写死绝对路径。
PYTHON = Path(sys.executable)
RESERVED_PORTS = {8792, 8793, 8795, 8799, 8801}


def load_cases() -> dict[str, dict]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {str(case["id"]): case for case in payload["cases"]}


# 网关模型可用性预检。2026-09-09 14:35 第一次基线批跑：C1 跑到一半 3× HTTP 429
# （cockpit 网关 model_cooldown，reset 1h27m），后面 11 题 2 秒内全 failed——那 12 份
# 收据度量的是网关配额，不是被测代码。key 只在 zsh 子进程里存在，Python 只拿回
# http 状态码与 reset 秒数，不进日志。
_GATEWAY_PROBE = r"""
set -a; . <(grep '^export ' "$HOME/.local/bin/start-finance-workbench"); set +a
model="${FORESIGHT_BUILTIN_LLM_MODEL:-gpt-5.6-sol}"
body="$(mktemp)"
code=$(curl -s -o "$body" -w '%{http_code}' -m 90 \
  -H "Authorization: Bearer $FORESIGHT_BUILTIN_LLM_API_KEY" -H 'Content-Type: application/json' \
  -d "{\"model\":\"$model\",\"messages\":[{\"role\":\"user\",\"content\":\"回复 ok\"}],\"max_tokens\":5}" \
  "${FORESIGHT_BUILTIN_LLM_BASE_URL:-http://localhost:57244/v1}/chat/completions")
reset=$(grep -oE 'reset_seconds[^0-9]*[0-9]+' "$body" | grep -oE '[0-9]+' | head -1)
rm -f "$body"
print -- "$code ${reset:-0} $model"
"""


def gateway_status() -> tuple[int, int, str]:
    """返回 (http_code, reset_seconds, model)；探针失败返回 (0, 0, '')。"""

    try:
        proc = subprocess.run(
            ["zsh", "-c", _GATEWAY_PROBE], capture_output=True, text=True, timeout=120
        )
    except (OSError, subprocess.TimeoutExpired):
        return (0, 0, "")
    parts = proc.stdout.strip().split()
    if len(parts) < 2:
        return (0, 0, "")
    try:
        return (int(parts[0]), int(parts[1]), parts[2] if len(parts) > 2 else "")
    except ValueError:
        return (0, 0, "")


def wait_for_gateway(log_path: Path, *, max_wait: float = 3 * 3600) -> None:
    """模型冷却中就等：每次等 min(reset+30, 600) 秒再探，直到 200 或超过 max_wait。"""

    started = time.monotonic()
    while True:
        code, reset, model = gateway_status()
        if code == 200:
            return
        waited = time.monotonic() - started
        if waited > max_wait:
            raise SystemExit(f"网关 {model} 持续不可用（最后 http={code}），放弃")
        sleep_for = min(max(reset, 60) + 30, 600) if code == 429 else 120
        record = {
            "gateway_wait": True,
            "http": code,
            "reset_seconds": reset,
            "model": model,
            "sleep": sleep_for,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"网关 {model} http={code} reset={reset}s → 等 {sleep_for}s", flush=True)
        time.sleep(sleep_for)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--arm", required=True, help="臂标签，如 base / cand")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--cases", default="", help="逗号分隔 case id，缺省全部")
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument(
        "--out-root",
        default=str(Path.home() / ".finance-runtime/cap06-20260909/arms"),
    )
    parser.add_argument("--no-skip-done", action="store_true")
    parser.add_argument(
        "--no-gateway-wait",
        action="store_true",
        help="不做模型网关可用性预检（默认每题开跑前探一次，429 冷却就等）",
    )
    args = parser.parse_args()

    if args.port in RESERVED_PORTS:
        raise SystemExit(f"端口 {args.port} 是保留端口（生产 / 他人臂），拒绝")
    cases = load_cases()
    selected = (
        [item.strip() for item in args.cases.split(",") if item.strip()]
        if args.cases
        else list(cases)
    )
    unknown = [item for item in selected if item not in cases]
    if unknown:
        raise SystemExit(f"未知 case: {unknown}")

    arm_dir = Path(args.out_root).expanduser() / args.arm
    arm_dir.mkdir(parents=True, exist_ok=True)
    base_url = f"http://127.0.0.1:{args.port}"
    user = f"cap06-{args.arm}"
    batch_log = arm_dir / "batch.jsonl"
    print(f"cap06 batch arm={args.arm} port={args.port} cases={len(selected)} out={arm_dir}", flush=True)

    for index, case_id in enumerate(selected, start=1):
        case = cases[case_id]
        out_path = arm_dir / case_id / "probe.json"
        if out_path.exists() and not args.no_skip_done:
            print(f"[{index}/{len(selected)}] {case_id} 已有结果，跳过", flush=True)
            continue
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if not args.no_gateway_wait:
            wait_for_gateway(batch_log)
        started = time.monotonic()
        started_at = datetime.now(timezone.utc).isoformat()
        proc = subprocess.run(
            [
                str(PYTHON),
                str(PROBE),
                "--base-url",
                base_url,
                "--user",
                user,
                "--question",
                str(case["question"]),
                "--timeout",
                str(args.timeout),
                "--output",
                str(out_path),
            ],
            capture_output=True,
            text=True,
        )
        elapsed = round(time.monotonic() - started, 1)
        summary: dict[str, object] = {}
        if out_path.exists():
            try:
                summary = json.loads(out_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                summary = {}
        record = {
            "case": case_id,
            "group": case.get("group"),
            "started_at": started_at,
            "elapsed_wall": elapsed,
            "exit_code": proc.returncode,
            "run_id": summary.get("run_id"),
            "terminal_outcome": summary.get("terminal_outcome"),
            "stderr_tail": proc.stderr[-400:],
        }
        with batch_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(
            f"[{index}/{len(selected)}] {case_id} exit={proc.returncode} "
            f"run={summary.get('run_id')} outcome={summary.get('terminal_outcome')} {elapsed}s",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
