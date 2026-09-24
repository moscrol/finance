#!/usr/bin/env bash
# 干净树门禁：ruff -> pytest -> 本轮唯一收据 -> 提交/退出码身份校验。
# 用法：
#   bash scripts/run_main_gate.sh
#   bash scripts/run_main_gate.sh --pytest-args "-q tests/test_example.py"
#   bash scripts/run_main_gate.sh --allow-dirty   # 仅本地迭代，不可作为合入依据
#   bash scripts/run_main_gate.sh --receipt <收据.json>
#   bash scripts/run_main_gate.sh --baseline <基线.json>  # 红集比较，不是合入门禁
#   bash scripts/run_main_gate.sh --receipt <收据.json> --baseline <基线.json>
# FWP_TEST_RECEIPT_DIR 指定收据根；每轮新建 gate-*/pytest.json 和完整 pytest.log.txt，不读共享 latest.json。
# --pytest-args 里显式给了 --basetemp=<dir> 时：门禁全绿即删该目录（红保留作证据）；GATE_KEEP_BASETEMP=1 强制保留。
#   为什么：2026-09-23 盘上 pytest 临时区累计 30 GB，全是绿了也没人删的 basetemp；pytest 只保 3 个的自清理
#   在并发跑 + 只读文件下失效。只认显式路径——默认编号目录（pytest-of-<user>/pytest-N）分不清是谁的。
# 退出码：0 全过/显式基线比较无新增红；1 ruff/测试红；2 脏树；3 新增红；4 设施/身份失败。
set -uo pipefail

GATE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 4
BASELINE=""
RECEIPT_ONLY=""
ALLOW_DIRTY=0
PYTEST_ARGS="-q -p no:cacheprovider"
while [ $# -gt 0 ]; do
  case "$1" in
    --baseline|--receipt|--pytest-args)
      [ $# -ge 2 ] || { echo "missing value: $1" >&2; exit 4; }
      case "$1" in
        --baseline) BASELINE="$2" ;;
        --receipt) RECEIPT_ONLY="$2" ;;
        --pytest-args) PYTEST_ARGS="$2" ;;
      esac
      shift 2 ;;
    --allow-dirty) ALLOW_DIRTY=1; shift ;;
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 4 ;;
  esac
done

# 仅用宿主标准库解析 JSON，测试本身仍用契约指定的解释器。
PY="$(python3 -c 'import json,sys; from pathlib import Path; p=Path(sys.argv[1]); print(json.loads(p.read_text()).get("interpreter", "") if p.is_file() else "")' "$REPO/test-environment.json")" || exit 4
[ -z "$PY" ] && PY="$REPO/.venv-workbench/bin/python"
if [ ! -x "$PY" ]; then
  echo "解释器不可执行: ${PY}" >&2
  exit 4
fi
cd "$REPO" || exit 4
canonical_path() {
  python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$1"
}
path_is_same_or_child() {
  case "$1" in
    "$2"|"$2"/*) return 0 ;;
    *) return 1 ;;
  esac
}
# 显式 --basetemp（"--basetemp=DIR" 或 "--basetemp DIR"）；没给就不管。
BASETEMP="$(printf '%s\n' "$PYTEST_ARGS" | sed -nE 's/.*--basetemp[= ]+([^[:space:]]+).*/\1/p')"
BASETEMP_REAL=""
if [ -n "$BASETEMP" ]; then
  BASETEMP_REAL="$(canonical_path "$BASETEMP")" || { echo "无法解析 basetemp: $BASETEMP" >&2; exit 4; }
  case "$BASETEMP_REAL" in
    /|"$HOME") echo "basetemp 是根目录或家目录，拒绝启动 pytest: $BASETEMP_REAL" >&2; exit 4 ;;
  esac
  if path_is_same_or_child "$BASETEMP_REAL" "$REPO" || path_is_same_or_child "$REPO" "$BASETEMP_REAL"; then
    echo "basetemp 与仓库树有包含关系，拒绝启动 pytest: $BASETEMP_REAL" >&2
    exit 4
  fi
