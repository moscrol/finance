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
import re
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


def wait_for_gateway(log_path: Path, *, max_wait: float = 6 * 3600) -> None:
    """模型冷却/上游闪断中就等；**连续 2 次 200（间隔 20s）才算稳**再放行本题。

    2026-09-09 19:11 实测：单次 200 放行后 37 秒内网关又 503，整题收据作废。
    闪断网关下「一次探通」不构成可跑条件。
    """

    started = time.monotonic()
    consecutive_ok = 0
    while True:
        code, reset, model = gateway_status()
        if code == 200:
            consecutive_ok += 1
            if consecutive_ok >= 2:
                return
            time.sleep(20)
            continue
        consecutive_ok = 0
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


_GATEWAY_ERROR_RE = re.compile(r"HTTP (?:429|500|502|503|504)")


def taint_reason(case_dir: Path, users_root: Path) -> str:
    """跑完一题立即验伤，返回污染原因（空串 = 干净）。

    - gateway：episode 里任一 model_error 命中 HTTP 429/5xx——收据度量的是网关不是臂。
    - judge：判官 unavailable——公开答案被扣成 160 字模板，答案类判卷点全部失真
      （2026-09-09 16 点档 C1–C3 全中：启动器钉死的判官二进制路径已被自动更新清掉）。
    """

    probe_path = case_dir / "probe.json"
    if not probe_path.is_file():
        return "no_probe"
    try:
        probe = json.loads(probe_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "bad_probe_json"
    receipt = probe.get("gate_receipt") or {}
    run_id = str(probe.get("run_id") or "")
    if run_id:
        for episode_path in users_root.glob(f"*/runs/{run_id}/continuous-episode.json"):
            try:
                episode = json.loads(episode_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            events = (episode.get("outcome") or {}).get("events") or episode.get("events") or []
            for event in events:
                if event.get("kind") != "model_error":
                    continue
                if _GATEWAY_ERROR_RE.search(str((event.get("payload") or {}).get("reason") or "")):
                    return "gateway"
    if str(receipt.get("judge_status") or "") == "unavailable":
        return "judge"
    return ""


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
    parser.add_argument(
        "--until-clean",
        type=int,
        default=3,
        help="对仍缺干净收据的题最多再过几轮（含首轮）；同题同因污染两次即停批",
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
    users_root = arm_dir.parent.parent / f"users-{args.arm}"
    base_url = f"http://127.0.0.1:{args.port}"
    user = f"cap06-{args.arm}"
    batch_log = arm_dir / "batch.jsonl"
    print(f"cap06 batch arm={args.arm} port={args.port} cases={len(selected)} out={arm_dir}", flush=True)

    # 同题同因污染两次即停批：闪断网关下污染是常态可重试，但同因复现说明是系统性
    # 故障（判官坏了 / 网关死了），继续跑只会量产废收据（tag-and-continue 不是门）。
    taint_counts: dict[tuple[str, str], int] = {}
    passes = max(1, int(args.until_clean))
    for pass_index in range(1, passes + 1):
        pending = [
            case_id
            for case_id in selected
            if args.no_skip_done or not (arm_dir / case_id / "probe.json").exists()
        ]
        if not pending:
            break
        print(f"— 第 {pass_index}/{passes} 轮，待跑 {len(pending)} 题 —", flush=True)
        for index, case_id in enumerate(pending, start=1):
            case = cases[case_id]
            out_path = arm_dir / case_id / "probe.json"
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
            taint = taint_reason(out_path.parent, users_root)
            record = {
                "case": case_id,
                "group": case.get("group"),
                "pass": pass_index,
                "started_at": started_at,
                "elapsed_wall": elapsed,
                "exit_code": proc.returncode,
                "run_id": summary.get("run_id"),
                "terminal_outcome": summary.get("terminal_outcome"),
                "taint": taint,
                "stderr_tail": proc.stderr[-400:],
            }
            with batch_log.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(
                f"[{index}/{len(pending)}] {case_id} exit={proc.returncode} "
                f"run={summary.get('run_id')} outcome={summary.get('terminal_outcome')} "
                f"taint={taint or '-'} {elapsed}s",
                flush=True,
            )
            if taint:
                stamp = datetime.now().strftime("%H%M%S")
                out_path.parent.rename(
                    out_path.parent.with_name(f"{case_id}.tainted-{taint}-{stamp}")
                )
                key = (case_id, taint)
                taint_counts[key] = taint_counts.get(key, 0) + 1
                if taint_counts[key] >= 2:
                    print(
                        f"✗ {case_id} 同因（{taint}）污染两次，判为系统性故障，停批",
                        flush=True,
                    )
                    return 3
    remaining = [
        case_id
        for case_id in selected
        if not (arm_dir / case_id / "probe.json").exists()
    ]
    if remaining:
        print(f"✗ {passes} 轮后仍缺干净收据：{remaining}", flush=True)
        return 2
    print(f"✓ {len(selected)} 题全部有干净收据", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
