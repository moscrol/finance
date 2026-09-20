#!/usr/bin/env bash
# 干净树门禁：ruff -> pytest -> 本轮唯一收据 -> 提交/退出码身份校验。
# 用法：
#   bash scripts/run_main_gate.sh
#   bash scripts/run_main_gate.sh --pytest-args "-q tests/test_example.py"
#   bash scripts/run_main_gate.sh --allow-dirty   # 仅本地迭代，不可作为合入依据
#   bash scripts/run_main_gate.sh --receipt <收据.json>
#   bash scripts/run_main_gate.sh --baseline <基线.json>  # 红集比较，不是合入门禁
#   bash scripts/run_main_gate.sh --receipt <收据.json> --baseline <基线.json>
# FWP_TEST_RECEIPT_DIR 指定收据根；每轮新建 gate-*/pytest.json，不读共享 latest.json。
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
  RECEIPT_DIR="$(cd "$RECEIPT_DIR" && pwd)" || exit 4
  RUN_DIR="$(mktemp -d "$RECEIPT_DIR/gate-XXXXXXXX")" || exit 4
  LATEST="$RUN_DIR/pytest.json"
  echo "== gate @ ${REV:0:12} tree=${REPO} py=${PY} receipt=${LATEST}"
  echo "== ruff check ."
  if ! "$PY" -m ruff check . ; then
    echo "ruff 红，停。" >&2
    exit 1
  fi
  echo "== pytest ${PYTEST_ARGS}"
  # Preserve the existing whitespace-separated --pytest-args contract; never eval it.
  # shellcheck disable=SC2086
  FWP_TEST_RECEIPT_DIR="$RECEIPT_DIR" FWP_TEST_RECEIPT_PATH="$LATEST" \
    "$PY" -m pytest $PYTEST_ARGS 2>&1 | tail -15
  PYTEST_EXIT="${PIPESTATUS[0]}"
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