fi
PYTEST_EXIT=""
cleanup_basetemp() {
  local real
  [ -d "$1" ] || return 0
  real="$(canonical_path "$1")" || { echo "== 无法解析 basetemp，保留: $1" >&2; return 4; }
  if [ "$real" != "$BASETEMP_REAL" ]; then
    echo "== basetemp 路径在测试期间改变，保留: $real" >&2
    return 4
  fi
  chmod -R u+w "$real" 2>/dev/null   # pytest 夹具常留只读文件，不加这步 rm 会失败一半
  # 注意 ${real} 要带花括号：bash 3.2 在 UTF-8 下会把紧跟的全角括号当成变量名的一部分，set -u 直接报 unbound。
  if rm -rf -- "${real}"; then
    echo "== 门禁绿，basetemp 已清: ${real}（要保留请设 GATE_KEEP_BASETEMP=1）"
    return 0
  fi
  echo "== basetemp 清理失败，保留: ${real}" >&2
  return 4
}
REV="$(git rev-parse HEAD)" || exit 4
STATUS="$(git status --porcelain)" || exit 4
if [ -n "$STATUS" ] && [ "$ALLOW_DIRTY" != "1" ]; then
  echo "树不干净，整仓收据只对干净树成立；本地迭代请加 --allow-dirty。" >&2
  exit 2
fi
CHECK_ARGS=(--revision "$REV" --tree "$REPO")
[ "$ALLOW_DIRTY" = "1" ] && CHECK_ARGS+=(--allow-dirty)
[ -n "$BASELINE" ] && CHECK_ARGS+=(--baseline "$BASELINE")
if [ -n "$RECEIPT_ONLY" ]; then
  LATEST="$RECEIPT_ONLY"
else
  RECEIPT_DIR="${FWP_TEST_RECEIPT_DIR:-$HOME/.finance-runtime/test-receipts}"
  mkdir -p "$RECEIPT_DIR" || exit 4
  RECEIPT_DIR="$(cd "$RECEIPT_DIR" && pwd -P)" || exit 4
  if [ -n "$BASETEMP_REAL" ] && path_is_same_or_child "$RECEIPT_DIR" "$BASETEMP_REAL"; then
    echo "receipt directory overlaps disposable basetemp; refusing pytest" >&2
    exit 4
  fi
  RUN_DIR="$(mktemp -d "$RECEIPT_DIR/gate-XXXXXXXX")" || exit 4
  LATEST="$RUN_DIR/pytest.json"
  PYTEST_LOG="$RUN_DIR/pytest.log.txt"
  echo "== gate @ ${REV:0:12} tree=${REPO} py=${PY} receipt=${LATEST}"
  echo "== ruff check ."
  if ! "$PY" -m ruff check . ; then
    echo "ruff 红，停。" >&2
    exit 1
  fi
  echo "== pytest ${PYTEST_ARGS}"
  echo "== pytest raw log: ${PYTEST_LOG}"
  # Retain live output even when interrupted, without treating it as a final receipt.
  # Preserve the existing whitespace-separated --pytest-args contract; never eval it.
  # shellcheck disable=SC2086
  FWP_TEST_RECEIPT_DIR="$RECEIPT_DIR" FWP_TEST_RECEIPT_PATH="$LATEST" \
    FWP_TEST_RECEIPT_OWNER_PID="" "$PY" -u -m pytest $PYTEST_ARGS 2>&1 | tee "$PYTEST_LOG" | tail -15
  PIPE_EXITS=("${PIPESTATUS[@]}")
  PYTEST_EXIT="${PIPE_EXITS[0]}"
  if [ "${PIPE_EXITS[1]}" != 0 ] || [ "${PIPE_EXITS[2]}" != 0 ] || [ ! -f "$PYTEST_LOG" ]; then
    echo "pytest output pipeline failed (output capture failed); receipt not accepted, full evidence is unavailable and basetemp retained." >&2
    exit 4
  fi
  CHECK_ARGS+=(--pytest-exit "$PYTEST_EXIT")
fi
AFTER_REV="$(git rev-parse HEAD)" || exit 4
AFTER_STATUS="$(git status --porcelain)" || exit 4
if [ "$REV" != "$AFTER_REV" ] || { [ "$ALLOW_DIRTY" != "1" ] && [ -n "$AFTER_STATUS" ]; }; then
  echo "测试期间提交或干净状态改变，收据不可采信。" >&2
  exit 4
fi
if [ ! -f "$LATEST" ]; then
  echo "没找到本轮收据 ${LATEST}（pytest 收据未写出；不会回退 latest.json）" >&2
  exit 4
fi
"$PY" "$GATE_DIR/main_gate_receipt.py" "$LATEST" "${CHECK_ARGS[@]}"
GATE_EXIT=$?
# 只有「本轮真跑了 pytest 且退出 0 且收据校验通过」才清；--receipt 只读回放、任何红、显式保留都不动。
if [ "$GATE_EXIT" = 0 ] && [ -z "$RECEIPT_ONLY" ] && [ "$PYTEST_EXIT" = 0 ] \
   && [ -n "$BASETEMP" ] && [ "${GATE_KEEP_BASETEMP:-0}" != "1" ]; then
  if ! cleanup_basetemp "$BASETEMP"; then
    GATE_EXIT=4
  fi
fi
exit "$GATE_EXIT"
