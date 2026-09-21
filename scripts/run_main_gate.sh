#!/usr/bin/env bash
# 干净树整仓门禁一把跑：树必须干净 → ruff check → 全量 pytest → 拿收据 → 对基线比红集。
#
# 它替代的手工流程（2026-09-03 一天重复了五次）：
#   1. 看 porcelain 是否为空（AGENTS.md：混着未提交改动的树跑出来的 exit code 不对你的 revision 成立）
#   2. 用 test-environment.json 里那个解释器跑 ruff + pytest（宿主 python3 会多出几十条环境红）
#   3. 从本次 pytest 标准输出取精确收据路径（全局 latest.json 会被并发运行覆盖）
#   4. 把 failed_ids 与上一张 PR 的收据逐条对，确认「同一组红、passed 只增不减」
# 第 4 步最容易偷懒成「都是 5 红」——今天 gitea/main 上就多出了一条时间敏感红，
# 只看计数看不出是哪条换了。这里按 id 集合比。
#
# 用法：
#   bash scripts/run_main_gate.sh                       # 在当前树跑，只打印本次读数
#   bash scripts/run_main_gate.sh --baseline <收据.json> # 再对基线收据比红集，红集变了退出码 3
#   bash scripts/run_main_gate.sh --allow-dirty          # 本地迭代用；收据会自带 dirty=true，不可跨 agent 采信
#   bash scripts/run_main_gate.sh --pytest-args "-x -q intelligence/tests"   # 换范围（收据 target 会跟着变）
#   bash scripts/run_main_gate.sh --receipt <收据.json> --baseline <基线.json>  # 不重跑，只比两张收据
#
# 退出码：0 全过（或与基线同一组红）；1 ruff 红；2 树脏且未 --allow-dirty；3 红集与基线不同 / 新增红；4 环境问题。
set -uo pipefail

# 门禁的对象是「你站着的那棵树」，不是脚本所在的树——脚本常从别的 worktree 借用
#（2026-09-03 首跑就把 gate-tools 树自己判成了脏树）。
REPO="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[ -z "$REPO" ] && REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASELINE=""
RECEIPT_ONLY=""
ALLOW_DIRTY=0
PYTEST_ARGS="-q -p no:cacheprovider"
while [ $# -gt 0 ]; do
  case "$1" in
    --baseline) BASELINE="$2"; shift 2 ;;
    --receipt) RECEIPT_ONLY="$2"; shift 2 ;;
    --allow-dirty) ALLOW_DIRTY=1; shift ;;
    --pytest-args) PYTEST_ARGS="$2"; shift 2 ;;
    -h|--help) sed -n '2,21p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 4 ;;
  esac
done

# 解释器：与 session_facts.sh / conftest.py 同一份真本源 test-environment.json，不另写路径。
PY=""
if [ -f "$REPO/test-environment.json" ]; then
  PY="$(sed -n 's/.*"interpreter"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$REPO/test-environment.json" | head -1)"
fi
[ -z "$PY" ] && PY="$REPO/.venv-workbench/bin/python"
if [ ! -x "$PY" ]; then
  echo "解释器不可执行: $PY（test-environment.json 指向的 venv 不在？）" >&2
  exit 4
fi

cd "$REPO" || exit 4
if [ -n "$RECEIPT_ONLY" ]; then
  LATEST="$RECEIPT_ONLY"
  PYTEST_EXIT=""  # archived receipt supplies its own exit status, never assume green
else
  REV="$(git rev-parse --short HEAD)"
  BRANCH="$(git rev-parse --abbrev-ref HEAD)"
  DIRTY_COUNT="$(git status --porcelain | wc -l | tr -d ' ')"
  if [ "$DIRTY_COUNT" != "0" ] && [ "$ALLOW_DIRTY" != "1" ]; then
    echo "树不干净（$DIRTY_COUNT 条 porcelain）。整仓收据只对干净树成立；本地迭代请加 --allow-dirty。" >&2
    git status --porcelain | head -10 >&2
    exit 2
  fi
  echo "== gate @ $BRANCH $REV  tree=$REPO  dirty=$DIRTY_COUNT  py=$PY"

  echo "== ruff check ."
  if ! "$PY" -m ruff check . ; then
    echo "ruff 红，停。" >&2
    exit 1
  fi

  echo "== pytest $PYTEST_ARGS"
  PYTEST_LOG="$(mktemp)" || exit 4
  trap 'rm -f -- "$PYTEST_LOG"' EXIT
  # shellcheck disable=SC2086
  "$PY" -m pytest $PYTEST_ARGS 2>&1 | tee "$PYTEST_LOG" | tail -15
  PIPE_EXITS=("${PIPESTATUS[@]}")
  PYTEST_EXIT="${PIPE_EXITS[0]}"
  if [ "${PIPE_EXITS[1]}" != 0 ] || [ "${PIPE_EXITS[2]}" != 0 ]; then
    echo "pytest 输出留证失败；不能确认本次收据。" >&2
    exit 4
  fi
  # conftest owns the receipt directory. Read its actual pointer, not an
  # unsupported directory override or a concurrently replaceable latest.json.
  LATEST="$("$PY" - "$PYTEST_LOG" <<'PYRECEIPT'
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
paths = [line.split("读数收据: ", 1)[1].strip() for line in text.splitlines() if "读数收据: " in line]
print(paths[-1] if paths else "")
PYRECEIPT
)" || exit 4
fi
if [ ! -f "$LATEST" ]; then
  echo "没找到本次收据 ${LATEST}（conftest 的收据插件没跑？）" >&2
  exit 4
