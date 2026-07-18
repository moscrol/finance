#!/bin/zsh
set -euo pipefail

repo_root="${FINANCE_WORKSPACE_CODE_ROOT:-/Users/a77/finance-workspace-runtime}"
finance_root="${FINANCE_WS:-/Users/a77/finance-workspace-private}"
venv="${AKSHARE_VENV:-/Users/a77/.local/share/finance-workbench/akshare-venv}"
snapshot_dir="${MARKET_SNAPSHOT_DIR:-${finance_root}/market_snapshot}"

cd "${repo_root}"
export FINANCE_WS="${finance_root}"
export MARKET_SNAPSHOT_DIR="${snapshot_dir}"
export PYTHONPATH="${repo_root}"

# AkShare 的公开行情端点对透明代理较敏感。定时任务默认直连，只有显式设置
# AKSHARE_PROXY_MODE=inherit 时才继承调用方代理，保证 launchd 与手工运行一致。
if [[ "${AKSHARE_PROXY_MODE:-direct}" != "inherit" ]]; then
  unset HTTP_PROXY HTTPS_PROXY ALL_PROXY
  unset http_proxy https_proxy all_proxy
  # requests 在 macOS 上还会读取 scutil 系统代理；NO_PROXY=* 才能真正直连。
  export NO_PROXY="*"
  export no_proxy="*"
fi

exec "${venv}/bin/python" -m scripts.sync_akshare_market_snapshot "$@"
