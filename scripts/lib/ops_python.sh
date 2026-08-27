# 评估/运维 launchd 共用：解析 workbench venv，拒绝 CLT/系统 python。
# 用法：source 本文件后使用 "$OPS_PYTHON"。不要直接执行。
#
# 解析序：FINANCE_PYTHON → $FINANCE_WS/.venv-workbench/bin/python
# → $FINANCE_CODE_ROOT/.venv-workbench/bin/python
# → $HOME/finance-workspace-private/.venv-workbench/bin/python
# FINANCE_PYTHON 若指向 CLT/系统解释器，直接失败（不许静默降级）。

_ops_python_is_forbidden() {
  case "$1" in
    /usr/bin/python|/usr/bin/python3|/Library/Developer/CommandLineTools/*)
      return 0
      ;;
  esac
  return 1
}

_ops_python_resolve() {
  unset OPS_PYTHON
  if [[ -n "${FINANCE_PYTHON:-}" ]]; then
    if _ops_python_is_forbidden "$FINANCE_PYTHON"; then
      print -u2 -- "ops_python: refusing CLT/system interpreter: $FINANCE_PYTHON"
      return 1
    fi
    if [[ ! -x "$FINANCE_PYTHON" ]]; then
      print -u2 -- "ops_python: FINANCE_PYTHON is not executable: $FINANCE_PYTHON"
      return 1
    fi
    OPS_PYTHON="$FINANCE_PYTHON"
    return 0
  fi
  local cand
  for cand in \
    "${FINANCE_WS:-}/.venv-workbench/bin/python" \
    "${FINANCE_CODE_ROOT:-}/.venv-workbench/bin/python" \
    "${HOME}/finance-workspace-private/.venv-workbench/bin/python"
  do
    [[ -n "$cand" && -x "$cand" ]] || continue
    if _ops_python_is_forbidden "$cand"; then
      continue
    fi
    OPS_PYTHON="$cand"
    return 0
  done
  print -u2 -- "ops_python: no workbench venv python (set FINANCE_PYTHON or FINANCE_WS)"
  return 1
}

ops_health_log() {
  local job="$1"
  local rc="$2"
  local log="${FINANCE_OPS_HEALTH_LOG:-${HOME}/.finance-runtime/ops-health.log}"
  mkdir -p "$(dirname "$log")"
  print -- "$(date -u +%Y-%m-%dT%H:%M:%SZ) job=${job} rc=${rc} python=${OPS_PYTHON:-unset} code_root=${FINANCE_CODE_ROOT:-} data_root=${FINANCE_WS:-}" >> "$log"
}

ops_wait_duckdb_unlocked() {
  local db="${MARKET_FEATURE_STORE_DB:-}"
  local attempts="${REVIEW_GATE_LOCK_ATTEMPTS:-36}"
  local delay="${REVIEW_GATE_LOCK_DELAY_SECONDS:-10}"
  local i=1
  if [[ -z "$db" || ! -x "${OPS_PYTHON:-}" ]]; then
    return 0
  fi
  while (( i <= attempts )); do
    if "$OPS_PYTHON" -c "import duckdb,sys; duckdb.connect(sys.argv[1], read_only=True).close()" "$db" >/dev/null 2>&1; then
      return 0
    fi
    print -- "[$(date '+%F %T')] duckdb locked, wait ${delay}s ($i/$attempts) db=$db"
    sleep "$delay"
    i=$((i + 1))
  done
  print -u2 -- "ops_python: duckdb still locked after ${attempts} attempts: $db"
  return 1
}

_ops_python_resolve