fi

"$PY" - "$LATEST" "$BASELINE" "$PYTEST_EXIT" "$REPO" "$(git rev-parse HEAD)" "$ALLOW_DIRTY" <<'PYEOF'
import json, sys
from pathlib import Path

latest_path, baseline_path, measured_exit, repo, revision, allow_dirty = sys.argv[1:]

def invalid(reason):
    print(f"收据不可用于门禁：{reason}", file=sys.stderr)
    sys.exit(4)

try:
    latest = json.loads(Path(latest_path).read_text())
except (OSError, ValueError) as exc:
    invalid(str(exc))
if not isinstance(latest, dict):
    invalid("对象格式无效")
counts = latest.get("counts")
keys = ("passed", "failed", "error", "skipped")
if not isinstance(counts, dict) or any(type(counts.get(k)) is not int or counts[k] < 0 for k in keys):
    invalid("缺少有效的执行计数")
if sum(counts[k] for k in keys) == 0:
    invalid("没有执行读数")
pytest_exit = latest.get("exit_status")
if type(pytest_exit) is not int or not 0 <= pytest_exit <= 5:
    invalid("缺少有效的 pytest 退出码")
if measured_exit:
    if latest.get("revision") != revision or latest.get("tree") != repo:
        invalid("本次运行的 revision/tree 不匹配")
    if pytest_exit != int(measured_exit):
        invalid("收据与 pytest 实测退出码不一致")
if latest.get("dirty") is not False and allow_dirty != "1":
    invalid("脏树或缺少身份状态；本地迭代请显式 --allow-dirty")
failed_ids = latest.get("failed_ids")
if not isinstance(failed_ids, list) or any(not isinstance(fid, str) for fid in failed_ids):
    invalid("缺少有效失败集合")
failed = sorted(failed_ids)
if pytest_exit == 0 and (failed or counts["failed"] or counts["error"]):
    invalid("成功退出码与失败记录冲突")
print(f"== receipt {latest_path}")
print(f"   revision={latest.get('revision','')[:12]} dirty={latest.get('dirty')} target={latest.get('target')}")
print(f"   passed={counts.get('passed')} failed={counts.get('failed')} error={counts.get('error')} skipped={counts.get('skipped')}")
for fid in failed:
    print(f"   RED {fid}")
if not baseline_path:
    # 没有基线就只能照实回 pytest 的退出码：已知的环境红也算红，要「同一组红」的判断请给 --baseline。
    sys.exit(pytest_exit)
# A baseline may acknowledge test failures, not interrupted/empty/internal-error runs.
if pytest_exit not in (0, 1):
    sys.exit(pytest_exit)
if pytest_exit == 1 and not failed:
    invalid("失败退出却无失败测试身份")
try:
    base = json.loads(Path(baseline_path).read_text())
except (OSError, ValueError) as exc:
    invalid(f"基线读取失败：{exc}")
if not isinstance(base, dict) or not isinstance(base.get("failed_ids"), list):
    invalid("基线缺少失败集合")
base_counts = base.get("counts")
if not isinstance(base_counts, dict) or any(type(base_counts.get(k)) is not int or base_counts[k] < 0 for k in keys):
    invalid("基线缺少有效计数")
if any(not isinstance(fid, str) for fid in base["failed_ids"]):
    invalid("基线失败身份无效")
base_failed = sorted(base["failed_ids"])
new_red = sorted(set(failed) - set(base_failed))
gone_red = sorted(set(base_failed) - set(failed))
print(f"== vs baseline {baseline_path} (revision={base.get('revision','')[:12]}, passed={base_counts.get('passed')}, failed={base_counts.get('failed')})")
for fid in new_red:
    print(f"   NEW RED  {fid}")
for fid in gone_red:
    print(f"   FIXED    {fid}")
passed_ok = (counts.get("passed") or 0) >= (base_counts.get("passed") or 0)
print(f"   same_red_set={not new_red and not gone_red} passed_non_decreasing={passed_ok}")
sys.exit(0 if not new_red and passed_ok else 3)
PYEOF
