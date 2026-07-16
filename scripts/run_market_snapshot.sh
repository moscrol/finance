#!/bin/zsh
set -euo pipefail

repo_root="${FINANCE_WORKSPACE_CODE_ROOT:-/Users/a77/finance-workspace-runtime}"
finance_root="${FINANCE_WS:-/Users/a77/finance-workspace-private}"
workbench_python="${WORKBENCH_PYTHON:-${finance_root}/.venv-workbench/bin/python}"
akshare_venv="${AKSHARE_VENV:-/Users/a77/.local/share/finance-workbench/akshare-venv}"
akshare_python="${AKSHARE_PYTHON:-${akshare_venv}/bin/python}"
market_db="${MARKET_DB_PATH:-${finance_root}/db/market_feature_store.duckdb}"
snapshot_dir="${MARKET_SNAPSHOT_DIR:-${finance_root}/market_snapshot}"

cd "${repo_root}"
export FINANCE_WS="${finance_root}"
export MARKET_SNAPSHOT_DIR="${snapshot_dir}"
export PYTHONPATH="${repo_root}"

# 只有 AkShare 子进程访问公开端点；清理代理后由 Python 编排器把同一环境传给它。
if [[ "${AKSHARE_PROXY_MODE:-direct}" != "inherit" ]]; then
  unset HTTP_PROXY HTTPS_PROXY ALL_PROXY
  unset http_proxy https_proxy all_proxy
  export NO_PROXY="*"
  export no_proxy="*"
fi

exec "${workbench_python}" -m scripts.sync_market_snapshot \
  --output-dir "${snapshot_dir}" \
  --db-path "${market_db}" \
  --akshare-python "${akshare_python}" \
  --code-root "${repo_root}" \
  "$@"
